"""
app/notifiers/telegram.py - Telegram Bot API notifier
"""
import logging
import httpx
from app import config
from app.notifiers.base import BaseNotifier

log = logging.getLogger("notifiers.telegram")


class TelegramNotifier(BaseNotifier):
    """Delivers alert messages to Telegram chats via the official HTTP Bot API."""

    def __init__(self, bot_token: str | None = None):
        self.bot_token = bot_token or config.TELEGRAM_BOT_TOKEN

    def send(self, recipient: str, message: str, channel: str = "telegram") -> bool:
        if config.DRY_RUN or not self.bot_token:
            formatted = f"[DRY RUN TELEGRAM] Chat ID: {recipient} | Message: {message}"
            print(formatted)
            log.info(formatted)
            return True

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": recipient,
            "text": message,
            "disable_web_page_preview": True,
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    log.info("Telegram alert delivered successfully to chat %s", recipient)
                    return True
                else:
                    log.warning("Telegram Bot API returned HTTP %s: %s", resp.status_code, resp.text)
                    return False
        except Exception as e:
            log.error("Failed sending Telegram alert to %s: %s", recipient, e)
            return False
