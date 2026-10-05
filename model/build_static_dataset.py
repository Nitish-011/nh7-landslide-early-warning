#!/usr/bin/env python3
"""
NH-7 STATIC landslide-susceptibility dataset + spatial-block CV
================================================================

Positives : Mey et al. (2024) inventory of 309 road-blocking landslides along
            NH-7 (Rishikesh-Joshimath), file: nh7_published_309_inventory.csv
Negatives : background points on the real road (OpenStreetMap) whose distance
            to the road mirrors the positives' distance distribution.
            If OSM is unreachable, falls back to offset-matched sampling around
            your nh7_segments.csv polyline ("Mode B").
Features  : terrain only (elevation, slope, aspect, local relief) from the
            Open-Meteo 90 m elevation API. NO rainfall: rainfall is applied at
            serving time in the backend, not learned here.
Checks    : (1) leak test - distance-to-route alone must NOT predict the label,
            (2) terrain source vs. the inventory's own 30 m DEM elevation,
            (3) spatial-block CV along the road with a buffer between blocks.

Quick test run:   python build_static_dataset.py --limit 30
Full run:         python build_static_dataset.py

Citation (keep in your pitch / paper):
  Mey, J., Guntu, R. K., Plakias, A., Silva de Almeida, I., and Schwanghart, W.
  (2024). More than one landslide per road kilometer - surveying and modelling
  mass movements along the Rishikesh-Joshimath (NH-7) highway, Uttarakhand,
  India. Nat. Hazards Earth Syst. Sci., 24, 3207. doi:10.5194/nhess-24-3207-2024
  (Check the supplement's license/terms before redistributing the data.)
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
INVENTORY_FILE = "nh7_published_309_inventory.csv"
SEGMENTS_FILE = "nh7_segments.csv"
ROAD_CACHE_FILE = "nh7_road_osm_cache.json"
ROAD_GEOJSON_FILE = "nh7_road_osm.geojson"      # optional manual Overpass-Turbo export
TERRAIN_CACHE_FILE = "terrain_cache_static.json"

OUT_DATA = "nh7_static_training_data.csv"
OUT_META = "pipeline_meta_static.json"
OUT_NOTES = "DATA_NOTES_static.md"
OUT_PLOTS = "diagnostic_plots_static.png"
OUT_MODEL = "nh7_static_model.joblib"
OUT_CV = "cv_report_static.json"

SLOPE_OFFSET_M = 150.0          # finite-difference offset; DEM is 90 m so stay > 90
FEATURES = ["elevation_m", "slope_deg", "aspect_sin", "aspect_cos", "local_relief_m"]

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OPEN_METEO_ELEV = "https://api.open-meteo.com/v1/elevation"

LEAK_MAX_DEVIATION = 0.07       # |AUC - 0.5| of distance-to-route alone must stay below this
OSM_ACCEPT_SHARE = 0.80         # share of positives within 300 m of OSM road
OSM_ACCEPT_DIST_KM = 0.30
MAX_OFFSET_KM = 10.0            # sanity cap on lateral offsets copied from positives

CITATION = (
    "Mey, J., Guntu, R. K., Plakias, A., Silva de Almeida, I., and Schwanghart, W. (2024). "
    "More than one landslide per road kilometer - surveying and modelling mass movements along "
    "the Rishikesh-Joshimath (NH-7) highway, Uttarakhand, India. Nat. Hazards Earth Syst. Sci., "
    "24, 3207. https://doi.org/10.5194/nhess-24-3207-2024"
)


# ----------------------------------------------------------------------
# GEOMETRY
# ----------------------------------------------------------------------
class Proj:
    """Local equirectangular projection to kilometres (fine at corridor scale)."""

    def __init__(self, lat0: float):
        self.kx = 111.320 * math.cos(math.radians(lat0))
        self.ky = 110.574

    def xy(self, lat, lon) -> np.ndarray:
        return np.column_stack([np.asarray(lon, float) * self.kx, np.asarray(lat, float) * self.ky])

    def latlon(self, xy: np.ndarray):
        return xy[:, 1] / self.ky, xy[:, 0] / self.kx


def densify_polyline(xy: np.ndarray, step_km: float):
    """Points every step_km along a polyline, with a unit tangent for each point."""
    pts, tans = [], []
    for a, b in zip(xy[:-1], xy[1:]):
        d = b - a
        length = float(np.hypot(*d))
        if length == 0:
            continue
        t = d / length
        s = np.arange(0.0, length, step_km)
        pts.append(a + s[:, None] * t)
        tans.append(np.tile(t, (len(s), 1)))
    if not pts:
        return np.empty((0, 2)), np.empty((0, 2))
    return np.vstack(pts), np.vstack(tans)


def project_to_polyline(q_xy: np.ndarray, poly_xy: np.ndarray):
    """Distance (km), signed distance, along-line position (km) of each query point."""
    a, b = poly_xy[:-1], poly_xy[1:]
    d = b - a
    l2 = (d ** 2).sum(1)
    seg_len = np.sqrt(l2)
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    best = np.full(len(q_xy), np.inf)
    along = np.zeros(len(q_xy))
    sign = np.ones(len(q_xy))
    for i in range(len(a)):
        if l2[i] == 0:
            continue
        w = q_xy - a[i]
        t = np.clip((w @ d[i]) / l2[i], 0.0, 1.0)
        proj = a[i] + t[:, None] * d[i]
        dist = np.hypot(q_xy[:, 0] - proj[:, 0], q_xy[:, 1] - proj[:, 1])
        cross = d[i, 0] * w[:, 1] - d[i, 1] * w[:, 0]
        better = dist < best
        best[better] = dist[better]
        along[better] = cum[i] + t[better] * seg_len[i]
        sign[better] = np.where(cross[better] >= 0, 1.0, -1.0)
    return best, best * sign, along, float(cum[-1])


# ----------------------------------------------------------------------
# INPUTS
# ----------------------------------------------------------------------
def load_inventory(path: str) -> pd.DataFrame:
    inv = pd.read_csv(path)
    low = {c.lower(): c for c in inv.columns}
    lat = next((low[k] for k in ("latitude", "lat") if k in low), None)
    lon = next((low[k] for k in ("longitude", "lon", "lng") if k in low), None)
    if lat is None or lon is None:
        raise ValueError(f"{path}: need latitude/longitude columns, found {list(inv.columns)}")
    inv = inv.rename(columns={lat: "latitude", lon: "longitude"})
    inv["latitude"] = pd.to_numeric(inv["latitude"], errors="coerce")
    inv["longitude"] = pd.to_numeric(inv["longitude"], errors="coerce")
    inv = inv.dropna(subset=["latitude", "longitude"]).drop_duplicates(["latitude", "longitude"])
    return inv.reset_index(drop=True)


def load_segments(path: str) -> pd.DataFrame:
    seg = pd.read_csv(path)
    low = {c.lower(): c for c in seg.columns}
    lat = next((low[k] for k in ("latitude", "lat") if k in low), None)
    lon = next((low[k] for k in ("longitude", "lon", "lng") if k in low), None)
    if lat is None or lon is None:
        raise ValueError(f"{path}: need latitude/longitude columns, found {list(seg.columns)}")
    seg = seg.rename(columns={lat: "latitude", lon: "longitude"}).dropna(subset=["latitude", "longitude"])
    seg = seg.reset_index(drop=True)
    if len(seg) < 2:
        raise ValueError(f"{path}: need at least 2 route vertices")
    trend = abs(np.corrcoef(np.arange(len(seg)), seg["longitude"])[0, 1])
    if trend < 0.9:
        print(f"  [WARN] {path} rows do not look ordered from Rishikesh to Joshimath "
              f"(|corr(row, longitude)|={trend:.2f}). Along-route blocks may be wrong.")
    return seg


# ----------------------------------------------------------------------
# ROAD GEOMETRY (OpenStreetMap)
# ----------------------------------------------------------------------
def overpass_query(bbox):
    s, w, n, e = bbox
    return (
        "[out:json][timeout:90];\n"
        f'way["highway"]["ref"~"^NH ?(7|58)(;.*)?$"]({s:.4f},{w:.4f},{n:.4f},{e:.4f});\n'
        "out geom;"
    )


def parse_overpass_json(payload):
    ways = []
    for el in payload.get("elements", []):
        if el.get("type") != "way":
            continue
        if str((el.get("tags") or {}).get("highway", "")).endswith("_link"):
            continue
        geom = el.get("geometry") or []
        if len(geom) >= 2:
            ways.append([(g["lat"], g["lon"]) for g in geom])
    return ways


def parse_geojson(gj):
    ways = []
    for f in gj.get("features", []):
        if str((f.get("properties") or {}).get("highway", "")).endswith("_link"):
            continue
        g = f.get("geometry") or {}
        if g.get("type") == "LineString":
            lines = [g["coordinates"]]
        elif g.get("type") == "MultiLineString":
            lines = g["coordinates"]
        else:
            continue
        for line in lines:
            if len(line) >= 2:
                ways.append([(c[1], c[0]) for c in line])
    return ways


def load_road_ways(bbox, session, use_osm=True):
    """Returns (ways or None, description). Order: cache -> manual geojson -> Overpass."""
    if not use_osm:
        return None, "OSM disabled by --no-osm"
    cache = Path(ROAD_CACHE_FILE)
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("ways"):
                return [[tuple(p) for p in w] for w in data["ways"]], f"cache {ROAD_CACHE_FILE}"
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] could not read {ROAD_CACHE_FILE}: {e}")
    gj_path = Path(ROAD_GEOJSON_FILE)
    if gj_path.exists():
        try:
            ways = parse_geojson(json.loads(gj_path.read_text(encoding="utf-8")))
            if ways:
                return ways, f"manual export {ROAD_GEOJSON_FILE}"
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] could not read {ROAD_GEOJSON_FILE}: {e}")

    q = overpass_query(bbox)
    last = "no response"
    for url in OVERPASS_URLS:
        try:
            print(f"  Querying Overpass: {url}")
            r = session.post(url, data={"data": q}, timeout=150)
            if r.status_code != 200:
                last = f"HTTP {r.status_code} from {url}: {r.text[:150]!r}"
                print(f"  [Overpass fail] {last}")
                continue
            ways = parse_overpass_json(r.json())
            if not ways:
                last = "Overpass returned 0 ways for ref NH 7 / NH 58 in this bbox"
                print(f"  [Overpass empty] {last}")
                continue
            Path(ROAD_CACHE_FILE).write_text(
                json.dumps({"bbox": bbox, "fetched": datetime.now(timezone.utc).isoformat(),
                            "query": q, "ways": ways}), encoding="utf-8")
            return ways, f"Overpass API ({len(ways)} ways)"
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
            print(f"  [Overpass exception] {url}: {last}")
    print("  Tip: open https://overpass-turbo.eu, run this query, Export -> GeoJSON, and save it as\n"
          f"       {ROAD_GEOJSON_FILE} next to this script:\n" + "\n".join("       " + l for l in q.splitlines()))
    return None, f"OSM unavailable ({last})"


# ----------------------------------------------------------------------
# NEGATIVE SAMPLING (distance-matched)
# ----------------------------------------------------------------------
def sample_negatives(pool_pts, pool_tans, offsets_km, pos_xy, n_target, min_sep_km, rng, ref_tree,
                     min_spacing_km=0.10, passes=8, tol_abs_km=0.05, tol_rel=0.15):
    """
    Take points from the reference-line pool, push each sideways by a distance drawn from the
    positives' own distance-to-line distribution, and keep it only if
      * its MEASURED distance to the reference line (same KD-tree used for the positives) is within
        tolerance of the drawn target (near bends a sideways push can land closer to another segment),
      * it is >= min_sep_km from every positive, and
      * it is >= min_spacing_km from the other negatives.
    """
    pos_tree = cKDTree(pos_xy)
    acc = np.empty((n_target, 2))
    n = 0
    offsets = np.asarray(offsets_km, float)
    offsets = offsets[offsets <= MAX_OFFSET_KM]
    if len(offsets) == 0:
        offsets = np.array([0.0])
    for _ in range(passes):
        for idx in rng.permutation(len(pool_pts)):
            t = pool_tans[idx]
            normal = np.array([-t[1], t[0]])
            off = float(rng.choice(offsets))
            p = pool_pts[idx] + normal * off * rng.choice([-1.0, 1.0])
            if abs(ref_tree.query(p)[0] - off) > max(tol_abs_km, tol_rel * off):
                continue
            if pos_tree.query(p)[0] < min_sep_km:
                continue
            if n and np.min(np.hypot(acc[:n, 0] - p[0], acc[:n, 1] - p[1])) < min_spacing_km:
                continue
            acc[n] = p
            n += 1
            if n >= n_target:
                return acc[:n]
    return acc[:n]


# ----------------------------------------------------------------------
# TERRAIN (Open-Meteo elevation, finite differences)
# ----------------------------------------------------------------------
def stencil(lat, lon, h):
    d_lat = h / 110574.0
    d_lon = h / (111320.0 * math.cos(math.radians(lat)))
    return [(lat, lon), (lat + d_lat, lon), (lat - d_lat, lon), (lat, lon + d_lon), (lat, lon - d_lon)]


def cache_key(lat, lon, h):
    return f"{lat:.5f},{lon:.5f},{int(h)}"


def request_elevation(session, coords, max_attempts=5):
    """Return (ok, values, reason). reason == 'bad_request' means: try a smaller batch."""
    params = {"latitude": ",".join(f"{c[0]:.6f}" for c in coords),
              "longitude": ",".join(f"{c[1]:.6f}" for c in coords)}
    wait = 2.0
    reason = "unknown"
    for attempt in range(1, max_attempts + 1):
        try:
            r = session.get(OPEN_METEO_ELEV, params=params, timeout=30)
            if r.status_code == 400:
                return False, None, f"bad_request: {r.text[:200]}"
            if r.status_code in (429, 500, 502, 503, 504):
                reason = f"HTTP {r.status_code}"
                retry_after = r.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else wait)
                wait = min(wait * 2, 30)
                continue
            r.raise_for_status()
            vals = r.json().get("elevation")
            if isinstance(vals, list) and len(vals) == len(coords) and all(v is not None for v in vals):
                return True, [float(v) for v in vals], "ok"
            reason = f"malformed response: {str(r.text)[:200]}"
            print(f"  [Terrain malformed] attempt {attempt}/{max_attempts}: {reason}")
        except Exception as e:  # noqa: BLE001
            reason = f"{type(e).__name__}: {e}"
            print(f"  [Terrain exception] attempt {attempt}/{max_attempts}: {reason}")
        time.sleep(wait)
        wait = min(wait * 2, 30)
    return False, None, reason


def fetch_terrain(points, session, h, batch_pts=20, pause=0.3):
    """points: list of (lat, lon). Returns (cache_dict, list_of_failed_points)."""
    cache_path = Path(TERRAIN_CACHE_FILE)
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cache = {}
    todo = [p for p in points if cache_key(p[0], p[1], h) not in cache]
    print(f"  Terrain: {len(points)} points, {len(points) - len(todo)} cached, {len(todo)} to fetch")
    failed, i, bs = [], 0, max(1, batch_pts)
    while i < len(todo):
        batch = todo[i:i + bs]
        coords = [c for p in batch for c in stencil(p[0], p[1], h)]
        ok, vals, reason = request_elevation(session, coords)
        if ok:
            for j, p in enumerate(batch):
                cache[cache_key(p[0], p[1], h)] = vals[j * 5:(j + 1) * 5]
            i += len(batch)
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
            if i % 100 < len(batch):
                print(f"    fetched {i}/{len(todo)}")
            time.sleep(pause)
        elif len(batch) > 1:
            bs = max(1, len(batch) // 2)
            print(f"  [Terrain batch failed] {reason} -> retrying with batch of {bs} points")
        else:
            failed.append(batch[0])
            print(f"  [Terrain GAVE UP] lat={batch[0][0]:.5f} lon={batch[0][1]:.5f}: {reason}")
            i += 1
    return cache, failed


def elevation_check(df):
    """Compare API elevation at the positives with the inventory's own DEM elevation (gross-error detector)."""
    chk = df[(df.label == 1) & df["elevation_m_inventory"].notna()]
    if len(chk) < 5:
        return {}
    diff = (chk["elevation_m"] - chk["elevation_m_inventory"]).abs()
    r = float(np.corrcoef(chk["elevation_m"], chk["elevation_m_inventory"])[0, 1])
    med = float(diff.median())
    # A 90 m DEM vs a 30 m DEM legitimately differs by tens of metres on steep road cuts, so the bar is lenient:
    # this only catches gross errors (swapped lat/lon, wrong units, broken API).
    ok = med <= 150 and r >= 0.90
    return {"n": int(len(chk)), "median_abs_diff_m": med, "pearson_r": r,
            "verdict": "OK" if ok else "CHECK: large mismatch - verify lat/lon order and the elevation API"}


def terrain_features(z5, h):
    zc, zn, zs, ze, zw = z5
    dz_dx = (ze - zw) / (2 * h)
    dz_dy = (zn - zs) / (2 * h)
    grad = math.hypot(dz_dx, dz_dy)
    slope = math.degrees(math.atan(grad))
    if grad == 0:
        a_sin = a_cos = 0.0
    else:
        # bearing (clockwise from north) of the DOWNSLOPE direction (east, north) = (-dz_dx, -dz_dy)
        aspect = math.atan2(-dz_dx, -dz_dy)
        a_sin, a_cos = math.sin(aspect), math.cos(aspect)
    return {
        "elevation_m": zc, "slope_deg": slope, "aspect_sin": a_sin, "aspect_cos": a_cos,
        "local_relief_m": max(z5) - min(z5),
    }


# ----------------------------------------------------------------------
# MODELS + SPATIAL-BLOCK CV
# ----------------------------------------------------------------------
def make_lr():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced"))


def make_rf(seed=42):
    return RandomForestClassifier(n_estimators=400, min_samples_leaf=5, class_weight="balanced_subsample",
                                  random_state=seed, n_jobs=-1)


def block_cv(df, cols, model_fn, buffer_km, min_pos_test=3):
    """Leave-one-block-out CV along the road, dropping training points within buffer_km of the test block."""
    oof = np.full(len(df), np.nan)
    per_block = []
    along = df["along_km"].to_numpy()
    y = df["label"].to_numpy()
    X = df[cols].to_numpy(float)
    for b in sorted(df["block_id"].unique()):
        te = (df["block_id"] == b).to_numpy()
        lo, hi = along[te].min(), along[te].max()
        tr = (~te) & ((along < lo - buffer_km) | (along > hi + buffer_km))
        if len(np.unique(y[tr])) < 2 or y[te].sum() < min_pos_test or y[te].sum() == te.sum():
            per_block.append(float("nan"))
            continue
        m = model_fn()
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        oof[te] = p
        per_block.append(float(roc_auc_score(y[te], p)))
    ok = ~np.isnan(oof)
    if ok.sum() == 0 or len(np.unique(y[ok])) < 2:
        return {"pooled_auc": float("nan"), "pooled_ap": float("nan"), "top20_capture": float("nan"),
                "block_auc": per_block, "block_auc_mean": float("nan"), "block_auc_std": float("nan"), "n_scored": 0}
    thr = np.quantile(oof[ok], 0.80)
    pos_scored = ok & (y == 1)
    return {
        "pooled_auc": float(roc_auc_score(y[ok], oof[ok])),
        "pooled_ap": float(average_precision_score(y[ok], oof[ok])),
        "top20_capture": float((oof[pos_scored] >= thr).mean()),
        "block_auc": per_block,
        "block_auc_mean": float(np.nanmean(per_block)),
        "block_auc_std": float(np.nanstd(per_block)),
        "n_scored": int(ok.sum()),
    }


def univariate_auc_ci(x, y, n_boot=500, seed=0):
    """Rank AUC of one feature vs the label, with a 95% bootstrap interval (no model, no CV noise)."""
    rng = np.random.default_rng(seed)
    auc = float(roc_auc_score(y, x))
    idx = np.arange(len(y))
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(idx, len(idx), replace=True)
        if len(np.unique(y[pick])) == 2:
            boots.append(roc_auc_score(y[pick], x[pick]))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return auc, float(lo), float(hi)


def leak_check(df, cols=("dist_coarse_km", "dist_ref_km")):
    """Distance-to-route alone must not predict the label. Returns (passed, details)."""
    details, passed = {}, True
    y = df["label"].to_numpy()
    for col in dict.fromkeys(cols):
        if col not in df:
            continue
        a, lo, hi = univariate_auc_ci(df[col].abs().to_numpy(), y)
        details[col] = {"auc": a, "ci95": [lo, hi]}
        if abs(a - 0.5) > LEAK_MAX_DEVIATION:
            passed = False
    return passed, details


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inventory", default=INVENTORY_FILE)
    ap.add_argument("--segments", default=SEGMENTS_FILE)
    ap.add_argument("--neg-ratio", type=float, default=3.0, help="negatives per positive (default 3)")
    ap.add_argument("--min-neg-sep-m", type=float, default=250.0, help="min distance from any positive (m)")
    ap.add_argument("--blocks", type=int, default=6, help="spatial blocks along the road for CV")
    ap.add_argument("--buffer-km", type=float, default=2.0, help="gap between train and test blocks")
    ap.add_argument("--limit", type=int, default=None, help="quick test: use only N positives")
    ap.add_argument("--no-osm", action="store_true", help="skip OpenStreetMap, use Mode B directly")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--batch-pts", type=int, default=20, help="points per elevation request (5 coords each)")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    rng = np.random.default_rng(args.seed)
    random.seed(args.seed)
    session = requests.Session()
    session.headers.update({"User-Agent": "nh7-landslide-hackathon/1.0"})

    print("1) Loading inventory and route ...")
    inv_full = load_inventory(args.inventory)
    seg = load_segments(args.segments)
    print(f"   inventory: {len(inv_full)} landslides | route file: {len(seg)} vertices")

    proj = Proj(float(inv_full["latitude"].mean()))
    coarse_xy = proj.xy(seg["latitude"], seg["longitude"])

    inv = inv_full
    n_blocks = args.blocks
    if args.limit:
        inv = inv_full.sample(n=min(args.limit, len(inv_full)), random_state=args.seed).reset_index(drop=True)
        n_blocks = min(n_blocks, 3)
        print(f"   [TEST MODE] using {len(inv)} positives, {n_blocks} blocks")
    pos_xy = proj.xy(inv["latitude"], inv["longitude"])

    d_c, _, along_c, route_len = project_to_polyline(pos_xy, coarse_xy)
    print(f"   route polyline length {route_len:.0f} km (real road is ~247 km; straight chords are shorter)")
    print(f"   positives' distance to your route polyline: median {np.median(d_c):.2f} km, max {d_c.max():.2f} km")
    a_min, a_max = float(along_c.min()), float(along_c.max())

    # ---------------- road geometry ----------------
    print("\n2) Road geometry ...")
    bbox = (inv_full.latitude.min() - 0.05, inv_full.longitude.min() - 0.05,
            inv_full.latitude.max() + 0.05, inv_full.longitude.max() + 0.05)
    ways, road_desc = load_road_ways(bbox, session, use_osm=not args.no_osm)
    mode, osm_stats = "B", {}
    ref_pool_pts = ref_pool_tans = None
    ref_tree = None
    if ways:
        pts25, _ = densify_polyline_ways(ways, proj, 0.025)
        tree25 = cKDTree(pts25)
        d_osm, _ = tree25.query(pos_xy)
        share = float((d_osm <= OSM_ACCEPT_DIST_KM).mean())
        osm_stats = {"source": road_desc, "positives_within_300m_share": share,
                     "median_dist_m": float(np.median(d_osm) * 1000), "p90_dist_m": float(np.quantile(d_osm, 0.9) * 1000)}
        print(f"   OSM road ({road_desc}): {share * 100:.0f}% of positives within 300 m "
              f"(median {osm_stats['median_dist_m']:.0f} m)")
        if share >= OSM_ACCEPT_SHARE:
            mode = "A"
            pool_pts, pool_tans = densify_polyline_ways(ways, proj, 0.10)
            dpool, _, apool, _ = project_to_polyline(pool_pts, coarse_xy)
            keep = (apool >= a_min - 1.0) & (apool <= a_max + 1.0) & (dpool <= 12.0)
            ref_pool_pts, ref_pool_tans = pool_pts[keep], pool_tans[keep]
            ref_tree = tree25
            offsets = d_osm
            print(f"   MODE A: negatives sampled on the real road ({len(ref_pool_pts)} candidate points)")
        else:
            print("   OSM geometry does not match the inventory well enough -> falling back to Mode B")
    else:
        print(f"   {road_desc}")
    if mode == "B":
        pool_pts, pool_tans = densify_polyline(coarse_xy, 0.10)
        _, _, apool, _ = project_to_polyline(pool_pts, coarse_xy)
        keep = (apool >= a_min - 1.0) & (apool <= a_max + 1.0)
        ref_pool_pts, ref_pool_tans = pool_pts[keep], pool_tans[keep]
        ref_pts50, _ = densify_polyline(coarse_xy, 0.05)
        ref_tree = cKDTree(ref_pts50)
        offsets, _ = ref_tree.query(pos_xy)
        print("   MODE B: offset-matched sampling around your route polyline. NOTE: negatives are matched "
              "on distance-to-route but are NOT guaranteed to lie on the actual road.")

    # ---------------- negatives ----------------
    print("\n3) Sampling distance-matched negatives ...")
    n_target = int(round(args.neg_ratio * len(inv)))
    neg_xy = sample_negatives(ref_pool_pts, ref_pool_tans, offsets, pos_xy, n_target,
                              args.min_neg_sep_m / 1000.0, rng, ref_tree)
    if len(neg_xy) < n_target:
        print(f"   [WARN] only {len(neg_xy)}/{n_target} negatives could be placed (pool exhausted)")
    nlat, nlon = proj.latlon(neg_xy)
    print(f"   {len(neg_xy)} negatives (ratio {len(neg_xy) / len(inv):.1f} : 1), "
          f">= {args.min_neg_sep_m:.0f} m from every positive")

    pos_df = pd.DataFrame({
        "label": 1, "source": "mey_2024_inventory",
        "latitude": inv["latitude"].to_numpy(), "longitude": inv["longitude"].to_numpy(),
        "landslide_id": inv["landslide_id"].to_numpy() if "landslide_id" in inv else np.arange(len(inv)),
        "elevation_m_inventory": inv["elevation_m_study"].to_numpy() if "elevation_m_study" in inv else np.nan,
    })
    neg_df = pd.DataFrame({"label": 0, "source": "road_background", "latitude": nlat, "longitude": nlon,
                           "landslide_id": np.nan, "elevation_m_inventory": np.nan})
    df = pd.concat([pos_df, neg_df], ignore_index=True)
    all_xy = proj.xy(df["latitude"], df["longitude"])
    d_all, sd_all, along_all, _ = project_to_polyline(all_xy, coarse_xy)
    df["dist_coarse_km"], df["along_km"] = d_all, along_all
    df["dist_ref_km"] = ref_tree.query(all_xy)[0]

    # ---------------- terrain ----------------
    print("\n4) Terrain from Open-Meteo (90 m DEM) ...")
    points = list(zip(df["latitude"].round(5), df["longitude"].round(5)))
    cache, failed = fetch_terrain(points, session, SLOPE_OFFSET_M, batch_pts=args.batch_pts)
    feats = []
    for lat, lon in points:
        z5 = cache.get(cache_key(lat, lon, SLOPE_OFFSET_M))
        feats.append(terrain_features(z5, SLOPE_OFFSET_M) if z5 else {k: np.nan for k in FEATURES})
    df = pd.concat([df, pd.DataFrame(feats)], axis=1)
    before = len(df)
    df = df.dropna(subset=FEATURES).reset_index(drop=True)
    print(f"   terrain failures: {len(failed)} | rows dropped: {before - len(df)} | rows kept: {len(df)}")
    if df["label"].nunique() < 2 or df["label"].sum() < 10:
        print("ERROR: too few rows survived to continue. Read the failure messages above.")
        return 1

    elev_check = elevation_check(df)
    if elev_check:
        print(f"   elevation check vs inventory's 30 m DEM: median |diff| {elev_check['median_abs_diff_m']:.0f} m, "
              f"r={elev_check['pearson_r']:.3f} -> {elev_check['verdict']}")

    # ---------------- blocks + CV ----------------
    df["block_id"] = pd.qcut(df["along_km"], q=n_blocks, labels=False, duplicates="drop").astype(int)
    print(f"\n5) Spatial-block CV: {df['block_id'].nunique()} blocks along the road, "
          f"{args.buffer_km:.1f} km buffer between train and test")

    leak_ok, leak_details = leak_check(df, cols=("dist_ref_km",))
    ref_label = "distance to the real road (OSM)" if mode == "A" else "distance to your route polyline"
    print(f"   LEAK TEST on {ref_label}: rank AUC of distance alone must be within +-{LEAK_MAX_DEVIATION} of 0.5")
    for k, v in leak_details.items():
        print(f"      {k:16s} AUC={v['auc']:.3f}  95% CI [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]")
    print(f"   -> {'PASS' if leak_ok else 'WARN: distance still predicts the label; do not trust terrain results'}")
    widest = max((v["ci95"][1] - v["ci95"][0]) for v in leak_details.values())
    if widest > 0.15:
        print("   (note: confidence interval is wide - too few points for a reliable leak test; use the full run)")
    coarse_info = {}
    if mode == "A":
        a, lo, hi = univariate_auc_ci(df["dist_coarse_km"].abs().to_numpy(), df["label"].to_numpy())
        coarse_info = {"auc": a, "ci95": [lo, hi]}
        print(f"   (info only) distance to your straight-line polyline: AUC={a:.3f} [{lo:.3f}, {hi:.3f}] - "
              "can reflect real geography (where the true road bends), so it is not an acceptance test in Mode A")

    experiments = {
        "slope only (LR)": (["slope_deg"], make_lr),
        "elevation only (LR)": (["elevation_m"], make_lr),
        "terrain (LR)": (FEATURES, make_lr),
        "terrain (RF)": (FEATURES, lambda: make_rf(args.seed)),
    }
    cv = {}
    print(f"\n   {'experiment':22s} {'pooled AUC':>10s} {'block AUC mean+-sd':>20s} {'AP':>6s} {'top20% capture':>15s}")
    base_ap = float(df["label"].mean())
    for name, (cols, fn) in experiments.items():
        r = block_cv(df, cols, fn, args.buffer_km)
        cv[name] = r
        print(f"   {name:22s} {r['pooled_auc']:10.3f} {r['block_auc_mean']:>10.3f} +- {r['block_auc_std']:.3f} "
              f"{r['pooled_ap']:6.3f} {r['top20_capture'] * 100:14.0f}%")
    print(f"   (chance: AUC 0.5, AP {base_ap:.2f}, top-20% capture 20%)")

    best_name = max(["terrain (LR)", "terrain (RF)"], key=lambda k: np.nan_to_num(cv[k]["pooled_auc"], nan=0))
    best_auc = cv[best_name]["pooled_auc"]
    skill = "no demonstrated skill" if best_auc < 0.58 else ("weak" if best_auc < 0.70 else "moderate")
    print(f"\n   Best terrain model: {best_name}, pooled AUC {best_auc:.3f} -> {skill} (heuristic labels)")

    # ---------------- final model ----------------
    final = make_rf(args.seed) if "RF" in best_name else make_lr()
    final.fit(df[FEATURES].to_numpy(float), df["label"].to_numpy())
    if "RF" in best_name:
        imp = dict(zip(FEATURES, map(float, final.feature_importances_)))
    else:
        coefs = final.named_steps["logisticregression"].coef_[0]
        imp = dict(zip(FEATURES, map(float, coefs)))
    print("   feature importance / std. coefficients:", {k: round(v, 3) for k, v in imp.items()})
    joblib.dump({"model": final, "feature_columns": FEATURES, "strategy": "static",
                 "feature_config": {"terrain_source": "openmeteo", "slope_offset_m": SLOPE_OFFSET_M},
                 "model_kind": "RF" if "RF" in best_name else "LR", "feature_importance": imp,
                 "model_name": best_name, "created": datetime.now(timezone.utc).isoformat(),
                 "trained_on": "Mey et al. 2024 NH-7 inventory (309 slides)"},
                OUT_MODEL)

    # ---------------- outputs ----------------
    df.to_csv(OUT_DATA, index=False, encoding="utf-8")
    Path(OUT_CV).write_text(json.dumps({"leak_test": leak_details, "leak_pass": leak_ok, "cv": cv,
                                        "feature_importance": imp}, indent=2), encoding="utf-8")
    make_plots(df, cv, ref_tree, ways is not None and mode == "A", proj, mode)

    meta = {
        "strategy": "static", "mode": mode, "feature_columns": FEATURES, "label_column": "label",
        "group_column": "block_id", "spatial_axis_column": "along_km",
        "positives": int(df.label.sum()), "negatives": int((df.label == 0).sum()),
        "neg_ratio_requested": args.neg_ratio, "min_neg_sep_m": args.min_neg_sep_m,
        "n_blocks": int(df.block_id.nunique()), "buffer_km": args.buffer_km,
        "osm": osm_stats, "elevation_check": elev_check,
        "terrain_failures": len(failed), "leak_test_passed": bool(leak_ok),
        "leak_test": leak_details, "coarse_distance_info": coarse_info,
        "best_model": best_name, "best_pooled_auc": best_auc, "skill_heuristic": skill,
        "citation": CITATION,
        "limitations": [
            "Positives are road-blocking landslides, mostly from one rainfall episode (Sept-Oct 2022); "
            "points, not polygons.",
            "Negatives are background points, not confirmed stable ground.",
            "Terrain from a 90 m DEM with a 150 m finite-difference stencil: coarse for road-cut slopes.",
            "No lithology or road-widening feature, which Mey et al. identify as main controls.",
            "No rainfall feature: apply live rainfall at serving time as an explicit, explainable factor.",
        ],
    }
    Path(OUT_META).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_notes(meta, cv, args, len(failed), road_desc)

    print("\nSaved:", ", ".join([OUT_DATA, OUT_MODEL, OUT_CV, OUT_META, OUT_NOTES, OUT_PLOTS]))
    print("\nNEXT: read DATA_NOTES_static.md, look at diagnostic_plots_static.png, then wire "
          f"{OUT_MODEL} into the backend (static score x live rainfall factor).")
    return 0


def densify_polyline_ways(ways, proj, step_km):
    pts, tans = [], []
    for w in ways:
        xy = proj.xy([p[0] for p in w], [p[1] for p in w])
        p, t = densify_polyline(xy, step_km)
        if len(p):
            pts.append(p)
            tans.append(t)
    return np.vstack(pts), np.vstack(tans)


def make_plots(df, cv, ref_tree, have_osm, proj, mode):
    fig, ax = plt.subplots(2, 2, figsize=(13, 9))
    pos, neg = df[df.label == 1], df[df.label == 0]
    if ref_tree is not None:
        ref = ref_tree.data[::4]
        la, lo = proj.latlon(ref)
        ax[0, 0].scatter(lo, la, s=1, c="lightgrey", label="road reference" if have_osm else "route polyline")
    ax[0, 0].scatter(neg.longitude, neg.latitude, s=6, c="tab:blue", alpha=0.5, label="negatives")
    ax[0, 0].scatter(pos.longitude, pos.latitude, s=8, c="tab:red", alpha=0.8, label="landslides (Mey 2024)")
    ax[0, 0].set_title(f"Positives vs negatives (Mode {mode})")
    ax[0, 0].legend(markerscale=3, fontsize=8)
    bins = np.linspace(0, max(df.dist_coarse_km.max(), 0.1), 25)
    ax[0, 1].hist(neg.dist_coarse_km.abs(), bins=bins, alpha=0.5, label="negatives", density=True)
    ax[0, 1].hist(pos.dist_coarse_km.abs(), bins=bins, alpha=0.5, label="landslides", density=True)
    ax[0, 1].set_title("Distance to route polyline (must overlap)")
    ax[0, 1].set_xlabel("km")
    ax[0, 1].legend()
    sb = np.linspace(0, max(df.slope_deg.quantile(0.99), 1), 25)
    ax[1, 0].hist(neg.slope_deg, bins=sb, alpha=0.5, label="negatives", density=True)
    ax[1, 0].hist(pos.slope_deg, bins=sb, alpha=0.5, label="landslides", density=True)
    ax[1, 0].set_title("Slope (deg) by label")
    ax[1, 0].legend()
    names = list(cv.keys())
    vals = [cv[n]["pooled_auc"] for n in names]
    ax[1, 1].barh(names, vals, color="tab:green")
    ax[1, 1].axvline(0.5, color="k", ls="--", lw=1)
    ax[1, 1].set_xlim(0.3, 1.0)
    ax[1, 1].set_title("Spatial-block CV, pooled AUC (0.5 = chance)")
    plt.tight_layout()
    plt.savefig(OUT_PLOTS, dpi=140)
    plt.close(fig)


def write_notes(meta, cv, args, n_failed, road_desc):
    rows = "\n".join(
        f"| {k} | {v['pooled_auc']:.3f} | {v['block_auc_mean']:.3f} +- {v['block_auc_std']:.3f} | "
        f"{v['pooled_ap']:.3f} | {v['top20_capture'] * 100:.0f}% |" for k, v in cv.items())
    leak = "\n".join(f"- {k}: AUC {v['auc']:.3f} (95% CI {v['ci95'][0]:.3f}-{v['ci95'][1]:.3f})"
                     for k, v in meta["leak_test"].items())
    ec = meta["elevation_check"]
    elev_line = (f"median |diff| {ec['median_abs_diff_m']:.0f} m, r={ec['pearson_r']:.3f} ({ec['verdict']})"
                 if ec else "not available")
    mode_text = ("Negatives lie on the real road (OpenStreetMap geometry), with sideways offsets copied from "
                 "the positives' own distance distribution." if meta["mode"] == "A" else
                 "OpenStreetMap was unavailable or did not match, so negatives are offset-matched around the "
                 "straight-line route polyline. They match positives on distance-to-route but are NOT guaranteed "
                 "to lie on the actual road.")
    text = f"""# Dataset notes: NH-7 static susceptibility model

## Source and citation
Positives: {CITATION}
Check the supplement's license/terms before redistributing the data, and cite it in the pitch and the paper.

## What this dataset is
- {meta['positives']} positives (surveyed road-blocking landslides) and {meta['negatives']} negatives
  (ratio {meta['negatives'] / meta['positives']:.1f} : 1, at least {args.min_neg_sep_m:.0f} m from any positive).
- Mode {meta['mode']}: {mode_text}
- Road source: {road_desc}
- Features (terrain only): {', '.join(meta['feature_columns'])}. No rainfall: apply it at serving time.

## Checks run
Leak test (distance-to-route alone must predict nothing; pass if |AUC-0.5| <= {LEAK_MAX_DEVIATION}):
{leak}
Result: {'PASS' if meta['leak_test_passed'] else 'WARN - do not trust the terrain results until this passes'}
Terrain failures: {n_failed}. Elevation vs the inventory's own DEM: {elev_line}

## Spatial-block CV ({meta['n_blocks']} blocks along the road, {meta['buffer_km']} km buffer)
| experiment | pooled AUC | block AUC mean +- sd | AP | top-20% capture |
|---|---|---|---|---|
{rows}
How to read it: pooled AUC ranks points across the whole corridor; block AUC ranks points
within each stretch. Elevation can look strong per block but weak pooled because it rises
steadily towards Joshimath.
Chance: AUC 0.5, top-20% capture 20%. Best model: {meta['best_model']} -> {meta['skill_heuristic']}
(heuristic labels: <0.58 none, <0.70 weak, otherwise moderate).

## Limitations
""" + "\n".join(f"- {l}" for l in meta["limitations"]) + "\n"
    Path(OUT_NOTES).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
