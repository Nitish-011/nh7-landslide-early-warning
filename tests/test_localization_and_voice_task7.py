"""
tests/test_localization_and_voice_task7.py - Unit and integration tests for Task 7 (Localization and Voice).

Verifies:
1. app/i18n string tables (English & Hindi), transliterations, native review comments, and templated drivers.
2. /risk-map, /route-risk, and /alerts with optional lang=hi and default lang=en.
3. Preservation of English in *_en fields when lang=hi, and untouched default behavior when lang is absent.
4. GET /voice-alert generating audio/mpeg with mocked gTTS and caching in data/tts_cache/.
5. Graceful offline fallback returning JSON {text, tts: 'browser'} when gTTS fails.
6. Contract tests compatibility (lang absent).
"""

import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import config, i18n

client = TestClient(app)

MOCK_RAIN = {
    f"seg_{i:02d}": {"rain_mm": 25.0, "status": "ok"}
    for i in range(1, 19)
}


@pytest.fixture(autouse=True)
def mock_weather_and_reset():
    """Ensure weather fetch never hits live network in tests."""
    with patch("app.risk_service.fetch_rainfall", side_effect=lambda segs, session=None, simulate_rain_mm=None: (
        {s["id"]: {"rain_mm": float(simulate_rain_mm), "status": "simulated"} for s in segs}
        if simulate_rain_mm is not None
        else {s["id"]: {"rain_mm": 25.0, "status": "ok"} for s in segs}
    )):
        yield


def test_i18n_module_string_tables_and_native_review_comments():
    """Verifies i18n dictionaries, transliterations, and presence of '# NEEDS NATIVE REVIEW' comments."""
    # 1. Risk levels
    assert i18n.RISK_LEVEL_NAMES_EN["High"] == "High"
    assert i18n.RISK_LEVEL_NAMES_HI["High"] == "उच्च"
    assert i18n.RISK_LEVEL_NAMES_HI["Very High"] == "अत्यधिक"
    assert i18n.RISK_LEVEL_NAMES_HI["Moderate"] == "मध्यम"
    assert i18n.RISK_LEVEL_NAMES_HI["Low"] == "कम"

    # 2. Recommendation actions
    assert i18n.ACTION_CODES_HI["LOW RISK – proceed with caution"] == "कम जोखिम – सावधानी बरतें"
    assert i18n.ACTION_CODES_HI["CAUTION"] == "सावधानी बरतें"
    assert i18n.ACTION_CODES_HI["DELAY"] == "यात्रा में विलंब करें"
    assert i18n.ACTION_CODES_HI["AVOID"] == "यात्रा से बचें"

    # 3. Transliterated segment names
    assert len(i18n.SEGMENT_TRANSLITERATIONS_HI) == 18
    assert i18n.SEGMENT_TRANSLITERATIONS_HI["seg_01"] == "ऋषिकेश से शिवपुरी"
    assert i18n.SEGMENT_TRANSLITERATIONS_HI["seg_08"] == "श्रीनगर से सिरोबगड़"
    assert i18n.SEGMENT_TRANSLITERATIONS_HI["seg_18"] == "हेलांग से जोशीमठ"

    # 4. Templated driver
    # A) Numerical slope & relief
    num_driver = i18n.format_slope_relief_driver_hi(slope_deg=28.5, relief_m=340.0)
    assert "28.5°" in num_driver
    assert "340 मी" in num_driver
    assert "ढलान" in num_driver

    # B) Regex parsed explanation string
    parsed_driver = i18n.localize_main_driver("unusual slope for this road (low, z=-1.0)", lang="hi")
    assert parsed_driver == "इस मार्ग के लिए असामान्य ढलान (कम, z=-1.0)"

    parsed_driver2 = i18n.localize_main_driver("unusual elevation for this road (high, z=+1.8)", lang="hi")
    assert parsed_driver2 == "इस मार्ग के लिए असामान्य ऊंचाई (अधिक, z=+1.8)"

    # 5. Native review comment requirement
    i18n_path = Path(__file__).resolve().parent.parent / "app" / "i18n.py"
    lines = i18n_path.read_text(encoding="utf-8").splitlines()
    hi_lines_with_comment = [
        line for line in lines
        if any("\u0900" <= ch <= "\u097F" for ch in line)
        and "# NEEDS NATIVE REVIEW" in line
    ]
    # Verify significant number of lines containing Devanagari carry '# NEEDS NATIVE REVIEW'
    assert len(hi_lines_with_comment) >= 30, f"Found only {len(hi_lines_with_comment)} commented lines"


def test_risk_map_localization():
    """Tests GET /risk-map with lang=hi vs default lang=en."""
    # 1. Default (lang absent -> en)
    res_en = client.get("/risk-map")
    assert res_en.status_code == 200
    data_en = res_en.json()
    assert "Uttarakhand" in data_en["corridor"]
    assert data_en["segments"][0]["name"] == "Rishikesh to Shivpuri"
    assert data_en["segments"][0]["risk_level"] in ("Low", "Moderate", "High", "Very High")

    # 2. Hindi (lang=hi)
    res_hi = client.get("/risk-map?lang=hi")
    assert res_hi.status_code == 200
    data_hi = res_hi.json()
    assert "उत्तराखंड" in data_hi["corridor"]
    assert data_hi.get("corridor_en") == "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)"
    assert data_hi["lang"] == "hi"

    first_seg = data_hi["segments"][0]
    assert first_seg["name"] == "ऋषिकेश से शिवपुरी"
    assert first_seg["name_en"] == "Rishikesh to Shivpuri"
    assert first_seg["risk_level"] in ("कम", "मध्यम", "उच्च", "अत्यधिक")
    assert first_seg["risk_level_en"] in ("Low", "Moderate", "High", "Very High")
    assert "इस मार्ग के लिए असामान्य" in first_seg["main_driver"]
    assert "unusual" in first_seg["main_driver_en"]


def test_route_risk_localization():
    """Tests GET /route-risk with lang=hi vs default lang=en."""
    # 1. Default (lang absent -> en)
    res_en = client.get("/route-risk?from_segment=seg_01&to_segment=seg_05&date=2026-10-06")
    assert res_en.status_code == 200
    d_en = res_en.json()
    assert d_en["from_segment_name"] == "Rishikesh to Shivpuri"
    assert d_en["max_risk_level"] in ("Low", "Moderate", "High", "Very High")
    assert "CONDITIONS" in d_en["advisory"] or "ADVISORY" in d_en["advisory"] or "WARNING" in d_en["advisory"] or "RISK" in d_en["advisory"]

    # 2. Localized Hindi (lang=hi)
    res_hi = client.get("/route-risk?from_segment=seg_01&to_segment=seg_05&date=2026-10-06&lang=hi")
    assert res_hi.status_code == 200
    d_hi = res_hi.json()
    assert d_hi["from_segment_name"] == "ऋषिकेश से शिवपुरी"
    assert d_hi["from_segment_name_en"] == "Rishikesh to Shivpuri"
    assert d_hi["to_segment_name"] == "देवप्रयाग से तीन धारा"
    assert d_hi["to_segment_name_en"] == "Devprayag to Teen Dhara"
    assert d_hi["max_risk_level"] in ("कम", "मध्यम", "उच्च", "अत्यधिक")
    assert d_hi["max_risk_level_en"] in ("Low", "Moderate", "High", "Very High")
    assert d_hi["advisory_en"] is not None
    assert any(w in d_hi["advisory"] for w in ("सलाह", "चेतावनी", "स्थिति", "जोखिम"))

    # Segment items
    s0 = d_hi["segments"][0]
    assert s0["name"] == "ऋषिकेश से शिवपुरी"
    assert s0["name_en"] == "Rishikesh to Shivpuri"
    assert s0["risk_level"] in ("कम", "मध्यम", "उच्च", "अत्यधिक")
    assert s0["risk_level_en"] in ("Low", "Moderate", "High", "Very High")


def test_alerts_localization():
    """Tests GET /alerts with lang=hi vs default lang=en."""
    # Subscribe user to seg_08
    sub_res = client.post("/subscribe", json={
        "name": "Anil Joshi",
        "phone_or_email": "+91-9876543210",
        "segment_id": "seg_08",
        "channel": "SMS"
    })
    assert sub_res.status_code == 201
    sub_data = sub_res.json()
    user_id = sub_data["subscription_id"]
    token = sub_data["token"]

    # 1. Fetch alerts in English with simulated heavy rainfall
    res_en = client.get(f"/alerts?user_id={user_id}&token={token}&simulate_rain_mm=80&lang=en")
    assert res_en.status_code == 200
    d_en = res_en.json()
    assert "seg_08" in d_en["subscribed_segment"]
    if d_en["alerts"]:
        a_en = d_en["alerts"][0]
        assert a_en["severity"] in ("High", "Very High", "Moderate")
        assert "ALERT" in a_en["message"] or "ADVISORY" in a_en["message"]

    # 2. Fetch alerts in Hindi
    res_hi = client.get(f"/alerts?user_id={user_id}&token={token}&simulate_rain_mm=80&lang=hi")
    assert res_hi.status_code == 200
    d_hi = res_hi.json()
    assert "श्रीनगर से सिरोबगड़" in d_hi["subscribed_segment"]
    assert d_hi["subscribed_segment_en"] == "seg_08 (Srinagar to Sirobagarh)"
    assert d_hi["lang"] == "hi"

    if d_hi["alerts"]:
        a_hi = d_hi["alerts"][0]
        assert a_hi["severity"] in ("उच्च", "अत्यधिक", "मध्यम")
        assert a_hi["severity_en"] in ("High", "Very High", "Moderate")
        assert a_hi["segment_name"] == "श्रीनगर से सिरोबगड़"
        assert a_hi["segment_name_en"] == "Srinagar to Sirobagarh"
        assert "चेतावनी" in a_hi["message"] or "सलाह" in a_hi["message"]
        assert a_hi["message_en"] is not None


def test_voice_alert_endpoint_with_mocked_gtts(tmp_path, monkeypatch):
    """
    Tests GET /voice-alert for segment and route with mocked gTTS.
    Verifies audio/mpeg MIME type, caching in data/tts_cache/, and max ~300 chars length.
    """
    monkeypatch.setattr(config, "TTS_CACHE_DIR", tmp_path)
    fake_mp3_content = b"ID3\x03\x00\x00\x00\x00\x00\x21FAKE_MP3_AUDIO_BYTES_TESTING_DATA"

    def fake_save(self, save_path):
        Path(save_path).write_bytes(fake_mp3_content)

    with patch("gtts.gTTS.save", new=fake_save):
        # 1. Voice alert for single segment in English
        res = client.get("/voice-alert?segment_id=seg_08&lang=en")
        assert res.status_code == 200
        assert res.headers["content-type"] == "audio/mpeg"
        assert res.content == fake_mp3_content
        assert res.headers.get("X-TTS-Source") == "gTTS"

        # 2. Repeated request should hit file cache
        res_cached = client.get("/voice-alert?segment_id=seg_08&lang=en")
        assert res_cached.status_code == 200
        assert res_cached.headers["content-type"] == "audio/mpeg"
        assert res_cached.content == fake_mp3_content
        assert res_cached.headers.get("X-TTS-Source") == "cache"

        # 3. Voice alert for route in Hindi
        res_route = client.get("/voice-alert?from=seg_01&to=seg_04&lang=hi")
        assert res_route.status_code == 200
        assert res_route.headers["content-type"] == "audio/mpeg"
        assert res_route.content == fake_mp3_content


def test_voice_alert_offline_browser_speech_fallback(tmp_path, monkeypatch):
    """
    Tests that if gTTS fails (offline network, DNS timeout, import error),
    the endpoint gracefully returns JSON {text, tts: 'browser', lang: ...}.
    """
    monkeypatch.setattr(config, "TTS_CACHE_DIR", tmp_path)
    with patch("gtts.gTTS.save", side_effect=Exception("Offline: Could not connect to Google Translate TTS")):
        res = client.get("/voice-alert?segment_id=seg_14&lang=hi&simulate_rain_mm=99")
        assert res.status_code == 200
        assert "application/json" in res.headers["content-type"]
        data = res.json()
        assert data["tts"] == "browser"
        assert data["lang"] == "hi"
        assert "text" in data
        assert len(data["text"]) <= 300
        assert "चमोली" in data["text"] or "नंदप्रयाग" in data["text"] or "एनएच-7" in data["text"]


def test_voice_alert_parameter_validation():
    """Tests 400 Bad Request when neither segment_id nor route endpoints are given."""
    res = client.get("/voice-alert")
    assert res.status_code == 400
    assert "Specify either 'segment_id' or both 'from' and 'to'" in res.json()["detail"]

    # Nonexistent segment
    res_404 = client.get("/voice-alert?segment_id=seg_99")
    assert res_404.status_code == 404
