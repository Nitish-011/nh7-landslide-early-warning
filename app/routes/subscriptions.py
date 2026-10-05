from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from app.database import get_db
from app.models import (
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionDetail,
    AlertsResponse,
    AlertItem,
)
from app.logger import logger

router = APIRouter(tags=["Subscriptions & Alerts"])

@router.post("/subscribe", response_model=SubscribeResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(req: SubscribeRequest):
    """
    Subscribes a traveler or resident to real-time alerts for an NH-7 segment.
    Returns the newly created numeric subscription_id.
    """
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
            INSERT INTO subscriptions (name, phone_or_email, segment_id, channel, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            req.name.strip(),
            req.phone_or_email.strip(),
            req.segment_id,
            req.channel,
            now_str
        ))
        sub_id = cursor.lastrowid

    logger.info(f"New subscription registered: ID {sub_id} for {req.name} ({req.channel}) on {segment['name']}")

    return SubscribeResponse(
        subscription_id=sub_id,
        status="Active",
        message=f"Successfully subscribed to alerts for '{segment['name']}' via {req.channel}.",
        subscription=SubscriptionDetail(
            id=sub_id,
            name=req.name.strip(),
            phone_or_email=req.phone_or_email.strip(),
            segment_id=req.segment_id,
            segment_name=segment["name"],
            channel=req.channel,
            created_at=now_str
        )
    )

@router.get("/alerts", response_model=AlertsResponse)
def get_alerts(
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
