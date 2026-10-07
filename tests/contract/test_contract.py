import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
import app.risk_service as RS

client = TestClient(app)

MOCK_RAIN = {
    f"seg_{i:02d}": {"rain_mm": 20.0, "status": "ok"}
    for i in range(1, 19)
}

EXPECTED_SEGMENT_KEYS = {
    "id": str,
    "name": str,
    "sequence_order": int,
    "start_lat": float,
    "start_lng": float,
    "end_lat": float,
    "end_lng": float,
    "subpoints": list,
    "risk_level": str,
    "risk_score": (float, int),
    "updated_at": str,
    "terrain_percentile": (float, int, type(None)),
    "terrain_level": (str, type(None)),
    "terrain_status": (str, type(None)),
    "rain_mm_3d": (float, int, type(None)),
    "rain_status": (str, type(None)),
    "main_driver": (str, type(None)),
    "method": (str, type(None)),
}

EXPECTED_ROUTE_SEGMENT_KEYS = dict(EXPECTED_SEGMENT_KEYS)
EXPECTED_ROUTE_SEGMENT_KEYS.pop("updated_at")
EXPECTED_ROUTE_SEGMENT_KEYS["subpoint_risk_scores"] = list


@pytest.fixture(autouse=True)
def mock_weather_and_reset():
    """Ensure weather fetch never hits live network and cache is reset."""
    RS._rain_cache = {"t": 0.0, "data": None}
    RS._fail_cache = {"t": 0.0, "data": None}
    with patch("app.risk_service.fetch_rainfall", side_effect=lambda segs, session=None, simulate_rain_mm=None: (
        {s["id"]: {"rain_mm": float(simulate_rain_mm), "status": "simulated"} for s in segs}
        if simulate_rain_mm is not None
        else {s["id"]: {"rain_mm": 20.0, "status": "ok"} for s in segs}
    )):
        yield


def test_health_contract():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["status"], str)
    assert isinstance(data["system"], str)
    assert isinstance(data["corridor"], str)


def test_root_ui_contract():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


@pytest.mark.parametrize("sim_rain", [None, 0, 40, 100])
def test_risk_map_contract(sim_rain):
    url = "/risk-map" if sim_rain is None else f"/risk-map?simulate_rain_mm={sim_rain}"
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()

    # Top-level keys and types
    assert isinstance(data["corridor"], str)
    assert isinstance(data["total_segments"], int)
    assert isinstance(data["high_or_very_high_risk_count"], int)
    assert isinstance(data["segments"], list)
    assert len(data["segments"]) == 18

    # Per-segment keys and types
    for seg in data["segments"]:
        for key, expected_type in EXPECTED_SEGMENT_KEYS.items():
            assert key in seg, f"Missing key '{key}' in segment {seg.get('id')}"
            val = seg[key]
            assert isinstance(val, expected_type), (
                f"Segment '{seg.get('id')}' key '{key}' has value {val!r} of type {type(val)}, "
                f"expected {expected_type}"
            )


@pytest.mark.parametrize("sim_rain", [None, 0, 40, 100])
def test_route_risk_contract(sim_rain):
    base_url = "/route-risk?from_segment=seg_01&to_segment=seg_05&date=2026-10-06"
    url = base_url if sim_rain is None else f"{base_url}&simulate_rain_mm={sim_rain}"
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data["from_segment"], str)
    assert isinstance(data["to_segment"], str)
    assert isinstance(data["from_segment_name"], str)
    assert isinstance(data["to_segment_name"], str)
    assert isinstance(data["date"], str)
    assert isinstance(data["total_segments"], int)
    assert isinstance(data["max_risk_level"], str)
    assert isinstance(data["average_risk_score"], (float, int))
    assert isinstance(data["advisory"], str)
    assert isinstance(data["segments"], list)

    for seg in data["segments"]:
        for key, expected_type in EXPECTED_ROUTE_SEGMENT_KEYS.items():
            assert key in seg, f"Missing key '{key}' in route segment {seg.get('id')}"
            val = seg[key]
            assert isinstance(val, expected_type), (
                f"Route segment '{seg.get('id')}' key '{key}' value {val!r} has type {type(val)}, expected {expected_type}"
            )


def test_subscribe_contract():
    payload = {
        "name": "Contract Test Driver",
        "phone_or_email": "+91-9988776655",
        "segment_id": "seg_08",
        "channel": "WhatsApp"
    }
    resp = client.post("/subscribe", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert isinstance(data["subscription_id"], int)
    assert isinstance(data["token"], str)
    assert isinstance(data["status"], str)
    assert isinstance(data["message"], str)
    sub = data["subscription"]
    assert isinstance(sub["id"], int)
    assert isinstance(sub["name"], str)
    assert isinstance(sub["phone_or_email"], str)
    assert isinstance(sub["segment_id"], str)
    assert isinstance(sub["segment_name"], str)
    assert isinstance(sub["channel"], str)
    assert isinstance(sub["created_at"], str)


@pytest.mark.parametrize("sim_rain", [None, 0, 40, 100])
def test_alerts_contract(sim_rain):
    # Register subscription first
    sub_payload = {
        "name": "Alerts Contract User",
        "phone_or_email": "+91-9123456789",
        "segment_id": "seg_08",
        "channel": "SMS"
    }
    sub_res = client.post("/subscribe", json=sub_payload)
    sub_data = sub_res.json()
    sub_id = sub_data["subscription_id"]
    token = sub_data["token"]

    base_url = f"/alerts?user_id={sub_id}&token={token}"
    url = base_url if sim_rain is None else f"{base_url}&simulate_rain_mm={sim_rain}"
    resp = client.get(url)
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data["user_id"], int)
    assert isinstance(data["subscriber_name"], str)
    assert isinstance(data["subscribed_segment"], str)
    assert isinstance(data["active_alerts_count"], int)
    assert isinstance(data["alerts"], list)

    for a in data["alerts"]:
        assert isinstance(a["alert_id"], str)
        assert isinstance(a["segment_id"], str)
        assert isinstance(a["segment_name"], str)
        assert isinstance(a["severity"], str)
        assert isinstance(a["risk_score"], (float, int))
        assert isinstance(a["message"], str)
        assert isinstance(a["channel"], str)
        assert isinstance(a["issued_at"], str)
        assert isinstance(a["rain_mm_3d"], (float, int, type(None)))
        assert isinstance(a["rain_status"], (str, type(None)))
        assert isinstance(a["main_driver"], (str, type(None)))


def test_field_report_and_validation_contract():
    # Submit field report
    rep_payload = {
        "lat": 30.25,
        "lng": 78.88,
        "description": "Loose scree on road shoulder",
        "reporter_name": "NH-7 Patrol Team"
    }
    rep_res = client.post("/field-report", json=rep_payload)
    assert rep_res.status_code == 201
    rep_data = rep_res.json()
    assert isinstance(rep_data["report_id"], int)
    assert isinstance(rep_data["status"], str)
    assert isinstance(rep_data["message"], str)
    assert isinstance(rep_data["submitted_at"], str)

    rep_id = rep_data["report_id"]

    # Validate report
    val_payload = {
        "report_id": rep_id,
        "decision": "Validated",
        "notes": "Verified by admin officer"
    }
    val_res = client.post("/admin/validate-report", json=val_payload)
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert isinstance(val_data["report_id"], int)
    assert isinstance(val_data["status"], str)
    assert isinstance(val_data["updated_at"], str)
    assert isinstance(val_data["message"], str)


def test_field_reports_list_contract():
    resp = client.get("/field-reports")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for r in data:
        assert isinstance(r["id"], int)
        assert isinstance(r["lat"], (float, int))
        assert isinstance(r["lng"], (float, int))
        assert isinstance(r["description"], str)
        assert isinstance(r["reporter_name"], str)
        assert isinstance(r["status"], str)
        assert isinstance(r["created_at"], str)
        assert isinstance(r["updated_at"], str)


def test_history_contract():
    resp = client.get("/history")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["total_events"], int)
    assert isinstance(data["events"], list)
    for ev in data["events"]:
        assert isinstance(ev["id"], int)
        assert isinstance(ev["title"], str)
        assert isinstance(ev["location"], str)
        assert isinstance(ev["lat"], (float, int))
        assert isinstance(ev["lng"], (float, int))
        assert isinstance(ev["event_date"], str)
        assert isinstance(ev["description"], str)
        assert isinstance(ev["severity"], str)
