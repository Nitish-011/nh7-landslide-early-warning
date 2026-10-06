# ⛰️ NH-7 Landslide Early Warning & Resilient Routing Network

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/PyTest-119%20Passed%20(100%25)-success.svg)](https://pytest.org/)
[![GIS](https://img.shields.io/badge/DEM-Copernicus%2030m-green.svg)](https://spacedata.copernicus.eu/)
[![PWA](https://img.shields.io/badge/PWA-Offline%20Ready-orange.svg)](https://web.dev/progressive-web-apps/)
[![Hackathon](https://img.shields.io/badge/Hackathon-IBM%20x%20Jigyasa-purple.svg)]()

> **The Highway:** National Highway 7 (Rishikesh to Joshimath, Uttarakhand, India — 247.37 km, 18 segments)  
> **The Problem:** The lifeline pilgrimage corridor for Char Dham (Badrinath, Hemkund Sahib) is crippled every monsoon by landslides and cloudbursts.  
> **Our Mission:** Deliver an AI-powered early warning network that combines satellite terrain physics with live multi-station rainfall forecasts, civil infrastructure vulnerability, two-way SMS, vernacular Hindi voice alerts, and offline survival packs.

---

## 🚀 Quickstart for Friends (Up and Running in 60 Seconds)

You don't need complicated setups or cloud accounts. Everything runs locally on your machine with a single command!

### Step 1: Clone the Repository & Enter Folder
```bash
git clone https://github.com/Nitish-011/nh7-landslide-early-warning.git
cd nh7-landslide-early-warning
```

### Step 2: Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Run the Server
```bash
python run.py
```

Now open your browser and visit:
👉 **[http://localhost:8000](http://localhost:8000)**

*The launcher automatically displays your local LAN IP (e.g. `http://192.168.1.15:8000`) so you can open it on your phone on the same Wi-Fi!*

---

## 🎮 Friend's Tour: 5 Coolest Things You MUST Try in the Web UI!

When you open **[http://localhost:8000](http://localhost:8000)**, you'll see our **Interactive 9-Tab Command Workbench**. Here is the ultimate 5-minute showcase tour:

```
+---------------------------------------------------------------------------------------------------+
|  1. 🌧️ TAB 5: TRIGGER A MONSOON CLOUDBURST                                                        |
|     Click the "Weather Sim" tab. Drag the rainfall slider from 0 mm to 150 mm (or hit the         |
|     "Cloudburst 140mm" button). Watch the highway polylines on the map instantly explode from     |
|     Green (Low) to Fiery Red and Purple (Severe)!                                                |
+---------------------------------------------------------------------------------------------------+
|  2. 🔊 TAB 9: HEAR HINDI NEURAL VOICE WARNINGS                                                    |
|     Go to "Offline & Voice" tab, or toggle the language switcher at the top right (EN ➔ HI).       |
|     Click "Play Localized Voice Audio". The server generates real-time audio speech alerts in      |
|     natural Hindi via gTTS with sub-10ms cached streaming!                                        |
+---------------------------------------------------------------------------------------------------+
|  3. 🚗 TAB 2: SMART TRIP SAFE PLANNER                                                             |
|     Click "Route Planner". Set your departure from Rishikesh to Badrinath. Hit "Analyze Route".   |
|     The engine checks progressive arrival ETAs for every mountain sector and recommends whether   |
|     to GO, exercise CAUTION, or AVOID due to upcoming storm peaks!                                 |
+---------------------------------------------------------------------------------------------------+
|  4. 📱 TAB 7: TRY THE IN-BROWSER SMS SIMULATOR                                                    |
|     Go to "Alerts & SMS". In the interactive Twilio SMS Simulator widget, type "NH7 HELP" or      |
|     "NH7 SEG08" and click "Send Simulated SMS". You'll see real-time TwiML XML mobile responses  |
|     formatting critical road advisories for drivers without smartphones!                          |
+---------------------------------------------------------------------------------------------------+
|  5. ⚡ TAB 9: CUT THE INTERNET (TEST OFFLINE PWA)                                                 |
|     Open your browser's Developer Tools (F12) ➔ Network tab ➔ Switch throttling to "Offline".     |
|     Refresh the page! Thanks to our Service Worker (`sw.js`) and `<17 KB` Offline Survival Pack,  |
|     the dashboard and highway map keep working seamlessly in mountain dead zones!                 |
+---------------------------------------------------------------------------------------------------+
```

---

## 🏗️ System Architecture

Our backend is built around a hybrid physical-statistical model: **Static Topographic Physics** combined with **100% Dynamic Real-Time Weather and Operational Incident States**.

```
                           +-------------------------------------------------+
                           |           SATELLITE & INVENTORY DATA             |
                           |  - Copernicus 30m DEM (Slope, Relief, TPI)       |
                           |  - Mey et al. (2024) 309 Historical Slide Scars  |
                           +------------------------+------------------------+
                                                    |
                                                    v
+-----------------------+  Hourly Rainfall  +---------------------------------+
|   Open-Meteo API      | ----------------> |     DYNAMIC HAZARD ENGINE       |
| 5 Virtual Stations on |                   |  P_hazard = P_terrain * (1-e^-kR)
| NH-7 (5-min circuit)  |                   |  Dry cap (25mm) + Storm Sim     |
+-----------------------+                   +---------------+-----------------+
                                                            |
              +---------------------------------------------+------------------------------------+
              |                                             |                                    |
              v                                             v                                    v
+---------------------------+                 +---------------------------+        +---------------------------+
|    TRIP SAFE PLANNER      |                 |    BRO ASSET PRIORITY     |        |   ROAD CLOSURES & DETOURS |
| Route waypoint ETAs &     |                 | Hazard x Bridge / Hospital|        | Active blockages, bypass  |
| safe departure windows    |                 | Consequence Pre-staging   |        | routing & crowd reports   |
+-------------+-------------+                 +-------------+-------------+        +-------------+-------------+
              |                                             |                                    |
              +---------------------------------------------+------------------------------------+
                                                            |
                                                            v
                                            +-------------------------------+
                                            |   MULTI-CHANNEL DISPATCHER    |
                                            | - Twilio SMS Webhook (TwiML)  |
                                            | - Telegram Bot Worker         |
                                            | - gTTS Voice Stream (Hindi/En)|
                                            | - PWA Offline Pack (< 17 KB)  |
                                            +-------------------------------+
```

---

## 🗂️ What's in the Workspace?

Here is a clean directory guide so you can find anything instantly:

```
nh7-landslide-early-warning/
├── app/                        # FastAPI application core
│   ├── main.py                 # Application startup, routing, and PWA static mount
│   ├── config.py               # Central configuration and environment settings
│   ├── models.py               # Pydantic schemas and contracts
│   ├── database.py             # SQLite database connection & table setup
│   ├── risk_service.py         # Real-time hazard computation & weather assimilation
│   ├── trip_planner.py         # Time-aware route planning & ETA calculators
│   ├── consequence_service.py   # Civil infrastructure vulnerability & BRO priority
│   ├── flywheel_service.py     # Ground-truth crowd report validation & model triggers
│   ├── alert_dispatcher.py     # Periodic 10-minute alert evaluation worker
│   ├── i18n.py                 # Bilingual translation layer (English & Hindi)
│   ├── limiter.py              # SlowAPI DDoS rate limiter
│   ├── middleware.py           # Request logging, correlation ID, timing headers
│   ├── routes/                 # Modular endpoint controllers
│   │   ├── risk.py             # /risk-map, /route-risk, /trip-planner, /consequence
│   │   ├── closures.py         # /closures, /closures/active, /admin/closure
│   │   ├── reports.py          # /field-report, /admin/validate-report
│   │   ├── subscriptions.py    # /subscribe, /alerts, /voice-alert
│   │   ├── history.py          # /history, /backtest
│   │   └── webhooks.py         # /webhook/sms (Twilio), /webhook/telegram
│   ├── notifiers/              # Messaging drivers (Twilio, Telegram, Console)
│   └── static/                 # Frontend UI (index.html, sw.js, manifest.json)
├── data/                       # Persistent data, caches, and geomorphic records
│   ├── landslide_nh7.db        # SQLite database (auto-seeded on first run)
│   ├── rain_snapshot.json      # Offline fallback rainfall cache
│   ├── segment_consequence.csv # Civil asset criticality & hospital proximities
│   ├── backtest_events.csv     # Historical monsoon ground-truth disaster events
│   └── tts_cache/              # Cached synthesized MP3 audio alerts
├── geojson/                    # Spatial corridor geometry
│   └── nh7_route.geojson       # Complete 247.37 km NH-7 highway polyline
├── model/                      # Data science models, training code & research assets
│   ├── nh7_static_model_v2.joblib # Trained Random Forest + XGBoost ensemble
│   ├── build_static_dataset.py # DEM feature extraction & geomorphic preprocessing
│   └── dem_cache/              # Copernicus 30m Digital Elevation Model TIF
├── scripts/                    # Command-line audit, backtest & utility tools
│   ├── backtest.py             # Replay historical storm events & compute metrics
│   ├── validation_audit.py     # Comprehensive 6-fold spatial CV audit runner
│   ├── smoke.py                # Fast endpoint health and contract verification
│   └── demo_check.py           # Pre-flight check script before live presentations
├── tests/                      # Automated test suite (119 test cases)
│   ├── contract/               # Golden schema regression tests
│   └── test_*.py               # Functional, security, freshness, and route tests
├── FEATURES.md                 # Complete feature accounting catalog
├── MODEL_PERFORMANCE.md        # Technical model performance report & metrics
├── FRONTEND_TESTING_GUIDE.md   # Step-by-step browser testing walkthrough
├── reset_db.py                 # One-click database wipe & re-seed utility
├── run.py                      # Production/Dev server launcher
└── requirements.txt            # Python dependencies
```

---

## 📡 API Endpoints Cheat Sheet

Here are the most important endpoints you can try right now via `curl` or in your browser:

| Method | Endpoint | Description | Example Query |
|---|---|---|---|
| `GET` | `/health` | Server health, database status, and uptime | `curl http://localhost:8000/health` |
| `GET` | `/risk-map` | Real-time risk for all 18 NH-7 segments | `curl http://localhost:8000/risk-map` |
| `GET` | `/risk-map?simulate_rain_mm=120` | Stress-test with simulated 120mm cloudburst | Test via browser or curl |
| `GET` | `/risk-map?as_of=2023-08-14` | Replay Chamoli disaster historical weather | Replay past monsoon event |
| `POST` | `/trip-planner` | Safe departure advisory with waypoint ETAs | Pass JSON with origin & destination |
| `GET` | `/consequence` | BRO infrastructure consequence & priority | `curl http://localhost:8000/consequence` |
| `GET` | `/closures` | Active road closures & bypass advisories | `curl http://localhost:8000/closures` |
| `POST` | `/field-report` | Crowd-sourced hazard report (3km geofence) | Submit road condition report |
| `GET` | `/voice-alert?lang=hi` | Stream bilingual neural audio alert (MP3) | Open in browser to listen |
| `GET` | `/offline-pack` | Lightweight JSON (<17 KB) with ETag/304 | `curl -i http://localhost:8000/offline-pack` |
| `POST` | `/webhook/sms` | Twilio SMS inbound query webhook (TwiML) | Test SMS commands (`NH7 HELP`) |

*Full interactive documentation and testing sandbox available at [http://localhost:8000/docs](http://localhost:8000/docs).*

---

## 🤖 Model Performance Snapshot

- **Trained On:** 309 field-mapped road-blocking landslide scars along NH-7 from published research (*Mey et al., 2024, Natural Hazards and Earth System Sciences*).
- **Spatial Resolution:** 30-meter Copernicus DEM features (Slope, Local Relief 300m, Curvature, TPI, Proximity to Drainage).
- **Pooled Out-of-Fold ROC-AUC:** **0.767** (Random Forest on Copernicus 30m DEM, 95% CI: `[0.680, 0.802]`).
- **Spatial Block Mean AUC:** **0.664** (across 6 spatial blocks with 2.0 km exclusion buffer).
- **Average Precision (PR-AUC):** **0.533**, **Top-20% Highway Capture Rate:** **43.0%**.
- **Spearman Rank Correlation:** **0.653** ($p = 0.0033$), verifying strong statistical concordance with ground-truth landslide frequency.
- **Inference Latency:** `< 12 ms` to evaluate the entire 247 km highway corridor.

👉 *For the complete model card, confusion matrices, and backtest results, check [MODEL_PERFORMANCE.md](file:///c:/hackathon%20IBM%20x%20Jigyasa/MODEL_PERFORMANCE.md).*

---

## 🧪 Running the Automated Tests

Our test suite guarantees that no regressions occur across API contracts, guardrails, or physics calculations:

```bash
# Run all 119 automated tests
python -m pytest
```

Output:
```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.0.3
collected 119 items

tests/contract/test_contract.py ..................                       [ 15%]
tests/contract/test_golden_schema.py .........                           [ 22%]
tests/test_alert_delivery_task6.py ......                                [ 27%]
tests/test_backtest_task2.py ......                                      [ 32%]
tests/test_closures_and_flywheel_task5.py .......                        [ 38%]
tests/test_consequence_task4.py ......                                   [ 43%]
tests/test_freshness_f2.py .......                                       [ 49%]
tests/test_localization_and_voice_task7.py .......                       [ 55%]
tests/test_model_info_f3.py ........                                     [ 62%]
tests/test_offline_pack_task8.py .......                                 [ 68%]
tests/test_production_f5.py ......                                       [ 73%]
tests/test_risk_resilience.py ...                                        [ 75%]
tests/test_security_f1.py .............                                  [ 86%]
tests/test_trip_planner_task3.py ....                                    [ 89%]
tests/test_validation_audit_f4.py ......                                 [ 94%]
tests/test_weather_upgrade_task1.py ......                               [100%]

====================== 119 passed in 17.50s ======================
```

---

## 🛠️ Environment Variables Configuration

The system works out-of-the-box with default values. To configure production integrations (SMS, Telegram, Admin Keys), create a `.env` file or export environment variables:

```bash
# Environment Mode: 'development' or 'production'
ENV=development

# Admin Secret Key (used for closure updates & report validations)
ADMIN_API_KEY=admin-dev-secret-key-nh7

# Twilio SMS Credentials (Optional for live SMS delivery)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Telegram Bot Credentials (Optional for live bot polling)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Background Scheduler Interval (seconds)
ALERT_CHECK_INTERVAL=600
```

---

## 📖 Additional Documentation Guides

- [ANTIGRAVITY_BACKEND_CONTEXT.md](file:///c:/hackathon%20IBM%20x%20Jigyasa/ANTIGRAVITY_BACKEND_CONTEXT.md) — 🧠 Comprehensive AI Agent specification with every route, request schema, and response payload.
- [AGENTS.md](file:///c:/hackathon%20IBM%20x%20Jigyasa/AGENTS.md) — Antigravity IDE & CLI agent instructions and engineering guidelines.
- [FEATURES.md](file:///c:/hackathon%20IBM%20x%20Jigyasa/FEATURES.md) — Exhaustive accounting of all 12 feature domains and database schemas.
- [MODEL_PERFORMANCE.md](file:///c:/hackathon%20IBM%20x%20Jigyasa/MODEL_PERFORMANCE.md) — In-depth data science report, spatial CV benchmarks, and model card.
- [FRONTEND_TESTING_GUIDE.md](file:///c:/hackathon%20IBM%20x%20Jigyasa/FRONTEND_TESTING_GUIDE.md) — Step-by-step browser walkthrough to test every button and tab from the UI.
- [CHANGELOG.md](file:///c:/hackathon%20IBM%20x%20Jigyasa/CHANGELOG.md) — Chronological integration history across all hackathon tasks.

---

## 🏆 Acknowledgements & Data Attribution

- **Geological Research:** Mey, J., et al. (2024). *Landslides triggered by the 2022 monsoon along National Highway 7, Uttarakhand, India*. Natural Hazards and Earth System Sciences (NHESS).
- **Elevation Data:** European Space Agency (ESA) Copernicus 30m Digital Elevation Model.
- **Meteorological Data:** Open-Meteo Weather API & ECMWF ERA5-Land Reanalysis.
- **Highway Alignment:** OpenStreetMap (OSM) Contributors & National Highways Authority of India (NHAI).
- **Built for:** IBM x Jigyasa Hackathon 2026.
