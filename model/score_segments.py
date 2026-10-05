#!/usr/bin/env python3
"""
score_segments.py - STEP 3: turn the trained model into per-segment terrain scores for the backend
===================================================================================================
Reads  : nh7_static_model_v2.joblib (or nh7_static_model.joblib), nh7_road_osm_cache.json (real road, if step 1
         got it), optional --backend-segments CSV (default: the 18 seeded backend segments).
Writes : segment_static_scores.json / .csv  -> loaded by risk_service.py at backend start-up.

Method : sample points every 250 m along the road, compute the SAME features used in training, score each point,
         assign points to the 18 backend segments by position along the route, and take the 90th percentile of the
         point scores per segment (a segment is as risky as its worst stretches, not its average).
         The percentile RANK of that value among the 18 segments is the "terrain percentile" (0 = safest, 1 = riskiest).

Backend segments CSV columns (optional): id,name,sequence_order,start_lat,start_lng,end_lat,end_lng
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests
from scipy.stats import rankdata

import build_static_dataset as B
import nh7_features as F

# The 18 seeded backend segments (from the backend plan). `mock_risk` is the placeholder value from the mock data.
DEFAULT_SEGMENTS = [
    ("seg_01", "Rishikesh to Shivpuri", 1, 30.0869, 78.2676, 30.1357, 78.3892, 0.15),
    ("seg_02", "Shivpuri to Byasi", 2, 30.1357, 78.3892, 30.1472, 78.4839, 0.35),
    ("seg_03", "Byasi to Kaudiyala", 3, 30.1472, 78.4839, 30.0765, 78.5028, 0.72),
    ("seg_04", "Kaudiyala to Devprayag", 4, 30.0765, 78.5028, 30.1459, 78.5986, 0.42),
    ("seg_05", "Devprayag to Teen Dhara", 5, 30.1459, 78.5986, 30.2015, 78.6820, 0.78),
    ("seg_06", "Teen Dhara to Kirtinagar", 6, 30.2015, 78.6820, 30.2173, 78.7456, 0.20),
    ("seg_07", "Kirtinagar to Srinagar", 7, 30.2173, 78.7456, 30.2224, 78.7845, 0.18),
    ("seg_08", "Srinagar to Sirobagarh", 8, 30.2224, 78.7845, 30.2390, 78.8540, 0.92),
    ("seg_09", "Sirobagarh to Rudraprayag", 9, 30.2390, 78.8540, 30.2844, 78.9811, 0.88),
    ("seg_10", "Rudraprayag to Gauchar", 10, 30.2844, 78.9811, 30.2872, 79.1557, 0.48),
    ("seg_11", "Gauchar to Karnaprayag", 11, 30.2872, 79.1557, 30.2587, 79.2173, 0.25),
    ("seg_12", "Karnaprayag to Langasu", 12, 30.2587, 79.2173, 30.2980, 79.2550, 0.38),
    ("seg_13", "Langasu to Nandprayag", 13, 30.2980, 79.2550, 30.3308, 79.3242, 0.44),
    ("seg_14", "Nandprayag to Chamoli", 14, 30.3308, 79.3242, 30.4074, 79.3524, 0.68),
    ("seg_15", "Chamoli to Birahi", 15, 30.4074, 79.3524, 30.4350, 79.3900, 0.75),
    ("seg_16", "Birahi to Pipalkoti", 16, 30.4350, 79.3900, 30.4297, 79.4304, 0.50),
    ("seg_17", "Pipalkoti to Helang (Tangani)", 17, 30.4297, 79.4304, 30.5280, 79.5380, 0.94),
    ("seg_18", "Helang to Joshimath", 18, 30.5280, 79.5380, 30.5564, 79.5663, 0.81),
]
SEG_COLS = ["id", "name", "sequence_order", "start_lat", "start_lng", "end_lat", "end_lng", "mock_risk"]
PRETTY = {
    "dem_slope_deg": "slope", "slope_deg": "slope", "dem_elev_m": "elevation", "elevation_m": "elevation",
    "dem_tpi_300m": "ridge/valley position (TPI)", "dem_relief_300m": "local relief", "local_relief_m": "local relief",
    "dem_curvature": "terrain curvature", "dist_river_km": "distance to river", "dist_stream_km": "distance to stream",
    "aspect_sin": "slope aspect (east-west)", "aspect_cos": "slope aspect (north-south)",
    "dem_aspect_sin": "slope aspect (east-west)", "dem_aspect_cos": "slope aspect (north-south)",
    "dist_fault_km": "distance to fault", "near_widened_100m": "recent road widening nearby",
}
FACE_VALIDITY = {"seg_08": "Srinagar-Sirobagarh", "seg_09": "Sirobagarh-Rudraprayag"}   # documented chronic slide zone


def pretty(name):
    return "lithology " + name[len("litho_"):] if name.startswith("litho_") else PRETTY.get(name, name)


def load_backend_segments(path):
    if path:
        seg = pd.read_csv(path)
        if "mock_risk" not in seg:
            seg["mock_risk"] = np.nan
        return seg[SEG_COLS].sort_values("sequence_order").reset_index(drop=True)
    return pd.DataFrame(DEFAULT_SEGMENTS, columns=SEG_COLS)


def road_points(proj, coarse_xy, a_min, a_max, step_km):
    """Points along the real road (OSM cache) inside the corridor; falls back to the straight route polyline."""
    cache = Path(B.ROAD_CACHE_FILE)
    if cache.exists():
        ways = [[tuple(p) for p in w] for w in json.loads(cache.read_text(encoding="utf-8")).get("ways", [])]
        if ways:
            pts, _ = B.densify_polyline_ways(ways, proj, step_km)
            d, _, along, _ = B.project_to_polyline(pts, coarse_xy)
            keep = (along >= a_min - 1.0) & (along <= a_max + 1.0) & (d <= 12.0)
            if keep.sum() > 20:
                return pts[keep], "real road (OpenStreetMap cache)"
    pts, _ = B.densify_polyline(coarse_xy, step_km)
    return pts, "STRAIGHT-LINE route polyline (no OSM road found: points may not lie on the actual road)"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model")
    ap.add_argument("--backend-segments")
    ap.add_argument("--step-km", type=float, default=0.25)
    ap.add_argument("--out", default="segment_static_scores")
    args = ap.parse_args(argv)

    model_path = args.model or ("nh7_static_model_v2.joblib" if Path("nh7_static_model_v2.joblib").exists()
                                else "nh7_static_model.joblib")
    if not Path(model_path).exists():
        print("ERROR: no trained model found. Run build_static_dataset.py (and add_features.py) first.")
        return 1
    bundle = joblib.load(model_path)
    cfg, cols = bundle["feature_config"], bundle["feature_columns"]
    print(f"Model: {bundle['model_name']} | features: {len(cols)} | terrain source: {cfg.get('terrain_source')}")

    bseg = load_backend_segments(args.backend_segments)
    verts = [(bseg.start_lat[0], bseg.start_lng[0])] + list(zip(bseg.end_lat, bseg.end_lng))
    proj = B.Proj(float(np.mean([v[0] for v in verts])))
    route_xy = proj.xy([v[0] for v in verts], [v[1] for v in verts])
    contiguous = all(np.hypot(*(proj.xy([bseg.end_lat[i]], [bseg.end_lng[i]])[0]
                               - proj.xy([bseg.start_lat[i + 1]], [bseg.start_lng[i + 1]])[0])) < 0.1
                     for i in range(len(bseg) - 1))
    if not contiguous:
        print("ERROR: backend segments are not contiguous (each end must equal the next start).")
        return 1
    _, _, _, total = B.project_to_polyline(route_xy[:1], route_xy)
    cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(route_xy, axis=0).T))])

    pts_xy, how = road_points(proj, route_xy, 0.0, total, args.step_km)
    print(f"Scoring points: {len(pts_xy)} every ~{args.step_km * 1000:.0f} m on the {how}")

    # assign points to backend segments by position along the route; any segment left empty is scored on its
    # straight chord instead (flagged), because "no data" must never silently look like "safe"
    _, _, along0, _ = B.project_to_polyline(pts_xy, route_xy)
    seg_idx = np.clip(np.searchsorted(cum[1:], along0, side="left"), 0, len(bseg) - 1)
    source = np.array(["road"] * len(pts_xy), dtype=object)
    extra_xy, extra_idx = [], []
    for i in range(len(bseg)):
        if not (seg_idx == i).any():
            chord, _ = B.densify_polyline(route_xy[i:i + 2], args.step_km)
            extra_xy.append(chord)
            extra_idx += [i] * len(chord)
            print(f"  [WARN] {bseg.id[i]}: no road points found; scoring along the straight chord instead "
                  "(not on the road: treat this segment's score with extra caution)")
    if extra_xy:
        pts_xy = np.vstack([pts_xy] + extra_xy)
        seg_idx = np.concatenate([seg_idx, extra_idx]).astype(int)
        source = np.concatenate([source, np.array(["chord"] * len(extra_idx), dtype=object)])

    lat, lon = proj.latlon(pts_xy)
    pts = pd.DataFrame({"latitude": lat, "longitude": lon})
    bbox = (lat.min() - 0.03, lon.min() - 0.03, lat.max() + 0.03, lon.max() + 0.03)
    session = requests.Session()
    session.headers.update({"User-Agent": "nh7-landslide-hackathon/1.0"})
    feats = F.FeatureEngine(cfg, session, bbox, proj).frame(pts)
    ok = feats.notna().all(axis=1).to_numpy()
    print(f"Feature rows complete: {int(ok.sum())}/{len(pts)}")
    if ok.sum() < 50:
        print("ERROR: too few scoring points have complete features. Read the messages above.")
        return 1
    feats, seg_idx, source = feats[ok].reset_index(drop=True), seg_idx[ok], source[ok]

    p = bundle["model"].predict_proba(feats[cols].to_numpy(float))[:, 1]

    imp = bundle.get("feature_importance", {})
    mu, sd = feats[cols].mean(), feats[cols].std().replace(0, 1)
    rows = []
    for i, s in bseg.iterrows():
        m = seg_idx == i
        if m.sum() == 0:
            rows.append({**s.to_dict(), "n_points": 0, "static_p90": np.nan, "static_mean": np.nan,
                         "driver": "no usable scoring points", "points_source": "none"})
            print(f"  [WARN] {s['id']}: no usable scoring points (features failed); it will be reported as no_data")
            continue
        z = (feats.loc[m, cols].mean() - mu) / sd
        if bundle.get("model_kind") == "LR":
            contrib = {c: imp.get(c, 0.0) * z[c] for c in cols}
            top = max(contrib, key=contrib.get)
            driver = f"{'high' if z[top] > 0 else 'low'} {pretty(top)} (z={z[top]:+.1f})"
        else:
            contrib = {c: abs(imp.get(c, 0.0)) * abs(z[c]) for c in cols}
            top = max(contrib, key=contrib.get)
            driver = f"unusual {pretty(top)} for this road ({'high' if z[top] > 0 else 'low'}, z={z[top]:+.1f})"
        rows.append({**s.to_dict(), "n_points": int(m.sum()), "static_p90": float(np.quantile(p[m], 0.9)),
                     "static_mean": float(p[m].mean()), "driver": driver,
                     "points_source": "chord" if (source[m] == "chord").all() else "road"})
    out = pd.DataFrame(rows)
    valid = out.static_p90.notna()
    ranks = rankdata(out.loc[valid, "static_p90"].to_numpy())
    out["terrain_percentile"] = np.nan
    out.loc[valid, "terrain_percentile"] = (ranks - 1) / max(len(ranks) - 1, 1)
    out["model_name"] = bundle["model_name"]
    out["generated"] = datetime.now(timezone.utc).isoformat()

    out.to_csv(args.out + ".csv", index=False, encoding="utf-8")
    Path(args.out + ".json").write_text(json.dumps(out.replace({np.nan: None}).to_dict("records"), indent=2),
                                        encoding="utf-8")

    print(f"\n{'seg':7s}{'name':34s}{'pts':>5s}{'p90':>7s}{'pctile':>8s}  {'src':5s} driver")
    for _, r in out.iterrows():
        print(f"{r['id']:7s}{r['name'][:33]:34s}{r['n_points']:5d}{r['static_p90']:7.2f}{r['terrain_percentile']:8.2f}  "
              f"{r['points_source']:5s} {r['driver']}")
    # face validity only: Sirobagarh is a documented chronic slide zone (NOT proof of accuracy)
    rank_desc = rankdata(-out.static_p90.fillna(-1))
    for sid, label in FACE_VALIDITY.items():
        print(f"face-validity: {label} ({sid}) ranks #{int(rank_desc[(out.id == sid).to_numpy()][0])} of {len(out)} "
              "(documented chronic slide zone; a sanity check, not a validation)")
    print(f"\nSaved {args.out}.json and {args.out}.csv  -> copy segment_static_scores.json next to risk_service.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
