"""
app/bot/telegram_bot.py - Long-polling Telegram bot for NH-7 landslide alerts & queries
========================================================================================
Runs as a background thread without requiring public webhooks.
Commands supported:
- /start: Welcome message & cheat-sheet
- /status <segment>: Live risk evaluation with real weather (fuzzy match on name or ID)
- /route <from> <to>: Route risk & travel recommendation
- /subscribe <segment>: Subscribes chat_id in the existing subscriptions table
- /unsubscribe: Removes all telegram subscriptions for this chat_id
- /lang en|hi: Sets language preference
"""
from __future__ import annotations

import difflib
import logging
import threading
import time
from typing import Dict, Any, Optional, List, Tuple

import httpx

from app import config
from app.database import get_db
from app.notifiers import get_notifier, TelegramNotifier
from app.risk_service import load_segments, get_live_risk_map_with_metadata

log = logging.getLogger("telegram_bot")

_bot_thread: Optional[threading.Thread] = None
_bot_running: bool = False
_user_langs: Dict[str, str] = {}


def fuzzy_match_segment(query: str, segments: List[dict]) -> Optional[dict]:
    """
    Fuzzy matches user input string against segment IDs, names, or waypoint locations.
    """
    q = query.lower().strip().replace(" ", "").replace("_", "").replace("-", "")
    if not q:
        return None

    # 1. Exact or normalized ID match (e.g. "seg08", "08", "8")
    for s in segments:
        s_id_clean = s["id"].lower().replace("_", "")
        if q == s_id_clean or q == s["id"].lower():
            return s
        num_part = s["id"].replace("seg_", "").lstrip("0")
        if q == num_part or q == f"seg{num_part}":
            return s

    # 2. Substring match on name
    for s in segments:
        s_name_clean = s["name"].lower().replace(" ", "").replace("-", "")
        if q in s_name_clean:
            return s

    # 3. Known landmark / hotspot mappings along NH-7
    HOTSPOT_MAP = {
        "sirobagarh": "seg_09",
        "kaliasaur": "seg_09",
        "byasi": "seg_03",
        "shivpuri": "seg_01",
        "kaudiyala": "seg_03",
        "devprayag": "seg_04",
        "maletha": "seg_05",
        "kirtinagar": "seg_06",
        "srinagar": "seg_07",
        "narkota": "seg_08",
        "rudraprayag": "seg_09",
        "gholtir": "seg_10",
        "gauchar": "seg_11",
        "karnaprayag": "seg_12",
        "langasu": "seg_13",
        "nandprayag": "seg_14",
        "chamoli": "seg_15",
        "pipalkoti": "seg_16",
        "tangni": "seg_17",
        "pagalnala": "seg_17",
        "helang": "seg_18",
        "joshimath": "seg_18",
        "rishikesh": "seg_01",
    }
    for landmark, target_id in HOTSPOT_MAP.items():
        if landmark in q or q in landmark:
            for s in segments:
                if s["id"] == target_id:
                    return s

    # 4. Difflib close match on name tokens
    names = [s["name"] for s in segments]
    matches = difflib.get_close_matches(query, names, n=1, cutoff=0.4)
    if matches:
        matched_name = matches[0]
        return next(s for s in segments if s["name"] == matched_name)

    return None


def handle_telegram_command(chat_id: int | str, text: str) -> str:
    """
    Pure command handler taking chat_id and input text, returning the response text.
    Allows unit testing with zero network overhead.
    """
    chat_key = str(chat_id)
    lang = _user_langs.get(chat_key, "en")
    msg = text.strip()
    cmd = msg.split()[0].lower() if msg else ""
    args = msg.split()[1:] if len(msg.split()) > 1 else []

    # Command: /lang en|hi
    if cmd == "/lang":
        if args and args[0].lower() in ("hi", "hindi"):
            _user_langs[chat_key] = "hi"
            return "भाषा हिंदी में सेट की गई है। सहायता के लिए /start भेजें।"
        else:
            _user_langs[chat_key] = "en"
            return "Language set to English. Send /start for command list."

    # Command: /start
    if cmd == "/start":
        if lang == "hi":
            return (
                "नमस्ते! मैं एनएच-7 भूस्खलन पूर्व चेतावनी बॉट हूँ।\n\n"
                "उपलब्ध आदेश:\n"
                "• /status <खंड> - सड़क खंड का वास्तविक जोखिम देखें (उदा. /status सिरोबगड़)\n"
                "• /route <शुरुआत> <अंत> - यात्रा मार्ग का मूल्यांकन (उदा. /route ऋषिकेश जोशीमठ)\n"
                "• /subscribe <खंड> - इस खंड के उच्च जोखिम अलर्ट प्राप्त करें\n"
                "• /unsubscribe - अपने अलर्ट बंद करें\n"
                "• /lang en|hi - भाषा बदलें"
            )
        return (
            "Welcome to the NH-7 Landslide Early Warning Bot (Rishikesh - Joshimath corridor).\n\n"
            "Commands:\n"
            "• /status <segment> - Live segment hazard (e.g. /status Sirobagarh or /status seg_08)\n"
            "• /route <from> <to> - Evaluate trip route risk (e.g. /route Rishikesh Joshimath)\n"
            "• /subscribe <segment> - Receive high-risk emergency alerts for this sector\n"
            "• /unsubscribe - Remove alert subscriptions\n"
            "• /lang en|hi - Switch between English and Hindi"
        )

    # Command: /status <segment>
    if cmd == "/status":
        if not args:
            return "Usage: /status <segment id or name> (e.g. /status Sirobagarh or /status seg_08)"

        query = " ".join(args)
        live_segs, _ = get_live_risk_map_with_metadata(simulate_rain_mm=None)
        matched = fuzzy_match_segment(query, live_segs)
        if not matched:
            return f"Segment '{query}' not found. Please specify a corridor sector (e.g. seg_01 to seg_18, Byasi, Devprayag, Sirobagarh, Helang)."

        risk_lvl = matched.get("adjusted_risk_level") or matched.get("risk_level", "Low")
        risk_idx = matched.get("risk_index", matched.get("risk_score", 0.0))
        rain_3d = matched.get("rain_mm_3d", 0.0)
        driver = matched.get("main_driver", "Physical terrain baseline")
        closure = matched.get("closure")

        closure_txt = f"\n⛔ CLOSURE ACTIVE: {closure['status'].upper()} - {closure['reason']}" if closure else ""

        if lang == "hi":
            return (
                f"एनएच-7 {matched['id']}: {matched['name']}\n"
                f"जोखिम स्तर: {risk_lvl} (सूचकांक: {risk_idx:.2f})\n"
                f"3-दिवसीय वर्षा: {rain_3d:.1f} मिमी\n"
                f"कारक: {driver}{closure_txt}"
            )

        return (
            f"NH-7 {matched['id']}: {matched['name']}\n"
            f"Risk Level: {risk_lvl} (Index: {risk_idx:.2f})\n"
            f"3-Day Rain: {rain_3d:.1f} mm\n"
            f"Primary Driver: {driver}{closure_txt}"
        )

    # Command: /route <from> <to>
    if cmd == "/route":
        if len(args) < 2:
            return "Usage: /route <from> <to> (e.g. /route Rishikesh Joshimath)"

        live_segs, _ = get_live_risk_map_with_metadata(simulate_rain_mm=None)
        s_from = fuzzy_match_segment(args[0], live_segs)
        s_to = fuzzy_match_segment(args[1], live_segs)

        if not s_from or not s_to:
            return "Could not match origin or destination. Use sector names like Rishikesh, Byasi, Srinagar, Joshimath."

        # Compute segments along route
        seq1, seq2 = s_from["sequence_order"], s_to["sequence_order"]
        low, high = min(seq1, seq2), max(seq1, seq2)
        route = [s for s in live_segs if low <= s["sequence_order"] <= high]

        LEVEL_ORDER = {"Low": 0, "Moderate": 1, "High": 2, "Very High": 3}
        max_seg = max(route, key=lambda s: LEVEL_ORDER.get(s.get("adjusted_risk_level") or s.get("risk_level", "Low"), 0))
        max_level = max_seg.get("adjusted_risk_level") or max_seg.get("risk_level", "Low")

        has_closure = any(s.get("closure") and s["closure"]["status"] == "closed" for s in route)

        if has_closure:
            rec = "AVOID - Active road closure on planned route."
        elif max_level in ("High", "Very High"):
            rec = "CAUTION / DELAY - Severe slope failure risk detected."
        else:
            rec = "GO - Favorable highway conditions."

        if lang == "hi":
            return (
                f"मार्ग: {s_from['name']} ➔ {s_to['name']} ({len(route)} खंड)\n"
                f"अधिकतम जोखिम: {max_level} ({max_seg['name']})\n"
                f"अनुशंसा: {rec}"
            )

        return (
            f"Route: {s_from['name']} ➔ {s_to['name']} ({len(route)} sectors)\n"
            f"Max Risk: {max_level} on {max_seg['name']}\n"
            f"Recommendation: {rec}"
        )

    # Command: /subscribe <segment>
    if cmd == "/subscribe":
        if not args:
            return "Usage: /subscribe <segment> (e.g. /subscribe Sirobagarh or /subscribe seg_09)"

        query = " ".join(args)
        segs = load_segments()
        matched = fuzzy_match_segment(query, segs)
        if not matched:
            return f"Segment '{query}' not recognized along NH-7 corridor."

        seg_id = matched["id"]
        with get_db() as conn:
            cursor = conn.cursor()
            # Clean existing telegram subscription for this chat to avoid duplicates
            cursor.execute("DELETE FROM subscriptions WHERE phone_or_email = ? AND channel = 'telegram'", (chat_key,))
            cursor.execute("""
                INSERT INTO subscriptions (name, phone_or_email, segment_id, channel, consent, created_at)
                VALUES (?, ?, ?, 'telegram', 1, ?)
            """, (f"Telegram User {chat_key}", chat_key, seg_id, time.strftime("%Y-%m-%dT%H:%M:%SZ")))

        if lang == "hi":
            return f"सफलतापूर्वक एनएच-7 {matched['name']} ({seg_id}) के अलर्ट के लिए सदस्यता ले ली गई है।"

        return f"Successfully subscribed to emergency alerts for NH-7 {matched['name']} ({seg_id})."

    # Command: /unsubscribe
    if cmd == "/unsubscribe":
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscriptions WHERE phone_or_email = ? AND channel = 'telegram'", (chat_key,))
            cursor.execute("DELETE FROM alert_state WHERE subscription_id NOT IN (SELECT id FROM subscriptions)")

        if lang == "hi":
            return "एनएच-7 अलर्ट की सदस्यता समाप्त कर दी गई है।"

        return "Unsubscribed from NH-7 Telegram alerts."

    return "Unknown command. Send /start to view available commands."


def process_update(update: dict) -> Optional[str]:
    """
    Processes a single Telegram Bot API update payload.
    Dispatches command and replies using TelegramNotifier.
    """
    message = update.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return None

    reply = handle_telegram_command(chat_id, text)
    notifier = get_notifier("telegram")
    notifier.send(recipient=str(chat_id), message=reply, channel="telegram")
    return reply


def _polling_worker():
    """Background polling worker fetching updates using long polling."""
    global _bot_running
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        log.info("telegram_bot: TELEGRAM_BOT_TOKEN not configured; polling worker idle.")
        return

    log.info("telegram_bot: Starting Telegram long polling worker...")
    offset = 0

    while _bot_running:
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {"timeout": 20, "offset": offset}

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    updates = data.get("result", [])
                    for u in updates:
                        offset = max(offset, u["update_id"] + 1)
                        process_update(u)
                else:
                    log.warning("telegram_bot: getUpdates HTTP %s: %s", resp.status_code, resp.text)
                    time.sleep(5)
        except Exception as e:
            log.warning("telegram_bot: polling network error: %s", e)
            time.sleep(5)


def start_telegram_bot() -> Optional[threading.Thread]:
    """Starts the Telegram bot background polling worker thread."""
    global _bot_thread, _bot_running
    if not (config.ENABLE_TELEGRAM_BOT and config.TELEGRAM_BOT_TOKEN):
        log.info("telegram_bot: Bot disabled or token unset (ENABLE_TELEGRAM_BOT=%s)", config.ENABLE_TELEGRAM_BOT)
        return None

    if _bot_running and _bot_thread and _bot_thread.is_alive():
        return _bot_thread

    _bot_running = True
    _bot_thread = threading.Thread(target=_polling_worker, name="TelegramBotPolling", daemon=True)
    _bot_thread.start()
    log.info("telegram_bot: Thread started.")
    return _bot_thread


def stop_telegram_bot() -> None:
    """Stops the Telegram bot polling worker."""
    global _bot_running, _bot_thread
    _bot_running = False
    _bot_thread = None
    log.info("telegram_bot: Stopped.")
