"""
scheduler.py - Background APScheduler for periodic weather polling
====================================================================
Runs an in-process BackgroundScheduler (single worker) that periodically
fetches live rainfall for all 18 segments in one batch, updates the in-memory
weather cache, and atomically persists data/rain_snapshot.json.

Guaranteed to never crash the main application on network or parser failures.
Controlled via ENABLE_SCHEDULER and WEATHER_POLL_MINUTES environment variables.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app import config
from app import risk_service
from app.logger import logger

_scheduler: Optional[BackgroundScheduler] = None
_scheduler_status: dict = {
    "last_run": None,
    "last_status": "not_started",
}


def poll_weather_job() -> None:
    """
    Periodic job: fetches weather for all stations in one batch,
    refreshes the in-memory cache, and atomically writes the rain snapshot.
    Failures are logged and never bubble up or crash the process.
    """
    logger.info("scheduler: starting scheduled weather poll job...")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        segments = risk_service.load_segments()
        # Reset cache timestamp and failure cache to force fresh retrieval from live Open-Meteo API
        risk_service._rain_cache["t"] = 0.0
        risk_service._fail_cache.update(t=0.0, data=None, meta=None)
        if config.PER_SEGMENT_WEATHER:
            try:
                from app import weather_service
                weather_service._rain_cache["t"] = 0.0
                weather_service._fail_cache.update(t=0.0, data=None, meta=None)
            except Exception:
                pass

        rain_data, meta = risk_service.fetch_rainfall_with_metadata(segments)
        _scheduler_status["last_run"] = now_iso
        _scheduler_status["last_status"] = f"ok (source: {meta.get('weather_source')})"
        logger.info(
            "scheduler: weather poll completed successfully (source: %s, segments: %d)",
            meta.get("weather_source"),
            len(rain_data) if rain_data else 0,
        )
    except Exception as e:
        _scheduler_status["last_run"] = now_iso
        _scheduler_status["last_status"] = f"error: {type(e).__name__}: {e}"
        logger.error("scheduler: weather poll encountered error: %s", e, exc_info=True)


def start_scheduler() -> Optional[BackgroundScheduler]:
    """
    Starts the APScheduler BackgroundScheduler if not already running.
    Gated by config.ENABLE_SCHEDULER.
    """
    global _scheduler
    if not config.ENABLE_SCHEDULER:
        logger.info("scheduler: ENABLE_SCHEDULER is false; scheduler will not start.")
        return None

    if _scheduler is not None and _scheduler.running:
        logger.debug("scheduler: already running.")
        return _scheduler

    logger.info(
        "scheduler: initializing BackgroundScheduler (interval: %d minutes)...",
        config.WEATHER_POLL_MINUTES,
    )
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        poll_weather_job,
        trigger="interval",
        minutes=config.WEATHER_POLL_MINUTES,
        id="weather_poll_batch",
        replace_existing=True,
    )
    from app.alert_dispatcher import dispatch_alerts
    _scheduler.add_job(
        dispatch_alerts,
        trigger="interval",
        minutes=config.ALERT_DISPATCH_INTERVAL_MINUTES,
        id="alert_dispatcher_job",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("scheduler: BackgroundScheduler started successfully.")
    return _scheduler


def shutdown_scheduler() -> None:
    """Gracefully shuts down the background scheduler if running."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("scheduler: shutting down BackgroundScheduler...")
        try:
            _scheduler.shutdown(wait=False)
        except Exception as e:
            logger.warning("scheduler: exception during shutdown: %s", e)
        finally:
            _scheduler = None
            logger.info("scheduler: BackgroundScheduler shutdown complete.")


def get_scheduler_last_run() -> Optional[str]:
    """Returns ISO UTC timestamp string of the last scheduler run, or None."""
    return _scheduler_status.get("last_run")


def get_scheduler_status() -> dict:
    """Returns scheduler operational status dictionary."""
    is_running = _scheduler is not None and _scheduler.running
    return {
        "enabled": config.ENABLE_SCHEDULER,
        "running": is_running,
        "poll_interval_minutes": config.WEATHER_POLL_MINUTES,
        "last_run": _scheduler_status.get("last_run"),
        "last_status": _scheduler_status.get("last_status"),
    }
