"""
app/notifiers/base.py - Base interface for alert notifiers
"""
from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    """Abstract interface for sending alerts across various channels."""

    @abstractmethod
    def send(self, recipient: str, message: str, channel: str = "sms") -> bool:
        """
        Sends an alert message to a recipient.

        Args:
            recipient: Phone number, WhatsApp number, or Telegram chat_id.
            message: Plain text alert message (concise, non-alarmist).
            channel: Delivery channel ('sms', 'whatsapp', 'telegram', 'console').

        Returns:
            bool: True if delivered or logged successfully in dry-run mode, False otherwise.
        """
        pass
