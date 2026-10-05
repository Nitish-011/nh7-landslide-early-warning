"""
consequence_service.py - Blockage consequence & BRO operational priority engine
================================================================================
Combines physical landslide hazard (relative risk index) with blockage consequence
metrics (hospital isolation distance, absence of alternate bypass route, and
highway traffic index) to prioritize highway sectors for BRO clearance pre-positioning.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app import config
from app.risk_service import get_live_risk_map_with_metadata

log = logging.getLogger("backend")

_consequence_cache: Dict[str, Any] = {"mtime": 0.0, "data": None}


def load_consequence_dataset() -> Dict[str, dict]:
    """
    Reads data/segment_consequence.csv with caching.
    Degrades gracefully to an empty dictionary if the file is missing or unreadable.
    """
    csv_path = Path(getattr(config, "CONSEQUENCE_CSV_PATH", config.DATA_DIR / "segment_consequence.csv")).resolve()
    if not csv_path.exists():
        log.warning("consequence_service: %s does not exist; consequence metrics unavailable", csv_path)
        return {}

    try:
        mtime = csv_path.stat().st_mtime
        if _consequence_cache.get("data") is not None and _consequence_cache.get("mtime") == mtime:
            return _consequence_cache["data"]

        data = {}
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                seg_id = row.get("segment_id", "").strip()
                if not seg_id:
                    continue

                nearest_town = row.get("nearest_town", "").strip() or None
                nearest_hosp = row.get("nearest_hospital", "").strip() or None

                town_km_str = row.get("nearest_town_km", "").strip()
                town_km = float(town_km_str) if town_km_str else None

                hosp_km_str = row.get("nearest_hospital_km", "").strip()
                hosp_km = float(hosp_km_str) if hosp_km_str else None

                lodging_str = row.get("lodging_count_5km", "").strip()
                lodging_cnt = int(lodging_str) if lodging_str else 0

                alt_str = row.get("has_alternate_route", "").strip().lower()
                if alt_str in ("true", "1", "yes"):
                    has_alt = True
                elif alt_str in ("false", "0", "no"):
                    has_alt = False
                else:
                    has_alt = None

                traf_str = row.get("traffic_index", "").strip()
                try:
                    traffic_idx = int(traf_str) if traf_str else 3
                except Exception:
                    traffic_idx = 3

                # Compute indicative consequence score (0.0 to 1.0)
                # 1. Hospital isolation penalty
                ref_hosp_km = getattr(config, "HOSPITAL_REF_KM", 30.0)
                c_hosp = min((hosp_km if hosp_km is not None else 10.0) / ref_hosp_km, 1.0)

                # 2. Alternate bypass route penalty (1.0 if no bypass / blank; 0.0 if alternate route exists)
                c_alt = 0.0 if has_alt is True else 1.0

                # 3. Traffic importance penalty (normalized 1-5 -> 0.2-1.0)
                c_traffic = max(1, min(5, traffic_idx)) / 5.0

                w_hosp = getattr(config, "W_CONSEQUENCE_HOSPITAL", 0.40)
                w_alt = getattr(config, "W_CONSEQUENCE_ALTERNATE", 0.35)
                w_traf = getattr(config, "W_CONSEQUENCE_TRAFFIC", 0.25)

                consequence_score = round(w_hosp * c_hosp + w_alt * c_alt + w_traf * c_traffic, 2)
                consequence_score = max(0.0, min(1.0, consequence_score))

                data[seg_id] = {
                    "segment_id": seg_id,
                    "nearest_town": nearest_town,
                    "nearest_town_km": town_km,
                    "nearest_hospital": nearest_hosp,
                    "nearest_hospital_km": hosp_km,
                    "lodging_count_5km": lodging_cnt,
                    "has_alternate_route": has_alt,
                    "traffic_index": traffic_idx,
                    "consequence_score": consequence_score,
                }

        _consequence_cache["mtime"] = mtime
        _consequence_cache["data"] = data
        log.info("consequence_service: loaded consequence metrics for %d segments from %s", len(data), csv_path)
        return data

    except Exception as e:
        log.error("consequence_service: failed reading %s: %s", csv_path, e)
        return {}


def build_action_template(
    priority_score: float,
    risk_level: str,
    nearest_town: Optional[str],
    nearest_hospital: Optional[str],
    nearest_hospital_km: Optional[float],
    is_degraded: bool = False
) -> str:
    """Constructs operational recommendation template for BRO / SDRF field teams."""
    if is_degraded:
        return f"INDICATIVE ADVISORY: Consequence data file unavailable; priority ranked by relative hazard tier ({risk_level}). Maintain standard corridor readiness."

    town = nearest_town or "local depot"
    hosp = nearest_hospital or "nearest civil hospital"
    hosp_km_str = f"{nearest_hospital_km:.1f} km" if nearest_hospital_km is not None else "unknown distance"

    if priority_score >= 0.35 or risk_level in ("High", "Very High"):
        if nearest_hospital_km is not None and nearest_hospital_km >= 10.0:
            return (
                f"CRITICAL INTERVENTION: Pre-position heavy tracked excavator, rock-clearing team, "
                f"and medical standby patrol at {town}; nearest medical facility ({hosp}) is {hosp_km_str} away. "
                "Maintain 24/7 radio contact."
            )
        else:
            return (
                f"HIGH CLEARANCE PRIORITY: Pre-position wheel loader and clearance patrol near {town}; "
                f"hospital ({hosp}) is {hosp_km_str} away. Monitor known debris flow chutes continuously."
            )
    elif priority_score >= 0.20 or risk_level == "Moderate":
        return (
            f"ROUTINE CLEARANCE STANDBY: Scheduled equipment patrol and culvert inspection along {town} sector; "
            f"nearest medical facility ({hosp}) is {hosp_km_str} away."
        )
    else:
        return (
            f"STANDARD READINESS: Normal highway patrol along {town} sector; "
            "low immediate blockage priority. Maintain normal depot readiness."
        )


def get_priority_list_data(simulate_rain_mm: Optional[float] = None) -> dict:
    """
    Computes BRO operational priority list ranking segments by priority_score = risk_index * consequence_score.
    Degrades gracefully when consequence CSV is missing.
    """
    live_segments, meta = get_live_risk_map_with_metadata(simulate_rain_mm=simulate_rain_mm)
    consequence_map = load_consequence_dataset()
    is_degraded = len(consequence_map) == 0

    items = []
    for s in live_segments:
        seg_id = s["id"]
        risk_idx = s.get("risk_index") if s.get("risk_index") is not None else s.get("risk_score", 0.0)
        risk_lvl = s.get("risk_level", "Low")
        c_item = consequence_map.get(seg_id)

        if c_item:
            consequence_score = c_item["consequence_score"]
            priority_score = round(risk_idx * consequence_score, 2)
            nearest_town = c_item["nearest_town"]
            nearest_town_km = c_item["nearest_town_km"]
            nearest_hosp = c_item["nearest_hospital"]
            nearest_hosp_km = c_item["nearest_hospital_km"]
            lodging_cnt = c_item["lodging_count_5km"]
            has_alt = c_item["has_alternate_route"]
            traffic_idx = c_item["traffic_index"]
        else:
            # Degraded mode: neutral consequence score of 0.50
            consequence_score = 0.50
            priority_score = round(risk_idx * 0.50, 2)
            nearest_town = None
            nearest_town_km = None
            nearest_hosp = None
            nearest_hosp_km = None
            lodging_cnt = None
            has_alt = None
            traffic_idx = 3

        action = build_action_template(
            priority_score=priority_score,
            risk_level=risk_lvl,
            nearest_town=nearest_town,
            nearest_hospital=nearest_hosp,
            nearest_hospital_km=nearest_hosp_km,
            is_degraded=is_degraded
        )

        items.append({
            "id": seg_id,
            "name": s["name"],
            "sequence_order": s["sequence_order"],
            "risk_level": risk_lvl,
            "risk_score": s["risk_score"],
            "risk_index": risk_idx,
            "consequence_score": consequence_score,
            "priority_score": priority_score,
            "nearest_town": nearest_town,
            "nearest_town_km": nearest_town_km,
            "nearest_hospital": nearest_hosp,
            "nearest_hospital_km": nearest_hosp_km,
            "lodging_count_5km": lodging_cnt,
            "has_alternate_route": has_alt,
            "traffic_index": traffic_idx,
            "recommended_action": action,
        })

    # Sort descending by priority_score, tie-breaking on risk_index
    items.sort(key=lambda x: (x["priority_score"], x["risk_index"], x["consequence_score"]), reverse=True)

    # Assign 1-indexed rank
    for rank_idx, item in enumerate(items, start=1):
        item["rank"] = rank_idx

    disclaimer = (
        "Indicative BRO / SDRF operational priority list combining landslide hazard "
        "and blockage consequence metrics. Traffic index and alternate route availability "
        "are indicative assumptions. Does not replace physical field reconnaissance."
    )
    if is_degraded:
        disclaimer += " (Notice: segment_consequence.csv was not found; running in degraded mode using neutral consequence baseline)."

    return {
        "corridor": "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
        "total_segments": len(items),
        "status": "indicative",
        "disclaimer": disclaimer,
        "is_simulated": meta.get("is_simulated", False),
        "segments": items,
    }
