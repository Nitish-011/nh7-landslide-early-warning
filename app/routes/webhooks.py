"""
app/routes/webhooks.py - Inbound webhooks for SMS and messaging integrations
============================================================================
Handles:
- POST /webhook/sms: Inbound SMS query processing via Twilio.
  Supports commands:
  - NH7 HELP
  - NH7 SEG08 (or NH7 <segment>)
  - NH7 ROUTE <FROM> <TO>
  Replies with valid TwiML XML (max 320 chars).
  Validates X-Twilio-Signature when TWILIO_AUTH_TOKEN is configured.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import logging
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, status

from app import config
from app.bot.telegram_bot import fuzzy_match_segment
from app.risk_service import get_live_risk_map_with_metadata

log = logging.getLogger("webhooks")
router = APIRouter(tags=["Webhooks"])


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


def build_twiml_response(text: str) -> Response:
    """Builds standard TwiML XML payload capped at 320 characters."""
    clean_text = text.strip()[:320]
    escaped_text = html.escape(clean_text)
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Response>\n'
        f'    <Message>{escaped_text}</Message>\n'
        '</Response>'
    )
    return Response(content=twiml, media_type="application/xml")


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
            "description": "TwiML XML response containing formatted SMS reply (max 320 chars)"
        }
    }
)
async def inbound_sms_webhook(request: Request):
    """
    Handles inbound SMS messages sent to the Twilio number.
    Parses 'Body' and 'From' form parameters.
    Returns TwiML XML response (max 320 characters).
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

    log.info("Received SMS from %s: '%s'", from_number, raw_body)

    # 2. Command Processing
    # Command: NH7 HELP
    if "HELP" in body_upper or not body_upper:
        reply = (
            "NH-7 Landslide Alerts:\n"
            "- Reply 'NH7 SEG08' for sector risk\n"
            "- Reply 'NH7 ROUTE RISHIKESH JOSHIMATH' for journey forecast\n"
            "Helpline: 1070 (SDRF) / 112"
        )
        return build_twiml_response(reply)

    # Command: NH7 ROUTE <FROM> <TO>
    if "ROUTE" in body_upper:
        tokens = raw_body.split()
        route_idx = -1
        for idx, t in enumerate(tokens):
            if t.upper() == "ROUTE":
                route_idx = idx
                break

        route_args = tokens[route_idx + 1:] if route_idx != -1 else []
        if len(route_args) >= 2:
            live_segs, _ = get_live_risk_map_with_metadata(simulate_rain_mm=None)
            s_from = fuzzy_match_segment(route_args[0], live_segs)
            s_to = fuzzy_match_segment(route_args[1], live_segs)

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
                    action = "GO"

                from_town = s_from["name"].split(" to ")[0].strip()
                to_town = s_to["name"].split(" to ")[-1].strip()
                reply = (
                    f"NH-7 {from_town}->{to_town}: {action}. "
                    f"Max {max_level} on {max_seg['id']} ({max_seg['name']}). "
                    f"Sectors: {len(route)}. Emergency: 1070."
                )
                return build_twiml_response(reply)

        reply = "Route format: NH7 ROUTE RISHIKESH JOSHIMATH. Send NH7 HELP for guidance."
        return build_twiml_response(reply)

    # Command: NH7 SEG08 or NH7 <SEGMENT>
    query_str = raw_body
    if query_str.upper().startswith("NH7"):
        query_str = query_str[3:].strip()

    live_segs, _ = get_live_risk_map_with_metadata(simulate_rain_mm=None)
    matched = fuzzy_match_segment(query_str, live_segs)

    if matched:
        risk_lvl = matched.get("adjusted_risk_level") or matched.get("risk_level", "Low")
        rain_3d = matched.get("rain_mm_3d", 0.0)
        closure = matched.get("closure")
        status_note = f"CLOSURE: {closure['status'].upper()}" if closure else f"Rain: {rain_3d:.1f}mm"

        reply = (
            f"NH-7 {matched['id']}: {matched['name']}\n"
            f"Risk: {risk_lvl.upper()} ({status_note})\n"
            f"Driver: {matched.get('main_driver', 'Terrain')[:40]}"
        )
        return build_twiml_response(reply)

    # Fallback response
    reply = "NH-7 Early Warning: Sector not recognized. Reply 'NH7 HELP' or 'NH7 SEG08'."
    return build_twiml_response(reply)
