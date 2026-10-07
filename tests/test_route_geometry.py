"""
tests/test_route_geometry.py - Verification suite for high-resolution NH-7 road geometry.

Assertions:
1. Every vertex-to-vertex gap in geojson/nh7_route.geojson is strictly under 300 m.
2. Median perpendicular distance from the 309 published landslide scars to the polyline is under 25 m.
3. Total highway centerline length is within 3% of the real road length (247.37 km).
4. All 18 segments returned by /risk-map have dense road-following subpoints (>= 20 points per segment, mean spacing < 250 m).
5. Adjacent segments connect contiguously without coordinate gaps or start-to-end shortcuts.
"""
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ROOT_DIR = Path(__file__).resolve().parent.parent
GEOJSON_ROUTE = ROOT_DIR / "geojson" / "nh7_route.geojson"
SCARS_CSV = ROOT_DIR / "model" / "nh7_published_309_inventory.csv"
REAL_HIGHWAY_KM = 247.37


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def min_dist_to_polyline_m(lat: float, lon: float, polyline_lat_lon: list) -> float:
    cos_lat = math.cos(math.radians(lat))
    R = 6371000.0
    rad = math.pi / 180.0
    min_d = float("inf")

    for i in range(len(polyline_lat_lon) - 1):
        lat1, lon1 = polyline_lat_lon[i]
        lat2, lon2 = polyline_lat_lon[i + 1]

        # Fast bounding box pre-filter (~3 km)
        if not (min(lat1, lat2) - 0.03 <= lat <= max(lat1, lat2) + 0.03 and
                min(lon1, lon2) - 0.03 <= lon <= max(lon1, lon2) + 0.03):
            continue

        vx = (lon2 - lon1) * rad * R * cos_lat
        vy = (lat2 - lat1) * rad * R
        wx = (lon - lon1) * rad * R * cos_lat
        wy = (lat - lat1) * rad * R

        seg_len_sq = vx * vx + vy * vy
        if seg_len_sq == 0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len_sq))

        proj_x = t * vx
        proj_y = t * vy
        d = math.hypot(wx - proj_x, wy - proj_y)
        if d < min_d:
            min_d = d

    return min_d


def test_nh7_route_vertex_spacing():
    """Verify every vertex-to-vertex gap is under 300 m."""
    assert GEOJSON_ROUTE.exists(), f"{GEOJSON_ROUTE} missing"
    with open(GEOJSON_ROUTE, "r", encoding="utf-8") as f:
        data = json.load(f)

    coords = data["features"][0]["geometry"]["coordinates"]
    assert len(coords) >= 4000, f"Expected high-resolution route (>=4000 vertices), found {len(coords)}"

    spacings_m = []
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i][0], coords[i][1]
        lon2, lat2 = coords[i + 1][0], coords[i + 1][1]
        d = haversine_m(lat1, lon1, lat2, lon2)
        spacings_m.append(d)
        assert d < 300.0, f"Vertex gap between index {i} and {i+1} is {d:.1f} m, exceeds 300 m limit!"

    max_gap = max(spacings_m)
    mean_gap = sum(spacings_m) / len(spacings_m)
    assert max_gap <= 100.0, f"Max gap {max_gap:.1f} m should be under 100 m for 50m resampled road"
    assert 40.0 <= mean_gap <= 60.0, f"Mean gap {mean_gap:.1f} m should be around 50 m"


def test_nh7_route_median_scar_distance():
    """Verify median distance from 309 Mey scars to polyline is under 25 m."""
    assert SCARS_CSV.exists(), f"{SCARS_CSV} missing"
    df_scars = pd.read_csv(SCARS_CSV)
    assert len(df_scars) == 309

    with open(GEOJSON_ROUTE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # (lat, lon) coordinates
    poly_lat_lon = [(c[1], c[0]) for c in data["features"][0]["geometry"]["coordinates"]]

    distances_m = [
        min_dist_to_polyline_m(float(row["latitude"]), float(row["longitude"]), poly_lat_lon)
        for _, row in df_scars.iterrows()
    ]

    median_d = float(np.median(distances_m))
    p90_d = float(np.percentile(distances_m, 90))
    max_d = float(np.max(distances_m))

    assert median_d < 25.0, f"Median scar distance {median_d:.2f} m exceeds 25 m threshold!"
    assert median_d < 10.0, f"Expected high road fidelity with median < 10 m, got {median_d:.2f} m"
    assert p90_d < 25.0, f"90th percentile scar distance {p90_d:.2f} m exceeds 25 m"
    assert max_d < 50.0, f"Max scar distance {max_d:.2f} m exceeds 50 m"


def test_nh7_route_total_length():
    """Verify total polyline length is within 3% of real road length (247.37 km)."""
    with open(GEOJSON_ROUTE, "r", encoding="utf-8") as f:
        data = json.load(f)

    coords = data["features"][0]["geometry"]["coordinates"]
    total_m = sum(
        haversine_m(coords[i][1], coords[i][0], coords[i+1][1], coords[i+1][0])
        for i in range(len(coords) - 1)
    )
    total_km = total_m / 1000.0

    percent_error = abs(total_km - REAL_HIGHWAY_KM) / REAL_HIGHWAY_KM
    assert percent_error <= 0.03, (
        f"Route length {total_km:.2f} km deviates by {percent_error*100:.2f}% from real {REAL_HIGHWAY_KM} km "
        f"(must be within 3%)"
    )


def test_all_segments_have_dense_subpoints():
    """Verify /risk-map returns dense subpoints for each of the 18 segments."""
    res = client.get("/risk-map")
    assert res.status_code == 200
    data = res.json()
    segments = data["segments"]
    assert len(segments) == 18

    for seg in segments:
        sub = seg.get("subpoints", [])
        assert len(sub) >= 20, (
            f"Segment {seg['id']} ({seg['name']}) has only {len(sub)} subpoints! "
            f"Expected dense road-following subpoints (>= 20)."
        )

        # Check mean spacing between subpoints
        spacings = [
            haversine_m(sub[i][0], sub[i][1], sub[i+1][0], sub[i+1][1])
            for i in range(len(sub) - 1)
        ]
        mean_spacing = sum(spacings) / len(spacings)
        assert mean_spacing < 250.0, (
            f"Segment {seg['id']} mean spacing {mean_spacing:.1f} m exceeds 250 m"
        )


def test_segment_contiguity_and_no_shortcuts():
    """Verify adjacent segments connect contiguously without coordinate jumps."""
    res = client.get("/risk-map")
    assert res.status_code == 200
    segments = res.json()["segments"]

    for i in range(len(segments) - 1):
        curr_end_lat = segments[i]["end_lat"]
        curr_end_lng = segments[i]["end_lng"]
        next_start_lat = segments[i + 1]["start_lat"]
        next_start_lng = segments[i + 1]["start_lng"]

        # Coordinate match to 4 decimal places (< 10 m)
        dist_gap_m = haversine_m(curr_end_lat, curr_end_lng, next_start_lat, next_start_lng)
        assert dist_gap_m < 15.0, (
            f"Gap between {segments[i]['id']} end and {segments[i+1]['id']} start is {dist_gap_m:.1f} m!"
        )

        # Subpoints must begin and end at the segment boundaries
        sub_curr = segments[i]["subpoints"]
        assert abs(sub_curr[0][0] - segments[i]["start_lat"]) < 1e-4
        assert abs(sub_curr[0][1] - segments[i]["start_lng"]) < 1e-4
        assert abs(sub_curr[-1][0] - curr_end_lat) < 1e-4
        assert abs(sub_curr[-1][1] - curr_end_lng) < 1e-4
