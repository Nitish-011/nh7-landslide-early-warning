"""
weather_service.py - Multi-tiered resilient weather engine for NH-7
====================================================================
Implements:
  Tier 1: Single batched Open-Meteo request using midpoints of all 18 segments
          with hourly precipitation, past_days=3, forecast_days=3, timezone=UTC.
          Computes: r3d_mm (past 72h), rain_24h_mm, forecast_24h_mm, forecast_72h_mm,
          and peak_hour_utc & peak_mm in the next 24h.
  Tier 2: 5-station corridor reference fallback (Rishikesh, Srinagar, Rudraprayag,
          Karnaprayag, Joshimath) mapped to nearest segment midpoints.
  Tier 3: Snapshot fallback from data/rain_snapshot.json supporting both
          extended and legacy schemas.
  Tier 4: Neutral terrain-only fallback ('unavailable').

Preserves 4.0s timeout, circuit breaker (5m failure cache), and atomic snapshot persistence.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import requests

from app import config
from app.config import SNAPSHOT_PATH

log = logging.getLogger("backend")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT_S = 4.0
CACHE_TTL_S = 1800.0          # 30 minutes fresh cache
FAILED_CACHE_TTL_S = 300.0    # 5 minutes failure cache circuit breaker

# 5 Major Reference Stations along NH-7 corridor for Tier 2 fallback
STATIONS_5 = [
    {"id": "stn_rishikesh", "name": "Rishikesh", "lat": 30.0869, "lng": 78.2676},
    {"id": "stn_srinagar", "name": "Srinagar", "lat": 30.2230, "lng": 78.7840},
    {"id": "stn_rudraprayag", "name": "Rudraprayag", "lat": 30.2844, "lng": 78.9811},
    {"id": "stn_karnaprayag", "name": "Karnaprayag", "lat": 30.2577, "lng": 79.2155},
    {"id": "stn_joshimath", "name": "Joshimath", "lat": 30.5564, "lng": 79.5664},
]

# In-memory caches
_rain_cache: Dict[str, Any] = {"t": 0.0, "data": None, "fetched_at": None, "source": None}
_fail_cache: Dict[str, Any] = {"t": 0.0, "data": None, "meta": None}


def find_nearest_station(lat: float, lng: float) -> dict:
    """Finds the nearest of the 5 reference corridor stations by squared Euclidean distance."""
    best = STATIONS_5[0]
    best_dist = float("inf")
    for stn in STATIONS_5:
        d = (stn["lat"] - lat) ** 2 + (stn["lng"] - lng) ** 2
        if d < best_dist:
            best_dist = d
            best = stn
    return best


def compute_hourly_metrics(
    hourly_data: dict,
    ref_time: Optional[datetime] = None,
) -> dict:
    """
    Parses Open-Meteo hourly precipitation dictionary and computes:
      - r3d_mm (past 72h antecedent rainfall sum)
      - rain_24h_mm (past 24h antecedent rainfall sum)
      - forecast_24h_mm (next 24h forecast rainfall sum)
      - forecast_72h_mm (next 72h forecast rainfall sum)
      - peak_hour_utc (timestamp string of highest hour in next 24h)
      - peak_mm (maximum hourly rainfall mm in next 24h)
    """
    time_list: List[str] = hourly_data.get("time", [])
    raw_precip = hourly_data.get("precipitation", [])
    precip_list: List[float] = [float(p) if p is not None else 0.0 for p in raw_precip]

    if not time_list or not precip_list or len(time_list) != len(precip_list):
        return {
            "r3d_mm": None,
            "rain_24h_mm": None,
            "forecast_24h_mm": None,
            "forecast_72h_mm": None,
            "peak_hour_utc": None,
            "peak_mm": None,
        }

    now_utc = ref_time or datetime.now(timezone.utc)
    now_hour_str = now_utc.strftime("%Y-%m-%dT%H:00")

    # Locate index of current hour
    idx_now = -1
    for i, t in enumerate(time_list):
        if t <= now_hour_str:
            idx_now = i
        else:
            break

    if idx_now < 0:
        idx_now = 0
    elif idx_now >= len(time_list):
        idx_now = len(time_list) - 1

    # 1. Past 72h antecedent sum (up to and including idx_now)
    past_72_slice = precip_list[max(0, idx_now - 71) : idx_now + 1]
    r3d_mm = round(float(sum(past_72_slice)), 1) if past_72_slice else 0.0

    # 2. Past 24h antecedent sum
    past_24_slice = precip_list[max(0, idx_now - 23) : idx_now + 1]
    rain_24h_mm = round(float(sum(past_24_slice)), 1) if past_24_slice else 0.0

    # 3. Forecast next 24h (hours following idx_now)
    fc_24_slice = precip_list[idx_now + 1 : idx_now + 25]
    forecast_24h_mm = round(float(sum(fc_24_slice)), 1) if fc_24_slice else 0.0

    # 4. Forecast next 72h
    fc_72_slice = precip_list[idx_now + 1 : idx_now + 73]
    forecast_72h_mm = round(float(sum(fc_72_slice)), 1) if fc_72_slice else 0.0

    # 5. Peak hour & mm in next 24h
    if fc_24_slice:
        peak_val = max(fc_24_slice)
        peak_mm = round(float(peak_val), 1)
        rel_idx = fc_24_slice.index(peak_val)
        peak_raw_time = time_list[idx_now + 1 + rel_idx]
        peak_hour_utc = peak_raw_time if peak_raw_time.endswith("Z") else f"{peak_raw_time}Z"
    else:
        peak_mm = 0.0
        peak_hour_utc = None

    return {
        "r3d_mm": r3d_mm,
        "rain_24h_mm": rain_24h_mm,
        "forecast_24h_mm": forecast_24h_mm,
        "forecast_72h_mm": forecast_72h_mm,
        "peak_hour_utc": peak_hour_utc,
        "peak_mm": peak_mm,
    }


def load_snapshot_data(segments: list, snapshot_path: Optional[Path] = None) -> Tuple[Optional[dict], Optional[str]]:
    """
    Loads weather snapshot from disk supporting both extended and legacy schemas.
    Returns (segment_map, timestamp_iso) or (None, None).
    """
    path = Path(snapshot_path or SNAPSHOT_PATH).resolve()
    if not path.exists():
        return None, None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        snap_time = raw.get("timestamp") or "unknown"
        snap_data = raw.get("data", {})
        result = {}
        for s in segments:
            item = snap_data.get(s["id"], {})
            # Read r3d_mm with fallback to legacy rain_mm
            rain_mm = item.get("rain_mm")
            r3d_mm = item.get("r3d_mm", rain_mm)
            if r3d_mm is None and rain_mm is not None:
                r3d_mm = rain_mm

            result[s["id"]] = {
                "rain_mm": r3d_mm,
                "r3d_mm": r3d_mm,
                "rain_24h_mm": item.get("rain_24h_mm"),
                "forecast_24h_mm": item.get("forecast_24h_mm"),
                "forecast_72h_mm": item.get("forecast_72h_mm"),
                "peak_hour_utc": item.get("peak_hour_utc"),
                "peak_mm": item.get("peak_mm"),
                "status": f"cached ({snap_time})",
                "hourly": item.get("hourly"),
            }
        return result, snap_time
    except Exception as e:
        log.warning("weather_service: failed reading snapshot %s: %s", path, e)
        return None, None


def fetch_tier1_per_segment_hourly(segments: list, session: requests.Session) -> dict:
    """
    Tier 1: Batched Open-Meteo request querying midpoints of all 18 segments
    with hourly precipitation, past_days=3, forecast_days=3, timezone=UTC.
    """
    mids = [((s["start_lat"] + s["end_lat"]) / 2, (s["start_lng"] + s["end_lng"]) / 2) for s in segments]
    params = {
        "latitude": ",".join(f"{m[0]:.4f}" for m in mids),
        "longitude": ",".join(f"{m[1]:.4f}" for m in mids),
        "hourly": "precipitation",
        "past_days": 3,
        "forecast_days": 3,
        "timezone": "UTC",
    }
    r = session.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT_S)
    r.raise_for_status()
    payload = r.json()
    items = payload if isinstance(payload, list) else [payload]
    if len(items) != len(segments):
        raise ValueError(f"expected {len(segments)} locations, got {len(items)}")

    result = {}
    ref_now = datetime.now(timezone.utc)
    for s, item in zip(segments, items):
        metrics = compute_hourly_metrics(item.get("hourly", {}), ref_time=ref_now)
        r3d = metrics["r3d_mm"]
        result[s["id"]] = {
            "rain_mm": r3d,
            "r3d_mm": r3d,
            "rain_24h_mm": metrics["rain_24h_mm"],
            "forecast_24h_mm": metrics["forecast_24h_mm"],
            "forecast_72h_mm": metrics["forecast_72h_mm"],
            "peak_hour_utc": metrics["peak_hour_utc"],
            "peak_mm": metrics["peak_mm"],
            "status": "ok" if r3d is not None else "unavailable",
            "hourly": item.get("hourly", {}),
        }
    return result


def fetch_tier2_5station_fallback(segments: list, session: requests.Session) -> dict:
    """
    Tier 2: 5-station corridor reference fallback.
    Queries the 5 primary corridor towns and maps each segment to the nearest station.
    """
    stn_lats = [stn["lat"] for stn in STATIONS_5]
    stn_lngs = [stn["lng"] for stn in STATIONS_5]
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat in stn_lats),
        "longitude": ",".join(f"{lng:.4f}" for lng in stn_lngs),
        "daily": "precipitation_sum",
        "past_days": 1,
        "forecast_days": 2,
        "timezone": "Asia/Kolkata",
    }
    r = session.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT_S)
    r.raise_for_status()
    payload = r.json()
    items = payload if isinstance(payload, list) else [payload]
    if len(items) != len(STATIONS_5):
        raise ValueError(f"expected {len(STATIONS_5)} station readings, got {len(items)}")

    station_sums = {}
    for stn, item in zip(STATIONS_5, items):
        vals = [v for v in (item.get("daily", {}).get("precipitation_sum") or []) if v is not None]
        station_sums[stn["id"]] = float(sum(vals)) if vals else None

    result = {}
    for s in segments:
        mid_lat = (s["start_lat"] + s["end_lat"]) / 2
        mid_lng = (s["start_lng"] + s["end_lng"]) / 2
        nearest = find_nearest_station(mid_lat, mid_lng)
        r3d = station_sums.get(nearest["id"])

        result[s["id"]] = {
            "rain_mm": r3d,
            "r3d_mm": r3d,
            "rain_24h_mm": None,
            "forecast_24h_mm": None,
            "forecast_72h_mm": None,
            "peak_hour_utc": None,
            "peak_mm": None,
            "status": "cached_5station" if r3d is not None else "unavailable",
        }
    return result


def fetch_weather_pipeline(
    segments: list,
    session: Optional[requests.Session] = None,
    simulate_rain_mm: Optional[float] = None,
) -> Tuple[dict, dict]:
    """
    Main resilient weather pipeline returning (segment_weather_dict, weather_meta).
    Follows:
      1. Simulation check (immediate synthetic values, marked is_simulated=True).
      2. Memory cache check (30 min TTL).
      3. Failure cache check (5 min circuit breaker).
      4. Tier 1: Per-segment 18-midpoint hourly batch request.
      5. Tier 2: 5-station fallback tier.
      6. Tier 3: Disk snapshot fallback (extended + legacy).
      7. Tier 4: Terrain-only fallback.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Simulation Mode
    if simulate_rain_mm is not None:
        rain_val = float(simulate_rain_mm)
        now_dt = datetime.now(timezone.utc)
        sim_times = [(now_dt - timedelta(hours=72-h)).strftime("%Y-%m-%dT%H:00") for h in range(144)]
        sim_rate = round(rain_val / 72.0, 3)
        sim_precip = [sim_rate if h <= 72 else 0.0 for h in range(144)]
        sim_hourly = {"time": sim_times, "precipitation": sim_precip}
        sim_data = {
            s["id"]: {
                "rain_mm": rain_val,
                "r3d_mm": rain_val,
                "rain_24h_mm": round(rain_val * 0.33, 1),
                "forecast_24h_mm": round(rain_val * 0.5, 1),
                "forecast_72h_mm": round(rain_val * 1.2, 1),
                "peak_hour_utc": now_iso,
                "peak_mm": round(rain_val * 0.15, 1),
                "status": "simulated",
                "hourly": sim_hourly,
            }
            for s in segments
        }
        meta = {
            "weather_source": "simulated",
            "weather_fetched_at": now_iso,
            "weather_age_minutes": 0.0,
            "is_simulated": True,
            "stale_warning": None,
        }
        return sim_data, meta

    now = time.time()

    # 2. In-Memory Cache Check
    if _rain_cache.get("data") is not None and now - _rain_cache.get("t", 0.0) < CACHE_TTL_S:
        age_min = round(max(0.0, (now - _rain_cache.get("t", now)) / 60.0), 1)
        meta = {
            "weather_source": "cached",
            "weather_fetched_at": _rain_cache.get("fetched_at") or now_iso,
            "weather_age_minutes": age_min,
            "is_simulated": False,
            "stale_warning": None,
        }
        return _rain_cache["data"], meta

    # 3. Circuit Breaker / Failure Cache Check
    if now - _fail_cache.get("t", 0.0) < FAILED_CACHE_TTL_S and _fail_cache.get("data") is not None:
        return _fail_cache["data"], _fail_cache["meta"]

    session = session or requests.Session()

    # 4. Tier 1: Per-Segment Hourly Batched Request
    try:
        data = fetch_tier1_per_segment_hourly(segments, session)
        _rain_cache.update(t=now, data=data, fetched_at=now_iso, source="live")
        _fail_cache.update(t=0.0, data=None, meta=None)
        log.info("weather_service: Tier 1 hourly batch weather fetched for %d segments", len(segments))

        meta = {
            "weather_source": "live",
            "weather_fetched_at": now_iso,
            "weather_age_minutes": 0.0,
            "is_simulated": False,
            "stale_warning": None,
        }

        # Persist extended snapshot
        save_extended_snapshot_atomic(data, now_iso)
        return data, meta

    except Exception as e1:
        log.warning("weather_service: Tier 1 fetch failed (%s: %s). Attempting Tier 2 fallback...", type(e1).__name__, e1)

    # 5. Tier 2: 5-Station Corridor Fallback
    try:
        data = fetch_tier2_5station_fallback(segments, session)
        _rain_cache.update(t=now, data=data, fetched_at=now_iso, source="cached_5station")
        _fail_cache.update(t=0.0, data=None, meta=None)
        log.info("weather_service: Tier 2 (5-station) fallback succeeded for %d segments", len(segments))

        meta = {
            "weather_source": "cached_5station",
            "weather_fetched_at": now_iso,
            "weather_age_minutes": 0.0,
            "is_simulated": False,
            "stale_warning": "Using 5-station fallback meteorology.",
        }
        save_extended_snapshot_atomic(data, now_iso)
        return data, meta

    except Exception as e2:
        log.warning("weather_service: Tier 2 fallback failed (%s: %s). Attempting Tier 3 snapshot...", type(e2).__name__, e2)

    # Cache failure timestamp for circuit breaker
    _fail_cache["t"] = now

    # 6. Tier 3: Snapshot Fallback
    snap_data, snap_time = load_snapshot_data(segments)
    if snap_data is not None:
        log.info("weather_service: using Tier 3 cached rain snapshot from %s", SNAPSHOT_PATH)
        age_min = 0.0
        stale_warning = None
        if snap_time and snap_time != "unknown":
            try:
                dt = datetime.fromisoformat(snap_time.replace("Z", "+00:00"))
                age_s = (datetime.now(timezone.utc) - dt).total_seconds()
                age_min = round(max(0.0, age_s / 60.0), 1)
                if age_min > 360.0:
                    stale_warning = f"Weather data is {round(age_min/60.0, 1)}h old (using snapshot from {snap_time})."
            except Exception:
                pass

        meta = {
            "weather_source": "snapshot",
            "weather_fetched_at": snap_time,
            "weather_age_minutes": age_min,
            "is_simulated": False,
            "stale_warning": stale_warning,
        }
        _fail_cache["data"] = snap_data
        _fail_cache["meta"] = meta
        return snap_data, meta

    # 7. Tier 4: Terrain-only fallback
    log.warning("weather_service: All weather tiers failed. Falling back to Tier 4 terrain-only.")
    fallback_data = {
        s["id"]: {
            "rain_mm": None,
            "r3d_mm": None,
            "rain_24h_mm": None,
            "forecast_24h_mm": None,
            "forecast_72h_mm": None,
            "peak_hour_utc": None,
            "peak_mm": None,
            "status": "unavailable",
        }
        for s in segments
    }
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


def save_extended_snapshot_atomic(data: dict, timestamp_iso: str, target_path: Optional[Path] = None) -> bool:
    """Atomically saves extended snapshot JSON using temp file and os.replace."""
    import os
    path = Path(target_path or SNAPSHOT_PATH).resolve()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": timestamp_iso,
            "data": data,
        }
        temp_file = path.with_suffix(".tmp")
        temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temp_file, path)
        log.info("weather_service: atomically wrote extended snapshot to %s", path)
        return True
    except Exception as e:
        log.warning("weather_service: failed saving snapshot atomically: %s", e)
        return False
