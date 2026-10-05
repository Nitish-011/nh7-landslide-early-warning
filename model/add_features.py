#!/usr/bin/env python3
"""
add_features.py - STEP 2: better terrain + extra layers, honest comparison, v2 model
=====================================================================================
Run after build_static_dataset.py (needs nh7_static_training_data.csv).

  python add_features.py --check-dem            # 1-minute smoke test: downloads one DEM tile, prints elevations
  python add_features.py                        # 30 m DEM terrain + rivers/streams
  python add_features.py --inspect FILE ...     # show columns of the Mey supplement layers (shp/gpkg/geojson)
  python add_features.py --litho LITHO.shp --litho-field NAME \
                         --faults FAULTS.shp --widened WIDEN.shp --widened-query "widened == 1"

It compares feature sets with the same spatial-block CV as step 1:
  A  Open-Meteo 90 m terrain (baseline)      B  Copernicus 30 m terrain
  C  B + distance to rivers/streams          D  C + Mey layers (only if you pass them)
and keeps the SIMPLEST set that beats the previous one by more than 0.01 pooled AUC.

Needs: pip install rasterio      (and geopandas only if you use --litho/--faults/--widened)
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests

import build_static_dataset as B
import nh7_features as F

IN_CSV = "nh7_static_training_data.csv"
OUT_CSV = "nh7_static_training_data_v2.csv"
OUT_MODEL = "nh7_static_model_v2.joblib"
OUT_META = "pipeline_meta_static_v2.json"
OUT_CV = "cv_report_static_v2.json"
OUT_NOTES = "DATA_NOTES_static_v2.md"
MIN_GAIN = 0.01
CORRIDOR_BBOX = (30.00, 78.20, 30.62, 79.60)     # south, west, north, east
SMOKE_POINTS = {"Rishikesh": ((30.0869, 78.2676), (300, 500)), "Joshimath": ((30.5564, 79.5663), (1700, 2100))}


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=IN_CSV)
    ap.add_argument("--check-dem", action="store_true")
    ap.add_argument("--inspect", nargs="+", metavar="FILE")
    ap.add_argument("--no-streams", action="store_true")
    ap.add_argument("--litho", help="lithology polygons from the Mey supplement")
    ap.add_argument("--litho-field", help="column in --litho holding the lithology name/code")
    ap.add_argument("--faults", help="fault lines")
    ap.add_argument("--widened", help="road sections that were widened (lines or polygons)")
    ap.add_argument("--widened-query", help='pandas query that selects widened rows, e.g. "widened == 1"')
    ap.add_argument("--buffer-km", type=float, default=2.0)
    ap.add_argument("--seed", type=int, default=42)
    return ap.parse_args(argv)


def check_dem(session):
    print("DEM smoke test ...")
    try:
        dem = F.load_dem_mosaic(CORRIDOR_BBOX, session)
    except ImportError:
        print("ERROR: rasterio is not installed. Run:  pip install rasterio")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"ERROR while loading the DEM: {type(e).__name__}: {e}")
        return 1
    ok = True
    for name, ((lat, lon), (lo, hi)) in SMOKE_POINTS.items():
        f = dem.features(lat, lon)
        z = f["dem_elev_m"]
        good = lo <= z <= hi
        ok &= good
        print(f"  {name:10s} elevation {z:7.1f} m (expected {lo}-{hi})  slope {f['dem_slope_deg']:.1f} deg  "
              f"-> {'OK' if good else 'UNEXPECTED'}")
    print("DEM looks right." if ok else "DEM values look wrong: check the tile download and the lat/lon order.")
    return 0 if ok else 1


def main(argv=None):
    args = parse_args(argv)
    session = requests.Session()
    session.headers.update({"User-Agent": "nh7-landslide-hackathon/1.0"})

    if args.inspect:
        for p in args.inspect:
            F.inspect_layer(p)
        return 0
    if args.check_dem:
        return check_dem(session)

    print("1) Loading step-1 dataset ...")
    df = pd.read_csv(args.input)
    need = {"latitude", "longitude", "label", "along_km", "block_id"} | set(B.FEATURES)
    if not need <= set(df.columns):
        print(f"ERROR: {args.input} is missing columns {sorted(need - set(df.columns))}. Run build_static_dataset.py first.")
        return 1
    print(f"   {len(df)} rows ({int(df.label.sum())} positives)")

    cfg_full = {"terrain_source": "dem30", "streams": not args.no_streams}
    if args.litho:
        if not args.litho_field:
            print("ERROR: --litho needs --litho-field (run --inspect on the file to see its columns)")
            return 1
        cfg_full["litho"] = {"path": args.litho, "field": args.litho_field}
    if args.faults:
        cfg_full["faults"] = {"path": args.faults}
    if args.widened:
        cfg_full["widened"] = {"path": args.widened, "query": args.widened_query}

    bbox = (df.latitude.min() - 0.03, df.longitude.min() - 0.03, df.latitude.max() + 0.03, df.longitude.max() + 0.03)

    print("\n2) Computing 30 m terrain (Copernicus DEM) ...")
    engine = F.FeatureEngine({"terrain_source": "dem30"}, session, bbox)
    try:
        dem_frame = engine.frame(df)
    except ImportError:
        print("ERROR: rasterio is not installed. Run:  pip install rasterio   (then try  --check-dem)")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"ERROR loading the DEM: {type(e).__name__}: {e}\n   Try:  python add_features.py --check-dem")
        return 1
    print(f"   rows with full 30 m neighbourhood: {int(dem_frame.notna().all(axis=1).sum())}/{len(df)}")

    inv = df[df.label == 1]
    if "elevation_m_inventory" in df and inv["elevation_m_inventory"].notna().sum() >= 5:
        m_om = (inv["elevation_m"] - inv["elevation_m_inventory"]).abs().median()
        m_dem = (dem_frame.loc[inv.index, "dem_elev_m"] - inv["elevation_m_inventory"]).abs().median()
        print(f"   median |elevation - inventory elevation| at the slides: Open-Meteo 90 m {m_om:.0f} m | "
              f"Copernicus 30 m {m_dem:.0f} m")
        if m_dem > 100:
            print("   [WARN] 30 m DEM disagrees with the inventory by >100 m: check --check-dem before trusting it.")

    parts = [dem_frame]
    streams_ok = False
    if cfg_full["streams"]:
        print("\n3) Distance to rivers/streams (OpenStreetMap) ...")
        try:
            parts.append(F.FeatureEngine({"terrain_source": "none", "streams": True}, session, bbox)
                         .water().frame(df["latitude"].to_numpy(), df["longitude"].to_numpy()).set_index(df.index))
            streams_ok = True
        except Exception as e:  # noqa: BLE001
            print(f"   [WARN] streams skipped: {type(e).__name__}: {e}")
    cfg_full["streams"] = streams_ok

    layers_ok = False
    if any(k in cfg_full for k in ("litho", "faults", "widened")):
        print("\n4) Mey supplement layers ...")
        try:
            lf = F.layer_features(df, cfg_full)
            parts.append(lf)
            layers_ok = True
            if "litho_unmatched_share" in lf.attrs:
                print(f"   lithology: {len(cfg_full['litho']['levels'])} classes kept, "
                      f"{lf.attrs['litho_unmatched_share'] * 100:.0f}% of points outside the polygons")
        except Exception as e:  # noqa: BLE001
            print(f"   [WARN] layers skipped: {type(e).__name__}: {e}")
            for k in ("litho", "faults", "widened"):
                cfg_full.pop(k, None)

    fr = pd.concat(parts, axis=1)
    keep = fr.notna().all(axis=1)
    if (~keep).any():
        print(f"\n   dropping {int((~keep).sum())} rows with missing features")
    data = pd.concat([df, fr], axis=1)[keep].reset_index(drop=True)

    # ---- feature sets ----
    cfg_A = {"terrain_source": "openmeteo", "slope_offset_m": B.SLOPE_OFFSET_M}
    cfg_B = {"terrain_source": "dem30"}
    sets = {"A  Open-Meteo 90 m terrain": cfg_A, "B  Copernicus 30 m terrain": cfg_B}
    if streams_ok:
        sets["C  B + rivers/streams"] = {**cfg_B, "streams": True}
    if layers_ok:
        sets["D  C + Mey layers"] = copy.deepcopy({k: v for k, v in cfg_full.items() if k != "terrain_source"} | cfg_B)

    print(f"\n5) Spatial-block CV, {data.block_id.nunique()} blocks, {args.buffer_km} km buffer")
    results, report = [], {}
    print(f"   {'feature set':30s} {'model':4s} {'pooled AUC':>10s} {'block mean+-sd':>16s} {'AP':>6s} {'top20%':>7s}")
    for name, cfg in sets.items():
        cols = F.feature_columns(cfg)
        best = None
        for mname, fn in (("LR", B.make_lr), ("RF", lambda: B.make_rf(args.seed))):
            r = B.block_cv(data, cols, fn, args.buffer_km)
            report[f"{name} | {mname}"] = r
            print(f"   {name:30s} {mname:4s} {r['pooled_auc']:10.3f} {r['block_auc_mean']:9.3f}+-{r['block_auc_std']:.3f} "
                  f"{r['pooled_ap']:6.3f} {r['top20_capture'] * 100:6.0f}%")
            if best is None or np.nan_to_num(r["pooled_auc"]) > np.nan_to_num(best[1]):
                best = (mname, r["pooled_auc"])
        results.append((name, cfg, cols, best[0], best[1]))

    chosen = results[0]
    for cand in results[1:]:
        if cand[4] > chosen[4] + MIN_GAIN:
            chosen = cand
    name, cfg, cols, mname, auc = chosen
    skill = "no demonstrated skill" if auc < 0.58 else ("weak" if auc < 0.70 else "moderate")
    print(f"\n   Chosen (simplest set within {MIN_GAIN} AUC of the best): {name} with {mname}, "
          f"pooled AUC {auc:.3f} -> {skill}")

    model = B.make_rf(args.seed) if mname == "RF" else B.make_lr()
    model.fit(data[cols].to_numpy(float), data["label"].to_numpy())
    if mname == "RF":
        imp = dict(zip(cols, map(float, model.feature_importances_)))
    else:
        imp = dict(zip(cols, map(float, model.named_steps["logisticregression"].coef_[0])))
    top = sorted(imp.items(), key=lambda kv: -abs(kv[1]))[:5]
    print("   strongest features:", ", ".join(f"{k} ({v:+.2f})" for k, v in top))

    joblib.dump({"model": model, "feature_columns": cols, "feature_config": cfg, "strategy": "static",
                 "model_name": f"{name.strip()} / {mname}", "created": datetime.now(timezone.utc).isoformat(),
                 "trained_on": "Mey et al. 2024 NH-7 inventory (309 slides)",
                 "model_kind": mname, "feature_importance": imp}, OUT_MODEL)
    data.to_csv(OUT_CSV, index=False, encoding="utf-8")
    Path(OUT_CV).write_text(json.dumps(report, indent=2), encoding="utf-8")
    meta = {"strategy": "static", "version": 2, "chosen_feature_set": name.strip(), "model": mname,
            "feature_columns": cols, "feature_config": cfg, "pooled_auc": auc, "skill_heuristic": skill,
            "group_column": "block_id", "rows": len(data), "positives": int(data.label.sum()),
            "feature_importance": imp, "citation": B.CITATION}
    Path(OUT_META).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    Path(OUT_NOTES).write_text(
        "# Dataset notes v2\n\n"
        f"Positives: {B.CITATION}\n\n"
        f"Chosen feature set: **{name.strip()}** ({len(cols)} features) with {mname}; pooled spatial-block AUC "
        f"{auc:.3f} ({skill}; heuristic labels).\n\n"
        "Feature sets compared (pooled AUC, best model per set):\n"
        + "\n".join(f"- {r[0].strip()}: {r[4]:.3f} ({r[3]})" for r in results)
        + "\n\nCaveats: Copernicus DEM is a surface model (trees/buildings included). Streams come from OpenStreetMap "
          "and may be incomplete. Lithology/faults/widening only enter if you supplied the Mey layers.\n",
        encoding="utf-8")
    print(f"\nSaved: {OUT_CSV}, {OUT_MODEL}, {OUT_META}, {OUT_CV}, {OUT_NOTES}")
    print("NEXT: python score_segments.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
