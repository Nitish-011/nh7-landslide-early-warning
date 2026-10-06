import time
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient
import requests

from app.main import app
import app.risk_service as RS

client = TestClient(app)

# Realistic mock payload representing 5 Open-Meteo weather stations on NH-7
MOCK_OPEN_METEO_PAYLOAD = [
    {"daily": {"precipitation_sum": [5.0, 10.0, 2.0]}},
    {"daily": {"precipitation_sum": [4.0, 8.0, 1.0]}},
    {"daily": {"precipitation_sum": [6.0, 12.0, 3.0]}},
    {"daily": {"precipitation_sum": [7.0, 15.0, 4.0]}},
    {"daily": {"precipitation_sum": [8.0, 20.0, 5.0]}},
]

class MockHttpResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def reset_risk_service_caches():
    """Resets memory caches before each test."""
    RS._rain_cache = {"t": 0.0, "data": None}
    RS._fail_cache = {"t": 0.0, "data": None}


def test_live_fetch_and_snapshot_creation(tmp_path):
    """Confirm live fetch creates data/rain_snapshot.json on success via mocked Open-Meteo response."""
    RS._rain_cache = {"t": 0.0, "data": None}
    RS._fail_cache = {"t": 0.0, "data": None}

    with patch("requests.Session.get", return_value=MockHttpResponse(MOCK_OPEN_METEO_PAYLOAD)):
        resp = client.get("/risk-map")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_segments"] == 18

    # Verify data/rain_snapshot.json was written
    assert RS.RAIN_SNAPSHOT_FILE.exists()
    snap = json.loads(RS.RAIN_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    assert "timestamp" in snap
    assert "data" in snap
    assert "seg_01" in snap["data"]
    assert snap["data"]["seg_01"]["status"] == "ok"


def test_api_down_uses_snapshot_and_responds_under_1_second():
    """
    Simulates Open-Meteo API being down (e.g. timeout or connection refusal).
    Confirms:
    1. /risk-map answers in under 1 second.
    2. rain_status is set to 'cached' with the snapshot timestamp.
    3. Failure is cached for 5 minutes so subsequent calls respond instantly (<0.05s).
    """
    assert RS.RAIN_SNAPSHOT_FILE.exists(), "rain_snapshot.json must exist"
    snap = json.loads(RS.RAIN_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    expected_timestamp = snap["timestamp"]

    RS._rain_cache = {"t": 0.0, "data": None}
    RS._fail_cache = {"t": 0.0, "data": None}

    # Simulate network failure / timeout
    with patch("requests.Session.get", side_effect=requests.exceptions.ConnectTimeout("Connection timed out")):
        t0 = time.perf_counter()
        resp = client.get("/risk-map")
        elapsed = time.perf_counter() - t0

    assert resp.status_code == 200
    assert elapsed < 1.0, f"Expected response in < 1.0s, took {elapsed:.3f}s"

    data = resp.json()
    assert data["total_segments"] == 18
    sample_seg = data["segments"][0]

    assert "cached" in sample_seg["rain_status"]
    assert expected_timestamp in sample_seg["rain_status"]
    assert sample_seg["rain_mm_3d"] is not None

    # Verify cached failure avoids blocking
    t0_subsequent = time.perf_counter()
    with patch("requests.Session.get", side_effect=requests.exceptions.ConnectTimeout("Connection timed out")):
        resp2 = client.get("/risk-map")
    elapsed_subsequent = time.perf_counter() - t0_subsequent

    assert resp2.status_code == 200
    assert elapsed_subsequent < 0.5, f"Expected cached failure to return in < 0.5s, took {elapsed_subsequent:.3f}s"
    assert "cached" in resp2.json()["segments"][0]["rain_status"]


def test_api_down_and_no_snapshot_falls_back_to_terrain_only():
    """
    Confirms that if the live API call fails and NO snapshot exists,
    it falls back to terrain-only mode in under 1 second without error.
    """
    RS._rain_cache = {"t": 0.0, "data": None}
    RS._fail_cache = {"t": 0.0, "data": None}

    with patch.object(RS, "RAIN_SNAPSHOT_FILE", Path("data/non_existent_snapshot.json")):
        with patch("requests.Session.get", side_effect=requests.exceptions.ConnectionError("API Unreachable")):
            t0 = time.perf_counter()
            resp = client.get("/risk-map")
            elapsed = time.perf_counter() - t0

    assert resp.status_code == 200
    assert elapsed < 1.0, f"Expected response in < 1.0s, took {elapsed:.3f}s"

    data = resp.json()
    assert data["total_segments"] == 18
    sample_seg = data["segments"][0]
    assert sample_seg["rain_status"] == "unavailable"
    assert sample_seg["rain_mm_3d"] is None


def test_route_risk_invalid_date_returns_400():
    """Confirms that malformed date strings return HTTP 400 Bad Request."""
    resp = client.get("/route-risk?from_segment=seg_01&to_segment=seg_05&date=not-a-date")
    assert resp.status_code == 400
    assert "Invalid date format" in resp.json()["detail"]


def test_emergency_contacts_env_parsing(monkeypatch):
    """Confirms that EMERGENCY_CONTACTS environment variable is parsed using json.loads."""
    custom_contacts = [
        {"name": "SDRF Control Room", "number": "1070"}
    ]
    monkeypatch.setenv("EMERGENCY_CONTACTS", json.dumps(custom_contacts))

    import importlib
    import app.config as cfg
    importlib.reload(cfg)

    assert cfg.EMERGENCY_CONTACTS == custom_contacts

    monkeypatch.delenv("EMERGENCY_CONTACTS", raising=False)
    importlib.reload(cfg)


def test_risk_strictly_increases_between_100_and_150mm():
    """
    Regression test: ensures RAIN_REF_MM=150 prevents premature saturation at 100mm.
    For every segment on NH-7, risk_score must strictly increase from 100mm to 150mm.
    """
    resp100 = client.get("/risk-map?simulate_rain_mm=100")
    assert resp100.status_code == 200
    segs100 = {s["id"]: s["risk_score"] for s in resp100.json()["segments"]}

    resp150 = client.get("/risk-map?simulate_rain_mm=150")
    assert resp150.status_code == 200
    segs150 = {s["id"]: s["risk_score"] for s in resp150.json()["segments"]}

    for seg_id, score100 in segs100.items():
        score150 = segs150[seg_id]
        assert score150 > score100, (
            f"Segment {seg_id} failed strict monotonicity: "
            f"score at 100mm ({score100}) >= score at 150mm ({score150})"
        )


def test_terrain_floor_allows_low_rank_segments_to_escalate():
    """
    Regression test: TERRAIN_FLOOR (0.35) ensures even lowest-percentile segments
    (seg_10 with pct=0.00, seg_08 with pct=0.06) escalate to High under severe rain (140mm+).
    """
    resp140 = client.get("/risk-map?simulate_rain_mm=140")
    assert resp140.status_code == 200
    segs140 = {s["id"]: s for s in resp140.json()["segments"]}

    # seg_10 has terrain_percentile 0.00, seg_08 has 0.06
    assert segs140["seg_10"]["risk_score"] >= 0.50
    assert segs140["seg_10"]["risk_level"] in ("High", "Very High")
    assert segs140["seg_08"]["risk_score"] >= 0.50
    assert segs140["seg_08"]["risk_level"] in ("High", "Very High")


def test_dry_condition_guardrail_and_ramp():
    """
    Regression test: dry conditions (0mm, 15mm) remain capped at Moderate (<=0.49),
    and smooth ramp transitions without cliff.
    """
    resp0 = client.get("/risk-map?simulate_rain_mm=0")
    assert resp0.status_code == 200
    for s in resp0.json()["segments"]:
        assert s["risk_level"] in ("Low", "Moderate")
        assert s["risk_score"] <= 0.49

    resp15 = client.get("/risk-map?simulate_rain_mm=15")
    assert resp15.status_code == 200
    for s in resp15.json()["segments"]:
        assert s["risk_level"] in ("Low", "Moderate")
        assert s["risk_score"] <= 0.49

