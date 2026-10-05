# Task 2: Landslide Backtest Harness & Model Calibration Report

> **Report Generated**: 2026-10-05 19:05:11Z
> **Mode**: ⚠️ SYNTHETIC DEMONSTRATION SMOKE TEST (data/backtest_events.csv had < 10 rows)
> **Corridor Scope**: NH-7 Highway, Uttarakhand (Rishikesh to Joshimath, 247.37 km)
> **Events Evaluated**: 12 Positives | 36 Monsoon Background Negatives

---

## 1. Executive Summary & Headline Scorer Benchmarks

| Model Scorer Formulation | Features Used | Out-of-Sample ROC-AUC | 95% Bootstrap CI | Discriminative Performance |
| :--- | :--- | :---: | :---: | :--- |
| **Rainfall Only** | $R_{\text{3d}} / 100$ | **0.549** | [0.354 – 0.723] | Captures synoptic monsoon intensity; blind to slope mechanics. |
| **Static Terrain Only** | Copernicus 30m DEM $P_{\text{terrain}}$ | **0.578** | [0.372 – 0.762] | Identifies steep physical cut-slopes; lacks dynamic trigger. |
| **Combined Production Model** | $0.6 \cdot P_{\text{terr}} + 0.4 \cdot R_{\text{3d}}$ | **0.618** | [0.401 – 0.815] | **Top Generalization**: Blends structural hazard with hydrologic trigger. |

---

## 2. Combined Model Precision & Recall by Categorical Tier

| Risk Tier | Threshold | Predicted Count | True Positives | Precision | Recall (Sensitivity) | Operational Advisory |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Very High** | $\ge 0.75$ | 1 | 0 | 0.0% | 0.0% | Immediate road closure / convoy stoppage |
| **High** | $\ge 0.50$ | 14 | 5 | 35.7% | 41.7% | Heavy caution & patrol escort |
| **Moderate** | $\ge 0.25$ | 38 | 10 | 26.3% | 83.3% | Standard alert |
| **Low** | $\ge 0.00$ | 48 | 12 | 25.0% | 100.0% | Standard alert |

---

## 3. $k_{\text{rain}}$ Grid Search & Hyperparameter Tuning

We evaluated cross-validated ROC-AUC across candidate rainfall coupling weights $k_{\text{rain}} \in [0.1, 0.9]$:

| Candidate $k_{\text{rain}}$ | Terrain Weight $(1 - k)$ | Cross-Validated AUC | Delta vs Production (0.4) |
| :---: | :---: | :---: | :---: |
| `0.1` | `0.9` | `0.5972` | `+-0.0093` |
| `0.2` | `0.8` | `0.6227` | `+0.0162` *(Optimal Candidate)* |
| `0.3` | `0.7` | `0.6227` | `+0.0162` |
| `0.4` | `0.6` | `0.6065` | `+0.0000` **(Production Default)** |
| `0.5` | `0.5` | `0.5625` | `+-0.0440` |
| `0.6` | `0.4` | `0.5394` | `+-0.0671` |
| `0.7` | `0.3` | `0.4954` | `+-0.1111` |
| `0.8` | `0.2` | `0.4861` | `+-0.1204` |
| `0.9` | `0.1` | `0.5116` | `+-0.0949` |

**Recommendation**: Grid-search indicates $k_{\text{rain}}^* = 0.2$ provides peak empirical discrimination on this dataset. **In accordance with project rules, production `K_RAIN = 0.4` is strictly maintained unchanged** until verified ground-truth closure datasets with $n \ge 50$ events are approved.

---

## 4. Scientific Caveats & Methodological Boundaries
1. **Coarse Reanalysis Weather Grid**: Open-Meteo Historical Archive / ERA5-Land uses an ~11–25 km numerical grid. In steep Himalayan terrain, violent convective cloudbursts often strike tributary catchments $< 5\text{ km}$ across, which coarse reanalysis models smooth over.
2. **Sample Size & Verification Gaps**: This demonstration audit utilized a synthetic smoke run because `data/backtest_events.csv` is an unpopulated template. No synthetic records were saved to the template to uphold Project Rule 5.
3. **Timestamp Uncertainty**: Official disaster records frequently note the time a highway patrol cleared or reopened a blockage rather than the exact initiation timestamp of the slope failure, introducing up to 24–48 hours of temporal uncertainty in rainfall alignment.
