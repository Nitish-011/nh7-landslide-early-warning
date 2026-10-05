import csv
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app import config

client = TestClient(app)


def test_consequence_artifacts_exist_and_conform():
    """Verify segment_consequence.csv exists, has 18 rows, correct columns, and blank alternate route."""
    csv_path = config.CONSEQUENCE_CSV_PATH
    assert csv_path.exists(), f"Expected {csv_path} to exist"

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 18, f"Expected 18 segments, got {len(reader)}"
    expected_cols = [
        "segment_id",
        "nearest_town",
        "nearest_town_km",
        "nearest_hospital",
        "nearest_hospital_km",
        "lodging_count_5km",
        "has_alternate_route",
        "traffic_index",
    ]
    for col in expected_cols:
        assert col in reader[0], f"Column '{col}' missing from consequence CSV"

    # Verify has_alternate_route is blank per Rule 5 (never invent unverified data)
    for row in reader:
        assert row["has_alternate_route"] == "", "has_alternate_route must remain blank for manual verification"
        assert int(row["traffic_index"]) == 3, "default traffic_index must be 3"


def test_osm_cache_exists():
    """Verify data/osm_cache.json exists and contains Overpass POI elements."""
    cache_path = config.DATA_DIR / "osm_cache.json"
    assert cache_path.exists(), "osm_cache.json must exist"
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    assert "elements" in data
    assert len(data["elements"]) > 100


def test_risk_map_includes_consequence_fields():
    """Verify /risk-map segments include indicative consequence and priority fields."""
    resp = client.get("/risk-map")
    assert resp.status_code == 200
    data = resp.json()

    for seg in data["segments"]:
        assert "consequence_score" in seg
        assert "priority_score" in seg
        assert "nearest_hospital_km" in seg
        assert "nearest_town" in seg
        if seg.get("consequence_score") is not None:
            assert 0.0 <= seg["consequence_score"] <= 1.0
            assert 0.0 <= seg["priority_score"] <= 1.0


def test_priority_list_endpoint():
    """Verify GET /priority-list returns ranked segments with recommended action templates."""
    resp = client.get("/priority-list")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_segments"] == 18
    assert data["status"] == "indicative"
    assert "disclaimer" in data
    assert "indicative" in data["disclaimer"].lower()

    segs = data["segments"]
    assert len(segs) == 18

    # Verify descending sort by priority_score
    for i in range(len(segs) - 1):
        assert segs[i]["priority_score"] >= segs[i + 1]["priority_score"], (
            f"Segments not properly sorted: seg[{i}] priority {segs[i]['priority_score']} < seg[{i+1}] priority {segs[i+1]['priority_score']}"
        )
        assert segs[i]["rank"] == i + 1

    # Verify recommended_action template text
    for s in segs:
        assert s["recommended_action"], "recommended_action must not be empty"
        assert len(s["recommended_action"]) > 20
        # Priority score math check
        expected_priority = round(s["risk_index"] * s["consequence_score"], 2)
        assert abs(s["priority_score"] - expected_priority) <= 0.02


def test_priority_list_simulation():
    """Verify GET /priority-list?simulate_rain_mm=100 reflects simulation state."""
    resp = client.get("/priority-list?simulate_rain_mm=100")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_simulated"] is True
    assert len(data["segments"]) == 18


def test_priority_list_graceful_degradation_when_csv_missing(tmp_path, monkeypatch):
    """Verify /priority-list degrades gracefully to neutral baseline when CSV is missing."""
    missing_path = tmp_path / "non_existent_consequence.csv"
    monkeypatch.setattr(config, "CONSEQUENCE_CSV_PATH", missing_path)

    # Force clear cache
    from app import consequence_service
    consequence_service._consequence_cache["data"] = None

    resp = client.get("/priority-list")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_segments"] == 18
    assert "degraded mode" in data["disclaimer"].lower()

    for s in data["segments"]:
        assert s["consequence_score"] == 0.50
        assert s["priority_score"] == round(s["risk_index"] * 0.50, 2)
        assert "degraded" in s["recommended_action"].lower() or "indicative" in s["recommended_action"].lower()
