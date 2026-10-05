"""
app/notifiers/twilio.py - Twilio SMS and WhatsApp alert notifier
"""
import logging
import httpx
from app import config
from app.notifiers.base import BaseNotifier

log = logging.getLogger("notifiers.twilio")


class TwilioNotifier(BaseNotifier):
    """Delivers SMS and WhatsApp emergency alerts via the Twilio REST API."""

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ):
        self.account_sid = account_sid or config.TWILIO_ACCOUNT_SID
        self.auth_token = auth_token or config.TWILIO_AUTH_TOKEN
        self.from_number = from_number or config.TWILIO_FROM

    def send(self, recipient: str, message: str, channel: str = "sms") -> bool:
        ch = channel.lower()
        if config.DRY_RUN or not (self.account_sid and self.auth_token and self.from_number):
            formatted = f"[DRY RUN TWILIO {ch.upper()}] To: {recipient} | Message: {message}"
            print(formatted)
            log.info(formatted)
            return True

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

        if ch == "whatsapp":
            from_target = self.from_number if self.from_number.startswith("whatsapp:") else f"whatsapp:{self.from_number}"
            to_target = recipient if recipient.startswith("whatsapp:") else f"whatsapp:{recipient}"
        else:
            from_target = self.from_number
            to_target = recipient

        data = {
            "From": from_target,
            "To": to_target,
            "Body": message,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    url,
                    data=data,
                    auth=(self.account_sid, self.auth_token),
                )
                if 200 <= resp.status_code < 300:
                    log.info("Twilio %s alert delivered successfully to %s", ch, recipient)
                    return True
                else:
                    log.warning("Twilio API error HTTP %s: %s", resp.status_code, resp.text)
                    return False
        except Exception as e:
            log.error("Failed sending Twilio %s alert to %s: %s", ch, recipient, e)
            return False
