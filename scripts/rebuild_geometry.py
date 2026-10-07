#!/usr/bin/env python3
"""
scripts/rebuild_geometry.py - Rebuilds the NH-7 road centerline and segment geometries.

1. Resamples geojson/nh7_route.geojson to a vertex every 50 m.
2. Snaps the 19 boundary towns onto the resampled line.
3. Generates dense subpoints (~150 m spacing) for each segment.
4. Updates app/seed_data.py, nh7_segments.csv, and model/score_segments.py.
5. Runs reset_db.py to update the SQLite database.
"""
import json
import math
import shutil
from pathlib import Path
import numpy as np
import pandas as pd


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def main():
    root = Path(__file__).resolve().parent.parent
    geojson_path = root / "geojson" / "nh7_route.geojson"
    geojson_bak = root / "geojson" / "nh7_route.geojson.bak"

    if not geojson_bak.exists():
        shutil.copyfile(geojson_path, geojson_bak)
        print(f"Backed up {geojson_path} to {geojson_bak}")

    with open(geojson_bak, "r", encoding="utf-8") as f:
        gj_data = json.load(f)

    # 1. Resample centerline
    raw_coords = [(c[1], c[0], c[2] if len(c) > 2 else 0.0) for c in gj_data["features"][0]["geometry"]["coordinates"]]

    # Cumulative distance
    dists = [0.0]
    for i in range(len(raw_coords) - 1):
        dists.append(dists[-1] + haversine_m(raw_coords[i][0], raw_coords[i][1], raw_coords[i+1][0], raw_coords[i+1][1]))
    total_dist = dists[-1]
    print(f"Raw centerline: {len(raw_coords)} vertices, {total_dist/1000.0:.2f} km")

    step_m = 50.0
    target_dists = np.arange(0.0, total_dist, step_m)
    if target_dists[-1] < total_dist:
        target_dists = np.append(target_dists, total_dist)

    resampled = []
    curr_idx = 0
    for td in target_dists:
        while curr_idx < len(dists) - 1 and dists[curr_idx + 1] < td:
            curr_idx += 1
        if curr_idx >= len(dists) - 1:
            resampled.append(raw_coords[-1])
            continue
        seg_d = dists[curr_idx + 1] - dists[curr_idx]
        frac = 0.0 if seg_d == 0 else (td - dists[curr_idx]) / seg_d
        lat = raw_coords[curr_idx][0] + frac * (raw_coords[curr_idx + 1][0] - raw_coords[curr_idx][0])
        lon = raw_coords[curr_idx][1] + frac * (raw_coords[curr_idx + 1][1] - raw_coords[curr_idx][1])
        ele = raw_coords[curr_idx][2] + frac * (raw_coords[curr_idx + 1][2] - raw_coords[curr_idx][2])
        resampled.append((lat, lon, ele))

    res_chainage = [0.0]
    for i in range(len(resampled) - 1):
        res_chainage.append(res_chainage[-1] + haversine_m(resampled[i][0], resampled[i][1], resampled[i+1][0], resampled[i+1][1]) / 1000.0)

    print(f"Resampled: {len(resampled)} vertices, {res_chainage[-1]:.2f} km (step ~{step_m} m)")

    # Save resampled GeoJSON
    gj_out = dict(gj_data)
    gj_out["features"][0]["geometry"]["coordinates"] = [
        [round(p[1], 6), round(p[0], 6), round(p[2], 1)] for p in resampled
    ]
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(gj_out, f, indent=2)
    print(f"Saved resampled GeoJSON to {geojson_path}")

    # 2. Boundary snapping
    boundaries = [
        ('Rishikesh', 30.0869, 78.2676),
        ('Shivpuri', 30.1357, 78.3892),
        ('Byasi', 30.1472, 78.4839),
        ('Kaudiyala', 30.0765, 78.5028),
        ('Devprayag', 30.1459, 78.5986),
        ('Teen Dhara', 30.2015, 78.6820),
        ('Kirtinagar', 30.2173, 78.7456),
        ('Srinagar', 30.2224, 78.7845),
        ('Sirobagarh', 30.2390, 78.8540),
        ('Rudraprayag', 30.2844, 78.9811),
        ('Gauchar', 30.2872, 79.1557),
        ('Karnaprayag', 30.2587, 79.2173),
        ('Langasu', 30.2980, 79.2550),
        ('Nandprayag', 30.3308, 79.3242),
        ('Chamoli', 30.4074, 79.3524),
        ('Birahi', 30.4350, 79.3900),
        ('Pipalkoti', 30.4297, 79.4304),
        ('Helang', 30.5280, 79.5380),
        ('Joshimath', 30.5564, 79.5663),
    ]

    snapped_indices = [0]
    for name, lat, lng in boundaries[1:-1]:
        dists_to_town = [haversine_m(lat, lng, r[0], r[1]) for r in resampled]
        snapped_indices.append(int(np.argmin(dists_to_town)))
    snapped_indices.append(len(resampled) - 1)

    assert all(snapped_indices[i] < snapped_indices[i+1] for i in range(len(snapped_indices)-1)), "Indices must be strictly increasing"
    print("All 19 boundaries snapped strictly monotonically.")

    # 3. Build dense subpoints for the 18 segments
    seg_names = [
        ("seg_01", "Rishikesh to Shivpuri", "Low", 0.15),
        ("seg_02", "Shivpuri to Byasi", "Moderate", 0.35),
        ("seg_03", "Byasi to Kaudiyala", "High", 0.72),
        ("seg_04", "Kaudiyala to Devprayag", "Moderate", 0.42),
        ("seg_05", "Devprayag to Teen Dhara", "High", 0.78),
        ("seg_06", "Teen Dhara to Kirtinagar", "Low", 0.20),
        ("seg_07", "Kirtinagar to Srinagar", "Low", 0.18),
        ("seg_08", "Srinagar to Sirobagarh", "Very High", 0.92),
        ("seg_09", "Sirobagarh to Rudraprayag", "Very High", 0.88),
        ("seg_10", "Rudraprayag to Gauchar", "Moderate", 0.48),
        ("seg_11", "Gauchar to Karnaprayag", "Low", 0.25),
        ("seg_12", "Karnaprayag to Langasu", "Moderate", 0.38),
        ("seg_13", "Langasu to Nandprayag", "Moderate", 0.44),
        ("seg_14", "Nandprayag to Chamoli", "High", 0.68),
        ("seg_15", "Chamoli to Birahi", "High", 0.75),
        ("seg_16", "Birahi to Pipalkoti", "Moderate", 0.50),
        ("seg_17", "Pipalkoti to Helang (Tangani)", "Very High", 0.94),
        ("seg_18", "Helang to Joshimath", "High", 0.81),
    ]

    new_seed_segments = []
    default_segments_code = []

    for i, (sid, name, r_lvl, r_score) in enumerate(seg_names):
        s_idx, e_idx = snapped_indices[i], snapped_indices[i+1]
        
        # Take vertices every 3rd step (~150 m)
        stride = 3
        sub_pts = [[round(resampled[j][0], 5), round(resampled[j][1], 5)] for j in range(s_idx, e_idx + 1, stride)]
        end_pt = [round(resampled[e_idx][0], 5), round(resampled[e_idx][1], 5)]
        if sub_pts[-1] != end_pt:
            sub_pts.append(end_pt)
        
        start_lat = sub_pts[0][0]
        start_lng = sub_pts[0][1]
        end_lat = sub_pts[-1][0]
        end_lng = sub_pts[-1][1]

        seg_dict = {
            "id": sid,
            "name": name,
            "sequence_order": i + 1,
            "start_lat": start_lat,
            "start_lng": start_lng,
            "end_lat": end_lat,
            "end_lng": end_lng,
            "subpoints": sub_pts,
            "risk_level": r_lvl,
            "risk_score": r_score,
            "updated_at": "2026-10-02T10:00:00Z"
        }
        new_seed_segments.append(seg_dict)
        default_segments_code.append(
            f'    ("{sid}", "{name}", {i+1}, {start_lat:.4f}, {start_lng:.4f}, {end_lat:.4f}, {end_lng:.4f}, {r_score}),'
        )
        print(f"{sid} ({name}): {len(sub_pts)} subpoints, length {(res_chainage[e_idx]-res_chainage[s_idx]):.2f} km")

    # 4. Update app/seed_data.py
    seed_data_path = root / "app" / "seed_data.py"
    seed_content = seed_data_path.read_text(encoding="utf-8")
    
    # Locate where SEED_SUBSCRIPTIONS begins
    sub_pos = seed_content.find("SEED_SUBSCRIPTIONS = [")
    assert sub_pos != -1, "Could not find SEED_SUBSCRIPTIONS in seed_data.py"
    tail_content = seed_content[sub_pos:]

    # Construct new SEED_SEGMENTS code
    segments_code = "SEED_SEGMENTS = [\n"
    for s in new_seed_segments:
        segments_code += "    {\n"
        segments_code += f'        "id": "{s["id"]}",\n'
        segments_code += f'        "name": "{s["name"]}",\n'
        segments_code += f'        "sequence_order": {s["sequence_order"]},\n'
        segments_code += f'        "start_lat": {s["start_lat"]},\n'
        segments_code += f'        "start_lng": {s["start_lng"]},\n'
        segments_code += f'        "end_lat": {s["end_lat"]},\n'
        segments_code += f'        "end_lng": {s["end_lng"]},\n'
        segments_code += f'        "subpoints": {json.dumps(s["subpoints"])},\n'
        segments_code += f'        "risk_level": "{s["risk_level"]}",\n'
        segments_code += f'        "risk_score": {s["risk_score"]},\n'
        segments_code += f'        "updated_at": "{s["updated_at"]}"\n'
        segments_code += "    },\n"
    segments_code = segments_code.rstrip(",\n") + "\n]\n\n"

    header = 'import json\nfrom datetime import datetime, timezone\n\n# 18 Named NH-7 Segments between Rishikesh and Joshimath\n# Each segment includes dense road-following subpoints spaced ~100-250 m apart\n'
    new_seed_data_text = header + segments_code + tail_content
    seed_data_path.write_text(new_seed_data_text, encoding="utf-8")
    print(f"Updated {seed_data_path}")

    # 5. Update nh7_segments.csv
    csv_path = root / "nh7_segments.csv"
    csv_rows = []
    for idx, pt in enumerate(resampled):
        csv_rows.append({
            "segment_id": idx,
            "longitude": round(pt[1], 6),
            "latitude": round(pt[0], 6)
        })
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
    print(f"Updated {csv_path} with {len(csv_rows)} points")

    # 6. Update DEFAULT_SEGMENTS in model/score_segments.py
    score_py_path = root / "model" / "score_segments.py"
    score_content = score_py_path.read_text(encoding="utf-8")
    start_tag = "DEFAULT_SEGMENTS = [\n"
    end_tag = "]\nSEG_COLS ="
    s_idx = score_content.find(start_tag)
    e_idx = score_content.find(end_tag)
    if s_idx != -1 and e_idx != -1:
        new_def_segs = start_tag + "\n".join(default_segments_code) + "\n"
        score_content = score_content[:s_idx] + new_def_segs + score_content[e_idx:]
        score_py_path.write_text(score_content, encoding="utf-8")
        print(f"Updated DEFAULT_SEGMENTS in {score_py_path}")

    print("Rebuild completed successfully!")


if __name__ == "__main__":
    main()
