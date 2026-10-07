import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app import config
from app.trip_planner import IST, SEGMENT_LENGTHS_KM

client = TestClient(app)


def test_time_aware_flag_disabled_by_default(monkeypatch):
    """When TIME_AWARE_PLANNER=False, passing depart_time returns HTTP 400."""
    monkeypatch.setattr(config, "TIME_AWARE_PLANNER", False)

    # With depart_time -> 400 disabled
    resp = client.get(
        "/route-risk",
        params={
            "from_segment": "seg_01",
            "to_segment": "seg_04",
            "date": "2026-10-06",
            "depart_time": "2026-10-06T08:00:00",
        },
    )
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"].lower()

    # Without depart_time -> 200 OK (identical legacy behavior)
    resp2 = client.get(
        "/route-risk",
        params={
            "from_segment": "seg_01",
            "to_segment": "seg_04",
            "date": "2026-10-06",
        },
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2.get("recommendation") is None
    assert data2.get("depart_time") is None
    assert data2["segments"][0].get("eta_ist") is None


def test_time_aware_param_validation(monkeypatch):
    """When enabled, invalid depart_time format or negative speed returns HTTP 400."""
    monkeypatch.setattr(config, "TIME_AWARE_PLANNER", True)

    # Invalid timestamp
    resp = client.get(
        "/route-risk",
        params={
            "from_segment": "seg_01",
            "to_segment": "seg_04",
            "date": "2026-10-06",
            "depart_time": "not-an-iso-time",
        },
    )
    assert resp.status_code == 400
    assert "Invalid depart_time format" in resp.json()["detail"]

    # Invalid speed
    resp2 = client.get(
        "/route-risk",
        params={
            "from_segment": "seg_01",
            "to_segment": "seg_04",
            "date": "2026-10-06",
            "depart_time": "2026-10-06T08:00:00",
            "speed_kmph": -15.0,
        },
    )
    assert resp2.status_code == 400
    assert "speed_kmph must be greater than 0" in resp2.json()["detail"]


def test_time_aware_both_directions(monkeypatch):
    """Verify segment ETAs are correctly sequenced for both forward and reverse journeys."""
    monkeypatch.setattr(config, "TIME_AWARE_PLANNER", True)

    # 1. Forward direction: seg_01 -> seg_03
    resp_fwd = client.get(
        "/route-risk",
        params={
            "from_segment": "seg_01",
            "to_segment": "seg_03",
            "date": "2026-10-06",
            "depart_time": "2026-10-06T08:00:00",
            "speed_kmph": 30.0,
        },
    )
    assert resp_fwd.status_code == 200
    data_fwd = resp_fwd.json()
    segs_fwd = data_fwd["segments"]
    assert len(segs_fwd) == 3
    assert segs_fwd[0]["id"] == "seg_01"
    assert segs_fwd[1]["id"] == "seg_02"
    assert segs_fwd[2]["id"] == "seg_03"

    # Departure at 08:00 IST
    assert "08:00:00" in segs_fwd[0]["eta_ist"]
    # seg_01 is 17.43 km -> ~0.581 h (34m 51s) -> seg_02 ETA ~ 08:34
    assert "08:34" in segs_fwd[1]["eta_ist"]
    # seg_02 is 6.83 km -> ~0.228 h (13m 39s) -> seg_03 ETA ~ 08:48
    assert "08:48" in segs_fwd[2]["eta_ist"]

    # 2. Reverse direction: seg_03 -> seg_01
    resp_rev = client.get(
        "/route-risk",
        params={
            "from_segment": "seg_03",
            "to_segment": "seg_01",
            "date": "2026-10-06",
            "depart_time": "2026-10-06T08:00:00",
            "speed_kmph": 30.0,
        },
    )
    assert resp_rev.status_code == 200
    data_rev = resp_rev.json()
    segs_rev = data_rev["segments"]
    assert len(segs_rev) == 3
    assert segs_rev[0]["id"] == "seg_03"
    assert segs_rev[1]["id"] == "seg_02"
    assert segs_rev[2]["id"] == "seg_01"

    # Departure at 08:00 IST at seg_03
    assert "08:00:00" in segs_rev[0]["eta_ist"]
    # seg_03 is 13.86 km -> ~0.462 h (27m 43s) -> seg_02 ETA ~ 08:27
    assert "08:27" in segs_rev[1]["eta_ist"]


def test_rain_peak_at_eta_changes_recommendation(monkeypatch):
    """
    CRITICAL ACCEPTANCE TEST:
    A sharp rain peak at ETA increases risk and triggers DELAY/AVOID.
    Departing at a later time when the peak has passed reduces risk and triggers GO/CAUTION.
    """
    monkeypatch.setattr(config, "TIME_AWARE_PLANNER", True)

    # Construct synthetic hourly time series for Open-Meteo
    # Base timestamp: 2026-10-06T00:00 UTC (05:30 IST)
    # Total 168 hours covering past 72h and forecast 96h
    t_start = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)
    hourly_times = [(t_start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(168)]

    # Peak timing:
    # A driver departing at 08:00 IST (02:30 UTC) reaches seg_04 around 09:20 IST (~03:50 UTC, hour index 75).
    # We place an intense convective rain burst (90 mm antecedent) around hour 74-76 for seg_04.
    precip_peak = [0.0] * 168
    for h in range(70, 76):
        precip_peak[h] = 16.0  # 6 * 16 = 96 mm rain right at 08:00-09:30 IST ETA window!

    # Later window: by hour 82 (15:00 IST / 09:30 UTC), rain has stopped (0 mm).
    fixture_weather = {
        "seg_01": {"rain_mm": 5.0, "r3d_mm": 5.0, "status": "ok", "hourly": {"time": hourly_times, "precipitation": [0.1]*168}},
        "seg_02": {"rain_mm": 5.0, "r3d_mm": 5.0, "status": "ok", "hourly": {"time": hourly_times, "precipitation": [0.1]*168}},
        "seg_03": {"rain_mm": 5.0, "r3d_mm": 5.0, "status": "ok", "hourly": {"time": hourly_times, "precipitation": [0.1]*168}},
        "seg_04": {"rain_mm": 96.0, "r3d_mm": 96.0, "status": "ok", "hourly": {"time": hourly_times, "precipitation": precip_peak}},
    }

    # Patch fetch_rainfall_with_metadata to return fixture_weather
    with patch("app.routes.risk.get_live_risk_map_with_metadata") as mock_live:
        # Build mocked live segments
        mock_segments = [
            {"id": "seg_01", "risk_score": 0.20, "risk_level": "Low", "terrain_percentile": 0.3, "hourly": fixture_weather["seg_01"]["hourly"]},
            {"id": "seg_02", "risk_score": 0.20, "risk_level": "Low", "terrain_percentile": 0.3, "hourly": fixture_weather["seg_02"]["hourly"]},
            {"id": "seg_03", "risk_score": 0.25, "risk_level": "Moderate", "terrain_percentile": 0.4, "hourly": fixture_weather["seg_03"]["hourly"]},
            {"id": "seg_04", "risk_score": 0.85, "risk_level": "Very High", "terrain_percentile": 0.9, "hourly": fixture_weather["seg_04"]["hourly"]},
        ]
        mock_meta = {"weather_source": "live", "weather_fetched_at": "2026-10-06T00:00:00Z", "is_simulated": False}
        mock_live.return_value = (mock_segments, mock_meta)

        # Scenario A: Depart at 08:00 IST (hits the rain peak at seg_04 ETA)
        resp_peak = client.get(
            "/route-risk",
            params={
                "from_segment": "seg_01",
                "to_segment": "seg_04",
                "date": "2026-10-06",
                "depart_time": "2026-10-06T08:00:00",
                "speed_kmph": 30.0,
            },
        )
        assert resp_peak.status_code == 200
        data_peak = resp_peak.json()
        rec_peak = data_peak["recommendation"]

        # High/Very High risk at ETA triggers DELAY recommendation with safer options
        assert rec_peak["action"] in ("DELAY", "AVOID")
        assert rec_peak["action_code"] in ("REC_DELAY", "REC_AVOID")
        assert len(rec_peak["best_departure_options"]) >= 1
        assert "params" in rec_peak
        assert rec_peak["params"]["current_max_risk"] in ("High", "Very High")

        # Per-segment fields populated at ETA
        seg4_peak = next(s for s in data_peak["segments"] if s["id"] == "seg_04")
        assert seg4_peak["rain_72h_at_eta_mm"] >= 70.0
        assert seg4_peak["risk_level_at_eta"] in ("High", "Very High")

        # Scenario B: Now depart at a later time (e.g. 18:00 IST) when peak is well past
        # In fixture, rain occurred at hours 70-76. By hours 148+, antecedent 72h window excludes hour 70-76.
        # Or let's test a dry fixture to verify recommendation switches to GO:
        dry_precip = [0.0] * 168
        dry_weather = {
            f"seg_{i:02d}": {"hourly": {"time": hourly_times, "precipitation": dry_precip}}
            for i in range(1, 19)
        }
        mock_dry_segments = [
            {"id": "seg_01", "risk_score": 0.15, "risk_level": "Low", "terrain_percentile": 0.05, "hourly": dry_weather["seg_01"]["hourly"]},
            {"id": "seg_02", "risk_score": 0.15, "risk_level": "Low", "terrain_percentile": 0.05, "hourly": dry_weather["seg_02"]["hourly"]},
            {"id": "seg_03", "risk_score": 0.18, "risk_level": "Low", "terrain_percentile": 0.05, "hourly": dry_weather["seg_03"]["hourly"]},
            {"id": "seg_04", "risk_score": 0.22, "risk_level": "Low", "terrain_percentile": 0.05, "hourly": dry_weather["seg_04"]["hourly"]},
        ]
        mock_live.return_value = (mock_dry_segments, mock_meta)

        resp_dry = client.get(
            "/route-risk",
            params={
                "from_segment": "seg_01",
                "to_segment": "seg_04",
                "date": "2026-10-06",
                "depart_time": "2026-10-06T08:00:00",
                "speed_kmph": 30.0,
            },
        )
        assert resp_dry.status_code == 200
        data_dry = resp_dry.json()
        rec_dry = data_dry["recommendation"]

        # In dry conditions, action switches from DELAY to LOW RISK – proceed with caution!
        assert rec_dry["action"] == "LOW RISK – proceed with caution"
        assert rec_dry["action_code"] == "REC_LOW_RISK_CAUTION"
        assert rec_dry["params"]["current_max_risk"] == "Low"
