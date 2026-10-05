import pytest
import secrets
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app import config
from app.database import get_db, init_db
from app.limiter import limiter
import app.routes.subscriptions as subs_mod

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_state():
    """Resets database and rate limiter state before every test."""
    init_db()
    with get_db() as db:
        db.execute("DELETE FROM field_reports")
        db.execute("DELETE FROM subscriptions WHERE id > 4")
    limiter.reset()


# ---------------------------------------------------------------------------
# 1. Admin API Key & Route Protection Tests
# ---------------------------------------------------------------------------

def test_admin_route_in_dev_allows_localhost_when_key_unset(monkeypatch):
    """In dev environment when ADMIN_API_KEY is unset, localhost requests are allowed."""
    monkeypatch.setattr(config, "ENV", "development")
    monkeypatch.setattr(config, "ADMIN_API_KEY", "")

    # Create a dummy report to validate
    report_res = client.post("/field-report", json={
        "lat": 30.12,
        "lng": 78.32,
        "reporter_name": "Test Localhost Admin",
        "description": "Dev localhost test report"
    })
    assert report_res.status_code == 201
    report_id = report_res.json()["report_id"]

    # Request from testclient (treated as localhost) with no key
    res = client.post("/admin/validate-report", json={
        "report_id": report_id,
        "decision": "Validated",
        "notes": "Approved in dev"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "Validated"


def test_admin_route_rejects_non_localhost_when_key_unset(monkeypatch):
    """In dev environment when ADMIN_API_KEY is unset, non-localhost request is rejected with 401."""
    monkeypatch.setattr(config, "ENV", "development")
    monkeypatch.setattr(config, "ADMIN_API_KEY", "")

    res = client.post(
        "/admin/validate-report",
        json={"report_id": 1, "decision": "Validated"},
        headers={"x-forwarded-for": "198.51.100.24"}
    )
    assert res.status_code == 401
    assert "Admin access requires X-API-Key" in res.json()["detail"]


def test_admin_route_with_configured_key(monkeypatch):
    """When ADMIN_API_KEY is set, valid key returns 200, invalid or missing returns 401."""
    monkeypatch.setattr(config, "ENV", "development")
    monkeypatch.setattr(config, "ADMIN_API_KEY", "super-secret-admin-token-12345")

    # Create report to validate
    report_res = client.post("/field-report", json={
        "lat": 30.12,
        "lng": 78.32,
        "reporter_name": "Admin Test Subject",
        "description": "Report for admin auth check"
    })
    assert report_res.status_code == 201
    report_id = report_res.json()["report_id"]

    # 1. Missing header -> 401
    res_missing = client.post(
        "/admin/validate-report",
        json={"report_id": report_id, "decision": "Validated"}
    )
    assert res_missing.status_code == 401
    assert "Invalid or missing" in res_missing.json()["detail"]

    # 2. Wrong header -> 401
    res_wrong = client.post(
        "/admin/validate-report",
        json={"report_id": report_id, "decision": "Validated"},
        headers={"X-API-Key": "wrong-token"}
    )
    assert res_wrong.status_code == 401
    assert "Invalid or missing" in res_wrong.json()["detail"]

    # 3. Correct header -> 200
    res_correct = client.post(
        "/admin/validate-report",
        json={"report_id": report_id, "decision": "Validated", "notes": "Authorized validation"},
        headers={"X-API-Key": "super-secret-admin-token-12345"}
    )
    assert res_correct.status_code == 200


def test_production_refuses_to_start_without_admin_api_key(monkeypatch):
    """If ENV=production and ADMIN_API_KEY is unset, startup Lifespan raises RuntimeError."""
    monkeypatch.setattr(config, "ENV", "production")
    monkeypatch.setattr(config, "ADMIN_API_KEY", "")

    # Attempting to run lifespan context in production without key must fail
    with pytest.raises(RuntimeError, match="ADMIN_API_KEY must be set in production mode"):
        with TestClient(app) as _:
            pass


# ---------------------------------------------------------------------------
# 2. Field Report Validation (3km corridor, HTML stripping, photo_url, 409 duplicate)
# ---------------------------------------------------------------------------

def test_field_report_corridor_distance_validation():
    """Points within 3km of NH-7 are accepted; points further are rejected with 422."""
    # Point on NH-7 corridor (near Rishikesh/Shivpuri)
    res_valid = client.post("/field-report", json={
        "lat": 30.135,
        "lng": 78.385,
        "reporter_name": "Valid Route Observer",
        "description": "Loose gravel on slope"
    })
    assert res_valid.status_code == 201

    # Point far away from corridor (Delhi coordinates: ~28.61, 77.20)
    res_far = client.post("/field-report", json={
        "lat": 28.6139,
        "lng": 77.2090,
        "reporter_name": "Delhi User",
        "description": "Pothole in Delhi"
    })
    assert res_far.status_code == 422
    assert "beyond 3.0 km of the NH-7 highway corridor" in res_far.json()["detail"]


def test_field_report_html_stripping_and_length():
    """HTML tags are stripped from description; descriptions over 500 chars fail 422."""
    # HTML stripped test
    res_html = client.post("/field-report", json={
        "lat": 30.20,
        "lng": 78.60,
        "reporter_name": "HTML Tester",
        "description": "<script>alert('xss')</script><b>Major boulder fall</b> blocking lane."
    })
    assert res_html.status_code == 201
    report_id = res_html.json()["report_id"]

    # Verify stored in DB without HTML
    with get_db() as db:
        row = db.execute("SELECT description FROM field_reports WHERE id = ?", (report_id,)).fetchone()
        assert row is not None
        assert "<script>" not in row["description"]
        assert "<b>" not in row["description"]
        assert "Major boulder fall" in row["description"]

    # Exceeding 500 characters
    long_desc = "A" * 501
    res_long = client.post("/field-report", json={
        "lat": 30.20,
        "lng": 78.60,
        "reporter_name": "Length Tester",
        "description": long_desc
    })
    assert res_long.status_code == 422


def test_field_report_photo_url_validation():
    """photo_url must be http/https and max 500 chars."""
    # Invalid scheme (javascript:)
    res_js = client.post("/field-report", json={
        "lat": 30.20,
        "lng": 78.60,
        "reporter_name": "Photo Tester",
        "description": "Hazard with bad scheme",
        "photo_url": "javascript:alert(1)"
    })
    assert res_js.status_code == 422

    # Invalid non-http scheme (ftp://)
    res_ftp = client.post("/field-report", json={
        "lat": 30.20,
        "lng": 78.60,
        "reporter_name": "Photo Tester",
        "description": "Hazard with ftp",
        "photo_url": "ftp://example.com/img.jpg"
    })
    assert res_ftp.status_code == 422

    # Valid https URL
    res_valid = client.post("/field-report", json={
        "lat": 30.20,
        "lng": 78.60,
        "reporter_name": "Photo Tester",
        "description": "Hazard with valid photo",
        "photo_url": "https://example.com/images/landslide1.jpg"
    })
    assert res_valid.status_code == 201


def test_field_report_duplicate_within_10_minutes_returns_409():
    """Same IP and same coordinate within 10 minutes returns 409 conflict."""
    coord_lat = 30.2851
    coord_lng = 78.9812

    # First report succeeds
    res1 = client.post(
        "/field-report",
        json={
            "lat": coord_lat,
            "lng": coord_lng,
            "reporter_name": "Patrol Officer",
            "description": "First report on slip"
        },
        headers={"x-forwarded-for": "203.0.113.50"}
    )
    assert res1.status_code == 201

    # Second report at exact same coordinates within 10 min from same IP -> 409
    res2 = client.post(
        "/field-report",
        json={
            "lat": coord_lat,
            "lng": coord_lng,
            "reporter_name": "Patrol Officer",
            "description": "Duplicate report on slip"
        },
        headers={"x-forwarded-for": "203.0.113.50"}
    )
    assert res2.status_code == 409
    assert "Duplicate report" in res2.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Subscription Validation, Consent & Contact Masking Tests
# ---------------------------------------------------------------------------

def test_subscribe_phone_normalization_and_email():
    """10-digit Indian phone normalized to +91; email accepted; invalid rejected."""
    # 10 digit Indian number without prefix -> normalized to +919876543210
    res_phone = client.post("/subscribe", json={
        "name": "Ramesh Local",
        "phone_or_email": "9876543210",
        "segment_id": "seg_08",
        "channel": "SMS"
    })
    assert res_phone.status_code == 201

    # International E.164 phone
    res_e164 = client.post("/subscribe", json={
        "name": "International Driver",
        "phone_or_email": "+919876543211",
        "segment_id": "seg_08",
        "channel": "SMS"
    })
    assert res_e164.status_code == 201

    # Email
    res_email = client.post("/subscribe", json={
        "name": "Email Subscriber",
        "phone_or_email": "traveller@nh7safety.org",
        "segment_id": "seg_01",
        "channel": "Email"
    })
    assert res_email.status_code == 201

    # Invalid contact format -> 422
    res_bad = client.post("/subscribe", json={
        "name": "Bad Contact",
        "phone_or_email": "not-a-valid-contact",
        "segment_id": "seg_01",
        "channel": "SMS"
    })
    assert res_bad.status_code == 422


def test_subscribe_consent_flag_default_and_explicit():
    """Consent defaults to True if omitted; persists False if explicitly set."""
    # Omitted consent -> default True
    res_default = client.post("/subscribe", json={
        "name": "Default Consent User",
        "phone_or_email": "user1@example.com",
        "segment_id": "seg_02",
        "channel": "Email"
    })
    assert res_default.status_code == 201
    sub_id_default = res_default.json()["subscription_id"]

    with get_db() as db:
        row = db.execute("SELECT consent FROM subscriptions WHERE id = ?", (sub_id_default,)).fetchone()
        assert row["consent"] == 1

    # Explicit consent = False
    res_no_consent = client.post("/subscribe", json={
        "name": "No Consent User",
        "phone_or_email": "user2@example.com",
        "segment_id": "seg_03",
        "channel": "Email",
        "consent": False
    })
    assert res_no_consent.status_code == 201
    sub_id_no_consent = res_no_consent.json()["subscription_id"]

    with get_db() as db:
        row = db.execute("SELECT consent FROM subscriptions WHERE id = ?", (sub_id_no_consent,)).fetchone()
        assert row["consent"] == 0


def test_contact_masking_helper():
    """Verify phone and email masking helper produces expected masked values."""
    assert subs_mod.mask_contact("+919876543210") == "+91******3210"
    assert subs_mod.mask_contact("alice@nh7corridor.in") == "a***e@nh7corridor.in"
    assert subs_mod.mask_contact("a@b.com") == "a*@b.com"
    assert subs_mod.mask_contact("123") == "123"


# ---------------------------------------------------------------------------
# 4. Rate Limiting Tests (Slowapi JSON 429)
# ---------------------------------------------------------------------------

def test_rate_limit_field_report_per_ip():
    """Exceeding 5 field reports/min from the same IP returns JSON 429."""
    client_ip = "192.0.2.99"
    headers = {"x-forwarded-for": client_ip}

    # First 5 succeed
    for i in range(5):
        res = client.post(
            "/field-report",
            json={
                "lat": 30.13 + (i * 0.002),
                "lng": 78.38 + (i * 0.002),
                "reporter_name": f"Rate Limit Tester {i}",
                "description": f"Incident report {i}"
            },
            headers=headers
        )
        assert res.status_code == 201

    # 6th request must trigger rate limit 429
    res_limited = client.post(
        "/field-report",
        json={
            "lat": 30.15,
            "lng": 78.40,
            "reporter_name": "Rate Limit Exceeded",
            "description": "Should be throttled"
        },
        headers=headers
    )
    assert res_limited.status_code == 429
    data = res_limited.json()
    assert "detail" in data
    assert "Rate limit exceeded" in data["detail"]


def test_rate_limit_subscribe_per_ip():
    """Exceeding 5 subscriptions/min from the same IP returns JSON 429."""
    client_ip = "192.0.2.100"
    headers = {"x-forwarded-for": client_ip}

    for i in range(5):
        res = client.post(
            "/subscribe",
            json={
                "name": f"Subscriber {i}",
                "phone_or_email": f"sub{i}@example.com",
                "segment_id": "seg_01",
                "channel": "SMS"
            },
            headers=headers
        )
        assert res.status_code == 201

    # 6th request triggers rate limit 429
    res_limited = client.post(
        "/subscribe",
        json={
            "name": "Subscriber 6",
            "phone_or_email": "sub6@example.com",
            "segment_id": "seg_01",
            "channel": "SMS"
        },
        headers=headers
    )
    assert res_limited.status_code == 429
    assert "Rate limit exceeded" in res_limited.json()["detail"]
