import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests
from fastapi.testclient import TestClient

from app.main import app
import app.risk_service as RS
from app.alert_service import (
    AlertSimulationSafetyError,
    persist_alert,
    dispatch_alert,
    can_dispatch_or_store,
)
from app.models import AlertItem

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_risk_cache():
    """Resets memory caches before each test."""
    RS._rain_cache = {"t": 0.0, "data": None, "fetched_at": None}
    RS._fail_cache = {"t": 0.0, "data": None, "meta": None}


# ---------------------------------------------------------------------------
# 1. Tier 1: Live Weather Fetch
# ---------------------------------------------------------------------------

def test_tier1_live_weather():
    """Live successful API fetch yields weather_source='live', is_simulated=False."""
    # Mock open-meteo response for 18 segments
    segments = RS.load_segments()
    mock_payload = [{"daily": {"precipitation_sum": [5.0, 3.0, 2.0]}} for _ in segments]

    with patch("requests.Session.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        res = client.get("/risk-map")
        assert res.status_code == 200
        data = res.json()

        assert data["weather_source"] == "live"
        assert data["is_simulated"] is False
        assert data["weather_fetched_at"] is not None
        assert isinstance(data["weather_age_minutes"], (float, int))
        assert data["weather_age_minutes"] < 1.0
        assert data["stale_warning"] is None


# ---------------------------------------------------------------------------
# 2. Tier 2: In-Memory Cached Weather
# ---------------------------------------------------------------------------

def test_tier2_cached_weather():
    """Second call within CACHE_TTL yields weather_source='cached'."""
    now_ts = time.time() - 300  # 5 minutes ago
    now_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sample_data = {s["id"]: {"rain_mm": 12.0, "status": "ok"} for s in RS.load_segments()}

    RS._rain_cache = {
        "t": now_ts,
        "data": sample_data,
        "fetched_at": now_iso
    }

    res = client.get("/risk-map")
    assert res.status_code == 200
    data = res.json()

    assert data["weather_source"] == "cached"
    assert data["is_simulated"] is False
    assert data["weather_fetched_at"] == now_iso
    assert data["weather_age_minutes"] == pytest.approx(5.0, abs=1.0)
    assert data["stale_warning"] is None


# ---------------------------------------------------------------------------
# 3. Tier 3: Fresh Snapshot Fallback (Age <= 6 hours)
# ---------------------------------------------------------------------------

def test_tier3_fresh_snapshot(tmp_path):
    """When live API is down and snapshot is fresh (<= 6h), weather_source='snapshot' and stale_warning=None."""
    snap_time = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap_content = {
        "timestamp": snap_time,
        "data": {s["id"]: {"rain_mm": 15.0, "status": "ok"} for s in RS.load_segments()}
    }

    test_snap_file = tmp_path / "test_fresh_snapshot.json"
    test_snap_file.write_text(json.dumps(snap_content), encoding="utf-8")

    with patch.object(RS, "RAIN_SNAPSHOT_FILE", test_snap_file):
        with patch("requests.Session.get", side_effect=requests.exceptions.ConnectTimeout("Down")):
            res = client.get("/risk-map")
            assert res.status_code == 200
            data = res.json()

            assert data["weather_source"] == "snapshot"
            assert data["is_simulated"] is False
            assert data["weather_fetched_at"] == snap_time
            assert data["weather_age_minutes"] == pytest.approx(120.0, abs=5.0)
            assert data["stale_warning"] is None


# ---------------------------------------------------------------------------
# 4. Tier 4: Stale Snapshot Fallback (Age > 6 hours)
# ---------------------------------------------------------------------------

def test_tier4_stale_snapshot(tmp_path):
    """When live API is down and snapshot is > 6h old, stale_warning is present."""
    snap_time = (datetime.now(timezone.utc) - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap_content = {
        "timestamp": snap_time,
        "data": {s["id"]: {"rain_mm": 20.0, "status": "ok"} for s in RS.load_segments()}
    }

    test_snap_file = tmp_path / "test_stale_snapshot.json"
    test_snap_file.write_text(json.dumps(snap_content), encoding="utf-8")

    with patch.object(RS, "RAIN_SNAPSHOT_FILE", test_snap_file):
        with patch("requests.Session.get", side_effect=requests.exceptions.ConnectTimeout("Down")):
            res = client.get("/risk-map")
            assert res.status_code == 200
            data = res.json()

            assert data["weather_source"] == "snapshot"
            assert data["is_simulated"] is False
            assert data["weather_fetched_at"] == snap_time
            assert data["weather_age_minutes"] == pytest.approx(480.0, abs=5.0)
            assert data["stale_warning"] is not None
            assert "8" in data["stale_warning"] or "old" in data["stale_warning"]


# ---------------------------------------------------------------------------
# 5. Tier 5: Simulation Mode
# ---------------------------------------------------------------------------

def test_tier5_simulation_mode():
    """Passing simulate_rain_mm yields weather_source='simulated', is_simulated=True."""
    res = client.get("/risk-map?simulate_rain_mm=75.0")
    assert res.status_code == 200
    data = res.json()

    assert data["weather_source"] == "simulated"
    assert data["is_simulated"] is True
    assert data["weather_fetched_at"] is not None
    assert data["weather_age_minutes"] == 0.0
    assert data["stale_warning"] is None


# ---------------------------------------------------------------------------
# 6. Endpoints Verification: /route-risk and /alerts Fields
# ---------------------------------------------------------------------------

def test_route_risk_and_alerts_freshness_fields():
    """Verify /route-risk and /alerts include the new freshness and simulation fields."""
    # 1. /route-risk with simulation
    res_route = client.get("/route-risk?from_segment=seg_01&to_segment=seg_04&date=2026-10-06&simulate_rain_mm=50")
    assert res_route.status_code == 200
    route_data = res_route.json()
    assert route_data["is_simulated"] is True
    assert route_data["weather_source"] == "simulated"
    assert "weather_fetched_at" in route_data
    assert "weather_age_minutes" in route_data

    # 2. Register subscriber for /alerts test
    sub_res = client.post("/subscribe", json={
        "name": "Freshness Test Driver",
        "phone_or_email": "+919876543299",
        "segment_id": "seg_08",
        "channel": "SMS"
    })
    sub_data = sub_res.json()
    sub_id = sub_data["subscription_id"]
    token = sub_data["token"]

    # /alerts with simulation
    res_alert_sim = client.get(f"/alerts?user_id={sub_id}&token={token}&simulate_rain_mm=100")
    assert res_alert_sim.status_code == 200
    alert_sim_data = res_alert_sim.json()
    assert alert_sim_data["is_simulated"] is True
    assert alert_sim_data["weather_source"] == "simulated"
    assert alert_sim_data["stale_warning"] is None


# ---------------------------------------------------------------------------
# 7. Alert Safety: Simulated Rainfall Must NEVER Store or Dispatch Alerts
# ---------------------------------------------------------------------------

def test_alert_safety_guard_blocks_simulated_dispatch_and_storage():
    """
    Verifies that calling persist_alert or dispatch_alert with is_simulated=True
    raises AlertSimulationSafetyError and strictly prevents simulated dispatch/storage.
    """
    sample_alert = AlertItem(
        alert_id="ALT-SIM-TEST",
        segment_id="seg_08",
        segment_name="Srinagar to Sirobagarh",
        severity="High",
        risk_score=0.82,
        message="Simulated storm alert",
        channel="SMS",
        issued_at=datetime.now(timezone.utc).isoformat()
    )

    # 1. can_dispatch_or_store returns False when simulated
    assert can_dispatch_or_store(is_simulated=True) is False
    assert can_dispatch_or_store(is_simulated=False) is True

    # 2. persist_alert raises error on simulation
    with pytest.raises(AlertSimulationSafetyError, match="Alerts must NEVER be created, persisted or sent"):
        persist_alert(conn=None, alert=sample_alert, user_id=1, is_simulated=True)

    # 3. dispatch_alert raises error on simulation
    with pytest.raises(AlertSimulationSafetyError, match="Alerts must NEVER be created, persisted or sent"):
        dispatch_alert(alert=sample_alert, recipient_contact="+919876543210", channel="SMS", is_simulated=True)

    # 4. Genuine (non-simulated) alert passes safety validation
    dispatched = dispatch_alert(alert=sample_alert, recipient_contact="+919876543210", channel="SMS", is_simulated=False)
    assert dispatched["status"] == "Dispatched"
    assert dispatched["simulated"] is False
