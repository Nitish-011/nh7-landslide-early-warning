"""
tests/test_model_info_f3.py - Verification suite for Task F3
Tests:
1. GET /model-info returns all required fields and parsed metrics from outputs/validation_report.md
2. Presence of risk_index (0.0 - 1.0) on /risk-map, /route-risk, and /alerts responses
3. Named constants K_RAIN, DRY_CAP_MM, RISK_LEVEL_THRESHOLDS in app/config.py
4. Geographical scope and terminology consistency
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
import app.config as config
from app.model_info import get_model_info_payload, parse_validation_report

client = TestClient(app)

MOCK_RAIN = {
    f"seg_{i:02d}": {"rain_mm": 20.0, "status": "ok"}
    for i in range(1, 19)
}

@pytest.fixture(autouse=True)
def mock_weather():
    with patch("app.risk_service.fetch_rainfall", return_value=MOCK_RAIN):
        yield


def test_config_exposed_constants():
    """Requirement 1: K_RAIN, DRY_CAP_MM and risk-level thresholds exposed as named constants."""
    assert hasattr(config, "K_RAIN"), "K_RAIN missing from app/config.py"
    assert config.K_RAIN == 0.4
    assert hasattr(config, "DRY_CAP_MM"), "DRY_CAP_MM missing from app/config.py"
    assert config.DRY_CAP_MM == 25.0
    assert hasattr(config, "RISK_LEVEL_THRESHOLDS"), "RISK_LEVEL_THRESHOLDS missing from app/config.py"
    assert len(config.RISK_LEVEL_THRESHOLDS) == 4
    assert config.RISK_LEVEL_THRESHOLDS[0] == {"threshold": 0.75, "level": "Very High"}
    assert config.RISK_LEVEL_THRESHOLDS[1] == {"threshold": 0.50, "level": "High"}
    assert config.RISK_LEVEL_THRESHOLDS[2] == {"threshold": 0.25, "level": "Moderate"}
    assert config.RISK_LEVEL_THRESHOLDS[3] == {"threshold": 0.00, "level": "Low"}


def test_validation_report_parser():
    """Requirement 2: Parsed metrics from outputs/validation_report.md match exactly."""
    metrics = parse_validation_report()
    assert metrics["positives"] == 309
    assert metrics["negatives"] == 927
    assert metrics["spearman_rho"] == 0.653
    assert metrics["spearman_pval"] == 0.0033
    assert metrics["pooled_auc"] == 0.767
    assert metrics["pooled_auc_ci"] == [0.680, 0.802]
    assert metrics["block_auc_mean"] == 0.664
    assert metrics["block_auc_ci"] == [0.630, 0.701]
    assert metrics["average_precision"] == 0.533
    assert metrics["top_20_capture"] == 0.430
    assert "dem_slope_deg" in metrics["permutation_importances"]
    assert metrics["permutation_importances"]["dem_slope_deg"] == 0.0523


def test_get_model_info_endpoint():
    """Requirement 2: GET /model-info returns complete transparency payload."""
    resp = client.get("/model-info")
    assert resp.status_code == 200
    data = resp.json()

    # Core required fields
    assert "model_version" in data
    assert "features_used" in data
    assert len(data["features_used"]) == 8
    assert "coefficients" in data
    assert "dem_slope_deg" in data["coefficients"]
    assert "training_sample_sizes" in data
    assert data["training_sample_sizes"]["presence_count"] == 309
    assert data["training_sample_sizes"]["absence_count"] == 927
    assert "validation_metrics" in data
    assert data["validation_metrics"]["pooled_auc"] == 0.767
    assert "thresholds" in data
    assert len(data["thresholds"]) == 4
    assert "k" in data
    assert data["k"]["k_rain"] == 0.4
    assert "dry_cap" in data
    assert data["dry_cap"] == 25.0
    assert "limitations" in data
    assert isinstance(data["limitations"], list)
    assert len(data["limitations"]) >= 5
    assert "data_sources" in data
    assert "inventory" in data["data_sources"]
    assert "Mey" in data["data_sources"]["inventory"]
    assert "scope" in data
    assert data["scope"] == "Rishikesh to Joshimath, 247.37 km"


def test_risk_index_on_risk_map():
    """Requirement 3: risk_index (0-1) is present alongside legacy risk_score on /risk-map."""
    resp = client.get("/risk-map")
    assert resp.status_code == 200
    data = resp.json()
    for seg in data["segments"]:
        assert "risk_index" in seg, f"Segment {seg['id']} missing risk_index"
        assert seg["risk_index"] is not None
        assert 0.0 <= seg["risk_index"] <= 1.0
        assert seg["risk_index"] == seg["risk_score"]


def test_risk_index_on_route_risk():
    """Requirement 3: risk_index (0-1) is present on /route-risk for segments and top-level."""
    resp = client.get("/route-risk?from_segment=seg_01&to_segment=seg_05&date=2026-10-06")
    assert resp.status_code == 200
    data = resp.json()
    assert "risk_index" in data, "RouteRiskResponse missing top-level risk_index"
    assert data["risk_index"] == data["average_risk_score"]

    for seg in data["segments"]:
        assert "risk_index" in seg, f"Route segment {seg['id']} missing risk_index"
        assert seg["risk_index"] == seg["risk_score"]


def test_risk_index_on_alerts():
    """Requirement 3: risk_index (0-1) is present on /alerts items."""
    # Create subscription
    sub_payload = {
        "name": "F3 Test User",
        "phone_or_email": "+91-9876500000",
        "segment_id": "seg_05",
        "channel": "SMS"
    }
    sub_res = client.post("/subscribe", json=sub_payload)
    assert sub_res.status_code == 201
    sub_data = sub_res.json()
    user_id = sub_data["subscription_id"]
    token = sub_data["token"]

    resp = client.get(f"/alerts?user_id={user_id}&token={token}")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["alerts"]:
        assert "risk_index" in item, "Alert item missing risk_index"
        assert item["risk_index"] == item["risk_score"]


def test_openapi_schema_contains_relative_risk_index():
    """Requirement 3: OpenAPI schema replaces 'probability' with 'relative risk index'."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    schemas = schema.get("components", {}).get("schemas", {})
    
    # Check SegmentResponse risk_index field
    seg_resp = schemas.get("SegmentResponse", {})
    assert "risk_index" in seg_resp.get("properties", {})
    desc = seg_resp["properties"]["risk_index"].get("description", "")
    assert "relative risk index" in desc.lower()


def test_scope_does_not_claim_badrinath():
    """Requirement 4: Corridor scope is Rishikesh to Joshimath, 247.37 km without Badrinath."""
    info = get_model_info_payload()
    assert "Badrinath" not in info["scope"]
    assert "247.37 km" in info["scope"]
    assert "Joshimath" in info["scope"]
