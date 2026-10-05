"""
app/notifiers/console.py - Console print notifier
"""
import logging
from app.notifiers.base import BaseNotifier

log = logging.getLogger("notifiers.console")


class ConsoleNotifier(BaseNotifier):
    """Fallback notifier that outputs structured alerts to standard output and logger."""

    def send(self, recipient: str, message: str, channel: str = "console") -> bool:
        formatted = f"[ALERT DISPATCH] [{channel.upper()}] To: {recipient} | Message: {message}"
        print(formatted)
        log.info(formatted)
        return True
