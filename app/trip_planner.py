"""
trip_planner.py - Time-aware, forecast-based trip planning engine for NH-7
===========================================================================
Computes segment-by-segment ETAs along the Rishikesh-Joshimath corridor (in either
direction), evaluates dynamic antecedent 72h rainfall at each segment's entry moment
from hourly past and forecast time series, and provides optimized departure
recommendations (GO / CAUTION / DELAY / AVOID) with a 48-hour departure window search.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

from app import config
from app.risk_service import level_for

log = logging.getLogger("backend")

# Indian Standard Time (UTC+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Exact highway lengths (km) per segment from verified 247.37 km corridor chainage
SEGMENT_LENGTHS_KM: Dict[str, float] = {
    "seg_01": 17.43,
    "seg_02": 6.83,
    "seg_03": 13.86,
    "seg_04": 32.51,
    "seg_05": 14.94,
    "seg_06": 12.47,
    "seg_07": 4.95,
    "seg_08": 9.42,
    "seg_09": 23.64,
    "seg_10": 22.49,
    "seg_11": 9.56,
    "seg_12": 6.07,
    "seg_13": 13.15,
    "seg_14": 13.05,
    "seg_15": 5.24,
    "seg_16": 6.74,
    "seg_17": 28.68,
    "seg_18": 6.33,
}

LEVEL_RANKS: Dict[str, int] = {
    "Low": 0,
    "Moderate": 1,
    "High": 2,
    "Very High": 3,
}


def parse_departure_time(depart_time_str: str) -> datetime:
    """
    Parses an ISO format timestamp string.
    If naive (no timezone specified), interprets as Indian Standard Time (IST, UTC+05:30).
    """
    cleaned = depart_time_str.strip()
    if cleaned.endswith("Z"):
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt


def extract_rain_at_eta(
    hourly_dict: Optional[dict],
    eta_utc: datetime,
    fallback_r3d: Optional[float] = None
) -> Tuple[float, float]:
    """
    Extracts rainfall metrics from Open-Meteo hourly precipitation dictionary at eta_utc:
      - rain_72h_at_eta_mm: antecedent 72h precipitation sum up to ETA
      - forecast_rain_6h_around_eta_mm: precipitation sum in a 6-hour window centered on ETA
    """
    if not hourly_dict or not isinstance(hourly_dict, dict):
        fb = float(fallback_r3d or 0.0)
        return round(fb, 1), round(fb * 6.0 / 72.0, 1)

    time_list: List[str] = hourly_dict.get("time", [])
    precip_raw = hourly_dict.get("precipitation", [])
    precip: List[float] = [float(p) if p is not None else 0.0 for p in precip_raw]

    if not time_list or not precip or len(time_list) != len(precip):
        fb = float(fallback_r3d or 0.0)
        return round(fb, 1), round(fb * 6.0 / 72.0, 1)

    eta_hour_str = eta_utc.strftime("%Y-%m-%dT%H:00")
    idx = -1
    for i, t in enumerate(time_list):
        if t <= eta_hour_str:
            idx = i
        else:
            break

    if idx < 0:
        idx = 0
    elif idx >= len(time_list):
        idx = len(time_list) - 1

    # 72h antecedent sum ending at idx
    slice_72 = precip[max(0, idx - 71) : idx + 1]
    rain_72h = round(float(sum(slice_72)), 1) if slice_72 else 0.0

    # 6h window centered around ETA (idx-2 to idx+3)
    start_6 = max(0, idx - 2)
    end_6 = min(len(precip), idx + 4)
    slice_6 = precip[start_6:end_6]
    rain_6h = round(float(sum(slice_6)), 1) if slice_6 else 0.0

    return rain_72h, rain_6h


def compute_risk_at_eta(terrain_percentile: Optional[float], rain_72h_mm: float) -> Tuple[float, str]:
    """Computes composite landslide risk score and categorical tier at a specific ETA."""
    terrain = 0.5 if terrain_percentile is None else float(terrain_percentile)
    effective_terrain = config.TERRAIN_FLOOR + (1.0 - config.TERRAIN_FLOOR) * terrain
    rain_index = min(rain_72h_mm / config.RAIN_REF_MM, 1.0)
    raw_score = min(config.K_TERRAIN * effective_terrain + config.K_RAIN * rain_index, 1.0)

    # Smooth linear ramp between DRY_RAMP_LOW_MM and DRY_RAMP_HIGH_MM
    if rain_72h_mm <= config.DRY_RAMP_LOW_MM:
        score = min(raw_score, config.DRY_CAP_MAX_SCORE)
    elif rain_72h_mm >= config.DRY_RAMP_HIGH_MM:
        score = raw_score
    else:
        ramp = (rain_72h_mm - config.DRY_RAMP_LOW_MM) / (config.DRY_RAMP_HIGH_MM - config.DRY_RAMP_LOW_MM)
        score = config.DRY_CAP_MAX_SCORE + ramp * (raw_score - config.DRY_CAP_MAX_SCORE) if raw_score > config.DRY_CAP_MAX_SCORE else raw_score

    risk_lvl = level_for(score, rain_status="ok", rain_mm=rain_72h_mm)
    return round(score, 2), risk_lvl


def simulate_route_at_departure(
    ordered_segments: List[dict],
    weather_map: Dict[str, dict],
    depart_dt_ist: datetime,
    speed_kmph: float
) -> Tuple[List[dict], str, float]:
    """
    Simulates vehicle traversing segments in ordered_segments starting at depart_dt_ist.
    Returns:
      (per_segment_results, max_risk_level, total_risk_score)
    """
    current_time_ist = depart_dt_ist
    results = []
    max_rank = 0
    max_level = "Low"
    total_score = 0.0

    for seg in ordered_segments:
        seg_id = seg["id"]
        length_km = SEGMENT_LENGTHS_KM.get(seg_id, 10.0)
        eta_ist_str = current_time_ist.strftime("%Y-%m-%dT%H:%M:%S+05:30")
        eta_utc = current_time_ist.astimezone(timezone.utc)

        w_entry = weather_map.get(seg_id, {})
        hourly_dict = w_entry.get("hourly")
        r3d_fb = w_entry.get("r3d_mm") or w_entry.get("rain_mm")

        rain_72h, rain_6h = extract_rain_at_eta(hourly_dict, eta_utc, fallback_r3d=r3d_fb)
        terrain_pct = seg.get("terrain_percentile")
        score_at_eta, level_at_eta = compute_risk_at_eta(terrain_pct, rain_72h)

        total_score += score_at_eta
        rank = LEVEL_RANKS.get(level_at_eta, 0)
        if rank > max_rank:
            max_rank = rank
            max_level = level_at_eta

        results.append({
            "id": seg_id,
            "eta_ist": eta_ist_str,
            "rain_72h_at_eta_mm": rain_72h,
            "forecast_rain_6h_around_eta_mm": rain_6h,
            "risk_level_at_eta": level_at_eta,
            "risk_score_at_eta": score_at_eta,
        })

        # Advance transit time by segment length / speed
        transit_hours = length_km / max(speed_kmph, 1.0)
        current_time_ist += timedelta(hours=transit_hours)

    return results, max_level, round(total_score, 2)


def evaluate_trip_plan(
    ordered_segments: List[dict],
    weather_map: Dict[str, dict],
    depart_time_str: str,
    speed_kmph: Optional[float] = None
) -> Tuple[List[dict], dict, str, float]:
    """
    Evaluates time-aware trip plan along ordered_segments.
    Returns:
      (per_segment_eta_info, recommendation_dict, depart_time_ist_str, speed_kmph)
    """
    if speed_kmph is None or speed_kmph <= 0:
        speed_kmph = getattr(config, "DEFAULT_SPEED_KMPH", 30.0)

    depart_dt_ist = parse_departure_time(depart_time_str)
    depart_ist_str = depart_dt_ist.strftime("%Y-%m-%dT%H:%M:%S+05:30")

    # 1. Base simulation for requested departure
    base_results, base_max_level, base_total_score = simulate_route_at_departure(
        ordered_segments, weather_map, depart_dt_ist, speed_kmph
    )
    base_rank = LEVEL_RANKS.get(base_max_level, 0)

    # 2. Search departure times hourly over the next 48h (limited to available forecast)
    candidate_options = []
    first_w = weather_map.get(ordered_segments[0]["id"], {}) if ordered_segments else {}
    first_hourly = first_w.get("hourly") or {}
    first_times = first_hourly.get("time", [])

    max_search_hours = 48
    if first_times:
        try:
            last_t = datetime.fromisoformat(first_times[-1].replace("Z", "+00:00"))
            avail_hours = int((last_t - depart_dt_ist.astimezone(timezone.utc)).total_seconds() / 3600.0)
            max_search_hours = min(48, max(1, avail_hours - 3))
        except Exception:
            max_search_hours = 48

    for h in range(max_search_hours):
        cand_dt = depart_dt_ist + timedelta(hours=h)
        _, cand_max_lvl, cand_tot_score = simulate_route_at_departure(
            ordered_segments, weather_map, cand_dt, speed_kmph
        )
        cand_rank = LEVEL_RANKS.get(cand_max_lvl, 0)
        cand_time_str = cand_dt.strftime("%Y-%m-%dT%H:%M:%S+05:30")
        candidate_options.append({
            "hours_offset": h,
            "depart_dt": cand_dt,
            "depart_time": cand_time_str,
            "max_risk_level": cand_max_lvl,
            "max_rank": cand_rank,
            "total_risk_score": cand_tot_score,
            "summary": f"Depart at {cand_dt.strftime('%H:%M IST')} ({cand_dt.strftime('%b %d')}) - Max Risk: {cand_max_lvl}, Route Score: {cand_tot_score:.2f}",
        })

    # Sort: minimize maximum risk level on route, then total risk score as tie-breaker
    sorted_candidates = sorted(candidate_options, key=lambda c: (c["max_rank"], c["total_risk_score"], c["hours_offset"]))

    # Pick up to 3 distinct departure options
    best_options = []
    seen_hours = set()
    for c in sorted_candidates:
        if c["hours_offset"] not in seen_hours:
            seen_hours.add(c["hours_offset"])
            best_options.append({
                "depart_time": c["depart_time"],
                "max_risk_level": c["max_risk_level"],
                "summary": c["summary"],
                "total_risk_score": c["total_risk_score"],
            })
            if len(best_options) >= 3:
                break

    best_candidate = sorted_candidates[0] if sorted_candidates else None
    best_rank = best_candidate["max_rank"] if best_candidate else base_rank
    best_lvl = best_candidate["max_risk_level"] if best_candidate else base_max_level
    best_offset = best_candidate["hours_offset"] if best_candidate else 0
    best_time_str = best_candidate["depart_time"] if best_candidate else depart_ist_str

    # 3. Determine top-level action: GO | CAUTION | DELAY | AVOID
    if base_rank >= 2:  # High or Very High
        if best_rank < base_rank:
            action = "DELAY"
            action_code = "REC_DELAY"
            reason = (
                f"Elevated landslide risk ({base_max_level}) detected along route at planned departure. "
                f"Delaying departure by {best_offset}h to {best_time_str[11:16]} IST reduces route risk to {best_lvl}."
            )
        else:
            action = "AVOID"
            action_code = "REC_AVOID"
            reason = (
                f"Severe landslide hazard ({base_max_level}) persists along the corridor across the 48-hour forecast window. "
                "Highway transit is strongly discouraged; monitor BRO and SDRF bulletins."
            )
    elif base_rank == 1:  # Moderate
        if best_rank < base_rank:
            action = "CAUTION"
            action_code = "REC_CAUTION"
            reason = (
                f"Moderate landslide risk detected. Proceed cautiously, or depart at {best_time_str[11:16]} IST for {best_lvl} risk."
            )
        else:
            action = "CAUTION"
            action_code = "REC_CAUTION"
            reason = "Moderate landslide risk along route. Drive cautiously near steep cuts and water crossings."
    else:  # Low
        action = "GO"
        action_code = "REC_GO"
        reason = "Conditions are favorable across all route segments at your planned departure time."

    recommendation = {
        "action": action,
        "action_code": action_code,
        "reason": reason,
        "params": {
            "depart_time": depart_ist_str,
            "speed_kmph": speed_kmph,
            "current_max_risk": base_max_level,
            "best_max_risk": best_lvl,
            "best_depart_time": best_time_str,
            "hours_delay": best_offset,
        },
        "best_departure_options": best_options,
    }

    return base_results, recommendation, depart_ist_str, speed_kmph
