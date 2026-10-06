import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import requests
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import config
from app import risk_service
from app import weather_service

client = TestClient(app)


def generate_mock_hourly_open_meteo(n_locations=18):
    """Generates synthetic Open-Meteo hourly response for n locations."""
    times = []
    base_t = datetime(2026, 10, 6, 0, 0, 0, tzinfo=timezone.utc)
    for h in range(-71, 73):
        t = datetime.fromtimestamp(base_t.timestamp() + h * 3600, tz=timezone.utc)
        times.append(t.strftime("%Y-%m-%dT%H:00"))

    payloads = []
    for _ in range(n_locations):
        precip = [0.5] * len(times)
        # Add peak at +6h
        precip[71 + 6] = 8.5
        payloads.append({
            "hourly": {
                "time": times,
                "precipitation": precip,
            }
        })
    return payloads


def test_hourly_metrics_computation():
    """Unit test for compute_hourly_metrics."""
    base_t = datetime(2026, 10, 6, 0, 0, 0, tzinfo=timezone.utc)
    times = []
    precip = []
    for h in range(-71, 73):
        t = datetime.fromtimestamp(base_t.timestamp() + h * 3600, tz=timezone.utc)
        times.append(t.strftime("%Y-%m-%dT%H:00"))
        precip.append(1.0)  # 1.0 mm per hour

    # Inject peak at hour +4
    precip[71 + 4] = 9.0

    raw_hourly = {"time": times, "precipitation": precip}
    metrics = weather_service.compute_hourly_metrics(raw_hourly, ref_time=base_t)

    assert metrics["r3d_mm"] == 72.0       # 72 hours * 1.0 mm
    assert metrics["rain_24h_mm"] == 24.0   # 24 hours * 1.0 mm
    assert metrics["forecast_24h_mm"] == 32.0  # 23*1.0 + 9.0 = 32.0 mm
    assert metrics["peak_mm"] == 9.0
    assert metrics["peak_hour_utc"] is not None
    assert metrics["peak_hour_utc"].endswith("Z")


def test_per_segment_weather_flag_off():
    """When PER_SEGMENT_WEATHER=false, risk-map preserves standard schema without new keys."""
    with patch.object(config, "PER_SEGMENT_WEATHER", False):
        resp = client.get("/risk-map?simulate_rain_mm=25")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["segments"]) == 18
        seg0 = data["segments"][0]
        # In flag off, these are None or default
        assert seg0.get("r3d_mm") is None
        assert seg0.get("rain_24h_mm") is None


def test_per_segment_weather_flag_on():
    """When PER_SEGMENT_WEATHER=true, risk-map populates additive weather and forecast fields."""
    mock_payload = generate_mock_hourly_open_meteo(18)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload
    mock_resp.raise_for_status = MagicMock()

    with patch.object(config, "PER_SEGMENT_WEATHER", True), \
         patch("requests.Session.get", return_value=mock_resp):

        # Reset caches
        weather_service._rain_cache = {"t": 0.0, "data": None, "fetched_at": None, "source": None}
        weather_service._fail_cache = {"t": 0.0, "data": None, "meta": None}

        resp = client.get("/risk-map")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["segments"]) == 18

        seg0 = data["segments"][0]
        assert seg0["r3d_mm"] is not None
        assert seg0["rain_24h_mm"] is not None
        assert seg0["forecast_24h_mm"] is not None
        assert seg0["forecast_72h_mm"] is not None
        assert seg0["peak_hour_utc"] is not None
        assert seg0["peak_mm"] is not None
        assert isinstance(seg0["r3d_mm"], (float, int))


def test_tier2_5station_fallback(tmp_path):
    """When Tier 1 raises an exception, the system falls back to Tier 2 (5-station)."""
    # Tier 1 fails, Tier 2 succeeds
    def mock_get(url, params=None, timeout=None):
        if "hourly" in str(params):
            raise requests.exceptions.ConnectTimeout("Tier 1 timeout")
        # Tier 2 daily response
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = [
            {"daily": {"precipitation_sum": [15.0, 10.0, 5.0]}}
            for _ in range(5)
        ]
        resp.raise_for_status = MagicMock()
        return resp

    segments = risk_service.load_segments()
    with patch("requests.Session.get", side_effect=mock_get):
        weather_service._rain_cache = {"t": 0.0, "data": None, "fetched_at": None, "source": None}
        weather_service._fail_cache = {"t": 0.0, "data": None, "meta": None}

        data, meta = weather_service.fetch_weather_pipeline(segments)
        assert meta["weather_source"] == "cached_5station"
        assert len(data) == 18
        assert data["seg_01"]["r3d_mm"] == 30.0


def test_tier3_snapshot_fallback_and_legacy_schema(tmp_path):
    """When live tiers fail, Tier 3 loads legacy snapshot format gracefully."""
    legacy_snapshot_file = tmp_path / "legacy_snapshot.json"
    legacy_payload = {
        "timestamp": "2026-10-05T12:00:00Z",
        "data": {
            f"seg_{i:02d}": {"rain_mm": 22.0, "status": "ok"}
            for i in range(1, 19)
        }
    }
    legacy_snapshot_file.write_text(json.dumps(legacy_payload), encoding="utf-8")

    segments = risk_service.load_segments()
    with patch.object(weather_service, "SNAPSHOT_PATH", legacy_snapshot_file), \
         patch("requests.Session.get", side_effect=requests.exceptions.ConnectionError("Offline")):

        weather_service._rain_cache = {"t": 0.0, "data": None, "fetched_at": None, "source": None}
        weather_service._fail_cache = {"t": 0.0, "data": None, "meta": None}

        data, meta = weather_service.fetch_weather_pipeline(segments)
        assert meta["weather_source"] == "snapshot"
        assert data["seg_01"]["r3d_mm"] == 22.0
        assert data["seg_01"]["rain_mm"] == 22.0


def test_contract_and_golden_with_flag_on():
    """Verify that contract tests and golden schema compatibility pass with PER_SEGMENT_WEATHER=True."""
    mock_payload = generate_mock_hourly_open_meteo(18)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload
    mock_resp.raise_for_status = MagicMock()

    with patch.object(config, "PER_SEGMENT_WEATHER", True), \
         patch("requests.Session.get", return_value=mock_resp):

        weather_service._rain_cache = {"t": 0.0, "data": None, "fetched_at": None, "source": None}
        weather_service._fail_cache = {"t": 0.0, "data": None, "meta": None}

        # 1. /risk-map with simulate_rain_mm=None, 0, 40, 100
        for sim in [None, 0, 40, 100]:
            url = "/risk-map" if sim is None else f"/risk-map?simulate_rain_mm={sim}"
            resp = client.get(url)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["segments"]) == 18
            for s in data["segments"]:
                assert "r3d_mm" in s
                assert "rain_24h_mm" in s
                assert "forecast_24h_mm" in s
                assert "forecast_72h_mm" in s
                assert "peak_hour_utc" in s
                assert "peak_mm" in s

        # 2. /route-risk
        resp = client.get("/route-risk?from_segment=seg_01&to_segment=seg_05&date=2026-10-06")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["segments"]) > 0
        seg0 = data["segments"][0]
        assert "r3d_mm" in seg0
        assert "forecast_24h_mm" in seg0


def test_per_segment_weather_pipeline_activation():
    """
    Verifies that when PER_SEGMENT_WEATHER is enabled, GET /risk-map exercises
    the advanced meteorological pipeline with hourly breakdown and peak metrics.
    """
    with patch.object(config, "PER_SEGMENT_WEATHER", True):
        resp = client.get("/risk-map?simulate_rain_mm=25")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["segments"]) == 18
        for seg in data["segments"]:
            assert "r3d_mm" in seg
            assert "rain_24h_mm" in seg
            assert "forecast_24h_mm" in seg
            assert "peak_mm" in seg


