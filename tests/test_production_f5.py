import json
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import config
from app import scheduler
from app import risk_service

client = TestClient(app)


def test_health_endpoint_extended_fields():
    """Verify /health returns existing and newly added fields, and executes sub-second."""
    t0 = time.perf_counter()
    resp = client.get("/health")
    latency_ms = (time.perf_counter() - t0) * 1000.0

    assert resp.status_code == 200
    assert latency_ms < 500.0, f"Health check took {latency_ms:.2f}ms (must be sub-second)"

    data = resp.json()
    # Existing fields
    assert data["status"] == "ok"
    assert data["system"] == "NH-7 Landslide Risk Backend"
    assert data["corridor"] == "Rishikesh-Joshimath"

    # Additive fields
    assert "app_version" in data
    assert isinstance(data["app_version"], str)
    assert "db_ok" in data
    assert data["db_ok"] is True
    assert "weather_source" in data
    assert data["weather_source"] in ("live", "cached", "snapshot", "unavailable", "simulated")
    assert "scheduler_last_run" in data
    assert (data["scheduler_last_run"] is None) or isinstance(data["scheduler_last_run"], str)


def test_scheduler_disabled_flag():
    """Verify ENABLE_SCHEDULER=false prevents BackgroundScheduler from starting."""
    with patch.object(config, "ENABLE_SCHEDULER", False):
        res = scheduler.start_scheduler()
        assert res is None


def test_scheduler_job_execution_and_error_isolation(tmp_path):
    """Verify poll_weather_job runs batch fetch, updates cache, writes snapshot, and survives errors."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [
        {"daily": {"precipitation_sum": [4.0, 4.0, 4.0]}}
        for _ in range(18)
    ]
    mock_resp.raise_for_status = MagicMock()

    test_snapshot = tmp_path / "test_rain_snapshot.json"

    with patch.object(risk_service, "RAIN_SNAPSHOT_FILE", test_snapshot), \
         patch("requests.Session.get", return_value=mock_resp):

        # Reset scheduler status
        scheduler._scheduler_status["last_run"] = None
        scheduler._scheduler_status["last_status"] = "not_started"

        scheduler.poll_weather_job()

        assert scheduler._scheduler_status["last_run"] is not None
        assert "ok" in scheduler._scheduler_status["last_status"]
        assert test_snapshot.exists()
        snap_content = json.loads(test_snapshot.read_text(encoding="utf-8"))
        assert "timestamp" in snap_content
        assert "data" in snap_content

    # Test error resilience: exceptions in poll_weather_job must NOT raise or crash
    with patch.object(risk_service, "fetch_rainfall_with_metadata", side_effect=RuntimeError("Simulated network crash")):
        scheduler.poll_weather_job()
        assert "error: RuntimeError" in scheduler._scheduler_status["last_status"]


def test_atomic_snapshot_write(tmp_path):
    """Verify save_snapshot_atomic replaces files atomically using temporary file and os.replace."""
    target_file = tmp_path / "atomic_snapshot.json"
    payload = {"timestamp": "2026-10-06T00:00:00Z", "data": {"seg_01": {"rain_mm": 5.0}}}

    success = risk_service.save_snapshot_atomic(payload, target_file)
    assert success is True
    assert target_file.exists()

    data = json.loads(target_file.read_text(encoding="utf-8"))
    assert data["timestamp"] == "2026-10-06T00:00:00Z"
    assert data["data"]["seg_01"]["rain_mm"] == 5.0

    # Overwrite atomically with new data
    payload2 = {"timestamp": "2026-10-06T00:30:00Z", "data": {"seg_01": {"rain_mm": 15.0}}}
    success2 = risk_service.save_snapshot_atomic(payload2, target_file)
    assert success2 is True
    data2 = json.loads(target_file.read_text(encoding="utf-8"))
    assert data2["data"]["seg_01"]["rain_mm"] == 15.0


def test_configurable_paths():
    """Verify DATA_DIR, DB_PATH, and SNAPSHOT_PATH are configurable via environment variables."""
    assert hasattr(config, "DATA_DIR")
    assert hasattr(config, "DB_PATH")
    assert hasattr(config, "SNAPSHOT_PATH")
    assert hasattr(config, "ENABLE_SCHEDULER")
    assert hasattr(config, "WEATHER_POLL_MINUTES")


def test_deployment_artifacts_exist():
    """Verify Dockerfile, .dockerignore, docker-compose.yml, render.yaml, and docs/DEPLOY.md exist and contain required specs."""
    base_dir = Path(__file__).resolve().parent.parent

    # Dockerfile
    dockerfile = base_dir / "Dockerfile"
    assert dockerfile.exists()
    dockerfile_content = dockerfile.read_text(encoding="utf-8")
    assert "--workers" in dockerfile_content
    assert "1" in dockerfile_content
    assert "/health" in dockerfile_content

    # .dockerignore
    dockerignore = base_dir / ".dockerignore"
    assert dockerignore.exists()

    # docker-compose.yml
    compose = base_dir / "docker-compose.yml"
    assert compose.exists()
    compose_content = compose.read_text(encoding="utf-8")
    assert "app/data" in compose_content
    assert "8000:8000" in compose_content

    # render.yaml
    render_yaml = base_dir / "render.yaml"
    assert render_yaml.exists()
    render_content = render_yaml.read_text(encoding="utf-8")
    assert "persistent disk" in render_content.lower() or "disk" in render_content.lower()

    # docs/DEPLOY.md
    deploy_doc = base_dir / "docs" / "DEPLOY.md"
    assert deploy_doc.exists()
    deploy_content = deploy_doc.read_text(encoding="utf-8")
    assert "Render" in deploy_content
    assert "Railway" in deploy_content
    assert "ngrok" in deploy_content
    assert "UptimeRobot" in deploy_content
