"""
app/routes/webhooks.py - Inbound webhooks for SMS and messaging integrations
============================================================================
Handles:
- POST /webhook/sms: Inbound SMS query processing via Twilio.
  Supports commands:
  - NH7 HELP (or HELP, मदद)
  - NH7 SEG08, SEG8, seg_08, seg 8, segment 8, or town names (Srinagar, Sirobagarh, etc.)
  - NH7 ROUTE <FROM> <TO>
  Replies with valid TwiML XML.
  Tracks and validates SMS segment boundaries:
  - GSM-7: 160 chars/segment (concatenated: 153 chars/segment)
  - UCS-2 (Hindi/Unicode): 70 chars/segment (concatenated: 67 chars/segment)
  Validates X-Twilio-Signature when TWILIO_AUTH_TOKEN is configured.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import logging
import math
import re
from typing import Optional, List, Tuple, Dict, Any
from fastapi import APIRouter, Request, Response, HTTPException, status

from app import config, i18n
from app.bot.telegram_bot import fuzzy_match_segment
from app.risk_service import get_live_risk_map_with_metadata

log = logging.getLogger("webhooks")
router = APIRouter(tags=["Webhooks"])

# Comprehensive town-to-segment mapping across the entire NH-7 corridor
TOWN_TO_SEGMENT: Dict[str, str] = {
    "rishikesh": "seg_01",
    "shivpuri": "seg_01",
    "byasi": "seg_02",
    "kaudiyala": "seg_03",
    "devprayag": "seg_04",
    "teendhara": "seg_05",
    "teen dhara": "seg_05",
    "kirtinagar": "seg_06",
    "srinagar": "seg_08",
    "sirobagarh": "seg_08",
    "kaliasaur": "seg_08",
    "narkota": "seg_09",
    "rudraprayag": "seg_09",
    "gholtir": "seg_10",
    "gauchar": "seg_11",
    "karnaprayag": "seg_12",
    "langasu": "seg_13",
    "nandprayag": "seg_14",
    "chamoli": "seg_15",
    "birahi": "seg_15",
    "pipalkoti": "seg_16",
    "tangani": "seg_17",
    "tangni": "seg_17",
    "pagalnala": "seg_17",
    "helang": "seg_18",
    "joshimath": "seg_18",
    # Devanagari Hindi town names
    "ऋषिकेश": "seg_01",
    "शिवपुरी": "seg_01",
    "ब्यासी": "seg_02",
    "कौड़ियाला": "seg_03",
    "देवप्रयाग": "seg_04",
    "तीनधारा": "seg_05",
    "तीन धारा": "seg_05",
    "कीर्तिनगर": "seg_06",
    "श्रीनगर": "seg_08",
    "सिरोबगड़": "seg_08",
    "कलियासौड़": "seg_08",
    "नरकोटा": "seg_09",
    "रुद्रप्रयाग": "seg_09",
    "घोलतीर": "seg_10",
    "गौचर": "seg_11",
    "कर्णप्रयाग": "seg_12",
    "लांगासू": "seg_13",
    "नंदप्रयाग": "seg_14",
    "चमोली": "seg_15",
    "बिरही": "seg_15",
    "पीपलकोटी": "seg_16",
    "पागलनाला": "seg_17",
    "हेलंग": "seg_18",
    "जोशीमठ": "seg_18",
}


def check_sms_encoding_and_segments(text: str) -> dict:
    """
    Analyzes an SMS message text for GSM-7 vs UCS-2 encoding and calculates segment count.
    - GSM-7: Standard 7-bit characters, up to 160 chars for 1 segment, 153 chars/segment concatenated.
    - UCS-2: Triggered by any non-GSM/Devanagari characters.
             Single segment limit: 70 characters.
             Concatenated segment limit: 67 characters per segment.
    """
    clean = text.strip()
    is_ucs2 = any(ord(c) > 127 for c in clean)
    char_count = len(clean)

    if is_ucs2:
        encoding = "UCS-2"
        max_single = 70
        concat_limit = 67
        if char_count <= 70:
            segments = 1 if char_count > 0 else 0
        else:
            segments = math.ceil(char_count / concat_limit)
    else:
        encoding = "GSM-7"
        max_single = 160
        concat_limit = 153
        if char_count <= 160:
            segments = 1 if char_count > 0 else 0
        else:
            segments = math.ceil(char_count / concat_limit)

    return {
        "text": clean,
        "char_count": char_count,
        "encoding": encoding,
        "is_ucs2": is_ucs2,
        "segments": segments,
        "max_single_segment_chars": max_single,
        "fits_single_segment": char_count <= max_single,
    }


def validate_twilio_signature(url: str, params: dict, signature: str, auth_token: str) -> bool:
    """
    Validates Twilio's X-Twilio-Signature HMAC-SHA1 header.
    Sorts POST form parameters alphabetically and computes HMAC digest.
    """
    data_to_sign = url
    for key in sorted(params.keys()):
        data_to_sign += f"{key}{params[key]}"

    mac = hmac.new(auth_token.encode("utf-8"), data_to_sign.encode("utf-8"), hashlib.sha1)
    computed = base64.b64encode(mac.digest()).decode("utf-8").strip()
    return hmac.compare_digest(computed, signature.strip())


def build_twiml_response(text: str, max_chars: Optional[int] = None) -> Response:
    """
    Builds standard TwiML XML payload capped at max_chars.
    Audits SMS encoding and segment limits (70 chars for UCS-2 Hindi).
    """
    limit = max_chars or 320
    clean_text = text.strip()[:limit]
    metrics = check_sms_encoding_and_segments(clean_text)

    log.info(
        "TwiML SMS constructed: %d chars, encoding=%s, segments=%d (fits_single=%s)",
        metrics["char_count"],
        metrics["encoding"],
        metrics["segments"],
        metrics["fits_single_segment"],
    )

    escaped_text = html.escape(clean_text)
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Response>\n'
        f'    <Message>{escaped_text}</Message>\n'
        '</Response>'
    )
    return Response(
        content=twiml,
        media_type="application/xml",
        headers={
            "X-SMS-Encoding": metrics["encoding"],
            "X-SMS-Segments": str(metrics["segments"]),
            "X-SMS-Char-Count": str(metrics["char_count"]),
        }
    )


def parse_segment_or_town(query: str, segments: List[dict]) -> Optional[dict]:
    """
    Parses a sector query case-insensitively.
    Accepts:
    - Standard & variation IDs: SEG8, SEG08, seg_08, seg8, seg08, seg 8, segment 8, segment08, 8, 08
    - Town / waypoint names: Srinagar, Sirobagarh, Devprayag, Joshimath, Pipalkoti, etc.
    - Hindi town names: श्रीनगर, सिरोबगड़, ऋषिकेश, जोशीमठ, etc.
    """
    raw = query.strip()
    if not raw:
        return None

    # Strip common leading command prefixes like NH7, NH-7, STATUS, CHECK, SECTOR
    clean = re.sub(r"^(?:nh[- ]?7|status|check|sector|segment)[\s:,-]*", "", raw, flags=re.IGNORECASE).strip()
    clean_lower = clean.lower()

    # 1. Regex check for segment ID or number (e.g. SEG8, SEG08, seg_08, seg 8, segment 8, 8, 08)
    num_match = re.search(r"\b(?:seg(?:ment)?[\s_]*)?0*([1-9]|1[0-8])\b", clean, flags=re.IGNORECASE)
    if num_match:
        try:
            num = int(num_match.group(1))
            if 1 <= num <= 18:
                target_id = f"seg_{num:02d}"
                for s in segments:
                    if s["id"].lower() == target_id:
                        return s
        except ValueError:
            pass

    # 2. Direct ID or stripped ID match (e.g. "seg_08", "seg08")
    clean_id = clean_lower.replace("_", "").replace("-", "").replace(" ", "")
    for s in segments:
        s_clean = s["id"].lower().replace("_", "")
        if clean_id == s_clean or clean_lower == s["id"].lower():
            return s

    # 3. Comprehensive Town & Landmark lookup
    for town_key, target_id in TOWN_TO_SEGMENT.items():
        if town_key in clean_lower or clean_lower in town_key:
            for s in segments:
                if s["id"].lower() == target_id.lower():
                    return s

    # 4. Substring match on segment official name (e.g. "Srinagar to Sirobagarh")
    for s in segments:
        s_name_lower = s["name"].lower()
        if clean_lower in s_name_lower:
            return s

    # 5. Fallback to fuzzy_match_segment
    return fuzzy_match_segment(clean, segments)


@router.post(
    "/webhook/sms",
    summary="Twilio Inbound SMS Webhook",
    responses={
        200: {
            "content": {
                "application/xml": {
                    "example": '<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n    <Message>NH7 Srinagar to Sirobagarh: HIGH RISK. 3-day rain: 38.2 mm. Travel with caution.</Message>\n</Response>'
                }
            },
            "description": "TwiML XML response containing formatted SMS reply"
        }
    }
)
async def inbound_sms_webhook(request: Request):
    """
    Handles inbound SMS messages sent to the Twilio number.
    Parses 'Body' and 'From' form parameters case-insensitively.
    Accepts: SEG8, SEG08, seg_08, town names (Srinagar, Sirobagarh, etc.), ROUTE, HELP.
    Checks reply length for UCS-2 encoding (Hindi: 70 chars per SMS segment).
    Returns TwiML XML response.
    """
    form = await request.form()
    form_dict = {k: str(v) for k, v in form.items()}

    # 1. Signature Verification
    if config.TWILIO_AUTH_TOKEN:
        signature = request.headers.get("X-Twilio-Signature")
        if not signature:
            log.warning("Twilio webhook rejected: missing X-Twilio-Signature header")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing X-Twilio-Signature header")

        url = str(request.url)
        if not validate_twilio_signature(url, form_dict, signature, config.TWILIO_AUTH_TOKEN):
            log.warning("Twilio webhook rejected: invalid signature")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")

    raw_body = form_dict.get("Body", "").strip()
    from_number = form_dict.get("From", "").strip()
    body_upper = raw_body.upper()
    body_lower = raw_body.lower()

    log.info("Received SMS from %s: '%s'", from_number, raw_body)

    # Detect if Hindi is requested (explicit keyword 'hi'/'hindi' or Devanagari script)
    is_hindi = bool(
        re.search(r"\b(?:hi|hindi)\b", raw_body, flags=re.IGNORECASE)
        or any("\u0900" <= c <= "\u097f" for c in raw_body)
    )

    # 2. Command Processing
    # Command: HELP / मदद
    if "HELP" in body_upper or "मदद" in raw_body or not raw_body:
        if is_hindi:
            # Concise Hindi help text tuned for UCS-2 single segment (<= 70 chars)
            reply = "NH-7 अलर्ट: SEG08 (जोखिम) या ROUTE A B भेजें। आपातकाल: 112"
        else:
            reply = (
                "NH-7 Landslide Alerts:\n"
                "- Reply 'NH7 SEG08' for sector risk\n"
                "- Reply 'NH7 ROUTE RISHIKESH JOSHIMATH' for journey forecast\n"
                "Decision-support prototype, not an official warning. Low risk does not mean safe. "
                "Landslides also occur in dry weather. Follow BRO/SDRF/police advisories. Emergency: 112"
            )
        return build_twiml_response(reply)

    # Command: ROUTE <FROM> <TO>
    if "ROUTE" in body_upper or "मार्ग" in raw_body:
        tokens = raw_body.split()
        route_idx = -1
        for idx, t in enumerate(tokens):
            if t.upper() in ("ROUTE", "मार्ग"):
                route_idx = idx
                break

        route_args = [t for t in tokens[route_idx + 1:] if t.upper() not in ("HI", "HINDI")] if route_idx != -1 else []
        if len(route_args) >= 2:
            live_segs, _ = get_live_risk_map_with_metadata(simulate_rain_mm=None)
            s_from = parse_segment_or_town(route_args[0], live_segs)
            s_to = parse_segment_or_town(route_args[1], live_segs)

            if s_from and s_to:
                seq1, seq2 = s_from["sequence_order"], s_to["sequence_order"]
                low, high = min(seq1, seq2), max(seq1, seq2)
                route = [s for s in live_segs if low <= s["sequence_order"] <= high]

                LEVEL_ORDER = {"Low": 0, "Moderate": 1, "High": 2, "Very High": 3}
                max_seg = max(route, key=lambda s: LEVEL_ORDER.get(s.get("adjusted_risk_level") or s.get("risk_level", "Low"), 0))
                max_level = max_seg.get("adjusted_risk_level") or max_seg.get("risk_level", "Low")

                closed_any = any(s.get("closure") and s["closure"]["status"] == "closed" for s in route)
                restricted_any = any(s.get("closure") and s["closure"]["status"] in ("restricted", "one_way") for s in route)
                if closed_any:
                    action = "AVOID"
                elif restricted_any or max_level in ("High", "Very High"):
                    action = "CAUTION"
                else:
                    action = "LOW RISK – proceed with caution"

                from_town = s_from["name"].split(" to ")[0].strip()
                to_town = s_to["name"].split(" to ")[-1].strip()

                if is_hindi:
                    action_hi = {"LOW RISK – proceed with caution": "कम जोखिम - सावधानी", "CAUTION": "सावधानी (CAUTION)", "AVOID": "रद्द (AVOID)"}.get(action, action)
                    from_hi = i18n.transliterate_town(from_town, "hi")
                    to_hi = i18n.transliterate_town(to_town, "hi")
                    max_lvl_hi = i18n.localize_risk_level(max_level, "hi")
                    reply = (
                        f"NH-7 {from_hi}->{to_hi}: {action_hi}। "
                        f"अधिकतम: {max_lvl_hi} ({max_seg['id']})। "
                        f"क्षेत्र: {len(route)}। आपातकाल: 1070 / 112"
                    )
                else:
                    reply = (
                        f"NH-7 {from_town}->{to_town}: {action}. "
                        f"Max {max_level} on {max_seg['id']} ({max_seg['name']}). "
                        f"Sectors: {len(route)}. Emergency: 1070 / 112."
                    )
                return build_twiml_response(reply)

        reply = "Route format: NH7 ROUTE RISHIKESH JOSHIMATH. Send NH7 HELP for guidance."
        return build_twiml_response(reply)

    # 3. Segment & Town Query (e.g. NH7 SEG08, SEG8, seg_08, Srinagar, Sirobagarh, etc.)
    clean_query = re.sub(r"\b(?:hi|hindi)\b", "", raw_body, flags=re.IGNORECASE).strip()
    live_segs, _ = get_live_risk_map_with_metadata(simulate_rain_mm=None)
    matched = parse_segment_or_town(clean_query, live_segs)

    if matched:
        risk_lvl = matched.get("adjusted_risk_level") or matched.get("risk_level", "Low")
        rain_3d = matched.get("rain_mm_3d", 0.0)
        closure = matched.get("closure")

        if is_hindi:
            # Highly compact, informative Hindi reply designed to fit UCS-2 single segment (<= 70 chars)
            seg_town = matched["name"].split(" to ")[-1].strip()
            seg_town_hi = i18n.transliterate_town(seg_town, "hi")
            risk_hi = i18n.localize_risk_level(risk_lvl, "hi")
            status_hi = f"बंद ({closure['status'].upper()})" if closure else f"वर्षा: {rain_3d:.1f}mm"
            reply = f"NH-7 {matched['id']} ({seg_town_hi}): {risk_hi} जोखिम ({status_hi})। हेल्पलाइन: 1070"
            # Verify and enforce UCS-2 limit
            metrics = check_sms_encoding_and_segments(reply)
            if metrics["char_count"] > 70:
                # Fallback to ultra-short single-segment format
                reply = f"NH-7 {matched['id']}: {risk_hi} जोखिम ({status_hi})। हेल्पलाइन: 1070"[:70]
        else:
            status_note = f"CLOSURE: {closure['status'].upper()}" if closure else f"Rain: {rain_3d:.1f}mm"
            reply = (
                f"NH-7 {matched['id']}: {matched['name']}\n"
                f"Risk: {risk_lvl.upper()} ({status_note})\n"
                f"Driver: {matched.get('main_driver', 'Terrain')[:40]}"
            )
        return build_twiml_response(reply)

    # Fallback response for unparsed queries
    if is_hindi:
        reply = "NH-7 अलर्ट: सेक्टर नहीं मिला। 'NH7 HELP' या 'SEG08' भेजें।"
    else:
        reply = "NH-7 Early Warning: Sector not recognized. Reply 'NH7 HELP' or 'NH7 SEG08'."
    return build_twiml_response(reply)
