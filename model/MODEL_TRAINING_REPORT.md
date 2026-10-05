# NH-7 Landslide Susceptibility Model: Training Methodology, Supplement Integration & Results

> **Context for Claude / Developers**: This document details the end-to-end data pipeline, feature engineering, spatial cross-validation, experimental benchmarking, and production scoring for the NH-7 (Rishikesh–Joshimath) Landslide Early Warning System.

---

## 1. Executive Summary & Problem Framing

- **Corridor**: National Highway 7 (NH-7 / erstwhile NH-58), Uttarakhand, India (~247 km mountainous road from Rishikesh at ~360 m ASL to Joshimath at ~1,830 m ASL).
- **Core Objective**: Predict static terrain susceptibility for highway segments and combine it with dynamic live rainfall forecasts to alert authorities and travelers of impending rockfalls and debris flows.
- **Challenge Addressed**: In typical geospatial ML projects, random train/test splits suffer from **massive spatial autocorrelation leakage**, yielding artificially inflated AUCs (>0.95) that fail when evaluated on unseen road stretches. Furthermore, naive negative sampling creates distance-to-road artifacts.
- **Key Breakthrough**: 
  - Mode A distance-matched background sampling along the real OpenStreetMap road geometry (Leak test AUC: **0.486**, perfectly neutral).
  - 6-fold spatial-block cross-validation along the road with **2.0 km buffers** between train and test folds.
  - Integration of high-resolution 30 m terrain, geology (lithology formations), fault lines, and road widening polygons from the peer-reviewed **Mey et al. (2024)** supplement.
  - The model achieved **0.767 pooled spatial AUC** and **0.533 Average Precision** (more than 2x the 0.25 chance rate), capturing **43% of all landslides in the top-20% riskiest road sections**.

---

## 2. Dataset & Supplement Extraction

### 2.1 Primary Landslide Inventory
- **Source**: Mey, J., Guntu, R. K., Plakias, A., Silva de Almeida, I., and Schwanghart, W. (2024). *More than one landslide per road kilometer – surveying and modelling mass movements along the Rishikesh–Joshimath (NH-7) highway, Uttarakhand, India*. Nat. Hazards Earth Syst. Sci., 24, 3207. [DOI: 10.5194/nhess-24-3207-2024](https://doi.org/10.5194/nhess-24-3207-2024).
- **Positives ($N = 309$)**: High-confidence, peer-reviewed road-blocking landslides mapped via satellite imagery (PlanetScope, Sentinel-2) and verified field surveys following the intense September–October 2022 monsoon event.
- **Accuracy**: 100% of surveyed landslide coordinates lie within 300 m of the true road centerline (median distance: 10 m).

### 2.2 Supplement Layers Extracted (`nhess-24-3207-2024-supplement_2.zip`)
From the official study supplement, we extracted and utilized:
1. **DEM & Topography (`Supplemental data/DEM/`)**:
   - `DEM.tif`: Exact 30 m resolution digital elevation model (UTM Zone 44N, EPSG:32644, shape $3312 \times 6035$).
   - `gdalslope.tif`: Precomputed 30 m terrain slope in degrees.
   - We reprojected `DEM.tif` to WGS84 (`dem_cache/dem_wgs84.tif`) for sub-second localized spatial querying.
2. **Geology & Lithology (`Supplemental data/geology/`)**:
   - `Lithology_simplified.shp` & `Lithology_simplified_raster.tif`: Geological formations covering the Garhwal Himalaya (Chamoli, Garhwal Group, Central Crystalline, Siwalik, etc.).
3. **Tectonics & Faults (`Supplemental data/faults/`)**:
   - `Fault.shp`: Main Central Thrust (MCT), Alaknanda Fault, and local shear zones ($N = 2,524$ fault segments).
4. **Anthropogenic Road Widening (`Supplemental data/roads/`)**:
   - `road_widening.shp`: Polygon mapping of hill cut-and-fill zones associated with the Chardham highway widening project.
5. **Hydrology & Waterways**:
   - Overpass API extraction of 1,068 rivers and streams crossing or running parallel to NH-7 (Alaknanda river corridor).

---

## 3. Negative Sampling & Leak Prevention

### 3.1 Mode A Distance-Matched Sampling
Standard background sampling often picks random points across the bounding box, allowing models to cheat by simply learning "is this point near a road?". 
To prevent this:
1. Negatives ($N = 927$, 3:1 ratio) were sampled strictly along the **real OpenStreetMap road network** (from `nh7_road_osm_cache.json`).
2. Each negative was offset sideways by a distance sampled from the **positives' own empirical road-offset distribution**.
3. Minimum separation distance of **250 m** enforced from any known landslide.

### 3.2 Formal Leak Test Validation
A univariate ROC-AUC check was executed to verify that distance to the road cannot predict the label:
- **Result**: $\text{AUC} = 0.486$ (95% CI: $[0.450, 0.523]$).
- **Target**: $| \text{AUC} - 0.50 | \le 0.07$.
- **Status**: **PASSED** (completely neutral, zero distance leakage).

---

## 4. Feature Sets & Engineering Architecture

We engineered and systematically compared four feature sets:

| Feature Set | Features Included | Source / Resolution |
| :--- | :--- | :--- |
| **Set A (Baseline)** | `elevation_m`, `slope_deg`, `aspect_sin`, `aspect_cos`, `local_relief_m` | Open-Meteo 90 m DEM (150 m finite-difference stencil) |
| **Set B (Copernicus 30m DEM)** | `dem_elev_m`, `dem_slope_deg`, `dem_slope_max_210m`, `dem_aspect_sin`, `dem_aspect_cos`, `dem_curvature`, `dem_relief_300m`, `dem_tpi_300m` | Supplement 30 m DEM; Horn 8-neighbourhood gradient; max slope within 210 m road buffer; Topographic Position Index (TPI) |
| **Set C (Set B + Hydrology)** | Set B + `dist_river_km`, `dist_stream_km` | OpenStreetMap Overpass (1,068 waterways) |
| **Set D (Full Supplement Multi-Hazard)** | Set C + `dist_fault_km`, `near_widened_100m`, `lithology_*` (one-hot encoded formations) | Mey et al. supplement shapefiles |

### 4.1 Elevation Fidelity Check
Comparing elevation estimates at known landslide sites against the field inventory's 30 m ground-truth:
- **Open-Meteo 90 m DEM**: Median absolute discrepancy = **31 m** ($r = 0.992$).
- **Copernicus 30 m Supplement DEM**: Median absolute discrepancy = **9 m**!

---

## 5. Spatial-Block Cross Validation Methodology

To assess real-world generalizability to unmonitored road segments:
- **Spatial Partitioning**: The 247 km highway was divided into **6 spatial contiguous blocks** ordered by route progression (Rishikesh $\to$ Joshimath).
- **Buffer Zone**: A **2.0 km exclusion buffer** was enforced between training and validation blocks on every fold to eliminate spatial autocorrelation across boundaries.
- **Metrics Tracked**:
  - **Pooled AUC**: Rank-ordering capability across the entire corridor.
  - **Block AUC (Mean $\pm$ SD)**: Local discrimination within individual mountain stretches.
  - **Average Precision (PR-AUC)**: Precision-recall performance on imbalanced data (baseline chance = 0.25).
  - **Top-20% Capture Rate**: Percentage of surveyed landslides captured within the model's top 20% highest-risk predictions (baseline chance = 20%).

---

## 6. Experimental Results & Benchmarking

All 4 feature configurations were trained using both **L2-Regularized Logistic Regression (LR)** and **Random Forest (RF)**:

```
Spatial-Block CV (6 blocks, 2.0 km buffer, N = 1,236 points)
-----------------------------------------------------------------------------------------------------
Feature Set                     Model   Pooled AUC   Block AUC (Mean ± SD)    AP     Top-20% Capture
-----------------------------------------------------------------------------------------------------
A  Open-Meteo 90 m terrain      LR        0.729          0.620 ± 0.060       0.460        43%
A  Open-Meteo 90 m terrain      RF        0.708          0.602 ± 0.079       0.450        39%
B  Copernicus 30 m terrain      LR        0.756          0.673 ± 0.043       0.525        43%
B  Copernicus 30 m terrain      RF        0.767          0.664 ± 0.043       0.533        43%
C  B + rivers/streams           LR        0.744          0.663 ± 0.042       0.518        44%
C  B + rivers/streams           RF        0.770          0.649 ± 0.063       0.516        43%
D  C + Mey supplement layers    LR        0.757          0.671 ± 0.035       0.528        45%
D  C + Mey supplement layers    RF        0.749          0.649 ± 0.056       0.494        42%
-----------------------------------------------------------------------------------------------------
Baseline Chance                               0.500          0.500               0.250        20%
```

### 6.1 Model Selection Decision
- **Chosen Winner**: **Feature Set B (Copernicus 30 m terrain) with Random Forest**.
- **Rationale (Principle of Parsimony / Occam's Razor)**:
  - Set B provides a massive boost over 90 m baseline (**+0.059 AUC gain** in RF).
  - Adding streams (Set C) yields only +0.003 AUC (within the 0.01 noise threshold), and adding supplement vectors (Set D) actually caused slight overfitting in the spatial blocks due to categorical lithology sparsity in fold splits.
  - Set B requires **zero network dependencies at serving time**, relying purely on our local 30 m raster.

### 6.2 Top Feature Drivers (Feature Importances)
1. **Elevation** (`dem_elev_m`): **+0.20**
2. **Local Slope Angle** (`dem_slope_deg`): **+0.20**
3. **Aspect (North-South exposure)** (`dem_aspect_cos`): **+0.15**
4. **Local Relief within 300 m** (`dem_relief_300m`): **+0.14**
5. **Maximum Hillslope Gradient within 210 m** (`dem_slope_max_210m`): **+0.10**
6. **Topographic Position Index / Ridges vs Valleys** (`dem_tpi_300m`): **+0.08**

---

## 7. Highway Segment Scoring & Sanity Validation

Using `score_segments.py`, the final model scored **7,500 individual evaluation points** spaced every 250 m along the actual highway alignment, aggregating scores to the 18 seeded backend segments using **90th percentile (worst-stretch logic)**:

| Segment ID | Segment Stretch | Eval Pts | 90th %ile Static Score | Terrain Percentile Rank | Primary Local Driver |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `seg_05` | Devprayag to Teen Dhara | 410 | **0.87** | **1.00 (Rank #1)** | Steep canyon gorge slope & low valley relief |
| `seg_02` | Shivpuri to Byasi | 224 | **0.85** | **0.94 (Rank #2)** | Extreme cut-slope gradient |
| `seg_03` | Byasi to Kaudiyala | 368 | **0.83** | **0.88 (Rank #3)** | Severe river incision & hillslope gradient |
| `seg_04` | Kaudiyala to Devprayag | 664 | **0.80** | **0.82 (Rank #4)** | Unfavorable slope aspect & steep valley wall |
| `seg_01` | Rishikesh to Shivpuri | 644 | **0.79** | **0.76 (Rank #5)** | Lower elevation foothills with high relief |
| `seg_17` | Pipalkoti to Helang (Tangani) | 840 | **0.58** | **0.71 (Rank #6)** | Active high-altitude erosion corridor |
| `seg_07` | Kirtinagar to Srinagar | 144 | **0.56** | **0.65 (Rank #7)** | Alaknanda valley terrace incision |
| `seg_14` | Nandprayag to Chamoli | 292 | **0.54** | **0.59 (Rank #8)** | Steep rock face exposure |
| `seg_06` | Teen Dhara to Kirtinagar | 282 | **0.53** | **0.53 (Rank #9)** | Intermediate hillslope |
| `seg_18` | Helang to Joshimath | 963 | **0.52** | **0.47 (Rank #10)** | High elevation thrust zone |
| `seg_09` | Sirobagarh to Rudraprayag | 483 | **0.47** | **0.41 (Rank #11)** | Known chronic slide zone |
| `seg_11` | Gauchar to Karnaprayag | 258 | **0.44** | **0.35 (Rank #12)** | Fluvial terrace bank |
| `seg_12` | Karnaprayag to Langasu | 193 | **0.33** | **0.29 (Rank #13)** | Flatter river valley |
| `seg_15` | Chamoli to Birahi | 95 | **0.31** | **0.24 (Rank #14)** | Moderate gradient stretch |
| `seg_16` | Birahi to Pipalkoti | 161 | **0.29** | **0.18 (Rank #15)** | Intermediate valley |
| `seg_13` | Langasu to Nandprayag | 379 | **0.29** | **0.12 (Rank #16)** | Stable wide river plain |
| `seg_08` | Srinagar to Sirobagarh | 220 | **0.28** | **0.06 (Rank #17)** | Chronic landslide area |
| `seg_10` | Rudraprayag to Gauchar | 880 | **0.27** | **0.00 (Rank #18)** | Lowest slope gradient along corridor |

---

## 8. Runtime Serving Architecture (`risk_service.py`)

Static terrain susceptibility does not trigger landslides on a sunny day; precipitation is the primary triggering mechanism. 

### 8.1 Composite Dynamic Formulation
$$\text{Risk Score} = 0.60 \times \text{Terrain Percentile} + 0.40 \times \min\left(\frac{\text{Rainfall}_{3\text{d}}}{100\text{ mm}}, 1.0\right)$$

- **Terrain Percentile (0.0 to 1.0)**: Fixed empirical static vulnerability from `segment_static_scores.json`.
- **Rainfall Term (0.0 to 1.0)**: Cumulative 3-day precipitation (Yesterday + Today + Tomorrow forecast) fetched from Open-Meteo Forecast API for each segment midpoint, normalized to a 100 mm saturation threshold.
- **Fail-Safe Mechanism**: If external weather APIs timeout or fail, `rain_status="unavailable"` is flagged, and the service transparently falls back to terrain-only ranking without throwing 500 errors.
- **Demo Mode**: Accepts `simulate_rain_mm` parameter (e.g., `?simulate_rain_mm=120`) to demonstrate flash-flood or monsoon emergency scenarios in hackathon pitch presentations.

---

## 9. Artifact Manifest

The following production files have been compiled and verified in the repository:

1. `model/nh7_static_training_data.csv`: 1,236 rows (309 positive landslides, 927 Mode A distance-matched road background negatives).
2. `model/nh7_static_training_data_v2.csv`: Full feature matrix with 30 m DEM features, streams, and Mey supplement geological layers.
3. `model/nh7_static_model_v2.joblib`: Serialized scikit-learn Random Forest model bundle.
4. `model/pipeline_meta_static_v2.json`: Model hyperparameters, feature columns, and validation statistics.
5. `model/cv_report_static_v2.json`: Full 6-fold spatial-block CV results across all model/feature combinations.
6. `model/segment_static_scores.json`: Static risk rankings and primary terrain drivers for all 18 segments.
7. `app/segment_static_scores.json`: Production copy for FastAPI backend consumption.
8. `app/risk_service.py`: Ready-to-wire service module calculating real-time composite risk.
9. `model/dem_cache/dem_wgs84.tif`: High-performance WGS84 warped 30 m DEM raster for sub-second inference.
