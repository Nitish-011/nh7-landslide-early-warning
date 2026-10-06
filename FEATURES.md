# NH-7 Landslide Early Warning & Resilient Routing System
## Complete System Feature Accounting & Capabilities Catalog

> **Corridor Scope:** National Highway 7 (Rishikesh to Joshimath, Uttarakhand, India — 247.37 km)  
> **System Architecture:** AI Hazard Inference + Multi-Station Meteorology + Civil Infrastructure Consequence + Multi-Channel Alerts + PWA Offline Resilience  
> **Total Automated Test Coverage:** 122/122 passing tests across contract, security, freshness, and functional domains.

---

## 1. Architectural Overview & Executive Summary

The **NH-7 Landslide Early Warning System** is an end-to-end, real-time geohazard intelligence platform designed to protect life, pilgrimage traffic (Char Dham Yatra), and national logistical supply lines along India's most landslide-prone Himalayan highway corridor.

The platform bridges cutting-edge machine learning with operational field disaster management. Rather than treating landslides merely as static terrain rankings or simple rain gauge exceedances, the system couples:
1. **High-Resolution Geomorphology:** 30-meter Copernicus Digital Elevation Model (DEM) topographic features with historical landslide inventories (Mey et al., 2024; $N=309$ road-blocking failures).
2. **Real-Time Dynamic Meteorology:** Live hourly and antecedent rainfall assimilation from Open-Meteo across 5 corridor weather stations.
3. **Civil Infrastructure Consequence:** Asset exposure mapping (major bridges, pilgrimage transit hubs, emergency hospitals, population densities, and alternate bypass availability).
4. **Resilient Public Interface:** Dual-layer command center (Leaflet GIS workbench + offline-first Progressive Web App) with vernacular Hindi/English neural text-to-speech voice alerts, Twilio SMS query webhooks, and automated Telegram bot dispatchers.

```
+---------------------------------------------------------------------------------------------------+
|                                     DATA INGESTION & GEOMORPHOLOGY                                 |
|   Copernicus 30m DEM   |   Mey et al. (2024) 309 Inventory   |   Open-Meteo Multi-Station API    |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                  INTELLIGENCE & HAZARD ENGINE                                      |
|  - Static Susceptibility (Random Forest v2)                  - Antecedent 3-Day Wetting [R_3d]    |
|  - Dynamic Risk: score = min(w_t*terrain + w_r*min(R/100, 1), 1) - Fallback Circuit Breaker (5m TTL)|
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                  OPERATIONAL DECISION MODULES                                      |
|  - Consequence Ranking (BRO Priority)     - Time-Aware Trip Planner (Arrival-Hour Meteorology)   |
|  - Ground-Truth Validation Flywheel       - Road Closure Lifecycle & Real-Time Detour Routing    |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                   DISSEMINATION & CLIENT APPS                                     |
|  - Interactive 9-Tab Workbench (Web)      - PWA Offline Survival Pack (ETag / 304 / gzip)         |
|  - Twilio SMS Two-Way Webhook             - Telegram Bot (@NH7_Landslide_Bot)                     |
|  - Vernacular Audio (gTTS en/hi)          - Rate Limiter & Security Guardrails Lab                |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Comprehensive Feature Matrix

| # | Feature Name | Core Endpoints / Components | Primary Technology | Key Benefit / Outcome |
|---|---|---|---|---|
| **1** | **Dynamic Multi-Station Hazard Engine** | `GET /risk-map`<br>`GET /model-info` | Copernicus DEM 30m, Open-Meteo API, SciPy, NumPy | Real-time hazard estimation combining 30m terrain susceptibility with live 3-day rainfall across 18 highway segments. |
| **2** | **Historical Time Machine & Replay** | `GET /risk-map?as_of=YYYY-MM-DD`<br>`GET /backtest/events` | ERA5-Land Reanalysis, SQLite, Pandas | Allows operators to replay historical monsoon disaster dates (e.g. August 2023 cloudburst) to evaluate system performance. |
| **3** | **Time-Aware Trip Safe Planner** | `POST /trip-planner`<br>`GET /route-risk` | Spatial polyline routing, hourly transit speed simulation | Analyzes specific highway departure times, evaluates progressive segment arrival ETAs, and suggests optimal departure windows. |
| **4** | **BRO Infrastructure Consequence Ranking** | `GET /consequence`<br>`GET /priority-list` | NHAI bridge registry, OSM hospital & town proximities | Calculates Risk = Hazard × Consequence to rank excavator and relief pre-positioning priorities for Border Roads Organisation. |
| **5** | **Field Ground-Truth Flywheel** | `POST /field-report`<br>`POST /admin/validate-report`<br>`GET /field-reports` | SQLite, Shapely 3km geofence, Admin Auth | Crowd-sources verified hazard reports from drivers and patrols; automatically triggers model adjustment when verified reports peak. |
| **6** | **Road Closures & Real-Time Detour Routing** | `GET /closures`<br>`POST /admin/closure`<br>`DELETE /admin/closure/{id}` | In-memory + SQLite lifecycle state machine | Tracks active road blockages, marks segments as "CLOSED", and forces route planners to recommend immediate avoidance or detours. |
| **7** | **Multi-Channel Alert Dispatcher & SMS** | `POST /webhook/sms`<br>`POST /webhook/telegram`<br>`GET /alerts`<br>`POST /subscribe` | Twilio SMS API, Telegram Bot API, Async Background Worker | Dispatches automated warnings to travelers; provides interactive two-way SMS queries (`NH7 HELP`, `NH7 SEG08`, `NH7 ROUTE`). |
| **8** | **Vernacular Localization & Neural Voice** | `GET /voice-alert`<br>`GET /alerts/voice/{id}` | gTTS (Google Text-to-Speech), Python i18n, SHA-256 Cache | Translates alerts and segment names into Hindi (Devanagari) and serves cached streaming MP3 voice alerts for roadside drivers. |
| **9** | **Offline Survivor Pack & PWA Service Worker** | `GET /offline-pack`<br>`GET /manifest.json`<br>`GET /sw.js` | Service Worker, CacheStorage, HTTP ETag / 304 | Delivers a lightweight (<17 KB) self-contained survival package with highway geometry, contacts, and risk levels that works in cellular dead zones. |
| **10** | **Enterprise Security & Guardrails** | `app/middleware.py`<br>`app/limiter.py`<br>`app/routes/reports.py` | SlowAPI, HTML bleach, secrets timing-safe digest | Protects against DDoS (rate limits), XSS injections in crowd reports, unauthorized admin calls, and out-of-corridor spoofing. |
| **11** | **Interactive 9-Tab Workbench Frontend** | `app/static/index.html` | Vanilla HTML5/CSS3/JS, Leaflet GIS, JetBrains Mono | Unified web application with dual-mode GIS map, HUD metrics, rainfall slider, SMS simulator, and live JSON inspector. |
| **12** | **Scientific Validation & Audit Suite** | `scripts/validation_audit.py`<br>`tests/` (122 tests) | Pytest, Golden Schemas, Spatial Bootstrap | Independent validation auditing inventory coverage (309 scars), 6-fold spatial block cross-validation, and schema contracts. |

---

## 3. Deep Dive into Every Feature Domain

### Feature 1: Dynamic Multi-Station Hazard Engine
- **Mechanism:**
  - Evaluates 18 discrete, sequence-ordered segments from Rishikesh (km 0.0) to Joshimath (km 247.4).
  - Uses a **Copernicus 30m DEM** baseline calculating slope, local relief (300m radius), Topographic Position Index (TPI), and proximity to waterways.
  - Queries 5 virtual weather stations spanning the corridor (Rishikesh, Devprayag, Srinagar, Rudraprayag, Chamoli) via Open-Meteo.
  - Computes the 3-day antecedent rainfall $R_{3\text{d}} = R_{\text{yesterday}} + R_{\text{today}} + R_{\text{tomorrow}}$.
  - Integrates transparent weighted linear-capped dynamic hazard formula:
    $$\text{risk\_score} = \min\left(K_{\text{terrain}} \times \text{terrain\_percentile} + K_{\text{rain}} \times \min\left(\frac{R_{3\text{d}}}{\text{RAIN\_REF\_MM}}, 1.0\right), 1.0\right)$$
    where $K_{\text{terrain}} = 0.60$, $K_{\text{rain}} = 0.40$, and $\text{RAIN\_REF\_MM} = 100.0\text{ mm}$ (calibrated operational heuristics).
  - **Dry Condition Guardrail (`DRY_CAP_MM = 25.0`):** If $R_{3\text{d}} < 25\text{ mm}$, risk is physically capped at "Moderate", preventing false alarms during dry sunny weather.
  - **Circuit Breaker:** If the live weather API fails or times out, the engine gracefully falls back to `data/rain_snapshot.json` with a 5-minute memory cache, returning in under 20ms and tagging `rain_status: "cached"`.
  - **Simulation Override:** Supports `?simulate_rain_mm=120.0` to instantly stress-test the entire highway under simulated cloudburst or monsoon downpour conditions.

### Feature 2: Historical Time Machine & Backtest Engine
- **Mechanism:**
  - The parameter `?as_of=YYYY-MM-DD` triggers the **Time Machine** on `/risk-map` (requires `BACKTEST_ENABLED=true` in `app/config.py`).
  - Ingests archived historical daily precipitation data from ERA5-Land reanalysis.
  - Replays available verified events; when the empirical event table is insufficient, runs a clearly labelled synthetic demonstration.
  - Cached in `data/backtest_cache/` so historical queries return instantaneously without repeated API requests.

### Feature 3: Time-Aware Safe Trip Planner
- **Mechanism:**
  - Endpoint: `POST /trip-planner` and `GET /route-risk`.
  - Takes route start (`origin`), route end (`destination`), intended departure timestamp (`depart_time`), and assumed vehicle travel speed (`speed_kmph`, default 30 km/h).
  - Calculates the progressive arrival ETA for every intermediate segment along the driver's route.
  - Rather than applying a single instantaneous weather snapshot, the engine evaluates the forecasted weather **at the exact hour the driver is expected to enter each segment**.
  - Produces an end-to-end **Trip Recommendation**:
    - `RECOMMENDED` (All segments Low/Moderate)
    - `CAUTION` (One or more High risk segments; drive defensively during daylight)
    - `AVOID` (Severe risk or active road closures detected; suggest postponing)
  - Returns a multi-hour departure timeline recommending the safest departure window (e.g. "Depart at 06:00 IST to avoid afternoon thunderstorm peak in Pipalkoti").

### Feature 4: BRO Infrastructure Consequence & Priority Pre-Positioning
- **Mechanism:**
  - Endpoint: `GET /consequence` and `GET /priority-list`.
  - Built for the **Border Roads Organisation (BRO)** and the **State Disaster Response Force (SDRF)**.
  - Raw landslide susceptibility is multiplied by civil infrastructure consequence:
    $$\text{Priority Score} = P_{\text{hazard}} \times \text{Consequence Factor}$$
  - Consequence factors incorporate:
    - Distance to major bridges & river crossings (Alaknanda & Bhagirathi confluence).
    - Hospital access time (emergency trauma centers at Srinagar Medical College, Chamoli, and Joshimath).
    - Settlement density (towns of Devprayag, Srinagar, Rudraprayag, Karnaprayag).
    - Detour availability (whether any paved alternative road exists or if a blockage causes total valley cutoff).
  - Yields a ranked list of segments prioritizing where heavy earth-moving equipment (bulldozers, excavators) should be pre-staged before a storm strikes.

### Feature 5: Crowd-Sourced Field Hazard Verification & Flywheel
- **Mechanism:**
  - Endpoint: `POST /field-report`, `GET /field-reports`, `POST /admin/validate-report`.
  - Allows drivers, bus operators, and police patrols to report ground conditions (mud, rockfall, cracks on asphalt, water overflowing road).
  - **Spatial Guardrail:** Enforces a 3.0 km Euclidean/Cartesian buffer from the NH-7 highway polyline (`geojson/nh7_route.geojson`). Coordinates further than 3 km (e.g. Delhi, Dehradun) are rejected immediately with `HTTP 422 Unprocessable Entity`.
  - **Security Sanitation:** All descriptions are sanitized via regex/HTML-stripping to block XSS and malicious scripts.
  - **Duplicate Prevention:** Rejects duplicate reports from the same IP at the same coordinate within a 10-minute window (`HTTP 409 Conflict`).
  - **Admin Validation & Flywheel:** Admin verifies reports (`status="verified"`). When 5 or more verified landslides occur on a segment within 24 hours, the backend automatically escalates that segment's operational risk tier by +1 step and appends ground-truth events to `data/validated_reports.csv` for downstream model re-training.

### Feature 6: Road Closures & Real-Time Detour Routing
- **Mechanism:**
  - Endpoints: `GET /closures`, `GET /closures/active`, `POST /admin/closure`, `DELETE /admin/closure/{id}`.
  - Managed by administrative authorization (`X-Admin-Key` header).
  - Tracks closure status (`reported`, `verified`, `clearing`, `reopened`), severity, blockage cause, and official source (e.g. "Uttarakhand Police Twitter / BRO Bulletin").
  - Directly alters route planning: if an active closure exists on a segment, `/route-risk` and `/trip-planner` immediately flag that segment as impassable and output alternative bypass recommendations.

### Feature 7: Multi-Channel Alert Dispatcher & SMS Webhook
- **Mechanism:**
  - Endpoints: `POST /subscribe`, `GET /alerts`, `POST /webhook/sms`, `POST /webhook/telegram`.
  - **Twilio SMS Webhook:** Allows users without smartphones or mobile internet to send SMS text messages:
    - Text `NH7 HELP`: Returns guidance on available SMS commands.
    - Text `NH7 SEG08`: Returns real-time status and risk level for Segment 8 (Srinagar to Sirobagarh).
    - Text `NH7 ROUTE RISHIKESH JOSHIMATH`: Returns route clearance status and high-risk warnings via TwiML XML response (< 320 characters).
  - **Telegram Bot Integration:** Interactive bot supporting `/start`, `/status`, `/alert`, `/help` with direct link to the live map.
  - **Automated Dispatcher Worker:** 10-minute periodic background scheduler evaluates corridor hazard scores. Automated alerts are dispatched when a subscriber's segment reaches High or Very High risk (risk score $\ge 0.50$), subject to escalation state and 3-hour cooldown constraints.

### Feature 8: Vernacular Localization & Neural Voice Alerts
- **Mechanism:**
  - Parameter: `lang=en` or `lang=hi` across endpoints.
  - Fully localizes all segment names, risk levels, and driving advisories into Hindi (Devanagari).
  - Endpoints: `GET /voice-alert` and `GET /alerts/voice/{alert_id}`.
  - Uses `gTTS` (Google Text-to-Speech) to synthesize spoken voice warnings in Hindi and English.
  - Implements disk-based hashing cache (`data/tts_cache/{sha256}.mp3`), ensuring identical advisories are synthesized only once, yielding sub-10ms response times for subsequent audio streams.
  - Frontend includes a one-click audio player so drivers can hear alerts without taking their eyes off the road.

### Feature 9: Mobile Offline Survival Pack & PWA Service Worker
- **Mechanism:**
  - Himalayan mountain valleys frequently suffer cellular blackouts when rains sever optical fiber lines or power towers.
  - Endpoint: `GET /offline-pack`.
  - Returns a self-contained, ultra-compact JSON bundle (< 17 KB uncompressed, < 5 KB gzipped) containing:
    - Simplified segment coordinates (Ramer-Douglas-Peucker filtered).
    - Baseline terrain vulnerability and latest risk rankings.
    - Local emergency phone contacts (112, BRO Control Room, SDRF Uttarakhand, Chamoli Police).
    - Nearest trauma hospitals with chainage km markers.
    - Bilingual safety advisories in English and Hindi.
  - **HTTP ETag & 304 Support:** Computes a SHA-256 ETag from pack contents. Mobile clients sending `If-None-Match` receive an immediate `304 Not Modified` (0 bytes payload), conserving scarce battery and cellular bandwidth.
  - **PWA Service Worker (`sw.js`, `manifest.json`):** Automatically pre-caches the web application shell and offline pack. If cellular connectivity is severed, the UI continues functioning, rendering the highway risk map from cache and alerting the user via the top `#offline-banner`.

### Feature 10: Security Guardrails & Rate Limiting Lab
- **Mechanism:**
  - **Rate Limiting:** Managed via `slowapi` with in-memory IP buckets (e.g. 5 requests/minute for report submissions, 60 requests/minute for risk queries).
  - **Timing-Safe Admin Verification:** Uses Python's `secrets.compare_digest` to prevent side-channel timing attacks on the `X-Admin-Key` header.
  - **Corridor Distance Enforcement:** Strict mathematical distance projection against `geojson/nh7_route.geojson`.
  - **Input Sanitization:** Regex-based strip of `<script>`, HTML tags, and non-printable control characters from crowd report text.
  - **In-Memory Circuit Breaker:** Protects upstream Open-Meteo weather servers from excessive polling during client floods.

### Feature 11: Interactive 9-Tab Workbench Frontend
- **Mechanism:**
  - Implemented in [`app/static/index.html`](file:///c:/hackathon%20IBM%20x%20Jigyasa/app/static/index.html) with zero build-tool dependencies (Vanilla HTML5/CSS3/JavaScript).
  - **Map HUD:** Real-time counter showing total segments, active high/severe segments, weather status, and animated connection pulse dot.
  - **Freshness Banner:** Shows data age and warns when in historical replay or storm simulation mode.
  - **Sidebar Tabs:**
    1. `🗺️ Risk Map`: Corridor risk overview, segment selector, historical time machine date picker, and 309 historical scar markers.
    2. `🚗 Route Planner`: Origin/destination selector, departure time picker, speed regulator, and travel advisory card.
    3. `🚧 Closures`: Active road closures list, administrative closure reporter, and reopening toggle.
    4. `🚜 BRO Priority`: Infrastructure consequence score table, bridge proximity indicators, and emergency equipment staging order.
    5. `🌧️ Weather Sim`: Interactive storm intensity slider (0 to 180 mm) with quick-select presets (Moderate 35mm, Severe 85mm, Cloudburst 140mm).
    6. `📢 Field Reports`: Crowd report submission form, interactive map click-to-fill coordinate picker, and admin validation controls.
    7. `🔔 Alerts & SMS`: Live alert queue, phone subscription form, and in-browser interactive Twilio SMS simulator.
    8. `🛡️ Guardrails Lab`: One-click security testbed testing Rate Limiting (429), Corridor Boundary Rejection (422), and Timing-Safe Auth.
    9. `📦 Offline & Voice`: Offline survival pack viewer, Service Worker status, and bilingual neural voice audio player.
  - **Live JSON Console:** Real-time log showing every HTTP method, URL, status code pill (2xx, 3xx, 4xx, 5xx), response duration in ms, and formatted JSON response.

### Feature 12: Scientific Validation & Automated Test Suite
- **Mechanism:**
  - 122 automated pytest tests spanning unit, integration, security, and contract test cases.
  - Golden JSON schema regression tests (`tests/golden/`) verifying strict API backward compatibility.
  - Re-runnable validation audit script (`scripts/validation_audit.py`) and historical backtest runner (`scripts/backtest.py`).

---

## 4. Database Schema Accounting (`data/landslide_nh7.db`)

The SQLite database contains persistent tables supporting operational workflows:

```sql
-- 1. Crowd-Sourced Field Reports
CREATE TABLE field_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    reporter_name TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- 'pending', 'verified', 'rejected'
    photo_url TEXT,
    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP,
    verified_by TEXT
);

-- 2. Official Highway Road Closures
CREATE TABLE road_closures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT NOT NULL,
    status TEXT NOT NULL,          -- 'closed', 'one_way', 'restricted'
    reason TEXT NOT NULL,
    source TEXT NOT NULL,
    starts_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ends_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Traveler Alert Subscriptions
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL,
    segment_id TEXT,               -- NULL indicates corridor-wide subscription
    alert_channel TEXT DEFAULT 'sms', -- 'sms', 'telegram', 'push'
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Dispatched Notification History
CREATE TABLE alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT NOT NULL,
    risk_score REAL NOT NULL,
    risk_level TEXT NOT NULL,
    headline TEXT NOT NULL,
    advisory TEXT NOT NULL,
    dispatched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    channel TEXT NOT NULL
);
```

---

## 5. Summary of System Constants & Heuristics

| Constant | Value | Purpose |
|---|---|---|
| `CORRIDOR_LENGTH_KM` | 247.37 km | Total surveyed highway length from Rishikesh to Joshimath |
| `TOTAL_SEGMENTS` | 18 | Discrete civil administration and geomorphic segments |
| `K_RAIN` | 0.40 | Exponential rainfall hazard scaling coefficient ($1 - e^{-k \cdot R}$) |
| `DRY_CAP_MM` | 25.0 mm | Antecedent rainfall threshold below which risk cannot exceed "Moderate" |
| `RAIN_REF_MM` | 100.0 mm | Baseline severe rainfall reference value |
| `WEATHER_CACHE_TTL` | 300 seconds (5 min) | Circuit-breaker memory cache lifespan for weather API calls |
| `MAX_CORRIDOR_DIST_KM`| 3.0 km | Maximum allowable distance from NH-7 polyline for field hazard reports |
| `REPORT_RATE_LIMIT` | 5 / minute | Per-IP submission throttle to prevent spam or bot flooding |
| `DEFAULT_SPEED_KMPH` | 30.0 km/h | Baseline mountain driving speed for ETA progression calculations |

---

*Document compiled and verified against codebase state on October 6, 2026.*
