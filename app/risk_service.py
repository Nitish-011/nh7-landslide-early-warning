"""
risk_service.py - STEP 4: live risk for the backend (/risk-map)
================================================================
Copy this file and segment_static_scores.json into your FastAPI project (e.g. app/).

  risk_score = TERRAIN_WEIGHT * terrain_percentile + RAIN_WEIGHT * min(rain_mm / RAIN_REF_MM, 1)

* terrain_percentile : 0..1 rank of the segment's modelled terrain susceptibility among the 18 segments
                       (from the trained model; it is a RANKING, not a probability).
* rain_mm            : rain over yesterday + today + tomorrow at the segment midpoint (Open-Meteo forecast API).
* The weights and RAIN_REF_MM are DEMO HEURISTICS, not calibrated and not learned. Say so if asked.
  Replace them with published Himalayan rainfall thresholds, or with the rainfall coefficient from the Mey et al.
  (2024) supplement, if you want to cite a source.
* If the rainfall service is down the segment keeps its terrain-only score and reports rain_status="unavailable".
* DEMO MODE: pass simulate_rain_mm (e.g. /risk-map?simulate_rain_mm=120) to show what a storm would do. Every segment
  is then labelled rain_status="simulated" so it can never be mistaken for a real reading.

Wire it into the existing route (example):

    from app.risk_service import get_live_risk_map

    @router.get("/risk-map")
    def risk_map(simulate_rain_mm: float | None = None):      # optional demo switch, see DEMO MODE above
        try:
            segments = get_live_risk_map(simulate_rain_mm=simulate_rain_mm)
        except Exception:
            logger.exception("live risk failed; serving seeded mock data instead")
            return existing_mock_response()          # keep your current implementation as the fallback
        return {"total_segments": len(segments),
                "high_risk_count": sum(s["risk_level"] in ("High", "Very High") for s in segments),
                "segments": segments}
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger("backend")

SCORES_FILE = Path(__file__).with_name("segment_static_scores.json")
TERRAIN_WEIGHT = 0.6
RAIN_WEIGHT = 0.4
RAIN_REF_MM = 100.0                  # 3-day rainfall at which the rain term saturates (demo heuristic)

# Uncalibrated heuristic threshold: in dry conditions without significant triggering rainfall
# (i.e. when rain_status == 'ok' and 3-day rainfall is below 25 mm), slope failure risk is
# capped at "Moderate". Note: This threshold is an uncalibrated heuristic reflecting that
# rainfall is the primary trigger for catastrophic slope mass movements in the Garhwal Himalayas.
DRY_CAP_MM = 25.0

LEVEL_CUTS = [(0.75, "Very High"), (0.50, "High"), (0.25, "Moderate"), (0.0, "Low")]
CACHE_TTL_S = 1800                   # re-query rainfall at most every 30 minutes
FAILED_CACHE_TTL_S = 300             # cache a failed fetch for 5 minutes so requests do not keep blocking
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
RAIN_SNAPSHOT_FILE = Path(__file__).resolve().parent.parent / "data" / "rain_snapshot.json"

CORRIDOR_NAME = "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)"

try:
    from app.seed_data import SEED_SEGMENTS
    SUBPOINTS_MAP = {s["id"]: s.get("subpoints", []) for s in SEED_SEGMENTS}
except Exception:
    SUBPOINTS_MAP = {}

_segments_cache = None
_rain_cache = {"t": 0.0, "data": None, "fetched_at": None}
_fail_cache = {"t": 0.0, "data": None, "meta": None}


def level_for(score: float, rain_status: str = "unavailable", rain_mm: float | None = None) -> str:
    lvl = "Low"
    for cut, name in LEVEL_CUTS:
        if score >= cut:
            lvl = name
            break
    # Uncalibrated heuristic: if rainfall measurement is valid ('ok' or 'cached') and 3-day precipitation is below DRY_CAP_MM,
    # cap risk level at Moderate to avoid false alarm saturation during dry weather.
    if (rain_status == "ok" or str(rain_status).startswith("cached")) and rain_mm is not None and rain_mm < DRY_CAP_MM:
        if lvl in ("High", "Very High"):
            lvl = "Moderate"
    return lvl


def load_segments(path=None):
    global _segments_cache
    if _segments_cache is None:
        path = Path(path or SCORES_FILE)
        _segments_cache = json.loads(path.read_text(encoding="utf-8"))
        log.info("risk_service: loaded %d scored segments from %s", len(_segments_cache), path)
    return _segments_cache


def load_snapshot(segments):
    """
    Loads snapshot from data/rain_snapshot.json if available;
    returns (formatted_segment_map, timestamp_iso) or (None, None).
    """
    if not RAIN_SNAPSHOT_FILE.exists():
        return None, None
    try:
        raw = json.loads(RAIN_SNAPSHOT_FILE.read_text(encoding="utf-8"))
        snap_time = raw.get("timestamp") or "unknown"
        snap_data = raw.get("data", {})
        result = {}
        for s in segments:
            item = snap_data.get(s["id"], {})
            result[s["id"]] = {
                "rain_mm": item.get("rain_mm"),
                "status": f"cached ({snap_time})",
            }
        return result, snap_time
    except Exception as e:
        log.warning("risk_service: failed reading %s: %s", RAIN_SNAPSHOT_FILE, e)
        return None, None


def _calc_snapshot_meta(snap_time: str | None) -> dict:
    age_min = 0.0
    stale_warning = None
    if snap_time and snap_time != "unknown":
        try:
            clean_iso = snap_time.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_s = (datetime.now(timezone.utc) - dt).total_seconds()
            age_min = round(max(0.0, age_s / 60.0), 1)
        except Exception:
            age_min = 0.0

    if age_min > 360.0:  # > 6 hours
        hours = round(age_min / 60.0, 1)
        stale_warning = f"Weather data is {hours}h old (using snapshot from {snap_time})."

    return {
        "weather_source": "snapshot",
        "weather_fetched_at": snap_time,
        "weather_age_minutes": age_min,
        "is_simulated": False,
        "stale_warning": stale_warning,
    }


def fetch_rainfall_with_metadata(segments, session=None, simulate_rain_mm=None) -> tuple[dict, dict]:
    """
    Returns (rain_dict, weather_meta).
    weather_meta tracks:
      - weather_source: 'live' | 'cached' | 'snapshot' | 'simulated' | 'unavailable'
      - weather_fetched_at: ISO UTC string
      - weather_age_minutes: float
      - is_simulated: bool
      - stale_warning: string if age > 6 hours, else None
    """
    if simulate_rain_mm is not None:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rain = {s["id"]: {"rain_mm": float(simulate_rain_mm), "status": "simulated"} for s in segments}
        meta = {
            "weather_source": "simulated",
            "weather_fetched_at": now_iso,
            "weather_age_minutes": 0.0,
            "is_simulated": True,
            "stale_warning": None,
        }
        return rain, meta

    now = time.time()

    # 1. Fresh in-memory cache check (30 minutes)
    if _rain_cache.get("data") is not None and now - _rain_cache.get("t", 0.0) < CACHE_TTL_S:
        age_min = round(max(0.0, (now - _rain_cache.get("t", now)) / 60.0), 1)
        meta = {
            "weather_source": "cached",
            "weather_fetched_at": _rain_cache.get("fetched_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "weather_age_minutes": age_min,
            "is_simulated": False,
            "stale_warning": None,
        }
        return _rain_cache["data"], meta

    # 2. Check if a recent failure occurred within 5 minutes so requests do not keep blocking
    if now - _fail_cache.get("t", 0.0) < FAILED_CACHE_TTL_S and _fail_cache.get("data") is not None:
        meta = _fail_cache.get("meta")
        if not meta:
            meta = {
                "weather_source": "snapshot" if "cached" in str(_fail_cache["data"]) else "unavailable",
                "weather_fetched_at": None,
                "weather_age_minutes": None,
                "is_simulated": False,
                "stale_warning": None,
            }
        return _fail_cache["data"], meta

    # 3. Attempt live fetch with 4 second timeout
    session = session or requests.Session()
    mids = [((s["start_lat"] + s["end_lat"]) / 2, (s["start_lng"] + s["end_lng"]) / 2) for s in segments]
    params = {"latitude": ",".join(f"{m[0]:.4f}" for m in mids), "longitude": ",".join(f"{m[1]:.4f}" for m in mids),
              "daily": "precipitation_sum", "past_days": 1, "forecast_days": 2, "timezone": "Asia/Kolkata"}

    try:
        r = session.get(OPEN_METEO, params=params, timeout=4)
        r.raise_for_status()
        payload = r.json()
        items = payload if isinstance(payload, list) else [payload]
        if len(items) != len(segments):
            raise ValueError(f"expected {len(segments)} locations, got {len(items)}")

        result = {}
        for s, item in zip(segments, items):
            vals = [v for v in (item.get("daily", {}).get("precipitation_sum") or []) if v is not None]
            if vals:
                result[s["id"]] = {"rain_mm": float(sum(vals)), "status": "ok"}
            else:
                result[s["id"]] = {"rain_mm": None, "status": "unavailable"}

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _rain_cache.update(t=now, data=result, fetched_at=now_iso)
        _fail_cache.update(t=0.0, data=None, meta=None)
        log.info("risk_service: rainfall refreshed for %d segments", len(segments))

        meta = {
            "weather_source": "live",
            "weather_fetched_at": now_iso,
            "weather_age_minutes": 0.0,
            "is_simulated": False,
            "stale_warning": None,
        }

        # On success also write result to data/rain_snapshot.json
        try:
            RAIN_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
            snap_payload = {
                "timestamp": now_iso,
                "data": result,
            }
            RAIN_SNAPSHOT_FILE.write_text(json.dumps(snap_payload, indent=2), encoding="utf-8")
            log.info("risk_service: saved rain snapshot to %s", RAIN_SNAPSHOT_FILE)
        except Exception as se:
            log.warning("risk_service: failed saving rain snapshot: %s", se)

        return result, meta

    except Exception as e:
        log.warning("risk_service: rainfall fetch failed (%s: %s); caching failure for 5m", type(e).__name__, e)
        _fail_cache["t"] = now

        # If live call fails and snapshot exists, use it and set rain_status to "cached" with snapshot time
        snap, snap_time = load_snapshot(segments)
        if snap is not None:
            log.info("risk_service: using cached rain snapshot from %s", RAIN_SNAPSHOT_FILE)
            meta = _calc_snapshot_meta(snap_time)
            _fail_cache["data"] = snap
            _fail_cache["meta"] = meta
            return snap, meta

        # Only fall back to terrain-only when there is neither
        fallback_data = {s["id"]: {"rain_mm": None, "status": "unavailable"} for s in segments}
        meta = {
            "weather_source": "unavailable",
            "weather_fetched_at": None,
            "weather_age_minutes": None,
            "is_simulated": False,
            "stale_warning": "Weather data unavailable; using terrain-only risk assessment.",
        }
        _fail_cache["data"] = fallback_data
        _fail_cache["meta"] = meta
        return fallback_data, meta


def fetch_rainfall(segments, session=None, simulate_rain_mm=None):
    """Backwards-compatible wrapper returning dict of segment rain info."""
    data, _ = fetch_rainfall_with_metadata(segments, session=session, simulate_rain_mm=simulate_rain_mm)
    return data


def compute_segment(seg, rain, force_terrain_only: bool = False):
    terrain = seg.get("terrain_percentile")
    terrain_status = "ok" if terrain is not None else "no_data"
    terrain = 0.5 if terrain is None else float(terrain)       # missing data is NEUTRAL, never "safest"
    
    if force_terrain_only:
        rain_mm = None
        rain_status = "not_factored_future_date"
        rain_index = 0.0
        score = min(TERRAIN_WEIGHT * terrain, 1.0)
    else:
        rain_status = rain.get("status", "unavailable")
        is_valid_rain = rain_status in ("ok", "simulated") or str(rain_status).startswith("cached")
        rain_mm = rain.get("rain_mm") if is_valid_rain else None
        rain_index = min(rain_mm / RAIN_REF_MM, 1.0) if rain_mm is not None else 0.0
        score = min(TERRAIN_WEIGHT * terrain + RAIN_WEIGHT * rain_index, 1.0)

    risk_lvl = level_for(score, rain_status=rain_status, rain_mm=rain_mm)
    subpoints = seg.get("subpoints") or SUBPOINTS_MAP.get(seg["id"], [])

    return {
        "id": seg["id"],
        "name": seg["name"],
        "sequence_order": seg["sequence_order"],
        "start_lat": seg["start_lat"],
        "start_lng": seg["start_lng"],
        "end_lat": seg["end_lat"],
        "end_lng": seg["end_lng"],
        "subpoints": subpoints,
        "risk_level": risk_lvl,
        "risk_score": round(score, 2),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # additive keys from trained ML model & live rainfall engine:
        "terrain_percentile": round(terrain, 2),
        "terrain_level": level_for(TERRAIN_WEIGHT * terrain),
        "terrain_status": terrain_status,
        "rain_mm_3d": None if rain_mm is None else round(rain_mm, 1),
        "rain_status": rain_status,
        "main_driver": seg.get("driver"),
        "method": "terrain model ranking + live-rainfall heuristic (not calibrated)" if not force_terrain_only else "terrain model ranking (forecast beyond 48h)",
    }


def get_live_risk_map_with_metadata(session=None, simulate_rain_mm=None, force_terrain_only: bool = False) -> tuple[list[dict], dict]:
    """Returns (segment_list, weather_meta)."""
    segments = load_segments()
    if force_terrain_only:
        rain = {s["id"]: {"rain_mm": None, "status": "not_factored_future_date"} for s in segments}
        meta = {
            "weather_source": "terrain_only",
            "weather_fetched_at": None,
            "weather_age_minutes": None,
            "is_simulated": False,
            "stale_warning": None,
        }
    else:
        rain, meta = fetch_rainfall_with_metadata(segments, session, simulate_rain_mm)
    
    seg_list = [
        compute_segment(s, rain.get(s["id"], {"rain_mm": None, "status": "unavailable"}), force_terrain_only=force_terrain_only)
        for s in segments
    ]
    return seg_list, meta


def get_live_risk_map(session=None, simulate_rain_mm=None, force_terrain_only: bool = False):
    """Backwards-compatible wrapper returning only segment list."""
    segs, _ = get_live_risk_map_with_metadata(session=session, simulate_rain_mm=simulate_rain_mm, force_terrain_only=force_terrain_only)
    return segs
