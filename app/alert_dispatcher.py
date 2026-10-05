"""
app/alert_dispatcher.py - Periodic alert delivery job with cooldown and state tracking
========================================================================================
Runs every 10 minutes:
1. Computes live corridor risk for subscriber segments using REAL weather only (never simulated).
2. Sends alerts only when risk level rises to High/Very High or changes from last_sent_level.
3. Enforces strict 3-hour cooldown per user and segment.
4. Persists alert_state (for deduplication/cooldown) and alert_log (for operational audits).
5. Uses concise, non-alarmist notification templates.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app import config
from app.database import get_db
from app.notifiers import get_notifier
from app.risk_service import get_live_risk_map_with_metadata

log = logging.getLogger("alert_dispatcher")


def build_alert_message(segment_name: str, risk_level: str) -> str:
    """Builds concise, non-alarmist alert text."""
    return f"NH-7 {segment_name}: {risk_level.upper()} risk after heavy rain. Avoid travel until updated."


def dispatch_alerts() -> int:
    """
    Evaluates all active subscriptions and dispatches notifications when risk thresholds
    are met and cooldown constraints are satisfied.
    Uses real weather only. Returns the count of dispatched alerts.
    """
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    sent_count = 0

    try:
        # Reuses existing risk_service functions with REAL weather only (never simulated)
        live_segments, meta = get_live_risk_map_with_metadata(simulate_rain_mm=None)
        seg_map = {s["id"]: s for s in live_segments}
    except Exception as e:
        log.error("dispatch_alerts: failed to compute live corridor risk: %s", e)
        return 0

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, phone_or_email, segment_id, channel, consent
                FROM subscriptions
                WHERE consent = 1
            """)
            subscribers = cursor.fetchall()

            for sub in subscribers:
                sub_id = sub["id"]
                contact = sub["phone_or_email"].strip()
                seg_id = sub["segment_id"].strip()
                channel = sub["channel"].strip()

                seg_data = seg_map.get(seg_id)
                if not seg_data:
                    continue

                # Use adjusted risk level if present from ground truth flywheel, else base level
                current_level = seg_data.get("adjusted_risk_level") or seg_data.get("risk_level", "Low")
                seg_name = seg_data.get("name", seg_id)

                # Query alert_state for last sent state
                cursor.execute("""
                    SELECT last_sent_level, last_sent_at
                    FROM alert_state
                    WHERE subscription_id = ? AND segment_id = ?
                """, (sub_id, seg_id))
                state_row = cursor.fetchone()

                last_sent_level = state_row["last_sent_level"] if state_row else None
                last_sent_at = state_row["last_sent_at"] if state_row else None

                # 1. Cooldown Check: 3h cooldown per user and segment
                if last_sent_at:
                    try:
                        last_dt = datetime.fromisoformat(last_sent_at.replace("Z", "+00:00"))
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        elapsed_hours = (now - last_dt).total_seconds() / 3600.0
                        if elapsed_hours < config.ALERT_COOLDOWN_HOURS:
                            log.debug(
                                "dispatch_alerts: skipping sub #%d on %s (cooldown active: %.1fh / %.1fh)",
                                sub_id, seg_id, elapsed_hours, config.ALERT_COOLDOWN_HOURS
                            )
                            continue
                    except Exception as e:
                        log.warning("dispatch_alerts: error parsing timestamp %s: %s", last_sent_at, e)

                # 2. Trigger Condition: Send only when level rises to High/Very High OR changes since last_sent_level
                should_send = False
                if last_sent_level is None:
                    if current_level in ("High", "Very High"):
                        should_send = True
                else:
                    if current_level != last_sent_level:
                        should_send = True

                if not should_send:
                    continue

                # 3. Format and dispatch alert message
                message = build_alert_message(seg_name, current_level)
                notifier = get_notifier(channel)

                try:
                    success = notifier.send(recipient=contact, message=message, channel=channel)
                except Exception as e:
                    log.error("dispatch_alerts: notifier failure for %s via %s: %s", contact, channel, e)
                    success = False

                if success:
                    # 4. Persist alert_state
                    cursor.execute("""
                        INSERT INTO alert_state (subscription_id, segment_id, last_sent_level, last_sent_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(subscription_id, segment_id) DO UPDATE SET
                            last_sent_level = excluded.last_sent_level,
                            last_sent_at = excluded.last_sent_at
                    """, (sub_id, seg_id, current_level, now_iso))

                    # 5. Persist alert_log
                    cursor.execute("""
                        INSERT INTO alert_log (subscription_id, segment_id, channel, contact, risk_level, message, sent_at, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'sent')
                    """, (sub_id, seg_id, channel, contact, current_level, message, now_iso))

                    sent_count += 1
                    log.info(
                        "dispatch_alerts: alert sent to sub #%d (%s) on %s at level %s",
                        sub_id, contact, seg_id, current_level
                    )

    except Exception as e:
        log.error("dispatch_alerts: unhandled error in dispatcher job: %s", e, exc_info=True)

    return sent_count
