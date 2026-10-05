"""
app/notifiers - Multichannel alert notification system
"""
from typing import Optional

from app.notifiers.base import BaseNotifier
from app.notifiers.console import ConsoleNotifier
from app.notifiers.telegram import TelegramNotifier
from app.notifiers.twilio import TwilioNotifier

_fake_notifier: Optional[BaseNotifier] = None


def set_fake_notifier(notifier: Optional[BaseNotifier]) -> None:
    """Configures a mock/fake notifier for test isolation."""
    global _fake_notifier
    _fake_notifier = notifier


def get_fake_notifier() -> Optional[BaseNotifier]:
    """Retrieves active test notifier if set."""
    return _fake_notifier


def get_notifier(channel: str = "console") -> BaseNotifier:
    """
    Factory resolving the appropriate notifier instance based on channel type.
    Honors test notifier override when active.
    """
    if _fake_notifier is not None:
        return _fake_notifier

    ch = channel.lower().strip()
    if ch == "telegram":
        return TelegramNotifier()
    elif ch in ("sms", "whatsapp"):
        return TwilioNotifier()
    else:
        return ConsoleNotifier()


__all__ = [
    "BaseNotifier",
    "ConsoleNotifier",
    "TelegramNotifier",
    "TwilioNotifier",
    "get_notifier",
    "set_fake_notifier",
    "get_fake_notifier",
]
