from typing import List
from fastapi import APIRouter
from app.database import get_db
from app.models import HistoryResponse, LandslideHistoryItem

router = APIRouter(tags=["Historical Events"])

@router.get("/history", response_model=HistoryResponse)
def get_landslide_history():
    """
    Returns verified historical landslide and flash-hazard events along the NH-7 corridor
    in Uttarakhand with geographical coordinates, date, and impact summary.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM landslide_history ORDER BY id ASC")
        rows = cursor.fetchall()

    events: List[LandslideHistoryItem] = [
        LandslideHistoryItem(
            id=r["id"],
            title=r["title"],
            location=r["location"],
            lat=r["lat"],
            lng=r["lng"],
            event_date=r["event_date"],
            description=r["description"],
            severity=r["severity"]
        )
        for r in rows
    ]

    return HistoryResponse(
        total_events=len(events),
        events=events
    )
