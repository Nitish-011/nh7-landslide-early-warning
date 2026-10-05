#!/usr/bin/env python3
"""
scripts/export_validated_reports.py - Export verified ground reports for model retraining
========================================================================================
Queries the local SQLite database for all validated crowd-sourced field reports,
formats them with assigned highway segments, and exports them to data/validated_reports.csv.
"""
import csv
import logging
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import config
from app.database import get_db, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("export_validated_reports")

EXPORT_CSV_PATH = getattr(config, "VALIDATED_REPORTS_CSV_PATH", config.DATA_DIR / "validated_reports.csv")

FIELDNAMES = [
    "report_id",
    "lat",
    "lng",
    "segment_id",
    "reporter_name",
    "description",
    "photo_url",
    "status",
    "decision_notes",
    "created_at",
    "updated_at",
]


def export_validated_reports(output_path: Path = EXPORT_CSV_PATH) -> int:
    """
    Exports all validated field reports to a CSV file.
    Creates parent directories if necessary and ensures header is always present.
    Returns the number of exported records.
    """
    init_db()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, lat, lng, segment_id, reporter_name, description, photo_url, status, decision_notes, created_at, updated_at
            FROM field_reports
            WHERE status = 'Validated'
            ORDER BY id ASC
        """)
        rows = cursor.fetchall()

    from app.flywheel_service import find_nearest_segment

    records = []
    for r in rows:
        seg_id = r["segment_id"] or find_nearest_segment(r["lat"], r["lng"])
        if not r["segment_id"]:
            with get_db() as update_conn:
                update_conn.execute("UPDATE field_reports SET segment_id = ? WHERE id = ?", (seg_id, r["id"]))

        records.append({
            "report_id": r["id"],
            "lat": r["lat"],
            "lng": r["lng"],
            "segment_id": seg_id,
            "reporter_name": r["reporter_name"],
            "description": r["description"],
            "photo_url": r["photo_url"] or "",
            "status": r["status"],
            "decision_notes": r["decision_notes"] or "",
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)

    log.info("Exported %d validated field reports to %s", len(records), output_path)
    return len(records)


def main():
    count = export_validated_reports()
    print(f"Export complete. {count} validated reports saved to {EXPORT_CSV_PATH}")


if __name__ == "__main__":
    main()
