#!/usr/bin/env python3
"""
Diagnostic script for STEP 1 of the Geometry Rebuild.
Does NOT modify any files. Prints diagnostic metrics.
"""
import json
import math
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def point_to_segment_dist_m(px, py, x1, y1, x2, y2, cos_lat):
    # Equirectangular approximation in meters
    R = 6371000.0
    rad = math.pi / 180.0
    
    # Project to local meter coordinates relative to (x1, y1)
    vx = (x2 - x1) * rad * R * cos_lat
    vy = (y2 - y1) * rad * R
    wx = (px - x1) * rad * R * cos_lat
    wy = (py - y1) * rad * R
    
    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq == 0:
        return math.hypot(wx, wy)
    
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len_sq))
    proj_x = t * vx
    proj_y = t * vy
    return math.hypot(wx - proj_x, wy - proj_y)


def min_dist_to_polyline_m(lat, lon, polyline_pts):
    # polyline_pts is list of (lat, lon)
    cos_lat = math.cos(math.radians(lat))
    min_d = float("inf")
    for i in range(len(polyline_pts) - 1):
        lat1, lon1 = polyline_pts[i]
        lat2, lon2 = polyline_pts[i + 1]
        # Quick bounding box pre-filter (in degrees) ~ 0.05 deg (~5km)
        if not (min(lat1, lat2) - 0.05 <= lat <= max(lat1, lat2) + 0.05 and
                min(lon1, lon2) - 0.05 <= lon <= max(lon1, lon2) + 0.05):
            continue
        d = point_to_segment_dist_m(lon, lat, lon1, lat1, lon2, lat2, cos_lat)
        if d < min_d:
            min_d = d
    if min_d == float("inf"):
        # fallback without bounding box filter
        for i in range(len(polyline_pts) - 1):
            lat1, lon1 = polyline_pts[i]
            lat2, lon2 = polyline_pts[i + 1]
            d = point_to_segment_dist_m(lon, lat, lon1, lat1, lon2, lat2, cos_lat)
            if d < min_d:
                min_d = d
    return min_d


def diagnose():
    print("=" * 80)
    print("STEP 1: GEOMETRY DIAGNOSIS")
    print("=" * 80)

    # 1. geojson/nh7_route.geojson
    geojson_path = Path("geojson/nh7_route.geojson")
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Coordinates are [lon, lat, (elev)]
    coords = data["features"][0]["geometry"]["coordinates"]
    vertex_count = len(coords)

    spacings_m = []
    total_len_m = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i][0], coords[i][1]
        lon2, lat2 = coords[i + 1][0], coords[i + 1][1]
        d = haversine_m(lat1, lon1, lat2, lon2)
        spacings_m.append(d)
        total_len_m += d

    mean_spacing_m = np.mean(spacings_m) if spacings_m else 0
    max_spacing_m = np.max(spacings_m) if spacings_m else 0
    total_len_km = total_len_m / 1000.0

    print("\n--- 1. geojson/nh7_route.geojson ---")
    print(f"Vertex count: {vertex_count}")
    print(f"Mean spacing between consecutive vertices: {mean_spacing_m:.2f} m")
    print(f"Max spacing between consecutive vertices:  {max_spacing_m:.2f} m")
    print(f"Total polyline length:                     {total_len_km:.2f} km")

    # Find where the largest gaps occur in nh7_route.geojson
    large_gaps = []
    for i, s in enumerate(spacings_m):
        if s > 500:
            lon1, lat1 = coords[i][0], coords[i][1]
            lon2, lat2 = coords[i + 1][0], coords[i + 1][1]
            large_gaps.append((i, s, (lat1, lon1), (lat2, lon2)))
    print(f"Number of gaps > 500 m: {len(large_gaps)}")
    if large_gaps:
        print("Sample large gaps:")
        for idx, dist, p1, p2 in sorted(large_gaps, key=lambda x: -x[1])[:5]:
            print(f"  idx {idx} -> {idx+1}: {dist:.1f} m from ({p1[0]:.4f}, {p1[1]:.4f}) to ({p2[0]:.4f}, {p2[1]:.4f})")

    # 2. Each of the 18 segments in the DB & in /risk-map
    print("\n--- 2. Database Segments & Subpoints (data/landslide_nh7.db) ---")
    conn = sqlite3.connect("data/landslide_nh7.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, sequence_order, start_lat, start_lng, end_lat, end_lng, subpoints_json FROM segments ORDER BY sequence_order")
    rows = cursor.fetchall()
    
    seg_subpoints = {}
    print(f"{'Segment ID':<8} {'Name':<28} {'Subpts':<8} {'Mean Spacing (m)':<18} {'Max Spacing (m)':<18} {'Length (km)':<12}")
    print("-" * 96)
    for r in rows:
        sid, name, seq, slat, slng, elat, elng, sub_json = r
        subpts = json.loads(sub_json) if sub_json else []
        seg_subpoints[sid] = subpts
        
        # calculate spacing between subpoints
        if len(subpts) >= 2:
            s_spacings = []
            s_len_m = 0.0
            for i in range(len(subpts) - 1):
                p1, p2 = subpts[i], subpts[i + 1]
                # check format: [lat, lng] or dict
                lat1, lon1 = (p1[0], p1[1]) if isinstance(p1, list) else (p1["lat"], p1["lng"])
                lat2, lon2 = (p2[0], p2[1]) if isinstance(p2, list) else (p2["lat"], p2["lng"])
                sd = haversine_m(lat1, lon1, lat2, lon2)
                s_spacings.append(sd)
                s_len_m += sd
            s_mean = np.mean(s_spacings)
            s_max = np.max(s_spacings)
            s_len_km = s_len_m / 1000.0
        else:
            s_mean, s_max = 0.0, 0.0
            s_len_km = haversine_m(slat, slng, elat, elng) / 1000.0

        print(f"{sid:<8} {name:<28} {len(subpts):<8} {s_mean:<18.1f} {s_max:<18.1f} {s_len_km:<12.2f}")
    conn.close()

    # 3. Check how app/static/index.html draws segments
    print("\n--- 3. Frontend Drawing Inspection (app/static/index.html) ---")
    html_text = Path("app/static/index.html").read_text(encoding="utf-8")
    has_subpoints = "seg.subpoints" in html_text
    has_fallback = "seg.start_lat" in html_text
    has_smooth = "smoothFactor" in html_text
    print(f"Uses seg.subpoints:               {has_subpoints}")
    print(f"Has start_lat/end_lat fallback:   {has_fallback}")
    print(f"Specifies Leaflet smoothFactor:   {has_smooth}")
    # Inspect lat/lng order in renderCorridorOnMap
    if "pt[0], pt[1]" in html_text:
        print("Coordinate parsing: pt[0], pt[1] assumed to be [lat, lng] by Leaflet L.polyline")

    # 4. Check whether offline-pack Ramer-Douglas-Peucker output feeds the main map
    print("\n--- 4. Offline Pack & Ramer-Douglas-Peucker vs Main Map ---")
    # Check offline route / offline pack logic
    has_offline_rdp_in_main = "rdp" in html_text.lower() or "offline-pack" in html_text
    print(f"RDP output feeds main map:        {has_offline_rdp_in_main}")

    # 5. Distance from 309 Mey scars to current polyline
    print("\n--- 5. Distance from 309 Mey Scars to Current Polyline ---")
    scars_csv = Path("model/nh7_published_309_inventory.csv")
    df_scars = pd.read_csv(scars_csv)
    print(f"Total scars loaded: {len(df_scars)}")
    
    # Current polyline: coords from nh7_route.geojson as (lat, lon)
    poly_lat_lon = [(c[1], c[0]) for c in coords]
    
    scar_distances_m = []
    for _, row in df_scars.iterrows():
        slat = float(row["latitude"])
        slon = float(row["longitude"])
        d_m = min_dist_to_polyline_m(slat, slon, poly_lat_lon)
        scar_distances_m.append(d_m)
        
    median_d = np.median(scar_distances_m)
    p90_d = np.percentile(scar_distances_m, 90)
    max_d = np.max(scar_distances_m)
    p95_d = np.percentile(scar_distances_m, 95)
    mean_d = np.mean(scar_distances_m)

    print(f"Distance to Current Polyline (geojson/nh7_route.geojson):")
    print(f"  Median: {median_d:.2f} m")
    print(f"  Mean:   {mean_d:.2f} m")
    print(f"  p90:    {p90_d:.2f} m")
    print(f"  p95:    {p95_d:.2f} m")
    print(f"  Max:    {max_d:.2f} m")

    # Inspect scars with large distances (> 100m, > 500m)
    far_scars = [(i, d, df_scars.iloc[i]["latitude"], df_scars.iloc[i]["longitude"]) for i, d in enumerate(scar_distances_m) if d > 100]
    print(f"  Number of scars > 100m from polyline: {len(far_scars)} / 309 ({len(far_scars)/309*100:.1f}%)")
    very_far = [x for x in far_scars if x[1] > 500]
    print(f"  Number of scars > 500m from polyline: {len(very_far)} / 309")
    if very_far:
        for idx, d, lat, lon in sorted(very_far, key=lambda x: -x[1])[:5]:
            print(f"    Scar #{idx+1}: {d:.1f} m at ({lat:.4f}, {lon:.4f})")

    # 6. Check which line model/build_static_dataset.py sampled DEM features along
    print("\n--- 6. Model Feature Sampling Line (model/build_static_dataset.py) ---")
    build_script = Path("model/build_static_dataset.py").read_text(encoding="utf-8")
    score_script = Path("model/score_segments.py").read_text(encoding="utf-8")
    
    print("In build_static_dataset.py:")
    for line in build_script.splitlines():
        if any(k in line for k in ["ROAD_CACHE_FILE", "SEGMENTS_FILE", "ROAD_GEOJSON_FILE", "nh7_segments.csv", "nh7_road_osm"]):
            print(" ", line.strip())
            
    print("\nIn score_segments.py:")
    for line in score_script.splitlines():
        if any(k in line for k in ["ROAD_CACHE_FILE", "road_points", "coarse_xy", "DEFAULT_SEGMENTS"]):
            print(" ", line.strip())


if __name__ == "__main__":
    diagnose()
