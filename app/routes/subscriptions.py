import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Query, Request, status
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

def validate_and_normalize_contact(contact: str) -> Tuple[bool, str, str]:
    """
    Validates E.164 phone or email.
    If phone is 10 digits without country code, defaults to +91.
    Returns (is_valid, normalized_contact, masked_contact).
    """
    contact = contact.strip()

    # Check email
    if "@" in contact:
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

    # Check phone (E.164 or Indian 10 digits)
    clean_phone = re.sub(r"[\s\-\(\)]", "", contact)
    if re.match(r"^[6-9]\d{9}$", clean_phone):
        clean_phone = f"+91{clean_phone}"
    elif clean_phone.startswith("0") and len(clean_phone) == 11 and re.match(r"^0[6-9]\d{9}$", clean_phone):
        clean_phone = f"+91{clean_phone[1:]}"
    elif not clean_phone.startswith("+") and clean_phone.isdigit() and len(clean_phone) >= 10:
        clean_phone = f"+{clean_phone}"

    # E.164 pattern: + followed by 7 to 15 digits
    e164_pattern = r"^\+[1-9]\d{6,14}$"
    if re.match(e164_pattern, clean_phone):
        if len(clean_phone) >= 7:
            prefix = clean_phone[:3]
            suffix = clean_phone[-4:]
            masked = f"{prefix}******{suffix}"
        else:
            masked = clean_phone[:2] + "****" + clean_phone[-2:]
        return True, clean_phone, masked

    return False, contact, contact

def mask_contact(contact: str) -> str:
    """Convenience helper to return masked phone or email."""
    _, _, masked = validate_and_normalize_contact(contact)
    return masked

@router.post("/subscribe", response_model=SubscribeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_subscription(request: Request, req: SubscribeRequest):
    """
    Subscribes a traveler or resident to real-time alerts for an NH-7 segment.
    Validates E.164 phone or email, masks contact in logs, stores consent,
    and returns the newly created numeric subscription_id.
    """
    is_valid, normalized_contact, masked_contact = validate_and_normalize_contact(req.phone_or_email)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail="Invalid contact: must be a valid E.164 phone number (e.g. +919876543210) or a valid email address."
        )

    consent_bool = True if req.consent is not False else False

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
        cursor.execute("""
            INSERT INTO subscriptions (name, phone_or_email, segment_id, channel, consent, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            req.name.strip(),
            normalized_contact,
            req.segment_id,
            req.channel,
            1 if consent_bool else 0,
            now_str
        ))
        sub_id = cursor.lastrowid

    # Masked logging: NEVER log full phone or email
    logger.info(f"New subscription registered: ID {sub_id} for {req.name} ({req.channel}) - contact: {masked_contact} on {segment['name']}")

    return SubscribeResponse(
        subscription_id=sub_id,
        status="Active",
        message=f"Successfully subscribed to alerts for '{segment['name']}' via {req.channel}.",
        subscription=SubscriptionDetail(
            id=sub_id,
            name=req.name.strip(),
            phone_or_email=normalized_contact,
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
    user_id: int = Query(..., description="Numeric subscription_id returned by /subscribe"),
    simulate_rain_mm: Optional[float] = Query(None, description="Simulate rainfall in mm for demo testing")
):
    """
    Returns active alerts for a user's subscription.
    Looks up the user's subscribed segment and generates active warnings
    using the unified live ML + rainfall risk assessment service.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Fetch subscription joined with segment
        cursor.execute("""
            SELECT s.id, s.name, s.phone_or_email, s.channel, s.segment_id,
                   seg.name as segment_name, seg.risk_level, seg.risk_score
            FROM subscriptions s
            JOIN segments seg ON s.segment_id = seg.id
            WHERE s.id = ?
        """, (user_id,))
        sub = cursor.fetchone()

        if not sub:
            raise HTTPException(
                status_code=404,
                detail=f"Subscription ID '{user_id}' not found. Please register via POST /subscribe first."
            )

    # Use unified risk service with fallback
    risk_level = sub["risk_level"]
    risk_score = sub["risk_score"]
    rain_mm_3d = None
    rain_status = "unavailable"
    main_driver = None

    try:
        from app.risk_service import get_live_risk_map
        live_segments = get_live_risk_map(simulate_rain_mm=simulate_rain_mm)
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

    # Generate realistic active alerts based on the segment's live hazard profile
    if risk_level in ["Very High", "High"]:
        alerts.append(AlertItem(
            alert_id=f"ALT-NH7-{sub['segment_id'].upper()}-01",
            segment_id=sub["segment_id"],
            segment_name=sub["segment_name"],
            severity=risk_level,
            risk_score=risk_score,
            message=(
                f"HIGH ALERT on {sub['segment_name']}: Geological instability & active rockfall hazard{rain_text}.{driver_text} "
                "Road clearance teams deployed. Travel with extreme caution or consider alternate routes."
            ),
            channel=sub["channel"],
            issued_at=now_str,
            rain_mm_3d=rain_mm_3d,
            rain_status=rain_status,
            main_driver=main_driver,
        ))
    elif risk_level == "Moderate":
        alerts.append(AlertItem(
            alert_id=f"ALT-NH7-{sub['segment_id'].upper()}-02",
            segment_id=sub["segment_id"],
            segment_name=sub["segment_name"],
            severity="Moderate",
            risk_score=risk_score,
            message=(
                f"ADVISORY on {sub['segment_name']}: Moderate slope wetness and slippery road conditions{rain_text}.{driver_text} "
                "Speed limits enforced near drainage outlets."
            ),
            channel=sub["channel"],
            issued_at=now_str,
            rain_mm_3d=rain_mm_3d,
            rain_status=rain_status,
            main_driver=main_driver,
        ))
    # If Low, no critical alerts are active (empty list)

    return AlertsResponse(
        user_id=sub["id"],
        subscriber_name=sub["name"],
        subscribed_segment=f"{sub['segment_id']} ({sub['segment_name']})",
        active_alerts_count=len(alerts),
        alerts=alerts
    )
