# NH-7 Landslide Risk Backend: Complete Testing & Verification Guide

This guide documents **every backend feature**, details **how to test every endpoint** (via the interactive testbench, `curl`, and automated tests), explains **how to replace the test frontend**, and directly addresses the core question: **What is static vs. dynamic in the backend?**

> [!TIP]
> **Looking for the browser UI testing walkthrough?** See [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) for a step-by-step tour of all 9 frontend tabs, live storm simulator, voice warnings, and PWA offline tests.

---

## 1. Deep Dive: "Is Nothing Static in Our Backend Right Now?"

**Short Answer:**  
The backend combines a **scientifically grounded static physical baseline** with a **100% dynamic, real-time hazard evaluation and alerting engine**.

If *everything* were dynamic (including topography), the model would violate the laws of physics. Mountain geology does not change overnight; weather changes constantly. Here is the exact architectural breakdown:

```
+-------------------------------------------------------------+
|               STATIC PHYSICAL BASELINE                      |
|  - 30m Copernicus DEM Topography (Slope, 300m Relief, TPI)  |
|  - 247.37 km NH-7 Corridor Polyline (OSM Alignment)         |
|  - 18 Segment Boundaries & Seeded Physical Subpoints         |
|  - Physically Motivated Statistical Model Weights (Mey 2024)|
+------------------------------+------------------------------+
                               |
                               v
+-------------------------------------------------------------+
|               DYNAMIC REAL-TIME ENGINE                      |
|  - Live 3-Day Antecedent Rainfall Fetch (Open-Meteo API)     |
|  - In-Memory Failure Circuit Breaker (5-minute TTL)         |
|  - Persistent Offline Fallback (data/rain_snapshot.json)     |
|  - On-the-Fly Trigger Curve & DRY_CAP_MM (25mm) Heuristic   |
|  - Real-Time Simulation Overrides (?simulate_rain_mm=...)    |
|  - Date-Aware Trip Forecasting & Advisory Logic             |
|  - SQLite Subscriptions, Alerts & Crowd-Sourced Reports      |
+-------------------------------------------------------------+
```

### What MUST Be Static (and Why)
1. **Topography & Geomorphology (Physical Mountain Baseline):**
   - Slope steepness, 300m local relief, curvature, and topographic position index (TPI) along the NH-7 highway corridor are derived from the 30-meter Copernicus Digital Elevation Model (DEM).
   - Himalayan bedrock formations and valley cliffs do not shift from hour to hour. Having a static, high-precision terrain susceptibility baseline ($P_{\text{terrain}}$) is standard scientific practice in geohazard engineering.
2. **Highway Route Geometry & 18 Segments:**
   - The 247.37 km highway alignment (`geojson/nh7_route.geojson`, `nh7_segments.csv`) and the 18 sequence-ordered segments from Rishikesh to Joshimath represent fixed civil road infrastructure.
3. **Machine Learning Model Parameters:**
   - The spatial model feature weights (slope, relief) and 90th percentile aggregation mappings are pre-fitted across spatial blocks.

### What IS Dynamic (Live, Reactive, & Real-Time)
1. **Live Meteorology:** Real-time 3-day antecedent rainfall is dynamically requested from the Open-Meteo API across 5 corridor weather stations (`fetch_rainfall`).
2. **Fault-Tolerant Fallback & Circuit Breaker:** If the live weather API experiences timeouts or goes offline, the backend dynamically falls back to `data/rain_snapshot.json` with a 5-minute memory circuit breaker, serving requests in under 100 milliseconds and tagging `rain_status: "cached"`.
3. **Dynamic Hazard Combination Engine:** Each request computes the real-time hazard score on the fly:
   $$P_{\text{hazard}} = P_{\text{terrain}} \times \left(1 - e^{-k \cdot R_{\text{3d}}}\right)$$
   and applies the `DRY_CAP_MM = 25.0` heuristic (capping risk at "Moderate" if dry).
4. **Simulation Overrides (`simulate_rain_mm`):** Any caller or UI user can supply `?simulate_rain_mm=85` to immediately simulate a monsoon downpour or cloudburst across `/risk-map`, `/route-risk`, and `/alerts`.
5. **Date-Aware Route Analysis:** If a travel date is beyond tomorrow (> 48 hours), the backend dynamically detects that rainfall forecasts are unreliable, evaluates risk using terrain susceptibility, and emits a clear travel advisory banner.
6. **Crowd-Sourced Reports & Alerts:** Submitting field hazard reports (`POST /field-report`), Admin validation (`POST /admin/validate-report`), creating subscriptions (`POST /subscribe`), and querying user-specific warnings (`GET /alerts`) are 100% dynamic operations stored in SQLite.

---

## 2. The Replaceable Test Frontend

The test frontend is located in [`app/static/index.html`](file:///c:/hackathon%20IBM%20x%20Jigyasa/app/static/index.html) and served automatically by FastAPI at `http://127.0.0.1:8000/`.

### Why It Is 100% Replaceable
- **Zero Build Step:** It is a single, self-contained HTML/CSS/JS file using Vanilla modern CSS, Leaflet.js, and browser-native `fetch()`. No Node.js build, bundler, or transpilation is required.
- **Strict API Decoupling:** It interacts exclusively via the official REST endpoints (`/risk-map`, `/route-risk`, `/subscribe`, `/alerts`, `/field-reports`, `/admin/validate-report`, `/history`).
- **CORS-Ready:** `CORSMiddleware` in `app/main.py` is configured with `allow_origins=["*"]`, allowing your friend to run their React/Vite/Next.js frontend on `http://localhost:3000` or `http://localhost:5173` without cross-origin issues.

### How to Replace It When Your Friend's Frontend Is Ready
- **Option 1 (Host Separate Dev Server):**  
  Keep the FastAPI backend running on port `8000`. Have your friend configure their frontend `BASE_URL` to `http://127.0.0.1:8000`.
- **Option 2 (Serve Friend's Build in FastAPI):**  
  Run `npm run build` in their project, copy the `dist` or `build` output into `app/static/`, and FastAPI will automatically serve their new `index.html` at `http://127.0.0.1:8000/`.

---

## 3. Quickstart: Launching the App

### 1. Start the Backend & Test Frontend
From the repository root in PowerShell or terminal:
```powershell
python run.py
```
*(Alternatively: `python -m uvicorn app.main:app --reload --port 8000`)*

Open your browser to:
👉 **`http://127.0.0.1:8000/`** (Interactive Map & Workbench)  
👉 **`http://127.0.0.1:8000/docs`** (Interactive Swagger / OpenAPI UI)

### 2. Run the Automated Test Suite
```powershell
python -m pytest tests/
```
Runs the resilience and API contract tests (`test_risk_resilience.py`).

---

## 4. Feature-by-Feature Testing Guide

The workbench at `http://127.0.0.1:8000/` contains **9 navigation tabs** and an interactive Leaflet map. Below is how to test every single feature:

```
+-----------------------------------------------------------------------------------+
|  [Leaflet Interactive Map]                        | [Workbench Sidebar - 9 Tabs]  |
|  - 18 Color-Coded Segments (Green/Amber/Orange/Red) |  Tab 1: 🗺️ Risk Map         |
|  - Popups with Score, Percentile, Rain & Driver   |  Tab 2: 🚗 Route Planner     |
|  - 309 Mey et al. 2024 Scars Layer Toggle         |  Tab 3: 🚧 Closures          |
|  - Click Map to Pin Field Report Coordinates      |  Tab 4: 🚜 BRO Priority      |
|  - Real-Time Simulation & Historical Overlays     |  Tab 5: 🌧️ Weather Sim       |
|                                                   |  Tab 6: 📢 Field Reports     |
|                                                   |  Tab 7: 🔔 Alerts & SMS      |
|                                                   |  Tab 8: 🛡️ Guardrails Lab    |
|                                                   |  Tab 9: 📦 Offline & Voice   |
|                                                   +-------------------------------+
|                                                   | [Live JSON Console & Latency] |
+-----------------------------------------------------------------------------------+
```

*(For the complete step-by-step browser walkthrough covering all 12 frontend scenarios, see [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md)).*

---

### Feature 1: Corridor Risk Map (`GET /risk-map`)

#### What It Does:
Returns risk assessments for all 18 segments along NH-7 (Rishikesh to Joshimath), combining the 30m DEM terrain percentile with 3-day rainfall.

#### How to Test on UI:
1. Open `http://127.0.0.1:8000/`.
2. Click the **"🗺️ Risk Map"** tab.
3. Click **"⚡ Fetch Live Risk Map"**.
4. The map renders the 18 segments color-coded:
   - 🟢 **Low** ($< 0.35$)
   - 🟡 **Moderate** ($0.35 - 0.65$)
   - 🟠 **High** ($0.65 - 0.85$)
   - 🔴 **Very High** ($\ge 0.85$)
5. Click any segment on the map or choose from the **"Segment Inspector"** dropdown to see:
   - Primary physical driver (e.g., `Steep 30.2° cut slope, high 300m relief (122m)`)
   - Terrain Percentile (e.g., `92nd (Critical)`)
   - 3-day rainfall in mm and status (`ok` or `cached`).
6. Toggle the **"Show 309 Surveyed Scars"** checkbox at the bottom-left of the map to see the Mey et al. (2024) landslide ground-truth scar locations.

#### Test via cURL:
```powershell
curl -X GET "http://127.0.0.1:8000/risk-map" -H "Accept: application/json"
```

#### Test via Python:
```python
import requests
res = requests.get("http://127.0.0.1:8000/risk-map")
data = res.json()
print("Corridor:", data["corridor"])
print("High/Very High Segments:", data["high_or_very_high_risk_count"])
for seg in data["segments"][:3]:
    print(f"- {seg['id']}: {seg['risk_level']} ({seg['risk_score']*100:.1f}%) | Driver: {seg['main_driver']}")
```

---

### Feature 2: Route Risk Evaluation (`GET /route-risk`)

#### What It Does:
Evaluates travel hazard between any two towns on NH-7. Computes route average risk, maximum segment hazard, and context-aware travel advisories.

#### How to Test on UI:
1. Click the **"🚗 Route Planner"** tab.
2. Select **Origin** (e.g., `seg_01: Rishikesh to Shivpuri`) and **Destination** (e.g., `seg_18: Helang to Joshimath`).
3. Set **Travel Date** to today or tomorrow.
4. Click **"🚗 Evaluate Trip Risk"**.
5. The map automatically zooms to frame the selected route, and the summary card displays:
   - Maximum Hazard Segment (e.g., `seg_08: Srinagar to Sirobagarh (Very High)`)
   - Average Risk Score across the journey
   - Specific BRO advisory instructions.
6. **Date-Awareness Test:**
   - Change the Travel Date to **10 days in the future** (e.g., `2026-10-15`).
   - Click **"🚗 Evaluate Trip Risk"**.
   - Notice the yellow advisory alert banner appears:  
     `ℹ️ FORECAST NOTICE for 2026-10-15: Target travel date is beyond the 48-hour rainfall forecast window. Risk scores reflect static terrain susceptibility only (weather impact not factored).`

#### Test via cURL:
```powershell
# Real-time route evaluation
curl -X GET "http://127.0.0.1:8000/route-risk?from_segment=seg_01&to_segment=seg_08&date=2026-10-06"

# Far future date (verifies terrain-only advisory fallback)
curl -X GET "http://127.0.0.1:8000/route-risk?from_segment=seg_01&to_segment=seg_08&date=2026-10-25"
```

---

### Feature 3: Rainfall Simulation Studio (`?simulate_rain_mm=...`)

#### What It Does:
Enables stress-testing the physical hazard curve and the `DRY_CAP_MM = 25.0` safety heuristic without waiting for real monsoon storms.

#### How to Test on UI:
1. Click the **"🌧️ Weather Sim"** tab.
2. Observe the quick presets:
   - **Dry (0 mm):** Risk capped at Moderate by `DRY_CAP_MM = 25.0`.
   - **Below Dry Cap (15 mm):** Demonstrates that dry ground prevents high alert escalation.
   - **Moderate Rain (50 mm):** Activates slope pore-pressure accumulation.
   - **Monsoon Downpour (100 mm):** Triggers widespread "High" warnings.
   - **Cloudburst (150 mm):** Escalates multiple critical segments (Sirobagarh, Tangani, Teen Dhara) to "Very High".
3. Click **"Monsoon Downpour (100 mm)"** -> Notice the map updates in real time, coloring severe segments orange and red!
4. Click **"Reset to Live Weather"** to return to real Open-Meteo readings.

#### Test via cURL:
```powershell
# Simulate 120mm cloudburst across the corridor
curl -X GET "http://127.0.0.1:8000/risk-map?simulate_rain_mm=120"

# Simulate route risk under 0mm dry conditions
curl -X GET "http://127.0.0.1:8000/route-risk?from_segment=seg_01&to_segment=seg_18&simulate_rain_mm=0"
```

---

### Feature 4: Subscriptions & Real-Time Alerts (`POST /subscribe`, `GET /alerts`)

#### What It Does:
Allows drivers, pilgrims, and local residents to subscribe to automatic warnings for specific road sections via SMS, WhatsApp, or Email.

#### How to Test on UI:
1. Click the **"🔔 Alerts"** tab.
2. Fill out the subscription form:
   - **Subscriber Name:** e.g., `Driver Ramesh Kumar`
   - **Phone / Email:** `+91-9876543210`
   - **Monitored Segment:** e.g., `seg_08: Srinagar to Sirobagarh`
   - **Dispatch Channel:** `WhatsApp`
3. Click **"Register Subscription"**.
4. A popup confirms registration and loads your newly assigned numeric `subscription_id` into the query box below.
5. Click **"Fetch Active User Alerts"**:
   - Under dry weather, it informs you that conditions are manageable.
   - Now switch to the **"🌧️ Weather Sim"** tab, click **"Monsoon Downpour (100 mm)"**, and return to click **"Fetch Active User Alerts"**.
   - Notice the high-severity alert card appears with road safety recommendations, channel routing, and rainfall metrics.

#### Test via cURL:
```powershell
# 1. Register subscription
curl -X POST "http://127.0.0.1:8000/subscribe" `
  -H "Content-Type: application/json" `
  -d '{"name":"Patrol Officer Singh","phone_or_email":"+91-9811223344","segment_id":"seg_08","channel":"SMS"}'

# 2. Check alerts for Subscription ID 1 (with simulated downpour)
curl -X GET "http://127.0.0.1:8000/alerts?user_id=1&simulate_rain_mm=80"
```

---

### Feature 5: Crowd-Sourced Field Reports & Admin Validation (`POST /field-report`, `POST /admin/validate-report`)

#### What It Does:
Enables on-the-ground patrol teams or travelers to report active rockfalls, blocked culverts, or fresh debris. Admins can review, validate, or reject incoming reports.

#### How to Test on UI:
1. Click the **"📢 Field Reports"** tab.
2. Click **"📍 Pick Location on Map"**.
3. Click anywhere near NH-7 on the Leaflet map:
   - A red pin drops, and the latitude & longitude auto-fill into the form!
4. Enter description: `Active rockfall blocking left lane near Sirobagarh.`
5. Click **"Submit Incident Report"**.
6. The report appears instantly in the **"Active Field Reports"** list with status `Pending`.
7. **1-Click Admin Validation:**
   - On the newly submitted report card, click the green **"✓ Validate"** button.
   - The status updates immediately to `Validated` via `POST /admin/validate-report`!
   - Or click **"✗ Reject"** to dismiss false alarms.

#### Test via cURL:
```powershell
# 1. Submit field report
curl -X POST "http://127.0.0.1:8000/field-report" `
  -H "Content-Type: application/json" `
  -d '{"lat":30.2390,"lng":78.8540,"description":"Fresh rockfall blocking both lanes.","reporter_name":"BRO Highway Unit 3"}'

# 2. Admin validates report #1
curl -X POST "http://127.0.0.1:8000/admin/validate-report" `
  -H "Content-Type: application/json" `
  -d '{"report_id":1,"decision":"Validated","notes":"Verified by patrol squad on site."}'

# 3. List all field reports
curl -X GET "http://127.0.0.1:8000/field-reports"
```

---

### Feature 6: Ground-Truth Landslide Inventory (`GET /history`)

#### What It Does:
Supplies historical landslide events from the Mey et al. (2024) inventory and historical records along NH-7.

#### How to Test:
```powershell
curl -X GET "http://127.0.0.1:8000/history"
```
Or check the **"Show 309 Surveyed Scars"** checkbox on the testbench map to render the points directly along the highway corridor.

---

### Feature 7: System Health & Audit Logging (`GET /health`)

#### What It Does:
Provides sub-second container health probes and audits incoming requests with latency timestamps.

#### How to Test:
```powershell
curl -X GET "http://127.0.0.1:8000/health"
```
Response:
```json
{
  "status": "ok",
  "system": "NH-7 Landslide Risk Backend",
  "corridor": "Rishikesh-Joshimath"
}
```

---

## 5. Offline Resilience & Sub-Second Fallback Verification

A major engineering requirement is that **the backend must never hang or crash if the Open-Meteo external weather API fails**.

### How Resilience Is Implemented (`app/risk_service.py`)
1. **4-Second Timeout:** The HTTP call to Open-Meteo will never block longer than 4.0 seconds.
2. **5-Minute Memory Failure Cache:** Once a fetch fails, subsequent calls immediately skip external network requests for 300 seconds, responding instantly.
3. **Local Disk Snapshot Fallback:** When live calls fail, the backend reads the last successful weather state from `data/rain_snapshot.json` and marks `rain_status: "cached"`.
4. **Sub-Second Guaranteed Response:** If neither live nor snapshot is available, it gracefully returns terrain-only susceptibility scores with `rain_status: "unavailable"`.

### How to Verify Resilience:
Run the automated resilience test suite:
```powershell
python -m pytest tests/test_risk_resilience.py -v
```
This tests:
- `test_dry_cap_heuristic`: Confirms scores are capped at "Moderate" when $R_{\text{3d}} < 25\text{ mm}$.
- `test_rain_failure_fallback_speed`: Simulates complete weather API failure and verifies `/risk-map` responds in **under 1.0 second** (typically ~40 ms).
- `test_future_date_route_risk_terrain_only`: Verifies dates past tomorrow trigger terrain-only mode with travel advisory warnings.

---

## 6. Scientific Validation & Model Performance Summary

The underlying predictive model is scientifically audited in [`outputs/validation_report.md`](file:///c:/hackathon%20IBM%20x%20Jigyasa/outputs/validation_report.md):

| Metric | Result | Interpretation |
| :--- | :--- | :--- |
| **Corridor Scored Length** | **247.37 km** | Matches the true Rishikesh-Joshimath alignment |
| **Point Density** | **4.00 points / km** | Exactly 1 evaluation point per 250m road segment |
| **Spearman Correlation ($\rho$)** | **0.653 ($p = 0.0033$)** | Out-of-fold terrain risk strongly correlates with observed slides |
| **Cross-Validated ROC-AUC** | **0.767** [95% CI: 0.680 - 0.802] | Statistically significant discrimination on held-out spatial blocks |
| **Key Physical Generalizer** | **Slope ($\Delta\text{AUC} = +0.0523$)** | Steep cut-slopes are the primary predictive factor of failures |
| **Sirobagarh Discrepancy** | **Rank #7 Model vs. Rank #17 Survey** | Mey 2022 survey mapped 1 large scar; model correctly identifies high risk |
| **Driver String Audit** | **18 / 18 (100%)** | Mathematical formulas generated directly by `score_segments.py` |

---

## 7. Summary Checklist for Your Frontend Teammate

When your partner is ready to integrate their custom frontend, they only need these endpoints:

1. **`GET /risk-map`** -> Highway segments with polyline points, risk scores, levels, and drivers.
2. **`GET /route-risk?from_segment=...&to_segment=...&date=...`** -> Journey hazard summary & advisory.
3. **`POST /subscribe`** -> Register notifications.
4. **`GET /alerts?user_id=...`** -> Fetch active subscriber alerts.
5. **`POST /field-report`** & **`GET /field-reports`** -> Crowd-sourced hazard reporting.
6. **`POST /admin/validate-report`** -> Verification workflow.
7. **`GET /history`** -> Historical landslide scar coordinates.
8. Optional query parameter: **`?simulate_rain_mm=...`** on `/risk-map`, `/route-risk`, and `/alerts` for interactive live demonstrations.
