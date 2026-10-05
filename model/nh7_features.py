"""
Shared feature code for the NH-7 demo model.
Used by add_features.py (training) and score_segments.py (scoring) so both compute
features the exact same way.

Feature groups
  openmeteo : elevation/slope/aspect/relief from the 90 m Open-Meteo API  (baseline, no extra installs)
  dem30     : Horn slope, aspect, curvature, relief, TPI from the 30 m Copernicus DEM (needs rasterio)
  streams   : distance to the nearest OSM river / stream                   (Overpass API)
  litho / faults / widened : optional layers taken from the Mey et al. supplement   (needs geopandas)
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

import build_static_dataset as B

DEM_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
DEM_CACHE_DIR = "dem_cache"
WATERWAYS_CACHE = "nh7_waterways_cache.json"

DEM_FEATURES = ["dem_elev_m", "dem_slope_deg", "dem_slope_max_210m", "dem_aspect_sin", "dem_aspect_cos",
                "dem_curvature", "dem_relief_300m", "dem_tpi_300m"]
NEIGHBOURHOOD_M = 210.0      # Mey et al. (2024) take the hillslope gradient within 210 m of the road
STREAM_FEATURES = ["dist_stream_km", "dist_river_km"]
MIN_LITHO_ROWS = 25          # lithology classes with fewer rows are merged into "other" (all zeros)
UTM44N = "EPSG:32644"        # corridor lies in UTM zone 44N (78-84 E)


# ----------------------------------------------------------------------
# 30 m DEM terrain (pure numpy core)
# ----------------------------------------------------------------------
class DemTerrain:
    """Terrain attributes from a north-up DEM array (row 0 = north). Pure numpy: easy to test."""

    NAN = {k: np.nan for k in DEM_FEATURES}

    def __init__(self, arr, west, north, res_x_deg, res_y_deg):
        self.arr = np.asarray(arr, dtype="float32")
        self.west, self.north, self.rx, self.ry = float(west), float(north), float(res_x_deg), float(res_y_deg)
        self.h, self.w = self.arr.shape

    def rowcol(self, lat, lon):
        return (int(math.floor((self.north - lat) / self.ry)),
                int(math.floor((lon - self.west) / self.rx)))

    def features(self, lat, lon, half=8):
        row, col = self.rowcol(lat, lon)
        r0, r1, c0, c1 = row - half, row + half + 1, col - half, col + half + 1
        if r0 < 0 or c0 < 0 or r1 > self.h or c1 > self.w:
            return dict(self.NAN)
        win = self.arr[r0:r1, c0:c1].astype(float)
        if not np.isfinite(win).all():
            return dict(self.NAN)
        dx = self.rx * 111320.0 * math.cos(math.radians(lat))   # metres per pixel, east-west
        dy = self.ry * 110574.0                                  # metres per pixel, north-south

        # Horn gradients for every interior cell of the window (shape 2*half-1 square, centred on the point)
        z = win
        gx = ((z[:-2, 2:] + 2 * z[1:-1, 2:] + z[2:, 2:]) - (z[:-2, :-2] + 2 * z[1:-1, :-2] + z[2:, :-2])) / (8 * dx)
        gy = ((z[:-2, :-2] + 2 * z[:-2, 1:-1] + z[:-2, 2:]) - (z[2:, :-2] + 2 * z[2:, 1:-1] + z[2:, 2:])) / (8 * dy)
        slope_grid = np.degrees(np.arctan(np.hypot(gx, gy)))
        k = half - 1
        yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
        inside = (xx * dx) ** 2 + (yy * dy) ** 2 <= NEIGHBOURHOOD_M ** 2
        slope_max = float(slope_grid[inside].max())

        c = half
        a, b, cc = win[c - 1, c - 1], win[c - 1, c], win[c - 1, c + 1]
        d, e, f = win[c, c - 1], win[c, c], win[c, c + 1]
        g, h, i = win[c + 1, c - 1], win[c + 1, c], win[c + 1, c + 1]
        dz_dx = gx[k, k]                                         # east gradient at the point
        dz_dy = gy[k, k]                                         # north gradient at the point (row 0 is north)
        grad = math.hypot(dz_dx, dz_dy)
        if grad == 0:
            a_sin = a_cos = 0.0
        else:
            bearing = math.atan2(-dz_dx, -dz_dy)    # compass bearing of the DOWNSLOPE direction
            a_sin, a_cos = math.sin(bearing), math.cos(bearing)
        near = win[c - 5:c + 6, c - 5:c + 6]                     # 11x11 pixels ~ 330 m
        return {
            "dem_elev_m": float(e),
            "dem_slope_deg": math.degrees(math.atan(grad)),
            "dem_slope_max_210m": slope_max,                     # steepest slope within 210 m
            "dem_aspect_sin": a_sin, "dem_aspect_cos": a_cos,
            "dem_curvature": (d + f - 2 * e) / dx ** 2 + (b + h - 2 * e) / dy ** 2,   # >0 = concave hollow
            "dem_relief_300m": float(near.max() - near.min()),
            "dem_tpi_300m": float(e - near.mean()),              # <0 = valley/hollow, >0 = ridge/spur
        }


def dem_tile_name(lat_floor: int, lon_floor: int) -> str:
    return f"Copernicus_DSM_COG_10_N{lat_floor:02d}_00_E{lon_floor:03d}_00_DEM"


def download_dem_tile(lat_floor, lon_floor, session, cache_dir=DEM_CACHE_DIR, min_bytes=100_000):
    name = dem_tile_name(lat_floor, lon_floor)
    url = f"{DEM_BASE}/{name}/{name}.tif"
    dest = Path(cache_dir) / f"{name}.tif"
    if dest.exists() and dest.stat().st_size > min_bytes:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading DEM tile {name} (one-time, tens of MB) ...")
    r = session.get(url, stream=True, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} for {url}")
    tmp = dest.with_suffix(".part")
    with open(tmp, "wb") as fh:
        for chunk in r.iter_content(chunk_size=1 << 20):
            fh.write(chunk)
    if tmp.stat().st_size <= min_bytes:
        raise RuntimeError(f"downloaded file for {name} is suspiciously small ({tmp.stat().st_size} bytes)")
    tmp.replace(dest)
    return dest


def load_dem_mosaic(bbox, session, cache_dir=DEM_CACHE_DIR):
    """
    bbox = (south, west, north, east). Downloads the 1-degree tiles that cover it, mosaics them
    (so points near a tile edge still get full neighbourhoods) and returns a DemTerrain.
    This is the only function that needs rasterio.
    """
    import rasterio
    from rasterio.merge import merge

    local_wgs84 = Path(cache_dir) / "dem_wgs84.tif"
    if local_wgs84.exists():
        with rasterio.open(local_wgs84) as ds:
            arr = ds.read(1)
            t = ds.transform
            return DemTerrain(arr, t.c, t.f, t.a, -t.e)

    s, w, n, e = bbox
    tiles = [download_dem_tile(la, lo, session, cache_dir)
             for la in range(int(math.floor(s)), int(math.floor(n)) + 1)
             for lo in range(int(math.floor(w)), int(math.floor(e)) + 1)]
    datasets = [rasterio.open(p) for p in tiles]
    try:
        mosaic, transform = merge(datasets, bounds=(w, s, e, n))
    finally:
        for ds in datasets:
            ds.close()
    return DemTerrain(mosaic[0], transform.c, transform.f, transform.a, -transform.e)


# ----------------------------------------------------------------------
# Rivers and streams (OpenStreetMap via Overpass)
# ----------------------------------------------------------------------
def fetch_waterways(bbox, session):
    """Returns a list of (kind, [(lat, lon), ...]) with kind in {'river', 'stream'}; cached on disk."""
    cache = Path(WATERWAYS_CACHE)
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("ways"):
                return [(k, [tuple(p) for p in pts]) for k, pts in data["ways"]]
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] cannot read {WATERWAYS_CACHE}: {e}")
    s, w, n, e = bbox
    q = ('[out:json][timeout:180];\n'
         f'way["waterway"~"^(river|stream)$"]({s:.4f},{w:.4f},{n:.4f},{e:.4f});\nout geom;')
    last = "no response"
    for url in B.OVERPASS_URLS:
        try:
            print(f"  Querying Overpass for rivers/streams: {url}")
            r = session.post(url, data={"data": q}, timeout=240)
            if r.status_code != 200:
                last = f"HTTP {r.status_code}: {r.text[:120]!r}"
                print(f"  [Overpass fail] {last}")
                continue
            ways = []
            for el in r.json().get("elements", []):
                geom = el.get("geometry") or []
                kind = (el.get("tags") or {}).get("waterway", "stream")
                if el.get("type") == "way" and len(geom) >= 2:
                    ways.append((kind, [(g["lat"], g["lon"]) for g in geom]))
            if not ways:
                last = "0 waterways returned"
                continue
            cache.write_text(json.dumps({"bbox": bbox, "fetched": datetime.now(timezone.utc).isoformat(),
                                         "ways": ways}), encoding="utf-8")
            print(f"  {len(ways)} waterways")
            return ways
        except Exception as e2:  # noqa: BLE001
            last = f"{type(e2).__name__}: {e2}"
            print(f"  [Overpass exception] {url}: {last}")
    raise RuntimeError(f"waterways unavailable ({last})")


class WaterwayDistance:
    def __init__(self, ways, proj):
        self.proj = proj
        pts_all, pts_river = [], []
        for kind, pts in ways:
            xy = proj.xy([p[0] for p in pts], [p[1] for p in pts])
            dense, _ = B.densify_polyline(xy, 0.05)
            if len(dense):
                pts_all.append(dense)
                if kind == "river":
                    pts_river.append(dense)
        self.tree_all = cKDTree(np.vstack(pts_all))
        self.tree_river = cKDTree(np.vstack(pts_river)) if pts_river else self.tree_all

    def frame(self, lat, lon):
        xy = self.proj.xy(lat, lon)
        return pd.DataFrame({"dist_stream_km": self.tree_all.query(xy)[0],
                             "dist_river_km": self.tree_river.query(xy)[0]})


# ----------------------------------------------------------------------
# Optional layers from the Mey et al. supplement (geopandas, lazy import)
# ----------------------------------------------------------------------
def _safe(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", str(name)).strip("_").lower()[:40]


def _union(gs):
    return gs.union_all() if hasattr(gs, "union_all") else gs.unary_union


def inspect_layer(path):
    """Print what is inside a vector file so you can choose --litho-field etc."""
    import geopandas as gpd
    g = gpd.read_file(path)
    print(f"\n{path}: {len(g)} features | geometry {sorted(set(g.geometry.geom_type))} | CRS {g.crs}")
    print("columns:", [c for c in g.columns if c != "geometry"])
    print(g.drop(columns="geometry").head(5).to_string())


def layer_features(df, cfg):
    """cfg may contain litho {path, field, levels}, faults {path}, widened {path, query}. Returns new columns."""
    import geopandas as gpd

    out = pd.DataFrame(index=df.index)
    pts = gpd.GeoDataFrame(df[["latitude", "longitude"]].copy(), crs="EPSG:4326",
                           geometry=gpd.points_from_xy(df["longitude"], df["latitude"]))
    pts_utm = pts.to_crs(UTM44N)

    if cfg.get("litho"):
        lc = cfg["litho"]
        polys = gpd.read_file(lc["path"]).to_crs("EPSG:4326")
        joined = gpd.sjoin(pts, polys[[lc["field"], "geometry"]], how="left", predicate="within")
        joined = joined[~joined.index.duplicated(keep="first")].reindex(df.index)
        codes = joined[lc["field"]].astype(object).where(joined[lc["field"]].notna(), "unknown").astype(str)
        if not lc.get("levels"):
            counts = codes.value_counts()
            lc["levels"] = [k for k, v in counts.items() if v >= MIN_LITHO_ROWS and k != "unknown"]
        for lv in lc["levels"]:
            out[f"litho_{_safe(lv)}"] = (codes == lv).astype(int)
        out.attrs["litho_unmatched_share"] = float((codes == "unknown").mean())

    if cfg.get("faults"):
        lines = gpd.read_file(cfg["faults"]["path"]).to_crs(UTM44N)
        out["dist_fault_km"] = pts_utm.distance(_union(lines.geometry)) / 1000.0

    if cfg.get("widened"):
        wc = cfg["widened"]
        feats = gpd.read_file(wc["path"])
        if wc.get("query"):
            feats = feats.query(wc["query"])
        feats = feats.to_crs(UTM44N)
        out["near_widened_100m"] = (pts_utm.distance(_union(feats.geometry)) <= 100).astype(int)
    return out


# ----------------------------------------------------------------------
# One engine for training AND scoring
# ----------------------------------------------------------------------
def feature_columns(cfg):
    cols = list(DEM_FEATURES) if cfg.get("terrain_source") == "dem30" else list(B.FEATURES)
    if cfg.get("streams"):
        cols += STREAM_FEATURES
    if cfg.get("litho"):
        cols += [f"litho_{_safe(lv)}" for lv in cfg["litho"].get("levels", [])]
    if cfg.get("faults"):
        cols += ["dist_fault_km"]
    if cfg.get("widened"):
        cols += ["near_widened_100m"]
    return cols


class FeatureEngine:
    def __init__(self, cfg, session, bbox, proj=None):
        self.cfg, self.session, self.bbox = cfg, session, bbox
        self.proj = proj or B.Proj((bbox[0] + bbox[2]) / 2)
        self._dem = None
        self._water = None

    def dem(self):
        if self._dem is None:
            self._dem = load_dem_mosaic(self.bbox, self.session)
        return self._dem

    def water(self):
        if self._water is None:
            self._water = WaterwayDistance(fetch_waterways(self.bbox, self.session), self.proj)
        return self._water

    def frame(self, df):
        """Feature frame aligned with df.index. Rows that cannot be computed contain NaN."""
        lat, lon = df["latitude"].to_numpy(float), df["longitude"].to_numpy(float)
        parts = []
        if self.cfg.get("terrain_source") == "dem30":
            dem = self.dem()
            parts.append(pd.DataFrame([dem.features(a, b) for a, b in zip(lat, lon)], index=df.index)[DEM_FEATURES])
        else:
            h = self.cfg.get("slope_offset_m", B.SLOPE_OFFSET_M)
            points = list(zip(np.round(lat, 5), np.round(lon, 5)))
            cache, _ = B.fetch_terrain(points, self.session, h)
            rows = []
            for p in points:
                z5 = cache.get(B.cache_key(p[0], p[1], h))
                rows.append(B.terrain_features(z5, h) if z5 else {k: np.nan for k in B.FEATURES})
            parts.append(pd.DataFrame(rows, index=df.index)[B.FEATURES])
        if self.cfg.get("streams"):
            wf = self.water().frame(lat, lon)
            wf.index = df.index
            parts.append(wf)
        if any(self.cfg.get(k) for k in ("litho", "faults", "widened")):
            parts.append(layer_features(df, self.cfg))
        out = pd.concat(parts, axis=1)
        return out.reindex(columns=feature_columns(self.cfg))
