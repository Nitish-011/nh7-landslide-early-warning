import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app import config

client = TestClient(app)


def test_backtest_events_template_empty_rule5():
    """Verify data/backtest_events.csv exists as an empty template per Rule 5 (no fabricated data)."""
    events_file = config.DATA_DIR / "backtest_events.csv"
    assert events_file.exists(), "data/backtest_events.csv must exist"
    
    lines = [line.strip() for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1, f"Expected header only, found {len(lines)} lines"
    assert lines[0] == "date,segment_id,event_type,source_url,notes"


def test_backtest_artifacts_exist_and_documented():
    """Verify outputs/backtest_report.md and outputs/backtest_summary.json exist with caveats."""
    summary_file = config.OUTPUTS_DIR / "backtest_summary.json"
    report_file = config.OUTPUTS_DIR / "backtest_report.md"

    assert summary_file.exists(), "outputs/backtest_summary.json must exist"
    assert report_file.exists(), "outputs/backtest_report.md must exist"

    summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
    assert summary_data["status"] == "completed"
    assert summary_data["k_rain_production"] == 0.4
    assert "k_rain_optimal" in summary_data
    assert "metrics" in summary_data
    assert "caveats" in summary_data
    assert len(summary_data["caveats"]) >= 3

    # Check caveat mentions in markdown report
    report_text = report_file.read_text(encoding="utf-8")
    assert "coarse" in report_text.lower()
    assert "cloudburst" in report_text.lower()
    assert "K_RAIN" in report_text or "k_rain" in report_text.lower()


def test_time_machine_api_flag_disabled_by_default(monkeypatch):
    """When BACKTEST_ENABLED=False, /risk-map?as_of=... and /backtest-summary return HTTP 400."""
    monkeypatch.setattr(config, "BACKTEST_ENABLED", False)

    # Historical replay request
    resp = client.get("/risk-map?as_of=2023-08-14")
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"].lower()

    # Backtest summary request
    resp2 = client.get("/backtest-summary")
    assert resp2.status_code == 400
    assert "disabled" in resp2.json()["detail"].lower()


def test_time_machine_api_invalid_date(monkeypatch):
    """When BACKTEST_ENABLED=True, invalid date returns HTTP 400."""
    monkeypatch.setattr(config, "BACKTEST_ENABLED", True)

    resp = client.get("/risk-map?as_of=not-a-date")
    assert resp.status_code == 400
    assert "Invalid date format" in resp.json()["detail"]


def test_time_machine_api_replay_success(monkeypatch):
    """When BACKTEST_ENABLED=True, valid date returns replay risk map with metadata."""
    monkeypatch.setattr(config, "BACKTEST_ENABLED", True)

    # Mock open-meteo archive API to guarantee 100% offline execution
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "daily": {
            "precipitation_sum": [12.5, 34.0, 5.0]
        }
    }
    mock_response.raise_for_status = MagicMock()

    with patch("requests.Session.get", return_value=mock_response):
        resp = client.get("/risk-map?as_of=2023-08-14")
        assert resp.status_code == 200
        data = resp.json()

        assert data["mode"] == "replay"
        assert data["as_of"] == "2023-08-14"
        assert data["weather_source"] == "archive_replay"
        assert data["is_simulated"] is False
        assert data["total_segments"] == 18
        assert len(data["segments"]) == 18

        # Each segment has risk scores and risk indices
        for s in data["segments"]:
            assert 0.0 <= s["risk_score"] <= 1.0
            assert 0.0 <= s["risk_index"] <= 1.0
            assert s["risk_level"] in ("Low", "Moderate", "High", "Very High")


def test_backtest_summary_endpoint(monkeypatch):
    """When BACKTEST_ENABLED=True, /backtest-summary returns the computed report."""
    monkeypatch.setattr(config, "BACKTEST_ENABLED", True)

    resp = client.get("/backtest-summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "completed"
    assert data["k_rain_production"] == 0.4
    assert data["k_rain_optimal"] > 0
    assert "metrics" in data
    assert "caveats" in data
    assert isinstance(data["caveats"], list)
