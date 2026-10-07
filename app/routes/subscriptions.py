import re
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from app.database import get_db
from app.models import (
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionDetail,
    AlertsResponse,
    AlertItem,
)
from app.logger import logger
from app.limiter import limiter

router = APIRouter(tags=["Subscriptions & Alerts"])

def validate_and_normalize_contact(contact: str, channel: str = "SMS") -> Tuple[bool, str, str]:
    """
    Validates E.164 phone, email, or telegram chat identifier.
    Strips spaces and hyphens. If phone is 10 digits without country code, defaults to +91.
    Normalizes phone numbers to standard E.164 (e.g. +919876543210).
    Returns (is_valid, normalized_contact, masked_contact).
    """
    contact = contact.strip()
    ch = channel.lower().strip() if channel else "sms"

    # Check email
    if "@" in contact and ch not in ("telegram",):
        email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if re.match(email_pattern, contact):
            parts = contact.split("@")
            user, domain = parts[0], parts[1]
            if len(user) <= 2:
                masked_user = user[0] + "*"
            else:
                masked_user = user[0] + "*" * min(6, len(user) - 2) + user[-1]
            return True, contact, f"{masked_user}@{domain}"
        return False, contact, contact

    # If Telegram channel, support numeric chat_id or telegram @username
    if ch == "telegram":
        if re.match(r"^-?\d{5,16}$", contact):
            masked = contact[:2] + "*****" + contact[-2:] if len(contact) >= 6 else "*****"
            return True, contact, masked
        if re.match(r"^@[a-zA-Z0-9_]{3,32}$", contact):
            masked = contact[:2] + "***" + contact[-1:] if len(contact) >= 4 else "@***"
            return True, contact, masked

    # Check phone (E.164 or Indian 10 digits): strip spaces, hyphens, parentheses, dots
    clean_phone = re.sub(r"[\s\-\(\)\.]", "", contact)

    # 1. 10 digits (e.g. 9876543210 or 9811223344) -> default to +91
    if len(clean_phone) == 10 and clean_phone.isdigit():
        clean_phone = f"+91{clean_phone}"
    # 2. 11 digits starting with 0 (e.g. 09876543210) -> replace 0 with +91
    elif len(clean_phone) == 11 and clean_phone.startswith("0") and clean_phone[1:].isdigit():
        clean_phone = f"+91{clean_phone[1:]}"
    # 3. 12 digits starting with 91 without plus (e.g. 919876543210) -> prepend +
    elif len(clean_phone) == 12 and clean_phone.startswith("91") and clean_phone.isdigit():
        clean_phone = f"+{clean_phone}"
    # 4. Digits without plus between 7 and 15 digits -> prepend +
    elif not clean_phone.startswith("+") and clean_phone.isdigit() and 7 <= len(clean_phone) <= 15:
        clean_phone = f"+{clean_phone}"

    # E.164 pattern: + followed by 7 to 15 digits
    e164_pattern = r"^\+[1-9]\d{6,14}$"
    if re.match(e164_pattern, clean_phone):
        if len(clean_phone) >= 7:
            prefix = clean_phone[:3]
            suffix = clean_phone[-4:]
            masked = f"{prefix}*****{suffix}"
        else:
            masked = clean_phone[:2] + "*****" + clean_phone[-2:]
        return True, clean_phone, masked

    return False, contact, contact

def mask_contact(contact: str) -> str:
    """Convenience helper to return masked phone or email."""
    _, _, masked = validate_and_normalize_contact(contact)
    return masked

def mask_subscriber_name(name: str) -> str:
    """
    Masks subscriber name for unauthenticated public alert queries
    to prevent subscriber enumeration and privacy leakage (e.g. 'R***h N***').
    """
    if not name or not name.strip():
        return "Subscriber"
    words = name.strip().split()
    masked_words = []
    for w in words:
        if len(w) <= 2:
            masked_words.append(w[0] + "*")
        else:
            masked_words.append(w[0] + "*" * (len(w) - 2) + w[-1])
    return " ".join(masked_words)


@router.post("/subscribe", response_model=SubscribeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_subscription(request: Request, req: SubscribeRequest):
    """
    Subscribes a traveler or resident to real-time alerts for an NH-7 segment.
    Validates E.164 phone or email, masks contact in logs, stores consent,
    and returns the newly created numeric subscription_id.
    """
    is_valid, normalized_contact, masked_contact = validate_and_normalize_contact(req.phone_or_email, req.channel)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail="Invalid contact: must be a valid E.164 phone number (e.g. +919876543210) or a valid email address."
        )

    consent_bool = bool(req.consent)

    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify segment exists
        cursor.execute("SELECT id, name FROM segments WHERE id = ?", (req.segment_id,))
        segment = cursor.fetchone()
        if not segment:
            raise HTTPException(
                status_code=404,
                detail=f"Segment '{req.segment_id}' does not exist on NH-7."
            )

        now_str = datetime.now(timezone.utc).isoformat()
        token = f"tok_{secrets.token_urlsafe(16)}"
        cursor.execute("""
            INSERT INTO subscriptions (name, phone_or_email, segment_id, channel, consent, token, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            req.name.strip(),
            normalized_contact,
            req.segment_id,
            req.channel,
            1 if consent_bool else 0,
            token,
            now_str
        ))
        sub_id = cursor.lastrowid

    # Masked logging: NEVER log full phone or email
    logger.info(f"New subscription registered: ID {sub_id} for {req.name} ({req.channel}) - contact: {masked_contact} on {segment['name']}")

    return SubscribeResponse(
        subscription_id=sub_id,
        token=token,
        status="Active",
        message=f"Successfully subscribed to alerts for '{segment['name']}' via {req.channel}.",
        subscription=SubscriptionDetail(
            id=sub_id,
            token=token,
            name=req.name.strip(),
            phone_or_email=masked_contact,
            segment_id=req.segment_id,
            segment_name=segment["name"],
            channel=req.channel,
            consent=consent_bool,
            created_at=now_str
        )
    )

@router.get("/alerts", response_model=AlertsResponse)
@limiter.limit("120/minute")
def get_alerts(
    request: Request,
    token: Optional[str] = Query(None, description="Random authorization token returned by /subscribe"),
    user_id: Optional[int] = Query(None, description="Numeric subscription_id returned by /subscribe"),
    simulate_rain_mm: Optional[float] = Query(None, description="Simulate rainfall in mm for demo testing"),
    lang: Optional[str] = Query("en", description="Language code: 'en' or 'hi' (default 'en')"),
    x_sub_token: Optional[str] = Header(None, alias="X-Subscription-Token")
):
    """
    Returns active alerts for a user's subscription.
    Requires the random authorization token generated during /subscribe
    (passed via query param 'token' or 'X-Subscription-Token' header)
    to prevent sequential user_id enumeration and unauthorized access.
    """
    if lang is not None and lang not in ("en", "hi"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{lang}'. Supported languages are 'en' and 'hi'."
        )
    if simulate_rain_mm is not None and (simulate_rain_mm < 0.0 or simulate_rain_mm > 1000.0):
        raise HTTPException(
            status_code=400,
            detail="simulate_rain_mm must be a positive number between 0.0 and 1000.0 mm."
        )

    auth_token = (token or x_sub_token or "").strip()
    if not auth_token:
        raise HTTPException(
            status_code=401,
            detail="Access denied: /alerts requires a valid subscription token returned by POST /subscribe. Pass via query param 'token' or 'X-Subscription-Token' header."
        )

    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify subscription using token (and optional user_id)
        if user_id is not None:
            cursor.execute("""
                SELECT s.id, s.name, s.phone_or_email, s.channel, s.segment_id, s.token,
                       seg.name as segment_name, seg.risk_level, seg.risk_score
                FROM subscriptions s
                JOIN segments seg ON s.segment_id = seg.id
                WHERE s.id = ?
            """, (user_id,))
            sub = cursor.fetchone()
            if not sub:
                raise HTTPException(
                    status_code=404,
                    detail=f"Subscription ID '{user_id}' not found."
                )
            if not sub["token"] or not secrets.compare_digest(sub["token"], auth_token):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid subscription token for this subscription ID."
                )
        else:
            cursor.execute("""
                SELECT s.id, s.name, s.phone_or_email, s.channel, s.segment_id, s.token,
                       seg.name as segment_name, seg.risk_level, seg.risk_score
                FROM subscriptions s
                JOIN segments seg ON s.segment_id = seg.id
                WHERE s.token = ?
            """, (auth_token,))
            sub = cursor.fetchone()
            if not sub:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid subscription token."
                )

    # Use unified risk service with fallback
    risk_level = sub["risk_level"]
    risk_score = sub["risk_score"]
    rain_mm_3d = None
    rain_status = "unavailable"
    main_driver = None

    meta = {}
    try:
        from app.risk_service import get_live_risk_map_with_metadata
        live_segments, meta = get_live_risk_map_with_metadata(simulate_rain_mm=simulate_rain_mm)
        live_map = {s["id"]: s for s in live_segments}
        seg_live = live_map.get(sub["segment_id"])
        if seg_live:
            risk_level = seg_live["risk_level"]
            risk_score = seg_live["risk_score"]
            rain_mm_3d = seg_live.get("rain_mm_3d")
            rain_status = seg_live.get("rain_status")
            main_driver = seg_live.get("main_driver")
    except Exception as e:
        logger.exception(f"get_live_risk_map in alerts failed ({e}); falling back to seeded database values")

    alerts: List[AlertItem] = []
    now_str = datetime.now(timezone.utc).isoformat()
    driver_text = f" Primary factor: {main_driver}." if main_driver else ""
    rain_text = f" (3-day rain: {rain_mm_3d} mm)" if rain_mm_3d is not None else ""

    from app import i18n
    is_hi = (lang == "hi")

    # Generate realistic active alerts based on the segment's live hazard profile
    if risk_level in ["Very High", "High"]:
        msg_en = (
            f"HIGH ALERT on {sub['segment_name']}: Geological instability & active rockfall hazard{rain_text}.{driver_text} "
            "Road clearance readiness advised. Travel with extreme caution or check official closure advisories."
        )
        msg = i18n.build_subscriber_alert_message(
            segment_name=sub["segment_name"],
            risk_level=risk_level,
            rain_mm=rain_mm_3d,
            main_driver=main_driver,
            lang=lang or "en"
        )
        alerts.append(AlertItem(
            alert_id=f"ALT-NH7-{sub['segment_id'].upper()}-01",
            segment_id=sub["segment_id"],
            segment_name=i18n.localize_segment_name(sub["segment_id"], sub["segment_name"], "hi") if is_hi else sub["segment_name"],
            segment_name_en=sub["segment_name"] if is_hi else None,
            severity=i18n.localize_risk_level(risk_level, "hi") if is_hi else risk_level,
            severity_en=risk_level if is_hi else None,
            risk_score=risk_score,
            risk_index=risk_score,
            message=msg,
            message_en=msg_en if is_hi else None,
            channel=sub["channel"],
            issued_at=now_str,
            rain_mm_3d=rain_mm_3d,
            rain_status=rain_status,
            main_driver=i18n.localize_main_driver(main_driver, "hi") if is_hi else main_driver,
            main_driver_en=main_driver if is_hi else None,
        ))
    elif risk_level == "Moderate":
        msg_en = (
            f"ADVISORY on {sub['segment_name']}: Moderate slope wetness and slippery road conditions{rain_text}.{driver_text} "
            "Speed limits enforced near drainage outlets."
        )
        msg = i18n.build_subscriber_alert_message(
            segment_name=sub["segment_name"],
            risk_level=risk_level,
            rain_mm=rain_mm_3d,
            main_driver=main_driver,
            lang=lang or "en"
        )
        alerts.append(AlertItem(
            alert_id=f"ALT-NH7-{sub['segment_id'].upper()}-02",
            segment_id=sub["segment_id"],
            segment_name=i18n.localize_segment_name(sub["segment_id"], sub["segment_name"], "hi") if is_hi else sub["segment_name"],
            segment_name_en=sub["segment_name"] if is_hi else None,
            severity=i18n.localize_risk_level("Moderate", "hi") if is_hi else "Moderate",
            severity_en="Moderate" if is_hi else None,
            risk_score=risk_score,
            risk_index=risk_score,
            message=msg,
            message_en=msg_en if is_hi else None,
            channel=sub["channel"],
            issued_at=now_str,
            rain_mm_3d=rain_mm_3d,
            rain_status=rain_status,
            main_driver=i18n.localize_main_driver(main_driver, "hi") if is_hi else main_driver,
            main_driver_en=main_driver if is_hi else None,
        ))
    # If Low, no critical alerts are active (empty list)

    sub_seg_en = f"{sub['segment_id']} ({sub['segment_name']})"
    if is_hi:
        sub_seg_name_hi = i18n.localize_segment_name(sub["segment_id"], sub["segment_name"], "hi")
        sub_seg_display = f"{sub['segment_id']} ({sub_seg_name_hi})"
    else:
        sub_seg_display = sub_seg_en

    return AlertsResponse(
        user_id=sub["id"],
        subscriber_name=mask_subscriber_name(sub["name"]),
        subscribed_segment=sub_seg_display,
        subscribed_segment_en=sub_seg_en if is_hi else None,
        active_alerts_count=len(alerts),
        alerts=alerts,
        weather_source=meta.get("weather_source"),
        weather_fetched_at=meta.get("weather_fetched_at"),
        weather_age_minutes=meta.get("weather_age_minutes"),
        is_simulated=meta.get("is_simulated", False),
        stale_warning=meta.get("stale_warning"),
        lang=lang or "en",
    )
