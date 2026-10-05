#!/usr/bin/env python3
"""
scripts/build_consequence.py - Query Overpass OSM API and build consequence dataset
===================================================================================
For each of the 18 NH-7 road segments:
  1. Computes midpoint coordinates.
  2. Queries OpenStreetMap Overpass API for:
     - Nearest place=town|city|village (and distance in km)
     - Nearest amenity=hospital|clinic|doctors (and distance in km)
     - Count of tourism=hotel|guest_house within 5.0 km radius
  3. Caches raw Overpass response to data/osm_cache.json.
  4. Generates data/segment_consequence.csv with columns:
     segment_id,nearest_town,nearest_town_km,nearest_hospital,nearest_hospital_km,lodging_count_5km,has_alternate_route,traffic_index
"""
import csv
import json
import logging
import math
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCORES_FILE = BASE_DIR / "app" / "segment_static_scores.json"
CACHE_FILE = DATA_DIR / "osm_cache.json"
OUTPUT_CSV = DATA_DIR / "segment_consequence.csv"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:35];
(
  node["place"~"^(town|city|village)$"](29.9,78.1,30.7,79.7);
  way["place"~"^(town|city|village)$"](29.9,78.1,30.7,79.7);
  node["amenity"~"^(hospital|clinic|doctors)$"](29.9,78.1,30.7,79.7);
  way["amenity"~"^(hospital|clinic|doctors)$"](29.9,78.1,30.7,79.7);
  node["tourism"~"^(hotel|guest_house)$"](29.9,78.1,30.7,79.7);
  way["tourism"~"^(hotel|guest_house)$"](29.9,78.1,30.7,79.7);
);
out center;
"""

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("build_consequence")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points on Earth in kilometers."""
    R = 6371.0  # Earth's mean radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return R * c


def get_osm_data() -> dict:
    """Loads OSM data from local disk cache if present, otherwise queries Overpass API."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists():
        log.info("Loading cached OSM data from %s", CACHE_FILE)
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed reading cache (%s); will re-query Overpass", e)

    log.info("Querying Overpass API for NH-7 corridor amenities & places...")
    headers = {
        "User-Agent": "NH7LandslideEarlyWarning/1.0 (Hackathon Research; anil.jha@jigyasa)",
    }
    resp = requests.post(OVERPASS_URL, data=OVERPASS_QUERY.encode("utf-8"), headers=headers, timeout=40)
    resp.raise_for_status()
    payload = resp.json()

    CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Cached %d OSM elements to %s", len(payload.get("elements", [])), CACHE_FILE)
    return payload


def extract_poi(element: dict) -> Tuple[Optional[float], Optional[float], str, str]:
    """Extracts (lat, lng, name, category) from an OSM element."""
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lng = element.get("lon") or element.get("center", {}).get("lon")
    tags = element.get("tags", {})
    name = tags.get("name:en") or tags.get("name") or tags.get("official_name") or ""

    if "place" in tags:
        category = "place"
        if not name:
            name = f"Unnamed {tags.get('place')}"
    elif "amenity" in tags:
        category = "medical"
        if not name:
            name = f"Unnamed {tags.get('amenity')}"
    elif "tourism" in tags:
        category = "lodging"
        if not name:
            name = f"Unnamed {tags.get('tourism')}"
    else:
        category = "other"

    return lat, lng, name, category


def main():
    if not SCORES_FILE.exists():
        log.error("Scores file %s not found", SCORES_FILE)
        sys.exit(1)

    segments = json.loads(SCORES_FILE.read_text(encoding="utf-8"))
    log.info("Loaded %d segments", len(segments))

    osm_raw = get_osm_data()
    elements = osm_raw.get("elements", [])
    log.info("Processing %d OSM elements...", len(elements))

    places = []
    medical = []
    lodgings = []

    for el in elements:
        lat, lng, name, cat = extract_poi(el)
        if lat is None or lng is None:
            continue
        if cat == "place":
            places.append({"lat": lat, "lng": lng, "name": name})
        elif cat == "medical":
            medical.append({"lat": lat, "lng": lng, "name": name})
        elif cat == "lodging":
            lodgings.append({"lat": lat, "lng": lng, "name": name})

    log.info("Parsed %d places, %d medical facilities, %d lodging facilities",
             len(places), len(medical), len(lodgings))

    rows = []
    print("\n" + "=" * 90)
    print(f"{'Seg ID':<8} | {'Midpoint':<17} | {'Nearest Town (km)':<25} | {'Nearest Hospital (km)':<25} | {'Hotels (5km)'}")
    print("-" * 90)

    for seg in sorted(segments, key=lambda s: s["sequence_order"]):
        mid_lat = (seg["start_lat"] + seg["end_lat"]) / 2.0
        mid_lng = (seg["start_lng"] + seg["end_lng"]) / 2.0

        # 1. Nearest place (town/city/village)
        nearest_town_name = ""
        nearest_town_dist = float("inf")
        for p in places:
            d = haversine_km(mid_lat, mid_lng, p["lat"], p["lng"])
            if d < nearest_town_dist:
                nearest_town_dist = d
                nearest_town_name = p["name"]

        # 2. Nearest medical (hospital/clinic/doctors)
        nearest_hosp_name = ""
        nearest_hosp_dist = float("inf")
        for m in medical:
            d = haversine_km(mid_lat, mid_lng, m["lat"], m["lng"])
            if d < nearest_hosp_dist:
                nearest_hosp_dist = d
                nearest_hosp_name = m["name"]

        # 3. Lodging count within 5 km
        lodging_5km = sum(1 for l in lodgings if haversine_km(mid_lat, mid_lng, l["lat"], l["lng"]) <= 5.0)

        town_dist_clean = round(nearest_town_dist, 2) if nearest_town_dist != float("inf") else None
        hosp_dist_clean = round(nearest_hosp_dist, 2) if nearest_hosp_dist != float("inf") else None

        # has_alternate_route: BLANK for user to fill (Rule 5 compliance)
        # traffic_index: default 3 (flagged as assumption)
        row = {
            "segment_id": seg["id"],
            "nearest_town": nearest_town_name if nearest_town_name else "",
            "nearest_town_km": town_dist_clean if town_dist_clean is not None else "",
            "nearest_hospital": nearest_hosp_name if nearest_hosp_name else "",
            "nearest_hospital_km": hosp_dist_clean if hosp_dist_clean is not None else "",
            "lodging_count_5km": lodging_5km,
            "has_alternate_route": "",  # BLANK for verified manual entry
            "traffic_index": 3,         # Default 3 (assumption)
        }
        rows.append(row)

        town_str = f"{nearest_town_name[:15]} ({town_dist_clean} km)"
        hosp_str = f"{nearest_hosp_name[:15]} ({hosp_dist_clean} km)"
        print(f"{seg['id']:<8} | {mid_lat:.4f}, {mid_lng:.4f} | {town_str:<25} | {hosp_str:<25} | {lodging_5km:<11}")

    print("=" * 90)

    # Write output CSV
    fieldnames = [
        "segment_id",
        "nearest_town",
        "nearest_town_km",
        "nearest_hospital",
        "nearest_hospital_km",
        "lodging_count_5km",
        "has_alternate_route",
        "traffic_index",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    log.info("Successfully wrote consequence dataset to %s (%d rows)", OUTPUT_CSV, len(rows))


if __name__ == "__main__":
    main()
