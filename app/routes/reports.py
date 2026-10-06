import json
import math
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from shapely.geometry import Point, LineString

from app import config
from app.config import BASE_DIR
from app.database import get_db
from app.logger import logger
from app.limiter import limiter
from app.models import (
    FieldReportCreate,
    FieldReportResponse,
    AdminValidateRequest,
    AdminValidateResponse,
)

router = APIRouter(tags=["Field Reports & Validation"])

# Preloaded NH-7 Polyline in local Cartesian coordinates (km)
_corridor_line = None

def get_corridor_line() -> Optional[LineString]:
    global _corridor_line
    if _corridor_line is None:
        geojson_path = BASE_DIR / "geojson" / "nh7_route.geojson"
        if geojson_path.exists():
            try:
                data = json.loads(geojson_path.read_text(encoding="utf-8"))
                coords = data["features"][0]["geometry"]["coordinates"]
                lat0, lon0 = 30.2, 78.5
                cos_lat = math.cos(math.radians(lat0))
                pts = [((lon - lon0) * 111.0 * cos_lat, (lat - lat0) * 111.0) for lon, lat, *rest in coords]
                _corridor_line = LineString(pts)
            except Exception as e:
                logger.error(f"Failed to load nh7_route.geojson for corridor boundary check: {e}")
    return _corridor_line

def check_within_corridor(lat: float, lng: float, max_dist_km: float = 3.0) -> bool:
    line = get_corridor_line()
    if line is None:
        # Fallback to NH-7 corridor bounding box if geometry uninitialized, preventing fail-open global acceptance
        return 29.9 <= lat <= 30.7 and 78.1 <= lng <= 79.7
    lat0, lon0 = 30.2, 78.5
    cos_lat = math.cos(math.radians(lat0))
    p = Point(((lng - lon0) * 111.0 * cos_lat, (lat - lat0) * 111.0))
    dist = line.distance(p)
    return dist <= max_dist_km

def verify_admin_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    """
    Validates X-Admin-Key or X-API-Key header against ADMIN_API_KEY using secrets.compare_digest.
    If ADMIN_API_KEY is unset in dev, logs a loud warning and allows only localhost.
    In production, returns 401 if missing or wrong.
    """
    key = x_admin_key or x_api_key
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    is_localhost = client_ip in ("127.0.0.1", "localhost", "::1", "testclient")

    if config.ADMIN_API_KEY:
        if not key or not secrets.compare_digest(key.strip(), config.ADMIN_API_KEY):
            logger.warning(f"Unauthorized admin access attempt from IP {client_ip} (missing or invalid admin key)")
            raise HTTPException(status_code=401, detail="Invalid or missing admin key header")
        return key

    # ADMIN_API_KEY is unset
    if config.ENV == "production":
        logger.error(f"ADMIN_API_KEY unset in production; rejected admin request from {client_ip}")
        raise HTTPException(status_code=401, detail="Admin API key not configured in production")

    # In development mode: allow only localhost with loud warning
    if is_localhost:
        logger.warning(f"SECURITY WARNING: ADMIN_API_KEY is unset in {config.ENV} mode! Allowing unauthenticated admin action from localhost ({client_ip}).")
        return "dev-localhost"

    logger.warning(f"ADMIN_API_KEY unset and non-localhost request from {client_ip}. Rejecting.")
    raise HTTPException(status_code=401, detail="Admin access requires X-API-Key header or localhost in development mode.")

@router.post("/field-report", response_model=FieldReportResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def submit_field_report(request: Request, report: FieldReportCreate):
    """
    Submits a crowd-sourced field report.
    Validates that:
    1. lat/lng is within 3 km of NH-7 corridor polyline (else 422).
    2. description has HTML stripped and length <= 500 chars (else 422).
    3. photo_url is http/https and <= 500 chars, never fetched server-side (else 422).
    4. duplicate reports from same IP at same coordinates within 10 minutes are rejected (409).
    """
    client_ip = request.client.host if request.client else "unknown"

    # 1. 3 km corridor distance check
    if not check_within_corridor(report.lat, report.lng, max_dist_km=3.0):
        raise HTTPException(
            status_code=422,
            detail="Report coordinates are beyond 3.0 km of the NH-7 highway corridor."
        )

    # 2. HTML stripping and length validation
    clean_desc = re.sub(r"<[^>]*?>", "", report.description).strip()
    if len(clean_desc) > 500:
        raise HTTPException(
            status_code=422,
            detail="Report description exceeds maximum length of 500 characters."
        )
    if len(clean_desc) < 5:
        raise HTTPException(
            status_code=422,
            detail="Report description must be at least 5 characters after HTML stripping."
        )

    # 3. photo_url validation
    clean_photo = None
    if report.photo_url:
        p_url = report.photo_url.strip()
        if len(p_url) > 500:
            raise HTTPException(status_code=422, detail="photo_url exceeds maximum length of 500 characters.")
        if not (p_url.startswith("http://") or p_url.startswith("https://")):
            raise HTTPException(status_code=422, detail="photo_url must be an http or https URL.")
        clean_photo = p_url

    # 4. Duplicate prevention within 10 minutes (409 Conflict)
    now_str = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, created_at FROM field_reports
            WHERE reporter_ip = ?
              AND ABS(lat - ?) < 0.0001
              AND ABS(lng - ?) < 0.0001
              AND datetime(created_at) > datetime('now', '-10 minutes')
        """, (client_ip, report.lat, report.lng))
        dup = cursor.fetchone()
        if dup:
            raise HTTPException(
                status_code=409,
                detail="Duplicate report from the same IP at these coordinates within 10 minutes."
            )

        from app.flywheel_service import find_nearest_segment
        assigned_seg = find_nearest_segment(report.lat, report.lng)

        cursor.execute("""
            INSERT INTO field_reports (
                lat, lng, description, photo_url, reporter_name, reporter_ip, status, decision_notes, created_at, updated_at, segment_id
            ) VALUES (?, ?, ?, ?, ?, ?, 'Pending', '', ?, ?, ?)
        """, (
            report.lat,
            report.lng,
            clean_desc,
            clean_photo,
            report.reporter_name.strip(),
            client_ip,
            now_str,
            now_str,
            assigned_seg
        ))
        report_id = cursor.lastrowid

    logger.info(
        f"Field report #{report_id} submitted by '{report.reporter_name}' (IP: {client_ip}) near {assigned_seg}: "
        f"{clean_desc[:50]}..."
    )

    return FieldReportResponse(
        report_id=report_id,
        status="Pending",
        message="Field report submitted successfully and queued for admin validation.",
        submitted_at=now_str
    )

@router.post("/admin/validate-report", response_model=AdminValidateResponse)
def validate_field_report(req: AdminValidateRequest, admin_key: str = Depends(verify_admin_key)):
    """
    Admin endpoint to validate or reject a crowd-sourced field report.
    Protected by X-Admin-Key / X-API-Key authentication.
    Assigns report to nearest highway segment on validation.
    """
    now_str = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, lat, lng, status, reporter_name, segment_id FROM field_reports WHERE id = ?", (req.report_id,))
        existing = cursor.fetchone()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Field report #{req.report_id} not found."
            )

        from app.flywheel_service import find_nearest_segment
        assigned_seg = existing["segment_id"] or find_nearest_segment(existing["lat"], existing["lng"])

        cursor.execute("""
            UPDATE field_reports
            SET status = ?, decision_notes = ?, updated_at = ?, segment_id = ?
            WHERE id = ?
        """, (
            req.decision,
            req.notes.strip() if req.notes else f"Updated to {req.decision} by Admin",
            now_str,
            assigned_seg,
            req.report_id
        ))

    logger.info(f"Field report #{req.report_id} status updated from '{existing['status']}' to '{req.decision}' (assigned segment: {assigned_seg}) by admin")

    return AdminValidateResponse(
        report_id=req.report_id,
        status=req.decision,
        updated_at=now_str,
        message=f"Report #{req.report_id} has been successfully updated to '{req.decision}'."
    )

@router.get("/field-reports")
@limiter.limit("120/minute")
def list_field_reports(request: Request):
    """
    Helper endpoint to list all field reports for the test map and admin panel.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM field_reports ORDER BY id DESC")
        rows = cursor.fetchall()

    return [
        {
            "id": r["id"],
            "lat": r["lat"],
            "lng": r["lng"],
            "description": r["description"],
            "photo_url": r["photo_url"],
            "reporter_name": r["reporter_name"],
            "status": r["status"],
            "decision_notes": r["decision_notes"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        }
        for r in rows
    ]
