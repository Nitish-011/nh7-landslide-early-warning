# Scientific Validation & Integrity Audit Report (NH-7 Landslide Model)

**Audit Date**: `2026-10-05 18:20:18 UTC`  
**Corridor Scope**: `Rishikesh to Joshimath, 247.37 km` (National Highway 7, Uttarakhand)  
**Inventory Evaluated**: Mey et al. (2024), $N = 309$ surveyed road-blocking landslides  
**Model Evaluated**: Copernicus 30 m DEM + Random Forest (`nh7_static_model_v2.joblib`)  

---

## Executive Summary

This audit report provides independent, transparent verification of the NH-7 landslide static hazard model across four rigorous axes:
1. **Inventory Spatial Coverage**: Evaluates whether the 309 surveyed landslides span the entire 247.37 km corridor and quantifies road-proximity buffer integrity.
2. **Headline Cross-Validation Metrics**: Reports pooled and per-block generalization ROC-AUCs with 95% block-bootstrap confidence intervals alongside corridor-wide rank correlation ($n=18$).
3. **Known Hotspot Recall**: Assesses historical chronic slide locations against model segment rankings via `data/known_hotspots.csv`.
4. **Aggregation Sensitivity**: Analyzes the stability of segment risk rankings under 90th percentile ($p_{90}$), 75th percentile ($p_{75}$), spatial mean, and maximum pooling.

---

## (a) Inventory Coverage Analysis

### Key Findings:
- **Total Landslide Scars in Inventory**: **309** field-mapped mass movements.
- **Chainage Extent Along Highway**: **9.07 km to 242.66 km** (spanning **233.59 km**).
- **Full 247.37 km Coverage Verdict**: **Does NOT span the full 247.37 km**.
  - The first **9.07 km** (from Rishikesh zero station to near Shivpuri) contains **zero** recorded road-blocking slides in this inventory due to lower foothill gradients.
  - The final **4.71 km** (from km 242.66 to Joshimath route end at km 247.37) contains **zero** recorded road-blocking slides in this 2022 survey.
- **Perpendicular Distance from Highway Centerline**: Min **0.0 m**, Median **5.4 m**, Max **22.5 m**.
  - Every recorded scar is within 22.5 m of the road centerline, verifying high positional fidelity to road cuts.
- **Segments with Zero Scars**: **1 segment(s)**:
  - `seg_15` (**Chamoli to Birahi**): length 5.24 km (0 scars, 0.00 scars/km)

### Per-Segment Scar Distribution Table

| Segment ID | Segment Name | Route Start (km) | Route End (km) | Length (km) | Observed Scars | Scars / km |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `seg_01` | Rishikesh to Shivpuri | 0.00 | 17.43 | 17.43 | **23** | **1.32** |
| `seg_02` | Shivpuri to Byasi | 17.43 | 24.26 | 6.83 | **20** | **2.93** |
| `seg_03` | Byasi to Kaudiyala | 24.26 | 38.12 | 13.86 | **36** | **2.60** |
| `seg_04` | Kaudiyala to Devprayag | 38.12 | 70.63 | 32.51 | **96** | **2.95** |
| `seg_05` | Devprayag to Teen Dhara | 70.63 | 85.56 | 14.94 | **44** | **2.95** |
| `seg_06` | Teen Dhara to Kirtinagar | 85.56 | 98.04 | 12.47 | **7** | **0.56** |
| `seg_07` | Kirtinagar to Srinagar | 98.04 | 102.99 | 4.95 | **4** | **0.81** |
| `seg_08` | Srinagar to Sirobagarh | 102.99 | 112.42 | 9.42 | **1** | **0.11** |
| `seg_09` | Sirobagarh to Rudraprayag | 112.42 | 136.06 | 23.64 | **17** | **0.72** |
| `seg_10` | Rudraprayag to Gauchar | 136.06 | 158.55 | 22.49 | **4** | **0.18** |
| `seg_11` | Gauchar to Karnaprayag | 158.55 | 168.12 | 9.56 | **3** | **0.31** |
| `seg_12` | Karnaprayag to Langasu | 168.12 | 174.18 | 6.07 | **4** | **0.66** |
| `seg_13` | Langasu to Nandprayag | 174.18 | 187.33 | 13.15 | **2** | **0.15** |
| `seg_14` | Nandprayag to Chamoli | 187.33 | 200.39 | 13.05 | **9** | **0.69** |
| `seg_15` | Chamoli to Birahi | 200.39 | 205.62 | 5.24 | **0** | **0.00** |
| `seg_16` | Birahi to Pipalkoti | 205.62 | 212.36 | 6.74 | **4** | **0.59** |
| `seg_17` | Pipalkoti to Helang (Tangani) | 212.36 | 241.04 | 28.68 | **32** | **1.12** |
| `seg_18` | Helang to Joshimath | 241.04 | 247.37 | 6.33 | **3** | **0.47** |

---

## (b) Headline Model Cross-Validation Metrics

The model was evaluated using **leave-one-block-out spatial cross-validation** across contiguous highway sections with a **2.0 km exclusion buffer** to prevent spatial data leakage.

| Metric | Value | 95% Confidence Interval | Evaluation Scope | Notes / Methodology |
| :--- | :---: | :---: | :---: | :--- |
| **Pooled Out-of-Fold AUC** | **0.767** | **[0.682, 0.800]** | Corridor-wide ($N=1,236$) | Block-bootstrap ($B=1,000$ resamples) |
| **Per-Block Mean AUC** | **0.664** | **[0.634, 0.699]** | Across 6 spatial blocks | Unweighted average of block test folds |
| **Spatial Blocks ($k$)** | **6** | — | Highway partition | Ordered route progression (2.0 km buffer) |
| **Spearman Rank Correlation ($\rho$)** | **0.653** | $p = 0.0033$ | $n = 18$ road segments | Model $p_{90}$ hazard vs observed slides/km |

> [!NOTE]
> The statistically significant Spearman rank correlation ($\rho = 0.653$, $p = 0.0033$) confirms that the model's out-of-fold hazard predictions successfully rank the 18 segments in accordance with real-world landslide frequency.

---

## (c) Known Hotspot Recall Evaluation

The file `data/known_hotspots.csv` tracks notorious chronic landslide and rockfall zones along the corridor.

> [!IMPORTANT]
> **Template Status**: All **8 hotspot rows** in `data/known_hotspots.csv` are currently TEMPLATE entries with blank coordinates. All 8 entries were skipped during evaluation.
> When GPS coordinates and source URLs are populated by the domain expert, re-running `python scripts/validation_audit.py` will dynamically map each hotspot to its nearest segment and report model percentile ranks.

| Hotspot Name | Status | Nearest Segment | Model Segment Rank | Model Percentile | Top-Third (Top 6 of 18)? |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Sirobagarh** | *Skipped (Blank Coordinates in Template)* | — | — | — | — |
| **Kaliasaur** | *Skipped (Blank Coordinates in Template)* | — | — | — | — |
| **Tangni** | *Skipped (Blank Coordinates in Template)* | — | — | — | — |
| **Pagal Nala** | *Skipped (Blank Coordinates in Template)* | — | — | — | — |
| **Lambagad** | *Skipped (Blank Coordinates in Template)* | — | — | — | — |
| **Chhinka** | *Skipped (Blank Coordinates in Template)* | — | — | — | — |
| **Helang** | *Skipped (Blank Coordinates in Template)* | — | — | — | — |
| **Bhanerpani** | *Skipped (Blank Coordinates in Template)* | — | — | — | — |

---

## (d) Aggregation Method Sensitivity Analysis

Segment hazard scores are derived by pooling predictions from deduplicated 250m points within each segment boundary. We evaluate sensitivity to the pooling statistic: **90th percentile ($p_{90}$)**, **75th percentile ($p_{75}$)**, **spatial mean**, and **spatial maximum**.

### Pairwise Spearman Rank Correlations

| Comparison Pair | Spearman Rank Correlation ($\rho$) | p-value | Statistical Significance | Agreement Interpretation |
| :--- | :---: | :---: | :---: | :--- |
| **P90 vs P75** | **0.9236** | `p < 0.001` | Statistically Significant | High Ranking Concordance |
| **P90 vs MEAN** | **0.8720** | `p < 0.001` | Statistically Significant | High Ranking Concordance |
| **P90 vs MAX** | **0.9133** | `p < 0.001` | Statistically Significant | High Ranking Concordance |
| **P75 vs MEAN** | **0.9174** | `p < 0.001` | Statistically Significant | High Ranking Concordance |
| **P75 vs MAX** | **0.8927** | `p < 0.001` | Statistically Significant | High Ranking Concordance |
| **MEAN vs MAX** | **0.8947** | `p < 0.001` | Statistically Significant | High Ranking Concordance |

### Per-Segment Ranking Under Different Aggregations

| Segment ID | Segment Name | Rank ($p_{90}$, Headline) | Rank ($p_{75}$) | Rank (Mean) | Rank (Max) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `seg_01` | Rishikesh to Shivpuri | **#2** | #5 | #7 | #2 |
| `seg_02` | Shivpuri to Byasi | **#6** | #4 | #3 | #9 |
| `seg_03` | Byasi to Kaudiyala | **#5** | #3 | #4 | #3 |
| `seg_04` | Kaudiyala to Devprayag | **#3** | #2 | #2 | #1 |
| `seg_05` | Devprayag to Teen Dhara | **#1** | #1 | #1 | #4 |
| `seg_06` | Teen Dhara to Kirtinagar | **#4** | #6 | #6 | #6 |
| `seg_07` | Kirtinagar to Srinagar | **#12** | #9 | #11 | #12 |
| `seg_08` | Srinagar to Sirobagarh | **#7** | #12 | #12 | #11 |
| `seg_09` | Sirobagarh to Rudraprayag | **#9** | #8 | #10 | #10 |
| `seg_10` | Rudraprayag to Gauchar | **#14** | #14 | #18 | #16 |
| `seg_11` | Gauchar to Karnaprayag | **#17** | #18 | #14 | #15 |
| `seg_12` | Karnaprayag to Langasu | **#16** | #17 | #16 | #17 |
| `seg_13` | Langasu to Nandprayag | **#13** | #15 | #13 | #13 |
| `seg_14` | Nandprayag to Chamoli | **#10** | #11 | #9 | #7 |
| `seg_15` | Chamoli to Birahi | **#18** | #16 | #15 | #18 |
| `seg_16` | Birahi to Pipalkoti | **#15** | #13 | #17 | #14 |
| `seg_17` | Pipalkoti to Helang (Tangani) | **#11** | #10 | #8 | #8 |
| `seg_18` | Helang to Joshimath | **#8** | #7 | #5 | #5 |

> [!TIP]
> **Aggregation Consistency Finding**: The pairwise Spearman rank correlations across all 4 aggregation strategies range between **0.8720 and 0.9236** ($p < 10^{-5}$ across all pairs). This confirms that segment hazard rankings are structurally robust and not an artifact of choosing the 90th percentile over the 75th percentile, spatial mean, or maximum.

---

*Report programmatically generated by `scripts/validation_audit.py`.*
