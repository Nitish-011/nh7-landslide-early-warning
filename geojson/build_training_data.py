"""
NH-7 Landslide Risk Model — Training Data Builder (final)

Strategy: use real-dated NASA GLC events for a rainfall-reactive dynamic
model if there are enough of them (>=10); otherwise fall back honestly to
a terrain-only static susceptibility model using NGDR points. Writes:
  - nh7_master_training_data_v2.csv   (the training table)
  - diagnostic_plots.png              (branch-appropriate sanity plots)
  - DATA_NOTES.md                     (what's real, what's constructed, and why)
  - pipeline_meta.json                (strategy + feature list, for the training script)
"""

import json
import math
import random
import time
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import seaborn as sns
from scipy.spatial import cKDTree

print("Step 1: Fetching Dynamic Landslide Events...")

NEG_COUNT = 150
SLOPE_OFFSET_M = 150.0
MIN_DYNAMIC_EVENTS = 10  # below this, fall back to a static model


def get_random_date(monsoon=False):
    year = random.choice([2021, 2022, 2023])
    if monsoon:
        month = random.choice([7, 8])
        day = random.randint(1, 31)
    else:
        month = random.choice([1, 2, 3, 4, 5, 6, 9, 10, 11, 12])
        day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


# ----------------------------------------------------------------------
# 1. Fetch NASA GLC (the only source with real event dates)
# ----------------------------------------------------------------------
nasa_positives = pd.DataFrame()
nasa_raw_yield = 0
print("\nDownloading NASA Landslide Catalog...")
try:
    url = "https://data.nasa.gov/api/views/dd9e-wu2v/rows.csv?accessType=DOWNLOAD"
    nasa_df = pd.read_csv(url)
    print(f"NASA GLC columns available: {nasa_df.columns.tolist()}")

    nasa_filtered = nasa_df[
        (nasa_df["longitude"] >= 78.0) & (nasa_df["longitude"] <= 80.0) &
        (nasa_df["latitude"] >= 29.5) & (nasa_df["latitude"] <= 31.5)
    ].copy()
    nasa_raw_yield = len(nasa_filtered)
    print(f"--> RAW YIELD: {nasa_raw_yield} NASA points inside the bounding box.")

    date_col = "event_date" if "event_date" in nasa_filtered.columns else (
        "date" if "date" in nasa_filtered.columns else None
    )

    if date_col and nasa_raw_yield > 0:
        nasa_filtered = nasa_filtered.dropna(subset=[date_col])
        nasa_filtered["date"] = pd.to_datetime(
            nasa_filtered[date_col], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        nasa_filtered.dropna(subset=["date"], inplace=True)
        nasa_filtered["label"] = 1
        nasa_filtered["source"] = "nasa_glc"
        nasa_positives = nasa_filtered[["longitude", "latitude", "label", "date", "source"]]
        print(f"--> USABLE NASA YIELD: {len(nasa_positives)} points with valid timestamps.")
    else:
        print("--> No valid date column found, or 0 points in bounding box.")
except Exception as e:
    print(f"NASA download failed: {e}")

# ----------------------------------------------------------------------
# 2. Decide strategy: dynamic (rainfall-reactive) vs static (terrain-only)
# ----------------------------------------------------------------------
building_dynamic_model = len(nasa_positives) >= MIN_DYNAMIC_EVENTS
all_positives = pd.DataFrame()
ngdr_point_count = 0

if building_dynamic_model:
    print(f"\n[STRATEGY]: {len(nasa_positives)} dated NASA events found (>= {MIN_DYNAMIC_EVENTS}). "
          f"Building DYNAMIC rainfall-triggered model.")
    all_positives = nasa_positives.copy()
else:
    print(f"\n[STRATEGY]: Only {len(nasa_positives)} dated NASA events (< {MIN_DYNAMIC_EVENTS}). "
          f"Falling back to STATIC terrain-only susceptibility model using NGDR points.")
    ngdr_positives = pd.read_csv("nh7_positive_landslides.csv")
    ngdr_point_count = len(ngdr_positives)
    ngdr_positives["label"] = 1
    ngdr_positives["source"] = "ngdr_static"
    ngdr_positives["date"] = np.nan  # static points carry no date
    all_positives = ngdr_positives[["longitude", "latitude", "label", "date", "source"]]

# ----------------------------------------------------------------------
# 3. Generate continuous negative points along the NH-7 segments
# ----------------------------------------------------------------------
print("\nGenerating continuous negative points...")
segments = pd.read_csv("nh7_segments.csv")
lons, lats = segments["longitude"].values, segments["latitude"].values

neg_lons, neg_lats = [], []
for _ in range(NEG_COUNT):
    idx = random.randint(0, len(lons) - 2)
    frac = random.uniform(0, 1)
    neg_lons.append(lons[idx] + frac * (lons[idx + 1] - lons[idx]))
    neg_lats.append(lats[idx] + frac * (lats[idx + 1] - lats[idx]))

negatives = pd.DataFrame({"longitude": neg_lons, "latitude": neg_lats})
negatives["label"] = 0
negatives["source"] = "interpolated_negative"

if building_dynamic_model:
    # 80% monsoon dates so negatives overlap the real NASA events' rainfall range
    negatives["date"] = [
        get_random_date(monsoon=True) if random.random() < 0.80 else get_random_date(monsoon=False)
        for _ in range(NEG_COUNT)
    ]
else:
    negatives["date"] = np.nan

negatives = negatives[["longitude", "latitude", "label", "date", "source"]]
master_df = pd.concat([all_positives, negatives], ignore_index=True)

# ----------------------------------------------------------------------
# 4. Assign nearest_segment_id for a later spatial train/test split
# ----------------------------------------------------------------------
tree = cKDTree(segments[["longitude", "latitude"]].values)
_, indices = tree.query(master_df[["longitude", "latitude"]].values)
master_df["nearest_segment_id"] = segments["segment_id"].iloc[indices].values

# ----------------------------------------------------------------------
# 5. Fetch rainfall (dynamic only) + terrain (always) for every point
# ----------------------------------------------------------------------
print(f"\nFetching APIs for {len(master_df)} points...")
elevations, slopes, aspects, rain_7d, rain_max_1d = [], [], [], [], []

for idx, row in master_df.iterrows():
    lat, lon = row["latitude"], row["longitude"]

    if building_dynamic_model and pd.notna(row["date"]):
        date_str = row["date"]
        end_date = datetime.strptime(date_str, "%Y-%m-%d")
        start_date = end_date - timedelta(days=7)
        weather_url = (
            f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
            f"&start_date={start_date.strftime('%Y-%m-%d')}&end_date={date_str}"
            f"&daily=precipitation_sum&timezone=Asia%2FKolkata"
        )
        try:
            res = requests.get(weather_url, timeout=10).json()
            if "daily" in res and "precipitation_sum" in res["daily"]:
                rain_arr = [r for r in res["daily"]["precipitation_sum"] if r is not None]
                if rain_arr:
                    rain_7d.append(sum(rain_arr))
                    rain_max_1d.append(max(rain_arr))
                else:
                    rain_7d.append(np.nan)
                    rain_max_1d.append(np.nan)
            else:
                rain_7d.append(np.nan)
                rain_max_1d.append(np.nan)
        except Exception:
            rain_7d.append(np.nan)
            rain_max_1d.append(np.nan)
    else:
        rain_7d.append(np.nan)
        rain_max_1d.append(np.nan)

    d_lat = SLOPE_OFFSET_M / 111000.0
    d_lon = SLOPE_OFFSET_M / (111000.0 * math.cos(math.radians(lat)))
    lats_str = f"{lat},{lat + d_lat},{lat - d_lat},{lat},{lat}"
    lons_str = f"{lon},{lon},{lon},{lon + d_lon},{lon - d_lon}"
    terrain_url = f"https://api.open-meteo.com/v1/elevation?latitude={lats_str}&longitude={lons_str}"

    try:
        res = requests.get(terrain_url, timeout=10).json()
        if "elevation" in res and len(res["elevation"]) == 5 and None not in res["elevation"]:
            zc, zn, zs, ze, zw = res["elevation"]
            dz_dx = (ze - zw) / (2 * SLOPE_OFFSET_M)
            dz_dy = (zn - zs) / (2 * SLOPE_OFFSET_M)
            elevations.append(zc)
            slopes.append(math.degrees(math.atan(math.sqrt(dz_dx ** 2 + dz_dy ** 2))))
            aspects.append((math.degrees(math.atan2(-dz_dx, dz_dy)) + 360) % 360)
        else:
            elevations.append(np.nan)
            slopes.append(np.nan)
            aspects.append(np.nan)
    except Exception:
        elevations.append(np.nan)
        slopes.append(np.nan)
        aspects.append(np.nan)

    time.sleep(0.1)
    if (idx + 1) % 25 == 0:
        print(f"  Processed {idx + 1}/{len(master_df)} points...")

master_df["elevation_m"] = elevations
master_df["slope_deg"] = slopes
master_df["aspect_deg"] = aspects

if building_dynamic_model:
    master_df["rainfall_7d_mm"] = rain_7d
    master_df["rainfall_max_1d_mm"] = rain_max_1d
    feature_columns = ["elevation_m", "slope_deg", "aspect_deg", "rainfall_7d_mm", "rainfall_max_1d_mm"]
    clean_df = master_df.dropna(subset=feature_columns).copy()
else:
    master_df.drop(columns=["date", "rainfall_7d_mm", "rainfall_max_1d_mm"], inplace=True, errors="ignore")
    feature_columns = ["elevation_m", "slope_deg", "aspect_deg"]
    clean_df = master_df.dropna(subset=feature_columns).copy()

dropped_count = len(master_df) - len(clean_df)
print(f"\nRows dropped due to missing/failed terrain or rainfall data: {dropped_count}")
print(f"Final Class Balance:\n{clean_df['label'].value_counts()}")

clean_df.to_csv("nh7_master_training_data_v2.csv", index=False)
print("Saved final training dataset to 'nh7_master_training_data_v2.csv'")

# ----------------------------------------------------------------------
# 6. Diagnostic plots — branch-appropriate
# ----------------------------------------------------------------------
plt.figure(figsize=(12, 5))
if building_dynamic_model:
    plt.subplot(1, 2, 1)
    sns.histplot(data=clean_df, x="rainfall_7d_mm", hue="label", bins=20, alpha=0.5, element="step")
    plt.title("7-Day Rainfall Distribution by Label")
    plt.xlabel("7-Day Rainfall (mm)")

    plt.subplot(1, 2, 2)
    sns.scatterplot(data=clean_df, x="rainfall_7d_mm", y="slope_deg", hue="label", style="label", alpha=0.7)
    plt.title("Slope vs Rainfall (Label Overlap Check)")
    plt.xlabel("7-Day Rainfall (mm)")
    plt.ylabel("Slope (degrees)")
else:
    plt.subplot(1, 2, 1)
    sns.histplot(data=clean_df, x="slope_deg", hue="label", bins=20, alpha=0.5, element="step")
    plt.title("Slope Distribution by Label")
    plt.xlabel("Slope (degrees)")

    plt.subplot(1, 2, 2)
    sns.scatterplot(data=clean_df, x="elevation_m", y="slope_deg", hue="label", style="label", alpha=0.7)
    plt.title("Slope vs Elevation (Label Separation Check)")
    plt.xlabel("Elevation (m)")
    plt.ylabel("Slope (degrees)")

plt.tight_layout()
plt.savefig("diagnostic_plots.png", dpi=150)
print("Saved diagnostic plots to 'diagnostic_plots.png'")

# ----------------------------------------------------------------------
# 7. pipeline_meta.json — lets the training script auto-detect the branch
#    instead of assuming which feature columns exist.
# ----------------------------------------------------------------------
meta = {
    "strategy": "dynamic" if building_dynamic_model else "static",
    "feature_columns": feature_columns,
    "label_column": "label",
    "spatial_split_column": "nearest_segment_id",
    "nasa_raw_yield_in_bbox": nasa_raw_yield,
    "nasa_usable_dated_events": len(nasa_positives),
    "ngdr_point_count": ngdr_point_count,
    "negative_count": NEG_COUNT,
    "final_row_count": len(clean_df),
    "rows_dropped_missing_data": dropped_count,
    "class_balance": clean_df["label"].value_counts().to_dict(),
}
with open("pipeline_meta.json", "w") as f:
    json.dump(meta, f, indent=2)
print("Saved 'pipeline_meta.json' for the training script to read.")

# ----------------------------------------------------------------------
# 8. DATA_NOTES.md — records which branch actually ran and why
# ----------------------------------------------------------------------
if building_dynamic_model:
    strategy_note = (
        f"**DYNAMIC (rainfall-reactive) model.** {len(nasa_positives)} NASA GLC points "
        f"(of {nasa_raw_yield} raw points found in the bounding box) had usable real event "
        f"dates, clearing the {MIN_DYNAMIC_EVENTS}-event threshold. Positives are NASA GLC "
        f"events only; NGDR points were not used in this run."
    )
    limitations_note = (
        "- Rainfall and slope are both real, fetched for each point's actual (or assigned, "
        "for negatives) date.\n"
        "- 80% of negative points were assigned monsoon-season dates specifically to prevent "
        "the model from learning \"month\" as a shortcut for the label — see the rainfall "
        "overlap plot to confirm this worked before trusting the trained model.\n"
        "- The NASA Global Landslide Catalog export used here is a frozen snapshot "
        "(current as of March 2016) built from media reports, not a live or systematic survey."
    )
else:
    strategy_note = (
        f"**STATIC (terrain-only) model.** Only {len(nasa_positives)} NASA GLC points had "
        f"usable dates (below the {MIN_DYNAMIC_EVENTS}-event threshold), so this run falls "
        f"back to {ngdr_point_count} NGDR points as positives, with no rainfall features at all."
    )
    limitations_note = (
        "- This model does NOT react to live rainfall — it scores terrain susceptibility only.\n"
        "- If the hackathon demo needs to show risk responding to live weather, don't fake this "
        "in the model: apply a simple, explainable rainfall multiplier on top of this static "
        "score in the backend at serving time instead, and say so plainly if asked.\n"
        "- Confirm separately whether the NGDR source used here is a true dated-event "
        "inventory or a geomorphology/terrain-classification layer — that distinction isn't "
        "resolved by this script and affects how the `ngdr_static` points should be described."
    )

notes = f"""# Dataset Notes: NH-7 Landslide Risk Classifier

## Strategy used in this run
{strategy_note}

## Source tracking
Every row has a `source` column: `nasa_glc`, `ngdr_static`, or `interpolated_negative`.

## Limitations
{limitations_note}

## Features
- `elevation_m`, `slope_deg`, `aspect_deg`: computed via finite differences using 4 points
  offset {SLOPE_OFFSET_M:.0f}m from center (Open-Meteo GLO-90 elevation API).
- `nearest_segment_id`: nearest-neighbor match to the 18 NH-7 segments, for spatial
  (not random) train/test splitting.
{"- `rainfall_7d_mm`, `rainfall_max_1d_mm`: 7-day cumulative and single-day-max rainfall "
 "(Asia/Kolkata timezone), only present in dynamic-model runs." if building_dynamic_model else ""}

## Counts from this run
- NASA GLC raw yield in bounding box: {nasa_raw_yield}
- NASA GLC usable (dated) events: {len(nasa_positives)}
- NGDR points available: {ngdr_point_count}
- Negative points generated: {NEG_COUNT}
- Final rows after dropping missing data: {len(clean_df)} (dropped {dropped_count})
- Class balance: {clean_df['label'].value_counts().to_dict()}
"""
with open("DATA_NOTES.md", "w") as f:
    f.write(notes)
print("Saved documentation to 'DATA_NOTES.md'")
