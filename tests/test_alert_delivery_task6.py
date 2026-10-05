import base64
import hashlib
import hmac
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app
from app import config
from app.database import get_db, init_db
from app.notifiers import (
    BaseNotifier,
    ConsoleNotifier,
    TelegramNotifier,
    TwilioNotifier,
    get_notifier,
    set_fake_notifier,
)
from app.alert_dispatcher import dispatch_alerts, build_alert_message
from app.bot.telegram_bot import handle_telegram_command, process_update, fuzzy_match_segment
from app.risk_service import load_segments

client = TestClient(app)


class FakeRecordingNotifier(BaseNotifier):
    """Test fake capturing all dispatched alert messages in memory."""
    def __init__(self):
        self.sent_messages = []

    def send(self, recipient: str, message: str, channel: str = "sms") -> bool:
        self.sent_messages.append({
            "recipient": recipient,
            "message": message,
            "channel": channel,
        })
        return True


@pytest.fixture(autouse=True)
def clean_test_state():
    """Ensures a clean database and mock notifier environment for each test."""
    init_db()
    set_fake_notifier(None)
    with get_db() as conn:
        conn.execute("DELETE FROM alert_log")
        conn.execute("DELETE FROM alert_state")
        conn.execute("DELETE FROM subscriptions WHERE phone_or_email LIKE 'test_%' OR channel = 'telegram'")
    yield
    set_fake_notifier(None)
    with get_db() as conn:
        conn.execute("DELETE FROM alert_log")
        conn.execute("DELETE FROM alert_state")
        conn.execute("DELETE FROM subscriptions WHERE phone_or_email LIKE 'test_%' OR channel = 'telegram'")


def test_notifier_implementations_dry_run():
    """Verify Console, Telegram, and Twilio notifiers operate safely in dry-run mode."""
    console = ConsoleNotifier()
    assert console.send("+919999999999", "Console Test", channel="console") is True

    telegram = TelegramNotifier(bot_token="fake_token")
    assert telegram.send("12345678", "Telegram Dry Run", channel="telegram") is True

    twilio = TwilioNotifier(account_sid="fake_sid", auth_token="fake_auth", from_number="+15550001")
    assert twilio.send("+919876543210", "SMS Dry Run", channel="sms") is True
    assert twilio.send("+919876543210", "WhatsApp Dry Run", channel="whatsapp") is True


def test_telegram_bot_commands():
    """Verify Telegram bot command processing: /start, /lang, /status, /route, /subscribe, /unsubscribe."""
    chat_id = "99887766"

    # 1. /start command
    start_reply = handle_telegram_command(chat_id, "/start")
    assert "NH-7 Landslide Early Warning" in start_reply
    assert "/status" in start_reply

    # 2. /lang hi command and Hindi response
    lang_reply = handle_telegram_command(chat_id, "/lang hi")
    assert "भाषा हिंदी" in lang_reply
    start_hi = handle_telegram_command(chat_id, "/start")
    assert "नमस्ते" in start_hi

    # Switch back to English
    handle_telegram_command(chat_id, "/lang en")

    # 3. /status with fuzzy match on ID and name
    status_id = handle_telegram_command(chat_id, "/status seg_08")
    assert "NH-7 seg_08" in status_id
    assert "Risk Level" in status_id

    status_name = handle_telegram_command(chat_id, "/status Sirobagarh")
    assert "seg_09" in status_name or "Sirobagarh" in status_name

    # 4. /route evaluation
    route_reply = handle_telegram_command(chat_id, "/route Rishikesh Joshimath")
    assert "Route:" in route_reply
    assert "Max Risk:" in route_reply
    assert "Recommendation:" in route_reply

    # 5. /subscribe command
    sub_reply = handle_telegram_command(chat_id, "/subscribe seg_09")
    assert "Successfully subscribed" in sub_reply
    assert "seg_09" in sub_reply

    # Verify subscription in DB
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT segment_id, channel FROM subscriptions WHERE phone_or_email = ?", (chat_id,))
        sub_row = cursor.fetchone()
        assert sub_row is not None
        assert sub_row["segment_id"] == "seg_09"
        assert sub_row["channel"] == "telegram"

    # 6. /unsubscribe command
    unsub_reply = handle_telegram_command(chat_id, "/unsubscribe")
    assert "Unsubscribed" in unsub_reply

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM subscriptions WHERE phone_or_email = ?", (chat_id,))
        assert cursor.fetchone() is None


def test_telegram_process_update_with_fake():
    """Verify process_update dispatches and replies via notifier."""
    fake = FakeRecordingNotifier()
    set_fake_notifier(fake)

    update_payload = {
        "update_id": 1001,
        "message": {
            "chat": {"id": 12345},
            "text": "/status seg_01"
        }
    }
    reply = process_update(update_payload)
    assert reply is not None
    assert "NH-7 seg_01" in reply

    assert len(fake.sent_messages) == 1
    assert fake.sent_messages[0]["recipient"] == "12345"
    assert "seg_01" in fake.sent_messages[0]["message"]


def test_twilio_sms_webhook_commands():
    """Verify Twilio webhook parses Body & From, supports commands, and caps TwiML at 320 chars."""
    # 1. NH7 HELP
    resp_help = client.post("/webhook/sms", data={"Body": "NH7 HELP", "From": "+919876543210"})
    assert resp_help.status_code == 200
    assert "application/xml" in resp_help.headers["Content-Type"]
    assert "<Response>" in resp_help.text
    assert "NH-7 Landslide Alerts:" in resp_help.text
    assert len(resp_help.text) <= 500  # Full XML including tags

    # 2. NH7 SEG08
    resp_seg = client.post("/webhook/sms", data={"Body": "NH7 SEG08", "From": "+919876543210"})
    assert resp_seg.status_code == 200
    assert "seg_08" in resp_seg.text or "Srinagar" in resp_seg.text
    assert "Risk:" in resp_seg.text

    # 3. NH7 ROUTE RISHIKESH JOSHIMATH
    resp_route = client.post("/webhook/sms", data={"Body": "NH7 ROUTE RISHIKESH JOSHIMATH", "From": "+919876543210"})
    assert resp_route.status_code == 200
    assert "<Message>" in resp_route.text
    assert "Emergency: 1070" in resp_route.text

    # Verify message body constraint: <= 320 characters
    import re
    match = re.search(r"<Message>(.*?)</Message>", resp_route.text)
    assert match is not None
    assert len(match.group(1)) <= 320


def test_twilio_signature_validation(monkeypatch):
    """Verify X-Twilio-Signature verification rejects invalid signature and accepts valid signature."""
    auth_token = "secret_twilio_token_123"
    monkeypatch.setattr(config, "TWILIO_AUTH_TOKEN", auth_token)

    # 1. Missing signature when token set -> 403
    unauth = client.post("/webhook/sms", data={"Body": "NH7 HELP", "From": "+919876500000"})
    assert unauth.status_code == 403

    # 2. Invalid signature -> 403
    bad_sig = client.post(
        "/webhook/sms",
        data={"Body": "NH7 HELP", "From": "+919876500000"},
        headers={"X-Twilio-Signature": "invalid_signature"}
    )
    assert bad_sig.status_code == 403

    # 3. Valid HMAC-SHA1 signature
    url = "http://testserver/webhook/sms"
    form_params = {"Body": "NH7 HELP", "From": "+919876500000"}
    data_to_sign = url
    for k in sorted(form_params.keys()):
        data_to_sign += f"{k}{form_params[k]}"

    mac = hmac.new(auth_token.encode("utf-8"), data_to_sign.encode("utf-8"), hashlib.sha1)
    valid_sig = base64.b64encode(mac.digest()).decode("utf-8")

    good_resp = client.post(
        "/webhook/sms",
        data=form_params,
        headers={"X-Twilio-Signature": valid_sig}
    )
    assert good_resp.status_code == 200
    assert "<Response>" in good_resp.text


def test_alert_dispatcher_dedupe_and_cooldown(monkeypatch):
    """
    Acceptance Test:
    Proves alert dispatcher respects deduplication, 3h cooldown, and level changes using fake notifier.
    """
    fake = FakeRecordingNotifier()
    set_fake_notifier(fake)

    # Create two subscriptions in DB
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute("""
            INSERT INTO subscriptions (id, name, phone_or_email, segment_id, channel, consent, created_at)
            VALUES (901, 'Test User High', 'test_user_high@example.com', 'seg_03', 'sms', 1, ?)
        """, (now_iso,))
        conn.execute("""
            INSERT INTO subscriptions (id, name, phone_or_email, segment_id, channel, consent, created_at)
            VALUES (902, 'Test User Low', 'test_user_low@example.com', 'seg_01', 'sms', 1, ?)
        """, (now_iso,))

    # Mock get_live_risk_map_with_metadata to return controlled risk levels:
    # seg_03 is High risk, seg_01 is Low risk
    def mock_risk_map(simulate_rain_mm=None):
        return [
            {"id": "seg_01", "name": "Rishikesh to Shivpuri", "risk_level": "Low"},
            {"id": "seg_03", "name": "Byasi to Kaudiyala", "risk_level": "High"},
        ], {}

    from app import alert_dispatcher
    monkeypatch.setattr(alert_dispatcher, "get_live_risk_map_with_metadata", mock_risk_map)

    # --- Run 1: First dispatch ---
    sent_count_1 = dispatch_alerts()
    # seg_03 is High risk (first time) -> should send
    # seg_01 is Low risk -> should not send
    assert sent_count_1 == 1
    assert len(fake.sent_messages) == 1
    assert fake.sent_messages[0]["recipient"] == "test_user_high@example.com"
    assert "HIGH risk" in fake.sent_messages[0]["message"]
    assert "Byasi to Kaudiyala" in fake.sent_messages[0]["message"]

    # Verify alert_state and alert_log persisted
    with get_db() as conn:
        state = conn.execute("SELECT * FROM alert_state WHERE subscription_id = 901").fetchone()
        assert state is not None
        assert state["last_sent_level"] == "High"

        log_rows = conn.execute("SELECT * FROM alert_log WHERE subscription_id = 901").fetchall()
        assert len(log_rows) == 1
        assert log_rows[0]["risk_level"] == "High"

    # --- Run 2: Immediate second dispatch (Dedupe & 3h Cooldown) ---
    fake.sent_messages.clear()
    sent_count_2 = dispatch_alerts()
    # Cooldown active (< 3 hours) and level unchanged -> 0 sent!
    assert sent_count_2 == 0
    assert len(fake.sent_messages) == 0

    # --- Run 3: Simulate 4 hours later, but risk level STILL High ---
    four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    with get_db() as conn:
        conn.execute("UPDATE alert_state SET last_sent_at = ? WHERE subscription_id = 901", (four_hours_ago,))

    fake.sent_messages.clear()
    sent_count_3 = dispatch_alerts()
    # Level is still High (has not changed from last_sent_level) -> 0 sent!
    assert sent_count_3 == 0
    assert len(fake.sent_messages) == 0

    # --- Run 4: Risk level escalates to Very High after cooldown ---
    def mock_risk_escalated(simulate_rain_mm=None):
        return [
            {"id": "seg_01", "name": "Rishikesh to Shivpuri", "risk_level": "Low"},
            {"id": "seg_03", "name": "Byasi to Kaudiyala", "risk_level": "Very High"},
        ], {}

    monkeypatch.setattr(alert_dispatcher, "get_live_risk_map_with_metadata", mock_risk_escalated)

    sent_count_4 = dispatch_alerts()
    # Level changed from High to Very High and cooldown passed -> should send!
    assert sent_count_4 == 1
    assert len(fake.sent_messages) == 1
    assert fake.sent_messages[0]["recipient"] == "test_user_high@example.com"
    assert "VERY HIGH risk" in fake.sent_messages[0]["message"]

    # Verify alert_state updated and second alert_log row recorded
    with get_db() as conn:
        state = conn.execute("SELECT * FROM alert_state WHERE subscription_id = 901").fetchone()
        assert state["last_sent_level"] == "Very High"

        log_rows = conn.execute("SELECT * FROM alert_log WHERE subscription_id = 901").fetchall()
        assert len(log_rows) == 2
        assert log_rows[1]["risk_level"] == "Very High"
