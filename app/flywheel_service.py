"""
flywheel_service.py - Ground truth report flywheel & road closures engine
=========================================================================
Implements:
1. Spatial mapping: assigns crowd-sourced reports to the nearest highway segment.
2. Verified reports flywheel: computes ground_report_count_24h and exponential
   decay weighting (half-life 48h) to escalate displayed risk by at most 1 step.
3. Road closure state management: retrieves active official road closures
   and evaluates their impact on route recommendations.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from app import config

log = logging.getLogger("backend")

_SEGMENTS_CACHE = None


def _load_segments_data() -> List[dict]:
    global _SEGMENTS_CACHE
    if _SEGMENTS_CACHE is not None:
        return _SEGMENTS_CACHE

    scores_file = Path(__file__).resolve().parent / "segment_static_scores.json"
    if scores_file.exists():
        try:
            _SEGMENTS_CACHE = json.loads(scores_file.read_text(encoding="utf-8"))
            return _SEGMENTS_CACHE
        except Exception as e:
            log.warning("flywheel_service: failed reading segment_static_scores.json: %s", e)

    return []


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points on Earth in kilometers."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def find_nearest_segment(lat: float, lon: float) -> str:
    """
    Finds the nearest NH-7 corridor segment ID for a given GPS coordinate
    by checking distance to segment vertices, midpoints, and subpoints.
    """
    segments = _load_segments_data()
    if not segments:
        return "seg_01"

    best_seg_id = segments[0]["id"]
    min_dist = float("inf")

    for s in segments:
        mid_lat = (s["start_lat"] + s["end_lat"]) / 2.0
        mid_lng = (s["start_lng"] + s["end_lng"]) / 2.0
        d_mid = haversine_km(lat, lon, mid_lat, mid_lng)
        d_start = haversine_km(lat, lon, s["start_lat"], s["start_lng"])
        d_end = haversine_km(lat, lon, s["end_lat"], s["end_lng"])
        d_best_local = min(d_mid, d_start, d_end)

        for pt in s.get("subpoints", []):
            if len(pt) >= 2:
                d_pt = haversine_km(lat, lon, pt[0], pt[1])
                if d_pt < d_best_local:
                    d_best_local = d_pt

        if d_best_local < min_dist:
            min_dist = d_best_local
            best_seg_id = s["id"]

    return best_seg_id


def assign_report_to_nearest_segment(report_id: int) -> Optional[str]:
    """
    Finds and records the nearest segment_id for a given field report.
    """
    try:
        from app.database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, lat, lng, segment_id FROM field_reports WHERE id = ?", (report_id,))
            row = cursor.fetchone()
            if not row:
                return None

            nearest_seg = find_nearest_segment(row["lat"], row["lng"])
            cursor.execute(
                "UPDATE field_reports SET segment_id = ? WHERE id = ?",
                (nearest_seg, report_id)
            )
            return nearest_seg
    except Exception as e:
        log.warning("flywheel_service: assign_report_to_nearest_segment failed for report #%s: %s", report_id, e)
        return None


def get_active_closures_map() -> Dict[str, dict]:
    """
    Returns a dictionary mapping segment_id -> active road closure dict.
    A closure is active if starts_at <= now AND (ends_at IS NULL OR ends_at >= now).
    Prioritizes 'closed' status if multiple active closures affect the same segment.
    """
    try:
        from app.database import get_db
        now_str = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM road_closures
                WHERE starts_at <= ? AND (ends_at IS NULL OR ends_at >= ?)
                ORDER BY id DESC
            """, (now_str, now_str))
            rows = cursor.fetchall()

        closures_by_seg: Dict[str, dict] = {}
        for r in rows:
            seg_id = r["segment_id"]
            d = dict(r)
            if seg_id not in closures_by_seg:
                closures_by_seg[seg_id] = d
            elif closures_by_seg[seg_id]["status"] != "closed" and d["status"] == "closed":
                closures_by_seg[seg_id] = d

        return closures_by_seg
    except Exception as e:
        log.warning("flywheel_service: get_active_closures_map failed: %s", e)
        return {}


def compute_segment_ground_truth(segment_id: str, base_risk_level: str) -> dict:
    """
    Computes ground_report_count_24h and exponential decay adjustment.
    Escalates displayed level by at most ONE step based on validated reports (half-life 48h).
    Gated behind GROUND_TRUTH_LAYER config.
    """
    if not getattr(config, "GROUND_TRUTH_LAYER", True):
        return {
            "adjusted_risk_level": None,
            "ground_report_count_24h": None,
            "adjustment_reason": None,
        }

    try:
        from app.database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, created_at, updated_at FROM field_reports WHERE segment_id = ? AND status = 'Validated'",
                (segment_id,)
            )
            rows = cursor.fetchall()
    except Exception as e:
        log.warning("flywheel_service: failed reading validated reports for %s: %s", segment_id, e)
        return {
            "adjusted_risk_level": base_risk_level,
            "ground_report_count_24h": 0,
            "adjustment_reason": None,
        }

    if not rows:
        return {
            "adjusted_risk_level": base_risk_level,
            "ground_report_count_24h": 0,
            "adjustment_reason": None,
        }

    now = datetime.now(timezone.utc)
    half_life_hours = getattr(config, "GROUND_REPORT_HALF_LIFE_HOURS", 48.0)
    escalate_threshold = getattr(config, "GROUND_REPORT_ESCALATE_THRESHOLD", 0.75)
    max_steps = getattr(config, "GROUND_REPORT_MAX_ESCALATION_STEPS", 1)

    count_24h = 0
    effective_weight = 0.0

    for r in rows:
        ts_str = r["created_at"] or r["updated_at"]
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
        except Exception:
            delta_hours = 0.0

        if delta_hours <= 24.0:
            count_24h += 1

        w = 0.5 ** (delta_hours / half_life_hours)
        effective_weight += w

    LEVELS = ["Low", "Moderate", "High", "Very High"]
    current_idx = LEVELS.index(base_risk_level) if base_risk_level in LEVELS else 0

    if effective_weight >= escalate_threshold and current_idx < len(LEVELS) - 1:
        new_idx = min(current_idx + max_steps, len(LEVELS) - 1)
        adjusted_level = LEVELS[new_idx]
        if count_24h > 0:
            reason = f"{count_24h} verified ground report(s) in last 24h"
        else:
            reason = f"Active verified ground reports (decayed weight: {effective_weight:.2f})"
    else:
        adjusted_level = base_risk_level
        reason = None

    return {
        "adjusted_risk_level": adjusted_level,
        "ground_report_count_24h": count_24h,
        "adjustment_reason": reason,
    }
