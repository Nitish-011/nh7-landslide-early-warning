import gzip
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import config

client = TestClient(app)


def test_offline_pack_schema_and_segments():
    """Verify GET /offline-pack returns complete schema, all 18 segments, and bilingual advisories."""
    res = client.get("/offline-pack")
    assert res.status_code == 200, res.text
    data = res.json()

    # Top-level required fields
    assert "version" in data
    assert len(data["version"]) >= 8
    assert "generated_at" in data
    assert "corridor" in data
    assert data["total_segments"] == 18
    assert "emergency_contacts" in data
    assert "segments" in data
    assert len(data["segments"]) == 18

    # Segment fields
    for seg in data["segments"]:
        assert seg["id"].startswith("seg_")
        assert len(seg["name"]) > 0
        assert isinstance(seg["simplified_polyline"], list)
        assert len(seg["simplified_polyline"]) >= 2
        for pt in seg["simplified_polyline"]:
            assert len(pt) == 2
            assert 28.0 <= pt[0] <= 32.0  # Lat within Uttarakhand region
            assert 77.0 <= pt[1] <= 81.0  # Lng within Uttarakhand region

        assert seg["current_risk_level"] in ("Low", "Moderate", "High", "Very High")
        assert seg["terrain_risk_level"] in ("Low", "Moderate", "High", "Very High")
        assert len(seg["advisory_en"]) > 0
        assert len(seg["advisory_hi"]) > 0
        # Hospital field present (either string or None)
        assert "nearest_hospital" in seg

    # Check known hospital on seg_01
    seg_01 = next(s for s in data["segments"] if s["id"] == "seg_01")
    assert seg_01["nearest_hospital"] == "Ayurveda Center"


def test_offline_pack_emergency_contacts_default():
    """Verify default contacts list contains 112 and no invented phone numbers."""
    res = client.get("/offline-pack")
    assert res.status_code == 200
    data = res.json()

    contacts = data["emergency_contacts"]
    assert len(contacts) >= 1

    # National Emergency 112 must be present
    helpline_112 = next((c for c in contacts if c.get("number") == "112"), None)
    assert helpline_112 is not None, "National helpline 112 must be included by default"

    # Other contacts must NOT have invented numbers
    other_contacts = [c for c in contacts if c.get("number") != "112"]
    for c in other_contacts:
        assert c.get("number") == "", f"Contact {c['name']} must have blank number, found: {c.get('number')}"


def test_offline_pack_size_budget():
    """Verify offline pack is strictly under the 100 KB limit (both uncompressed and compressed)."""
    res = client.get("/offline-pack")
    assert res.status_code == 200
    raw_size_bytes = len(res.content)
    assert raw_size_bytes < 100 * 1024, f"Payload {raw_size_bytes} exceeds 100 KB limit!"
    # Actual payload is ~16 KB
    assert raw_size_bytes < 50 * 1024, f"Expected compact payload < 50 KB, got {raw_size_bytes}"


def test_offline_pack_etag_and_304_not_modified():
    """Verify ETag header generation and conditional 304 Not Modified requests."""
    # 1. Initial GET
    res = client.get("/offline-pack")
    assert res.status_code == 200
    etag = res.headers.get("etag")
    assert etag is not None
    assert len(etag) > 0

    # 2. Conditional GET with matching quoted ETag
    res_304 = client.get("/offline-pack", headers={"If-None-Match": etag})
    assert res_304.status_code == 304
    assert len(res_304.content) == 0, "304 body must be 0 bytes"
    assert res_304.headers.get("etag") == etag

    # 3. Conditional GET with unquoted ETag
    clean_etag = etag.strip('"')
    res_304_unquoted = client.get("/offline-pack", headers={"If-None-Match": clean_etag})
    assert res_304_unquoted.status_code == 304
    assert len(res_304_unquoted.content) == 0

    # 4. Conditional GET with weak ETag prefix
    res_304_weak = client.get("/offline-pack", headers={"If-None-Match": f"W/{etag}"})
    assert res_304_weak.status_code == 304

    # 5. Outdated / mismatched ETag returns fresh 200
    res_mismatch = client.get("/offline-pack", headers={"If-None-Match": '"outdated_version_123"'})
    assert res_mismatch.status_code == 200
    assert len(res_mismatch.content) > 0


def test_offline_pack_gzip_compression():
    """Verify GZip compression is active when client sends Accept-Encoding: gzip."""
    res = client.get("/offline-pack", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200
    assert "gzip" in res.headers.get("content-encoding", "")


def test_offline_pack_simulated_rain():
    """Verify simulate_rain_mm alters risk levels and generates distinct version hash."""
    res_normal = client.get("/offline-pack")
    res_sim = client.get("/offline-pack?simulate_rain_mm=85")

    assert res_normal.status_code == 200
    assert res_sim.status_code == 200

    normal_data = res_normal.json()
    sim_data = res_sim.json()

    assert normal_data["version"] != sim_data["version"], "Simulated rain must change version hash"

    # Count High / Very High segments in simulated rain
    high_sim_count = sum(1 for s in sim_data["segments"] if s["current_risk_level"] in ("High", "Very High"))
    assert high_sim_count >= 10, "Heavy rain simulation must escalate risk levels"


def test_service_worker_and_manifest():
    """Verify PWA manifest and service worker endpoints, ensuring map tiles are not cached."""
    # 1. Manifest
    res_m = client.get("/manifest.json")
    assert res_m.status_code == 200
    manifest = res_m.json()
    assert manifest["name"] == "NH-7 Landslide Early Warning System"
    assert manifest["start_url"] == "/"

    # 2. Service Worker
    res_sw = client.get("/sw.js")
    assert res_sw.status_code == 200
    sw_text = res_sw.text
    assert "/offline-pack" in sw_text
    # Explicit tile exclusion rule
    assert "isMapTileRequest" in sw_text
    assert "tile.openstreetmap.org" in sw_text
    assert "Do not cache map tiles" in sw_text or "never store in cache" in sw_text
