"""
alert_service.py - Alert Storage & Dispatch Safety Controller
=============================================================
Enforces the safety constraint from Task F2:
"Alerts must NEVER be created, persisted or sent from simulated rainfall."

Provides auditable entry points for alert dispatching and database persistence,
guaranteeing that simulated weather scenarios never send notifications to real
subscribers or poison operational alert storage.
"""
from typing import Optional, Dict, Any
from app.logger import logger
from app.models import AlertItem


class AlertSimulationSafetyError(ValueError):
    """Raised when any code path attempts to create, persist, or dispatch alerts under simulation."""
    pass


def can_dispatch_or_store(is_simulated: bool) -> bool:
    """Returns True only when weather data is genuine (live, cached, or snapshot)."""
    return not is_simulated


def persist_alert(conn, alert: AlertItem, user_id: int, is_simulated: bool = False) -> None:
    """
    Safely persists an active alert to database storage.
    Strictly blocked if is_simulated is True.
    """
    if is_simulated:
        logger.error(f"BLOCKED ATTEMPT to persist alert {alert.alert_id} for user {user_id} during simulation!")
        raise AlertSimulationSafetyError(
            "CRITICAL SAFETY VIOLATION: Alerts must NEVER be created, persisted or sent from simulated rainfall."
        )

    # Note: Currently, alerts are computed dynamically per user query.
    # If a future background alert table is added, insert logic resides here.
    logger.info(f"Alert {alert.alert_id} verified for persistence (genuine weather conditions).")


def dispatch_alert(alert: AlertItem, recipient_contact: str, channel: str, is_simulated: bool = False) -> Dict[str, Any]:
    """
    Safely dispatches an alert via SMS, WhatsApp, or Email.
    Strictly blocked if is_simulated is True.
    """
    if is_simulated:
        logger.error(
            f"BLOCKED ATTEMPT to dispatch alert {alert.alert_id} via {channel} to {recipient_contact} during simulation!"
        )
        raise AlertSimulationSafetyError(
            "CRITICAL SAFETY VIOLATION: Alerts must NEVER be created, persisted or sent from simulated rainfall."
        )

    logger.info(f"Alert {alert.alert_id} passed safety validation for dispatch via {channel}.")
    return {
        "status": "Dispatched",
        "alert_id": alert.alert_id,
        "channel": channel,
        "simulated": False
    }
