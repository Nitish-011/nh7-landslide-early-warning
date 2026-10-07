import json
from pathlib import Path
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden"

MOCK_RAIN = {
    f"seg_{i:02d}": {"rain_mm": 18.5, "status": "ok"}
    for i in range(1, 19)
}


def assert_schema_compatible(actual, golden, path="root"):
    """
    Asserts that:
    1. Every key present in `golden` must exist in `actual`. (No keys disappeared)
    2. The type of each value in `actual` must match `golden` (or compatible numeric float/int).
    3. New keys in `actual` ARE permitted (additive changes allowed).
    """
    if golden is None:
        # None can be populated by any optional type or remain None
        return

    if isinstance(golden, dict):
        assert isinstance(actual, dict), f"At {path}: expected dict, got {type(actual).__name__}"
        for key, golden_val in golden.items():
            assert key in actual, f"At {path}: previously existing key '{key}' disappeared from response!"
            actual_val = actual[key]
            assert_schema_compatible(actual_val, golden_val, path=f"{path}.{key}")

    elif isinstance(golden, list):
        assert isinstance(actual, list), f"At {path}: expected list, got {type(actual).__name__}"
        if len(golden) > 0 and len(actual) > 0:
            # Check element schema against sample element
            assert_schema_compatible(actual[0], golden[0], path=f"{path}[0]")

    elif isinstance(golden, (int, float)):
        assert isinstance(actual, (int, float)), f"At {path}: expected number, got {type(actual).__name__}"

    elif isinstance(golden, str):
        assert isinstance(actual, str), f"At {path}: expected str, got {type(actual).__name__}"

    elif isinstance(golden, bool):
        assert isinstance(actual, bool), f"At {path}: expected bool, got {type(actual).__name__}"


@pytest.fixture(autouse=True)
def mock_weather():
    with patch("app.risk_service.fetch_rainfall", return_value=MOCK_RAIN):
        yield


def test_golden_health_schema():
    golden = json.loads((GOLDEN_DIR / "health_golden.json").read_text(encoding="utf-8"))
    res = client.get("/health").json()
    assert_schema_compatible(res, golden, path="health")


def test_golden_risk_map_schema():
    golden = json.loads((GOLDEN_DIR / "risk_map_golden.json").read_text(encoding="utf-8"))
    res = client.get("/risk-map").json()
    assert_schema_compatible(res, golden, path="risk_map")


def test_golden_route_risk_schema():
    golden = json.loads((GOLDEN_DIR / "route_risk_golden.json").read_text(encoding="utf-8"))
    res = client.get("/route-risk?from_segment=seg_01&to_segment=seg_04&date=2026-10-06").json()
    assert_schema_compatible(res, golden, path="route_risk")


def test_golden_subscribe_schema():
    golden = json.loads((GOLDEN_DIR / "subscribe_golden.json").read_text(encoding="utf-8"))
    payload = {
        "name": "Ramesh Kumar",
        "phone_or_email": "+91-9876543210",
        "segment_id": "seg_01",
        "channel": "SMS"
    }
    res = client.post("/subscribe", json=payload).json()
    assert_schema_compatible(res, golden, path="subscribe")


def test_golden_alerts_schema():
    golden = json.loads((GOLDEN_DIR / "alerts_golden.json").read_text(encoding="utf-8"))
    # Use existing or first valid subscriber
    sub_res = client.post("/subscribe", json={
        "name": "Golden Alert User",
        "phone_or_email": "+91-9876543210",
        "segment_id": "seg_01",
        "channel": "SMS"
    })
    sub_data = sub_res.json()
    sub_id = sub_data["subscription_id"]
    token = sub_data["token"]
    res = client.get(f"/alerts?user_id={sub_id}&token={token}").json()
    assert_schema_compatible(res, golden, path="alerts")


def test_golden_field_report_schema():
    golden = json.loads((GOLDEN_DIR / "field_report_golden.json").read_text(encoding="utf-8"))
    payload = {
        "lat": 30.12,
        "lng": 78.32,
        "description": "Small rockfall near Byasi bend",
        "reporter_name": "Patrol Team 1"
    }
    res = client.post("/field-report", json=payload).json()
    assert_schema_compatible(res, golden, path="field_report")


def test_golden_admin_validate_schema():
    golden = json.loads((GOLDEN_DIR / "admin_validate_golden.json").read_text(encoding="utf-8"))
    # Create a fresh report to validate
    rep_res = client.post("/field-report", json={
        "lat": 30.15,
        "lng": 78.35,
        "description": "Fresh scree accumulation",
        "reporter_name": "Patrol Unit"
    })
    rep_id = rep_res.json()["report_id"]
    val_payload = {
        "report_id": rep_id,
        "decision": "Validated",
        "notes": "Verified by ground team"
    }
    res = client.post("/admin/validate-report", json=val_payload).json()
    assert_schema_compatible(res, golden, path="admin_validate")


def test_golden_field_reports_list_schema():
    golden = json.loads((GOLDEN_DIR / "field_reports_list_golden.json").read_text(encoding="utf-8"))
    res = client.get("/field-reports").json()
    assert_schema_compatible(res, golden, path="field_reports_list")


def test_golden_history_schema():
    golden = json.loads((GOLDEN_DIR / "history_golden.json").read_text(encoding="utf-8"))
    res = client.get("/history").json()
    assert_schema_compatible(res, golden, path="history")
