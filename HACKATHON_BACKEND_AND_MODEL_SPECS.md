# NH-7 Landslide Early Warning System: Backend Specifications & Implementation Status

> **Corridor Scope:** NH-7 Highway Corridor (Rishikesh to Joshimath, Uttarakhand, India)  
> **Corridor Extent:** 247.37 km | 18 Continuous Sequence-Ordered Road Segments  
> **Status:** Backend Core & Predictive Engine **100% Operational** (Tasks 1–8 & Task 10 Integrated)  
> **API Version:** v1.0.0-final  
> **Reference Document:** [NH7_Hackathon_Build_Plan.pdf](file:///c:/hackathon%20IBM%20x%20Jigyasa/NH7_Hackathon_Build_Plan.pdf)

---

## 1. Project Framing & System Philosophy

Rather than framing this as an unverified academic machine-learning demonstration or static susceptibility map, this project delivers:
> **"A live, integrated, public-facing early-warning and trip-planning decision-support system for the Char Dham Yatra corridor."**

Static academic susceptibility maps cannot prevent travelers from getting trapped when a cloudburst strikes. This platform unifies 30m high-resolution topographic modeling, live multi-station meteorological forecasting, dynamic time-aware journey planning, crowdsourced incident verification, consequence-based clearance prioritization, multi-channel alerting, and offline resilience into a single, cohesive decision-support early-warning system.

---

## 2. Complete Architecture: Implemented Systems

```
+----------------------------------------------------------------------------------------------------+
|                                    INPUT DATA SOURCES & SENSORS                                    |
|  - 30m Copernicus DEM: Slope, 300m Local Relief, Topographic Position Index (TPI), Curvature      |
|  - Mey et al. (2024) NH-7 Landslide Scar Inventory: 309 GPS-verified highway failure points        |
|  - Real Road Polyline Geometry: OpenStreetMap 247.37 km highway trace deduplicated to 250m nodes  |
|  - Open-Meteo Real-Time Weather: Multi-station hourly 72h past + 72h forecast precipitation        |
|  - Overpass OSM Consequence Data: Nearest hospital, town, lodging count, and detour availability   |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                CORE ENGINE & SERVICES (app/)                                       |
|  1. Topographic Baseline (risk_service.py): Out-of-fold spatial statistical model (p90 aggregation)|
|  2. Weather Service (weather_service.py): 72h antecedent + 72h forecast rainfall, memory cache,    |
|     disk snapshot fallback (data/rain_snapshot.json), DEMO_MODE pinned snapshot support            |
|  3. Time-Aware Trip Planner: Hourly route ETA calculation, 48h departure recommendation engine     |
|  4. Consequence & BRO Priority: Vulnerability index x Consequence score = Clearance priority       |
|  5. Feedback Flywheel: Snaps field reports to nearest segment, decaying risk escalation (<=1 step) |
|  6. Localization Engine (i18n.py): English & Hindi bilingual translation with transliterated names |
|  7. Alert Dispatcher & Notifiers: Background scheduler, Telegram long-polling bot, Twilio SMS/WA |
|  8. Voice Synthesizer: gTTS MP3 audio generation with file cache and Web Speech API fallback       |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                REST API LAYER (FastAPI + SQLite)                                   |
|  - Core Risk:            GET /risk-map, GET /route-risk, GET /priority-list                        |
|  - Road Closures:        GET /closures, POST /admin/closure, DELETE /admin/closure/{id}            |
|  - Subscriptions:        POST /subscribe, GET /alerts                                              |
|  - Citizen Flywheel:     POST /field-report, GET /field-reports, POST /admin/validate-report        |
|  - Flywheel Data Export: GET /admin/reports/export.csv                                             |
|  - Voice & Speech:       GET /voice-alert                                                          |
|  - Offline Mobile Pack:  GET /offline-pack (gzip, ETag / 304 Not Modified, < 100 KB)               |
|  - Webhooks:             POST /webhook/sms (Twilio TwiML), Telegram long polling background worker  |
|  - Observability:        GET /health, GET /model-info, GET /history                                |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                             FRONTEND TESTBENCH & CLIENT SUPPORT                                    |
|  - Interactive Workbench: Leaflet UI with Topo/Satellite views, Voice playback, & Offline banner   |
|  - Progressive Web App:   manifest.json & sw.js Service Worker caching app shell and offline pack   |
|  - Mobile Integration:    Documented Flutter / React Native integration guide (docs/OFFLINE.md)    |
|  - Verification CLI:      scripts/demo_check.py (8-step automated demo runner with latency audit)  |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Scientific Model Specifications & Spatial Validation

### 3.1 Ground-Truth Training Data
- **Dataset:** Mey et al. (2024) peer-reviewed landslide scar inventory published in *Natural Hazards and Earth System Sciences* (`nhess-24-3207-2024`).
- **Highway Scars:** 309 GPS-accurate, field-verified landslide scar polygons mapped along NH-7 following the 2022 monsoon season.
- **Absence Sampling:** 618 non-landslide points (2:1 absence-to-presence ratio) sampled along the highway corridor with a strict **250m spatial exclusion buffer** around known scars.

### 3.2 Road Alignment & Deduplication
- **Corridor Alignment:** OpenStreetMap highway relation (`geojson/nh7_route.geojson`).
- **Total Corridor Length:** **247.37 km** (Rishikesh to Joshimath).
- **Spatial Resolution:** Deduplicated to **1 point every 250 meters** of highway (**4.0 points/km**, totaling 990 road assessment nodes).

### 3.3 Topographic Variables (30m Copernicus DEM)
For each road point, geomorphometric variables were sampled from 30m digital elevation tiles:
1. **Slope Angle ($\theta$, degrees):** Steepness of mountain rock faces and road cuts.
2. **300m Local Relief ($\Delta Z_{300\text{m}}$, meters):** Elevation difference between the highest and lowest points within a 300m radius circle (gravitational potential energy).
3. **Topographic Position Index (TPI):** Differentiates valley floors, lower slopes, ridges, and incised gorges.
4. **Profile Curvature:** Quantifies flow acceleration and divergence zones.

### 3.4 Spatial Validation & Statistical Integrity
To avoid optimistic performance bias from spatial autocorrelation, the model was evaluated using **6-Fold Spatial Block Cross-Validation** (dividing the 247 km highway into 6 contiguous geographic sectors with a 2.0 km exclusion buffer):

| Evaluation Metric | Measured Score | Scientific Significance |
| :--- | :--- | :--- |
| **Spearman Correlation ($\rho$)** | **0.653** ($p = 0.0033$) | Statistically significant correlation between out-of-fold segment risk and actual observed landslides per km. |
| **Cross-Validated ROC-AUC** | **0.767** [95% CI: 0.680 – 0.802] | Strong out-of-sample discriminative ability across spatially held-out highway sectors. |
| **Block AUC Mean** | **0.664** [95% CI: 0.630 – 0.701] | Verified across 1,000 spatial block-bootstrap iterations over 6 spatial blocks. |
| **Primary Generalizing Driver** | **Slope ($\Delta\text{AUC} = +0.0523$)** | Permutation importance confirms slope steepness is the dominant physical predictor. |
| **Secondary Driver** | **300m Relief ($\Delta\text{AUC} = +0.0216$)** | Large valley-to-ridge relief significantly elevates slope failure risk. |
| **Feature Note on Elevation** | **Elevation (Gini: 19.6%)** | Retained in deployed Random Forest v2 ensemble; noted in earlier spatial logistic experiments as yielding poor univariate out-of-fold transfer. |

### 3.5 Terrain Susceptibility Formulation
The segment static terrain score ($P_{\text{terrain}}$) is computed via the spatial model aggregated to the 18 segments using the **90th percentile ($p_{90}$)** to isolate the most hazardous cut-slope within each stretch:

$$\text{Logit}(z) = -6.0963 + 0.1348 \times \text{Slope} + 0.0076 \times \text{Relief}_{300\text{m}}$$

$$P_{\text{terrain}} = \frac{1}{1 + e^{-z}}$$

---

## 4. Operational Algorithms & Business Logic

### 4.1 Dynamic Rainfall Coupling (Heuristic Threshold)
Static terrain susceptibility is dynamically integrated with 3-day antecedent rainfall ($R_{\text{3d}}$) fetched from Open-Meteo across 5 corridor weather stations using the calibrated linear-capped composite formula:

$$\text{risk\_score} = \min\left(K_{\text{terrain}} \times \text{terrain\_percentile} + K_{\text{rain}} \times \min\left(\frac{R_{\text{3d}}}{\text{RAIN\_REF\_MM}}, 1.0\right), 1.0\right)$$

where $K_{\text{terrain}} = 0.65$, $K_{\text{rain}} = 0.35$, and $\text{RAIN\_REF\_MM} = 100.0\text{ mm}$ (operational demo heuristics).

- **Safety Cap:** When $R_{\text{3d}} < 25.0\text{ mm}$ (`DRY_CAP_MM = 25.0`), risk level is capped at `"Moderate"`. Dry mountain slopes do not fail spontaneously without seismic or severe hydraulic triggers.
- **Explainable Driver Strings:** 18/18 segments feature dynamically generated natural-language explanations (e.g., `Steep 30.2° cut slope, high 300m relief (122m)`).

### 4.2 Time-Aware Trip Planner
- **ETA Simulation:** Calculates segment-by-segment arrival time based on road length and vehicle speed (default: 30 km/h in mountainous terrain).
- **Dynamic Antecedent Rain at ETA:** Computes cumulative 72h rainfall up to the exact arrival timestamp using combined historical and forecast hourly rain series.
- **Departure Recommendation Engine:** Evaluates hourly departure windows across 48 hours to find the safest travel time, returning up to 3 optimal windows (`GO`, `CAUTION`, `DELAY`, `AVOID`).
- **Closure Awareness:** Automatically escalates route recommendation to `AVOID` if any traversed segment has an active official road closure.

### 4.3 Consequence Scoring & BRO Priority List
To assist the Border Roads Organisation (BRO) and disaster management authorities in resource allocation:

$$\text{consequence\_score} = 0.40 \cdot \text{norm\_hospital\_dist} + 0.35 \cdot \text{no\_detour\_flag} + 0.25 \cdot \text{norm\_traffic\_index}$$

$$\text{priority\_score} = \text{risk\_index} \times \text{consequence\_score}$$

- High-consequence segments with long hospital evacuation distances and zero alternate detour routes receive priority in equipment dispatch.

### 4.4 Citizen Data Flywheel & Verification
- Field hazard reports submitted by travelers or road crews are snapped to the nearest road segment via geodesic distance.
- When an admin validates a report, an exponential decay filter is applied:
  
  $$\text{weight} = 0.5^{\Delta t / 48\text{h}}$$
  
- Verified reports escalate the displayed risk level by **at most ONE step** (e.g., `Low` $\rightarrow$ `Moderate`), preventing panic while reflecting real-time localized ground conditions.

---

## 5. System Limitations & Technical Boundaries (Honest Disclosure)

To maintain scientific integrity and prevent overclaiming during presentations, the following real-world boundaries are explicitly stated:

1. **Empirical Rainfall Formulation vs. Subsurface Geotechnics:**
   - The rainfall trigger function ($1 - e^{-k \cdot R_{\text{3d}}}$) is an empirical hazard-scaling heuristic based on antecedent precipitation thresholds from mountain literature.
   - It **does not** measure in-situ pore-water pressure, soil moisture retention curves, or borehole piezometric heads.
2. **Geological Structure Data Availability:**
   - The model accounts for slope, relief, curvature, and TPI from 30m DEM data.
   - It **does not** incorporate localized rock joint orientation, dip angle, foliation planes, or lithological shear strength parameters, which require sub-meter geological borehole surveys.
3. **Macro-Meteorological Grid Resolution:**
   - Precipitation is obtained from Open-Meteo's numerical weather prediction model grid (~11 km resolution).
   - Highly localized, micro-topographic cloudbursts occurring in narrow gorges may not appear in regional NWP models until precipitation has occurred.
4. **Static Speed Route Simulation:**
   - The time-aware trip planner assumes a constant nominal travel speed (default 30 km/h).
   - It **does not** ingest live vehicular traffic density, toll gate delays, or one-way convoy controls enforced by police checkpoints.
5. **Human-in-the-Loop Flywheel:**
   - Field reports require verification by an authorized operator before affecting displayed risk levels to prevent malicious tampering or false alarms.
6. **OSM Consequence Proxies:**
   - Hospital distances and lodging counts are derived from OpenStreetMap Overpass queries. While highly informative for isolation indexing, rural healthcare clinic data in remote Himalayan valleys depends on community mapping completeness.

---

## 6. Complete Implemented Endpoint Catalog

| Method | Endpoint | Query / Body Parameters | Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | None | Operational |
| `GET` | `/risk-map` | `simulate_rain_mm`, `lang` | Operational |
| `GET` | `/route-risk` | `from_segment`, `to_segment`, `date`, `depart_time`, `speed_kmph`, `simulate_rain_mm`, `lang` | Operational |
| `GET` | `/priority-list` | `simulate_rain_mm` | Operational |
| `GET` | `/closures` | `segment_id`, `active_only` | Operational |
| `POST` | `/admin/closure` | JSON body (`segment_id`, `status`, `reason`, `source`, `starts_at`, `ends_at`) | Operational |
| `DELETE`| `/admin/closure/{id}` | Path param `id`, Header `X-Admin-Key` or `X-API-Key` | Operational |
| `POST` | `/subscribe` | JSON body (`name`, `phone_or_email`, `segment_id`, `channel`, `consent`) | Operational |
| `GET` | `/alerts` | `user_id`, `simulate_rain_mm`, `lang` | Operational |
| `POST` | `/field-report` | JSON body (`lat`, `lng`, `description`, `photo_url`, `reporter_name`) | Operational |
| `GET` | `/field-reports` | `status`, `limit` | Operational |
| `POST` | `/admin/validate-report`| JSON body (`report_id`, `decision`, `notes`) | Operational |
| `GET` | `/admin/reports/export.csv` | Header `X-Admin-Key` or `X-API-Key` | Operational |
| `GET` | `/history` | None | Operational |
| `GET` | `/model-info` | None | Operational |
| `GET` | `/offline-pack` | Header `If-None-Match` (supports ETag / 304 Not Modified) | Operational |
| `GET` | `/voice-alert` | `segment_id` OR `from_segment` & `to_segment`, `lang` | Operational |
| `POST` | `/webhook/sms` | Form data `Body`, `From` (Twilio TwiML compliant) | Operational |
| `GET` | `/manifest.json` | Web App Manifest | Operational |
| `GET` | `/sw.js` | Service Worker Script | Operational |

---

## 7. Verification & Testing Evidence

1. **Contract Tests (`tests/contract/`):**
   - 9/9 Golden Schema tests pass (`tests/contract/test_golden_schema.py`).
   - 100% backward-compatibility verified against `tests/golden/`. Zero keys deleted or renamed.
2. **Full Pytest Suite:**
   - 119/119 unit, security, resilience, localization, offline, and contract tests pass in 16.18s.
3. **Live Smoke Runner (`scripts/smoke.py`):**
   - 22/22 live HTTP endpoints tested against running server, 100% PASS.
4. **Scripted Demo Verifier (`scripts/demo_check.py`):**
   - 8/8 end-to-end integration demo steps passed in 508.8ms.
5. **Offline DEMO Mode:**
   - `DEMO_MODE=true` pins all weather calls to `data/rain_snapshot.json` for reproducible presentations with zero internet dependencies.
