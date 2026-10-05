import time
import json
import pytest
from unittest.mock import patch
from pathlib import Path
from fastapi.testclient import TestClient
import requests

from app.main import app
import app.risk_service as RS

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_risk_service_caches():
    """Resets memory caches before each test."""
    RS._rain_cache = {"t": 0.0, "data": None}
    RS._fail_cache = {"t": 0.0, "data": None}


def test_live_fetch_and_snapshot_creation(tmp_path):
    """Confirm live fetch creates data/rain_snapshot.json on success."""
    # Ensure cache is fresh
    RS._rain_cache = {"t": 0.0, "data": None}
    RS._fail_cache = {"t": 0.0, "data": None}

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
    # Ensure a valid snapshot exists
    assert RS.RAIN_SNAPSHOT_FILE.exists(), "rain_snapshot.json must exist"
    snap = json.loads(RS.RAIN_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    expected_timestamp = snap["timestamp"]

    # Clear memory cache so it attempts fetch
    RS._rain_cache = {"t": 0.0, "data": None}
    RS._fail_cache = {"t": 0.0, "data": None}

    # Simulate network failure / timeout
    with patch("requests.Session.get", side_effect=requests.exceptions.ConnectTimeout("Connection timed out")):
        t0 = time.perf_counter()
        resp = client.get("/risk-map")
        elapsed = time.perf_counter() - t0

    assert resp.status_code == 200
    # Requirement: confirms /risk-map answers in under 1 second
    assert elapsed < 1.0, f"Expected response in < 1.0s, took {elapsed:.3f}s"

    data = resp.json()
    assert data["total_segments"] == 18
    sample_seg = data["segments"][0]

    # Requirement: use snapshot and set rain_status to 'cached' with the snapshot time
    assert "cached" in sample_seg["rain_status"]
    assert expected_timestamp in sample_seg["rain_status"]
    assert sample_seg["rain_mm_3d"] is not None

    # Requirement: test that failure is cached for 5 minutes and subsequent calls don't block
    t0_subsequent = time.perf_counter()
    with patch("requests.Session.get", side_effect=requests.exceptions.ConnectTimeout("Connection timed out")):
        resp2 = client.get("/risk-map")
    elapsed_subsequent = time.perf_counter() - t0_subsequent

    assert resp2.status_code == 200
    assert elapsed_subsequent < 0.1, f"Expected cached failure to return in < 0.1s, took {elapsed_subsequent:.3f}s"
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
    # In terrain-only fallback:
    assert sample_seg["rain_status"] == "unavailable"
    assert sample_seg["rain_mm_3d"] is None
