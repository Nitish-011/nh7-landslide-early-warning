from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from app.database import get_db
from app.models import (
    FieldReportCreate,
    FieldReportResponse,
    AdminValidateRequest,
    AdminValidateResponse,
)
from app.logger import logger

router = APIRouter(tags=["Field Reports & Validation"])

@router.post("/field-report", response_model=FieldReportResponse, status_code=status.HTTP_201_CREATED)
def submit_field_report(report: FieldReportCreate):
    """
    Submits a crowd-sourced or patrol field report for a landslide or road hazard.
    Stores record with status='Pending' and returns report_id.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO field_reports (
                lat, lng, description, photo_url, reporter_name, status, decision_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'Pending', '', ?, ?)
        """, (
            report.lat,
            report.lng,
            report.description.strip(),
            report.photo_url.strip() if report.photo_url else None,
            report.reporter_name.strip(),
            now_str,
            now_str
        ))
        report_id = cursor.lastrowid

    logger.info(
        f"Field report #{report_id} submitted by '{report.reporter_name}' at ({report.lat}, {report.lng}): "
        f"{report.description[:50]}..."
    )

    return FieldReportResponse(
        report_id=report_id,
        status="Pending",
        message="Field report submitted successfully and queued for admin validation.",
        submitted_at=now_str
    )

@router.post("/admin/validate-report", response_model=AdminValidateResponse)
def validate_field_report(req: AdminValidateRequest):
    """
    Admin endpoint to validate or reject a crowd-sourced field report.
    Updates the report status to 'Validated' or 'Rejected'.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, status, reporter_name FROM field_reports WHERE id = ?", (req.report_id,))
        existing = cursor.fetchone()
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Field report #{req.report_id} not found."
            )

        cursor.execute("""
            UPDATE field_reports
            SET status = ?, decision_notes = ?, updated_at = ?
            WHERE id = ?
        """, (
            req.decision,
            req.notes.strip() if req.notes else f"Updated to {req.decision} by Admin",
            now_str,
            req.report_id
        ))

    logger.info(f"Field report #{req.report_id} status updated from '{existing['status']}' to '{req.decision}'")

    return AdminValidateResponse(
        report_id=req.report_id,
        status=req.decision,
        updated_at=now_str,
        message=f"Report #{req.report_id} has been successfully updated to '{req.decision}'."
    )

@router.get("/field-reports")
def list_field_reports():
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
