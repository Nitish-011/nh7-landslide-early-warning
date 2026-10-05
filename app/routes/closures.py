"""
app/routes/closures.py - Official road closures API endpoints
=============================================================
Endpoints:
- POST   /admin/closure      (admin key required): Create official road closure
- DELETE /admin/closure/{id} (admin key required): Delete/reopen official closure
- GET    /closures           (public): List active or all closures
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.database import get_db
from app.logger import logger
from app.limiter import limiter
from app.models import RoadClosureCreate, RoadClosureResponse
from app.routes.reports import verify_admin_key

router = APIRouter(tags=["Road Closures"])


@router.post(
    "/admin/closure",
    response_model=RoadClosureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create official road closure (Admin only)"
)
def create_road_closure(
    closure: RoadClosureCreate,
    admin_key: str = Depends(verify_admin_key)
):
    """
    Creates an official road closure or transit restriction (closed, one_way, restricted).
    Immediately updates route recommendations across /route-risk and /risk-map.
    Protected by admin key (X-Admin-Key or X-API-Key).
    """
    now_str = datetime.now(timezone.utc).isoformat()
    starts_at = closure.starts_at or now_str
    created_by = closure.created_by or "admin"

    with get_db() as conn:
        cursor = conn.cursor()
        # Verify segment exists
        cursor.execute("SELECT id FROM segments WHERE id = ?", (closure.segment_id,))
        seg_row = cursor.fetchone()
        if not seg_row:
            # Also allow seg_01..seg_18 even if DB has custom seed
            valid_segs = {f"seg_{i:02d}" for i in range(1, 19)}
            if closure.segment_id not in valid_segs:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid segment_id '{closure.segment_id}'. Must be a valid NH-7 corridor segment (e.g. seg_01 to seg_18)."
                )

        cursor.execute("""
            INSERT INTO road_closures (
                segment_id, status, reason, source, starts_at, ends_at, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            closure.segment_id,
            closure.status,
            closure.reason.strip(),
            closure.source.strip(),
            starts_at,
            closure.ends_at,
            created_by,
            now_str
        ))
        closure_id = cursor.lastrowid

    logger.info(
        f"Admin created official road closure #{closure_id} on {closure.segment_id}: "
        f"status={closure.status}, reason='{closure.reason}', source='{closure.source}'"
    )

    return RoadClosureResponse(
        id=closure_id,
        segment_id=closure.segment_id,
        status=closure.status,
        reason=closure.reason.strip(),
        source=closure.source.strip(),
        starts_at=starts_at,
        ends_at=closure.ends_at,
        created_by=created_by,
        created_at=now_str
    )


@router.delete(
    "/admin/closure/{closure_id}",
    summary="Delete / reopen official road closure (Admin only)"
)
def delete_road_closure(
    closure_id: int,
    admin_key: str = Depends(verify_admin_key)
):
    """
    Deletes an official road closure, restoring the sector to standard physical risk evaluation.
    Protected by admin key (X-Admin-Key or X-API-Key).
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, segment_id, status FROM road_closures WHERE id = ?", (closure_id,))
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Road closure #{closure_id} not found."
            )

        cursor.execute("DELETE FROM road_closures WHERE id = ?", (closure_id,))

    logger.info(f"Admin deleted road closure #{closure_id} on {existing['segment_id']}")
    return {
        "ok": True,
        "deleted_id": closure_id,
        "segment_id": existing["segment_id"],
        "message": f"Road closure #{closure_id} on {existing['segment_id']} removed successfully."
    }


@router.get(
    "/closures",
    response_model=List[RoadClosureResponse],
    summary="List active or corridor road closures (Public)"
)
@limiter.limit("120/minute")
def list_road_closures(
    request: Request,
    segment_id: Optional[str] = Query(None, description="Filter closures by segment ID"),
    active_only: bool = Query(True, description="Filter for currently active closures only")
):
    """
    Public listing of official road closures and restrictions along NH-7.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    query = "SELECT * FROM road_closures WHERE 1=1"
    params = []

    if active_only:
        query += " AND starts_at <= ? AND (ends_at IS NULL OR ends_at >= ?)"
        params.extend([now_str, now_str])

    if segment_id:
        query += " AND segment_id = ?"
        params.append(segment_id)

    query += " ORDER BY id DESC"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    return [
        RoadClosureResponse(
            id=r["id"],
            segment_id=r["segment_id"],
            status=r["status"],
            reason=r["reason"],
            source=r["source"],
            starts_at=r["starts_at"],
            ends_at=r["ends_at"],
            created_by=r["created_by"],
            created_at=r["created_at"]
        )
        for r in rows
    ]
