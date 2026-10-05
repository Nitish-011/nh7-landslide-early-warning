import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import config
from app.database import get_db, init_db
from app.flywheel_service import find_nearest_segment, compute_segment_ground_truth
from scripts.export_validated_reports import export_validated_reports

client = TestClient(app)
ADMIN_HEADERS = {"X-Admin-Key": config.ADMIN_API_KEY} if config.ADMIN_API_KEY else {"X-API-Key": "dev-localhost"}


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    with get_db() as conn:
        conn.execute("DELETE FROM road_closures")
        conn.execute("DELETE FROM field_reports WHERE reporter_name LIKE 'Test-%'")
    yield
    with get_db() as conn:
        conn.execute("DELETE FROM road_closures")
        conn.execute("DELETE FROM field_reports WHERE reporter_name LIKE 'Test-%'")


def test_closure_crud_lifecycle():
    """Verify POST /admin/closure, GET /closures, and DELETE /admin/closure/{id}."""
    # 1. Unauthenticated creation should fail if ADMIN_API_KEY is configured
    if config.ADMIN_API_KEY:
        unauth_resp = client.post("/admin/closure", json={
            "segment_id": "seg_08",
            "status": "closed",
            "reason": "Debris clearance",
            "source": "BRO"
        })
        assert unauth_resp.status_code == 401

    # 2. Authenticated creation
    payload = {
        "segment_id": "seg_08",
        "status": "closed",
        "reason": "Active rockfall near Kaliasaur chute",
        "source": "BRO Project Shivalik",
        "created_by": "Officer-In-Charge"
    }
    resp = client.post("/admin/closure", json=payload, headers=ADMIN_HEADERS)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["id"] > 0
    assert created["segment_id"] == "seg_08"
    assert created["status"] == "closed"
    assert created["source"] == "BRO Project Shivalik"
    closure_id = created["id"]

    # 3. Public GET /closures
    list_resp = client.get("/closures")
    assert list_resp.status_code == 200
    closures = list_resp.json()
    assert len(closures) >= 1
    found = [c for c in closures if c["id"] == closure_id]
    assert len(found) == 1
    assert found[0]["reason"] == "Active rockfall near Kaliasaur chute"

    # Filter by segment
    filter_resp = client.get("/closures?segment_id=seg_08")
    assert filter_resp.status_code == 200
    assert any(c["id"] == closure_id for c in filter_resp.json())

    filter_other = client.get("/closures?segment_id=seg_01")
    assert filter_other.status_code == 200
    assert all(c["id"] != closure_id for c in filter_other.json())

    # 4. Authenticated DELETE /admin/closure/{id}
    del_resp = client.delete(f"/admin/closure/{closure_id}", headers=ADMIN_HEADERS)
    assert del_resp.status_code == 200
    assert del_resp.json()["ok"] is True

    # Check that closure is gone
    check_resp = client.get("/closures")
    assert all(c["id"] != closure_id for c in check_resp.json())


def test_closure_affects_risk_map_and_route_risk():
    """Verify /risk-map and /route-risk include closure object and force AVOID recommendation."""
    # Create active closure on seg_03
    payload = {
        "segment_id": "seg_03",
        "status": "closed",
        "reason": "Massive landslide block at Byasi curve",
        "source": "Uttarakhand Police",
        "created_by": "ControlRoom"
    }
    resp = client.post("/admin/closure", json=payload, headers=ADMIN_HEADERS)
    assert resp.status_code == 201
    closure_id = resp.json()["id"]

    # 1. Verify in /risk-map
    rm_resp = client.get("/risk-map")
    assert rm_resp.status_code == 200
    rm_data = rm_resp.json()
    seg_03 = next(s for s in rm_data["segments"] if s["id"] == "seg_03")
    assert seg_03["closure"] is not None
    assert seg_03["closure"]["status"] == "closed"
    assert "Byasi" in seg_03["closure"]["reason"]

    # Other segment should not have closure
    seg_01 = next(s for s in rm_data["segments"] if s["id"] == "seg_01")
    assert seg_01["closure"] is None

    # 2. Verify in /route-risk (route passing through seg_03: seg_01 -> seg_05)
    rr_resp = client.get("/route-risk?from_segment=seg_01&to_segment=seg_05&date=2026-10-06")
    assert rr_resp.status_code == 200
    rr_data = rr_resp.json()

    assert rr_data["closure"] is not None
    assert rr_data["closure"]["segment_id"] == "seg_03"
    assert rr_data["recommendation"] is not None
    assert rr_data["recommendation"]["action"] == "AVOID"
    assert "Official road closure" in rr_data["recommendation"]["reason"]
    assert "Byasi" in rr_data["recommendation"]["reason"]
    assert "OFFICIAL CLOSURE WARNING" in rr_data["advisory"]

    # Clean up closure
    client.delete(f"/admin/closure/{closure_id}", headers=ADMIN_HEADERS)


def test_validation_assigns_nearest_segment():
    """Verify that when an admin validates a field report, it assigns it to the nearest segment."""
    # Submit report near Srinagar / seg_08 (~30.22, 78.78)
    sub_resp = client.post("/field-report", json={
        "lat": 30.22,
        "lng": 78.78,
        "description": "Test-Ground fissure observed above highway shoulder",
        "reporter_name": "Test-Observer"
    })
    assert sub_resp.status_code == 201
    report_id = sub_resp.json()["report_id"]

    # Validate report via admin endpoint
    val_resp = client.post("/admin/validate-report", json={
        "report_id": report_id,
        "decision": "Validated",
        "notes": "Verified by field team"
    }, headers=ADMIN_HEADERS)
    assert val_resp.status_code == 200

    # Query DB to check assigned segment_id
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, segment_id, status FROM field_reports WHERE id = ?", (report_id,))
        row = cursor.fetchone()
        assert row["status"] == "Validated"
        assert row["segment_id"] in ("seg_07", "seg_08"), f"Expected near Srinagar, got {row['segment_id']}"


def test_exponential_decay_and_half_life():
    """Verify exponential decay with 48h half-life: fresh report escalates, 150h old report does not."""
    target_seg = "seg_10"
    now = datetime.now(timezone.utc)

    # 1. Insert a 150-hour-old validated report (weight: 0.5^(150/48) = 0.11 < 0.75)
    old_time = (now - timedelta(hours=150)).isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO field_reports (
                lat, lng, description, reporter_name, status, created_at, updated_at, segment_id
            ) VALUES (30.28, 78.98, 'Test-Old boulder on road', 'Test-Historic', 'Validated', ?, ?, ?)
        """, (old_time, old_time, target_seg))

    # Compute ground truth for old report
    res_old = compute_segment_ground_truth(target_seg, base_risk_level="Low")
    assert res_old["adjusted_risk_level"] == "Low", "Old decayed report should not escalate risk level"
    assert res_old["ground_report_count_24h"] == 0

    # 2. Insert a fresh validated report from 2 hours ago (weight: 0.5^(2/48) = 0.97 > 0.75)
    fresh_time = (now - timedelta(hours=2)).isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO field_reports (
                lat, lng, description, reporter_name, status, created_at, updated_at, segment_id
            ) VALUES (30.28, 78.98, 'Test-Fresh debris slide', 'Test-Patrol', 'Validated', ?, ?, ?)
        """, (fresh_time, fresh_time, target_seg))

    res_fresh = compute_segment_ground_truth(target_seg, base_risk_level="Low")
    assert res_fresh["adjusted_risk_level"] == "Moderate", "Fresh report should escalate Low to Moderate"
    assert res_fresh["ground_report_count_24h"] == 1
    assert "1 verified ground report" in res_fresh["adjustment_reason"]


def test_maximum_one_step_cap():
    """Verify escalation is strictly capped at at most ONE step even with multiple fresh reports."""
    target_seg = "seg_12"
    now_str = datetime.now(timezone.utc).isoformat()

    # Insert 5 fresh validated reports for seg_12
    with get_db() as conn:
        for i in range(5):
            conn.execute("""
                INSERT INTO field_reports (
                    lat, lng, description, reporter_name, status, created_at, updated_at, segment_id
                ) VALUES (30.26, 79.22, ?, 'Test-Team', 'Validated', ?, ?, ?)
            """, (f"Test-Emergency observation {i}", now_str, now_str, target_seg))

    # Low should escalate to Moderate, NOT High or Very High
    res_low = compute_segment_ground_truth(target_seg, base_risk_level="Low")
    assert res_low["adjusted_risk_level"] == "Moderate", "Must be capped at 1 step (Low -> Moderate)"
    assert res_low["ground_report_count_24h"] == 5

    # Moderate should escalate to High
    res_mod = compute_segment_ground_truth(target_seg, base_risk_level="Moderate")
    assert res_mod["adjusted_risk_level"] == "High", "Must be capped at 1 step (Moderate -> High)"

    # High should escalate to Very High
    res_high = compute_segment_ground_truth(target_seg, base_risk_level="High")
    assert res_high["adjusted_risk_level"] == "Very High"

    # Very High remains Very High
    res_vh = compute_segment_ground_truth(target_seg, base_risk_level="Very High")
    assert res_vh["adjusted_risk_level"] == "Very High"


def test_ground_truth_layer_gating(monkeypatch):
    """Verify GROUND_TRUTH_LAYER=False disables flywheel adjustments."""
    monkeypatch.setattr(config, "GROUND_TRUTH_LAYER", False)
    res = compute_segment_ground_truth("seg_08", base_risk_level="Low")
    assert res["adjusted_risk_level"] is None
    assert res["ground_report_count_24h"] is None
    assert res["adjustment_reason"] is None


def test_export_validated_reports_script(tmp_path):
    """Verify scripts/export_validated_reports.py creates valid CSV with headers and records."""
    out_csv = tmp_path / "validated_reports_test.csv"
    count = export_validated_reports(output_path=out_csv)
    assert out_csv.exists()
    assert count >= 2  # Seed has at least 2 validated reports

    with open(out_csv, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == count
    required_cols = ["report_id", "lat", "lng", "segment_id", "reporter_name", "description", "status"]
    for col in required_cols:
        assert col in reader[0]
        assert reader[0][col] != "", f"Column {col} should have data"
