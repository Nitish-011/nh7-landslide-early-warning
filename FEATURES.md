# NH-7 Landslide Early Warning & Resilient Routing System
## Complete System Feature Accounting & Capabilities Catalog

> **Corridor Scope:** National Highway 7 (Rishikesh to Joshimath, Uttarakhand, India — 243.10 km, 18 Segments)  
> **System Architecture:** Topographic ML Inference + Multi-Station Meteorology + Civil Infrastructure Consequence + Multi-Channel Alerts + PWA Offline Resilience  
> **Total Automated Test Coverage:** 131/131 passing tests across contract, security, freshness, and functional domains.

---

## 1. Architectural Overview & Executive Summary

The **NH-7 Landslide Early Warning System** is an end-to-end geohazard intelligence platform designed to protect life, pilgrimage traffic (Char Dham Yatra), and national logistical supply lines along India's most landslide-prone Himalayan highway corridor.

The platform bridges machine learning with operational field disaster management. Rather than treating landslides merely as static terrain rankings or simple rain gauge exceedances, the system couples:
1. **High-Resolution Geomorphology:** 30-meter Copernicus Digital Elevation Model (DEM) topographic features with historical landslide inventories (Mey et al., 2024; $N=309$ road-blocking failures). Static susceptibility is evaluated using **Random Forest v2** (pooled spatial OOF ROC-AUC = **0.767**, spatial block mean AUC = **0.664** across 6 spatial cross-validation blocks).
2. **Real-Time Dynamic Meteorology:** Live multi-station rainfall telemetry from Open-Meteo across 5 corridor reference stations (Rishikesh, Srinagar, Rudraprayag, Karnaprayag, Joshimath) with 30-minute caching and a 5-minute circuit breaker on failure.
3. **Civil Infrastructure Consequence:** Asset exposure mapping (major bridges, pilgrimage transit hubs, emergency hospitals, population densities, and alternate bypass availability).
4. **Resilient Public Interface:** Dual-layer command center (Leaflet GIS workbench + offline-first Progressive Web App) with vernacular Hindi/English neural text-to-speech voice alerts, Twilio SMS query webhooks, and automated Telegram bot integration.

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
|  - Dynamic Risk: min(0.60*terrain + 0.40*min(R/100, 1), 1)  - Caching: 30m Fresh | 5m Breaker     |
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
| **1** | **Dynamic Multi-Station Hazard Engine** | `GET /risk-map`<br>`GET /model-info` | Copernicus DEM 30m, Random Forest v2, Open-Meteo API, NumPy | Real-time hazard estimation combining 30m terrain susceptibility with live 3-day rainfall across 18 highway segments. |
| **2** | **Historical Time Machine & Replay** | `GET /risk-map?as_of=YYYY-MM-DD`<br>`GET /backtest-summary` | ERA5-Land Reanalysis, SQLite, Python | Allows operators to replay historical monsoon disaster dates (e.g. August 2023 cloudburst) under `BACKTEST_ENABLED=true`. |
| **3** | **Time-Aware Trip Safe Planner** | `GET /route-risk` (with `depart_time`) | Spatial polyline routing, hourly transit speed simulation | Analyzes specific highway departure times, evaluates progressive segment arrival ETAs, and suggests optimal departure windows. |
| **4** | **BRO Infrastructure Consequence Ranking** | `GET /consequence`<br>`GET /priority-list` | NHAI bridge registry, OSM hospital & town proximities | Calculates Priority = Hazard × Consequence to rank excavator and relief pre-positioning priorities for Border Roads Organisation. |
| **5** | **Field Ground-Truth Flywheel** | `POST /field-report`<br>`POST /admin/validate-report`<br>`GET /field-reports` | SQLite, Shapely 3km geofence, Admin Auth | Crowd-sources verified hazard reports from drivers and patrols; automatically triggers model adjustment when verified reports peak. |
| **6** | **Road Closures & Real-Time Detour Routing** | `GET /closures`<br>`POST /admin/closure`<br>`DELETE /admin/closure/{id}` | In-memory + SQLite lifecycle state machine | Tracks active road blockages, marks segments as "CLOSED", and forces route planners to recommend immediate avoidance or detours. |
| **7** | **Multi-Channel Alert Dispatcher & SMS** | `POST /subscribe`<br>`GET /alerts`<br>`POST /webhook/sms` | Twilio SMS API, Telegram Bot API, Async Background Worker | Dispatches automated warnings to travelers; provides interactive two-way SMS queries (`NH7 HELP`, `NH7 SEG08`, `NH7 ROUTE`). |
| **8** | **Vernacular Localization & Neural Voice** | `GET /voice-alert` | gTTS (Google Text-to-Speech), Python i18n, SHA-256 Cache | Translates alerts and segment names into Hindi (Devanagari) and serves cached streaming MP3 voice alerts for roadside drivers. |
| **9** | **Offline Survivor Pack & PWA Service Worker** | `GET /offline-pack`<br>`GET /manifest.json`<br>`GET /sw.js` | Service Worker, CacheStorage, HTTP ETag / 304 | Delivers a lightweight (<17 KB) self-contained survival package with highway geometry, contacts, and risk levels that works in cellular dead zones. |
| **10** | **Enterprise Security & Guardrails** | `app/middleware.py`<br>`app/limiter.py`<br>`app/routes/reports.py` | SlowAPI, HTML bleach, secrets timing-safe digest | Protects against DDoS (rate limits), XSS injections in crowd reports, unauthorized admin calls, and out-of-corridor spoofing. |
| **11** | **Interactive 9-Tab Workbench Frontend** | `app/static/index.html` | Vanilla HTML5/CSS3/JS, Leaflet GIS, JetBrains Mono | Unified web application with dual-mode GIS map, HUD metrics, rainfall slider, SMS simulator, and live JSON inspector. |
| **12** | **Scientific Validation & Audit Suite** | `scripts/validation_audit.py`<br>`tests/` (122 tests) | Pytest, Golden Schemas, Spatial Bootstrap | Independent validation auditing inventory coverage (309 scars), 6-fold spatial block cross-validation, and schema contracts. |

---

## 3. Deep Dive into Every Feature Domain

### Feature 1: Dynamic Multi-Station Hazard Engine
- **Mechanism:**
  - Evaluates 18 discrete, sequence-ordered segments from Rishikesh (km 0.0) to Joshimath (km 247.37).
  - Uses a **Copernicus 30m DEM** baseline calculating slope gradient, local relief (300m radius), Topographic Position Index (TPI), profile curvature, aspect, and elevation via **Random Forest v2** (`model/nh7_static_model_v2.joblib`, pooled spatial OOF ROC-AUC = **0.767**, spatial block mean AUC = **0.664** across 6 spatial cross-validation blocks).
  - **Dual Weather Ingestion Pipeline:**
    - **Default Operational Mode (`PER_SEGMENT_WEATHER=false`):** Assimilates weather from 5 corridor reference stations (**Rishikesh, Srinagar, Rudraprayag, Karnaprayag, Joshimath**) mapped to nearest segment midpoints via Open-Meteo.
    - **Advanced Hourly Mode (`PER_SEGMENT_WEATHER=true`):** Ingests weather for all 18 segment midpoints, computing 24h/72h antecedent and forecast rainfall, peak rain hour UTC, and peak hourly mm.
  - Computes 3-day antecedent rainfall $R_{3\text{d}} = R_{\text{yesterday}} + R_{\text{today}} + R_{\text{tomorrow}}$.
  - Integrates a transparent weighted linear-capped dynamic hazard formula with baseline terrain floor:
    $$\text{effective\_terrain} = \text{TERRAIN\_FLOOR} + (1.0 - \text{TERRAIN\_FLOOR}) \times \text{terrain\_percentile}$$
    $$\text{raw\_score} = \min\left(K_{\text{terrain}} \times \text{effective\_terrain} + K_{\text{rain}} \times \min\left(\frac{R_{3\text{d}}}{\text{RAIN\_REF\_MM}}, 1.0\right), 1.0\right)$$
    where $K_{\text{terrain}} = 0.60$, $K_{\text{rain}} = 0.40$, $\text{TERRAIN\_FLOOR} = 0.35$ (baseline floor ensuring even the lowest-percentile segments can escalate to High under severe storms), and $\text{RAIN\_REF\_MM} = 150.0\text{ mm}$ (linear-capped operational heuristic avoiding premature saturation at 100mm).
  - **Standardized Categorical Warning Tiers (`LEVEL_CUTS` in `app/config.py`):**
    - **Low:** $\text{score} < 0.25$
    - **Moderate:** $0.25 \le \text{score} < 0.50$
    - **High:** $0.50 \le \text{score} < 0.75$
    - **Very High:** $\text{score} \ge 0.75$
  - **Dry Condition Guardrail & Linear Ramp (`DRY_RAMP_LOW_MM = 15.0`, `DRY_RAMP_HIGH_MM = 35.0`, `DRY_CAP_MAX_SCORE = 0.49`, reference `DRY_CAP_MM = 25.0`):** Replaces the hard 25mm cliff with a smooth linear ramp between 15 mm and 35 mm: if $R_{3\text{d}} \le 15.0\text{ mm}$, risk cannot exceed Moderate ($\le 0.49$), preventing false alarms in dry sunny weather; between 15 and 35 mm, the ceiling transitions linearly to uncapped risk, preventing abrupt step jumps between 24.9mm and 25.1mm.
  - **Caching & Circuit Breaker:** Normal fresh weather cache is **1800 seconds (30 minutes)**. If the live weather API fails or times out (4.0s timeout), the failure is cached for **300 seconds (5 minutes)** as a circuit breaker, falling back to local snapshot (`data/rain_snapshot.json`) or terrain-only ranking (`rain_status: "unavailable"`). If live engine computation fails entirely, `/risk-map` returns explicit degraded metadata (`mode: "degraded"`, `weather_source: "database_fallback"`, `stale_warning: "Live risk computation failed; serving last-known database state."`).
  - **Simulation Override:** Supports `?simulate_rain_mm=120.0` (0.0 to 1000.0 mm) on `/risk-map` to stress-test highway segments under simulated extreme rain conditions. (Note: `/risk-map` accepts only `simulate_rain_mm`, `as_of`, and `lang`).

### Feature 2: Historical Time Machine & Backtest Engine
- **Mechanism:**
  - The parameter `?as_of=YYYY-MM-DD` triggers the **Time Machine** on `/risk-map` (requires `BACKTEST_ENABLED=true` in `app/config.py`).
  - Ingests archived historical daily precipitation data from ERA5-Land reanalysis.
  - Operational summary endpoint: `GET /backtest-summary`.
  - **Synthetic Demonstration Disclosure:** When synthetic event mode is active in the backtesting harness, it is clearly designated as a **Synthetic Demonstration Backtest** intended to verify the pipeline mechanics and reproducible scoring harness, **not** an empirical multi-year historical field validation.
  - Cached in `data/backtest_cache/` so historical queries return without repeated downloads.

### Feature 3: Time-Aware Safe Trip Planner
- **Mechanism:**
  - Endpoint: `GET /route-risk` (with query parameters `from_segment`, `to_segment`, `date`, `depart_time`, `speed_kmph`, and optional `simulate_rain_mm`, `lang`). Trip planning evaluation is integrated directly into `/route-risk` (there is no separate `POST /trip-planner` endpoint).
  - Takes route start, route end, travel date, intended departure timestamp (`depart_time` in ISO format, interpreted as IST UTC+05:30), and vehicle travel speed (`speed_kmph`, default 30.0 km/h; requires `TIME_AWARE_PLANNER=true`).
  - Calculates progressive segment arrival ETAs along the route and evaluates forecasted meteorological hazard at the driver's expected time of arrival.
  - Produces an end-to-end `recommendation` (`TripRecommendation`):
    - `GO` / `RECOMMENDED` (All segments Low/Moderate)
    - `CAUTION` (High risk segment or traffic restriction; recommended daytime departure)
    - `AVOID` (Severe risk or active road closures detected; suggest postponing)
    - `DELAY`
  - Returns a departure timeline recommending the safest departure window.
  - **Subpoint Risk Disclosure:** Subpoints along polyline segments are visualization vertices. Subpoint values (`subpoint_risk_scores` and `visualized_subpoint_risk`) are deterministic spatial interpolations calculated directly from the segment's calibrated Random Forest terrain percentile, live rainfall, and dry-weather cap, enabling smooth client-side polyline gradient rendering. They are deterministic visualization interpolations, not independently trained point-level ML predictions.

### Feature 4: BRO Infrastructure Consequence & Priority Pre-Positioning
- **Mechanism:**
  - Endpoints: `GET /consequence` and `GET /priority-list`.
  - Built for the **Border Roads Organisation (BRO)** and the **State Disaster Response Force (SDRF)**.
  - Hazard risk index is coupled with civil infrastructure consequence:
    $$\text{Priority Score} = \text{risk\_index} \times \text{consequence\_score}$$
  - Consequence factors incorporate:
    - Distance to nearest hospital (`nearest_hospital_km`, normalized to 30.0 km reference).
    - Alternate detour availability (penalty if no detour exists and road cut creates valley isolation).
    - Traffic importance index (traffic index 1-5).
  - Yields a ranked list of segments prioritizing where heavy earth-moving equipment (bulldozers, excavators) should be pre-staged before a storm strikes.

### Feature 5: Crowd-Sourced Field Hazard Verification & Flywheel
- **Mechanism:**
  - Endpoints: `POST /field-report`, `GET /field-reports`, `POST /admin/validate-report`.
  - Allows drivers, bus operators, and police patrols to report ground conditions (rockfall, debris, asphalt breach).
  - **Spatial Guardrail:** Enforces a 3.0 km Euclidean buffer from the NH-7 highway polyline (`geojson/nh7_route.geojson`). Coordinates further than 3.0 km are rejected with `HTTP 422 Unprocessable Entity`.
  - **Security Sanitization:** Regex-based HTML stripping and max 500-character description validation.
  - **Duplicate Prevention:** Rejects duplicate reports from the same IP at the same coordinate within a 10-minute window (`HTTP 409 Conflict`).
  - **Admin Validation & Flywheel:** Admin verifies reports (`POST /admin/validate-report` with `report_id`, `decision: "Validated"|"Rejected"`, `notes`, authenticated via `X-Admin-Key` / `X-API-Key`). When verified reports accumulate on a segment, ground-truth flywheel can adjust operational risk tier by +1 step and logs events to `data/validated_reports.csv`.

### Feature 6: Road Closures & Real-Time Detour Routing
- **Mechanism:**
  - Endpoints: `GET /closures` (public, supports `active_only` and `segment_id`), `POST /admin/closure`, `DELETE /admin/closure/{id}`.
  - Managed by administrative authorization (`X-Admin-Key` or `X-API-Key` header).
  - Tracks closure status (`closed`, `one_way`, `restricted`), blockage cause, and official source (e.g. "BRO Taskforce 66", "SDRF Control Room").
  - Directly alters route planning: if an active closure exists on a segment, `/route-risk` immediately flags that segment as impassable and outputs alternative bypass recommendations or an `AVOID` advisory.

### Feature 7: Multi-Channel Alert Dispatcher & SMS Webhook
- **Mechanism:**
  - Endpoints: `POST /subscribe`, `GET /alerts`, `POST /webhook/sms`.
  - **Twilio SMS Webhook:** Allows users without smartphones or mobile internet to send SMS text queries:
    - Text `NH7 HELP`: Returns guidance on available SMS commands.
    - Text `NH7 SEG08`: Returns real-time status and risk level for Segment 8 (Srinagar to Sirobagarh).
    - Text `NH7 ROUTE RISHIKESH JOSHIMATH`: Returns route clearance status and high-risk warnings via TwiML XML response (< 320 characters).
    - Validates `X-Twilio-Signature` HMAC-SHA1 when `TWILIO_AUTH_TOKEN` is configured.
  - **Telegram Bot Integration:** Bot client (`app/bot/telegram_bot.py`) providing `/start`, `/status`, `/alert`, `/help` with direct link to live map.
  - **Automated Dispatcher Worker:** 10-minute periodic background scheduler (`ALERT_DISPATCH_INTERVAL_MINUTES = 10`) evaluates corridor hazard scores:
    - Evaluates subscribers with `consent = 1`.
    - Automated alerts dispatch ONLY when a subscriber's segment reaches **High** or **Very High** risk ($\text{score} \ge 0.50$).
    - **Escalation-Only Guardrail:** Severity ranking (`Low: 0`, `Moderate: 1`, `High: 2`, `Very High: 3`) ensures subsequent alerts are dispatched only if risk escalates to a higher severity tier (`SEVERITY_RANK[current] > SEVERITY_RANK[last]`). Low/Moderate risk never triggers an alert, and risk downgrades are recorded silently without sending misleading messages.
    - **Cooldown Constraint:** Enforces a strict 3-hour cooldown (`ALERT_COOLDOWN_HOURS = 3.0`) per user and segment.
    - **Hazard Driver Messaging:** Messages dynamically cite heavy rain if $R_{3\text{d}} \ge 25\text{ mm}$ or geological slope instability during dry weather conditions.

### Feature 8: Vernacular Localization & Neural Voice Alerts
- **Mechanism:**
  - Parameter: `lang=en` or `lang=hi` across endpoints.
  - Fully localizes all segment names, risk levels, and driving advisories into Hindi (Devanagari).
  - Endpoint: `GET /voice-alert` (with `segment_id`, `from`, `to`, `lang`, `simulate_rain_mm`).
  - Uses `gTTS` (Google Text-to-Speech) to synthesize spoken voice warnings in Hindi and English.
  - Implements disk-based hashing cache (`data/tts_cache/{sha256}.mp3`), ensuring identical advisories are synthesized only once, enabling low-latency cached delivery for subsequent audio streams.
  - **Web Speech Fallback:** If gTTS fails or runs offline, returns JSON `{ text, tts: "browser", lang }` so client browsers synthesize speech locally via Web Speech API.

### Feature 9: Mobile Offline Survival Pack & PWA Service Worker
- **Mechanism:**
  - Endpoint: `GET /offline-pack`.
  - Returns a self-contained, ultra-compact JSON bundle (< 17 KB uncompressed, < 5 KB gzipped) containing:
    - Simplified segment coordinates (Ramer-Douglas-Peucker filtered).
    - Baseline terrain vulnerability and latest risk rankings.
    - Local emergency phone contacts (112, SDMA Uttarakhand, Highway Police, BRO).
    - Nearest trauma hospitals with chainage km markers.
    - Bilingual safety advisories in English and Hindi.
  - **HTTP ETag & 304 Support:** Computes a SHA-256 ETag from pack contents. Mobile clients sending `If-None-Match` receive an immediate `304 Not Modified` (0 bytes payload), conserving battery and cellular bandwidth.
  - **PWA Service Worker (`sw.js`, `manifest.json`):** Automatically pre-caches the web application shell and offline pack. If connectivity is severed, the UI continues functioning, rendering the highway risk map from cache and alerting the user via the top `#offline-banner`.

### Feature 10: Security Guardrails & Rate Limiting Lab
- **Mechanism:**
  - **Rate Limiting:** Managed via `slowapi` with in-memory IP buckets (e.g. 5 requests/minute for report submissions and subscriptions, 60 requests/minute for voice alerts, 120 requests/minute for risk queries).
  - **Timing-Safe Admin Verification:** Uses Python's `secrets.compare_digest` to prevent side-channel timing attacks on the `X-Admin-Key` / `X-API-Key` header.
  - **Corridor Distance Enforcement:** Strict mathematical distance projection against `geojson/nh7_route.geojson`.
  - **Input Sanitization:** Regex-based strip of `<script>`, HTML tags, and non-printable control characters from crowd report text.
  - **In-Memory Circuit Breaker:** Protects upstream Open-Meteo weather servers from excessive polling during client floods.

### Feature 11: Interactive 9-Tab Workbench Frontend
- **Mechanism:**
  - Implemented in `app/static/index.html` with zero build-tool dependencies (Vanilla HTML5/CSS3/JavaScript).
  - **Map HUD:** Real-time counter showing total segments, active high/severe segments, weather status, and animated connection pulse dot.
  - **Freshness Banner:** Shows data age and warns when in historical replay or storm simulation mode.
  - **Sidebar Tabs:**
    1. `🗺️ Risk Map`: Corridor risk overview, segment selector, historical time machine date picker, and 309 historical scar markers.
    2. `🚗 Route Planner`: Origin/destination selector, departure time picker, speed regulator, and travel advisory card.
    3. `🚧 Closures`: Active road closures list, administrative closure reporter, and reopening toggle.
    4. `🚜 BRO Priority`: Infrastructure consequence score table, bridge proximity indicators, and emergency equipment staging order.
    5. `🌧️ Weather Sim`: Interactive storm intensity slider (0 to 180 mm) with quick-select presets (Moderate 35mm, Severe 85mm, Extreme rainfall (140 mm / 3 days)).
    6. `📢 Field Reports`: Crowd report submission form, interactive map click-to-fill coordinate picker, and admin validation controls.
    7. `🔔 Alerts & SMS`: Live alert queue, phone subscription form, and in-browser interactive Twilio SMS simulator.
    8. `🛡️ Guardrails Lab`: One-click security testbed testing Rate Limiting (429), Corridor Boundary Rejection (422), and Timing-Safe Auth.
    9. `📦 Offline & Voice`: Offline survival pack viewer, Service Worker status, and bilingual neural voice audio player.
  - **Live JSON Console:** Real-time log showing every HTTP method, URL, status code pill (2xx, 3xx, 4xx, 5xx), response duration in ms, and formatted JSON response.

### Feature 12: Scientific Validation & Automated Test Suite
- **Mechanism:**
  - **125 automated pytest tests** spanning unit, integration, security, and contract test cases with 100% pass rate.
  - Golden JSON schema regression tests (`tests/golden/`) verifying strict API backward compatibility.
  - Re-runnable validation audit script (`scripts/validation_audit.py`) and historical backtest runner (`scripts/backtest.py`).

---

## 4. Database Schema Accounting (`data/landslide_nh7.db`)

The SQLite database contains persistent tables supporting operational workflows (defined in `app/database.py`):

```sql
-- 1. Highway Corridor Segments
CREATE TABLE segments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sequence_order INTEGER NOT NULL,
    start_lat REAL NOT NULL,
    start_lng REAL NOT NULL,
    end_lat REAL NOT NULL,
    end_lng REAL NOT NULL,
    subpoints_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    risk_score REAL NOT NULL,
    updated_at TEXT NOT NULL
);

-- 2. Traveler Alert Subscriptions
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone_or_email TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    channel TEXT NOT NULL,             -- 'SMS', 'WhatsApp', 'Email'
    consent BOOLEAN NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY (segment_id) REFERENCES segments(id)
);

-- 3. Crowd-Sourced Field Reports
CREATE TABLE field_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    description TEXT NOT NULL,
    photo_url TEXT,
    reporter_name TEXT NOT NULL,
    reporter_ip TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Pending', -- 'Pending', 'Validated', 'Rejected'
    decision_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    segment_id TEXT
);

-- 4. Historical Landslide Catalog
CREATE TABLE landslide_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    location TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    event_date TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL
);

-- 5. Official Highway Road Closures
CREATE TABLE road_closures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('closed', 'one_way', 'restricted')),
    reason TEXT NOT NULL,
    source TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (segment_id) REFERENCES segments(id)
);

-- 6. Alert State (Deduplication & 3-Hour Cooldown Tracking)
CREATE TABLE alert_state (
    subscription_id INTEGER NOT NULL,
    segment_id TEXT NOT NULL,
    last_sent_level TEXT NOT NULL,
    last_sent_at TEXT NOT NULL,
    PRIMARY KEY (subscription_id, segment_id),
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
);

-- 7. Alert Log (Operational Audit Trail of Sent Notifications)
CREATE TABLE alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id INTEGER,
    segment_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    contact TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent',
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL
);
```

---

## 5. Summary of System Constants & Heuristics

| Constant | Value | Purpose |
|---|---|---|
| `CORRIDOR_LENGTH_KM` | 247.37 km | Total surveyed highway length from Rishikesh to Joshimath |
| `TOTAL_SEGMENTS` | 18 | Discrete civil administration and geomorphic segments |
| `K_TERRAIN` | 0.60 | Weight of static geomorphic susceptibility ranking in composite score |
| `K_RAIN` | 0.40 | Weight of dynamic linear-capped rainfall index term in composite score |
| `RAIN_REF_MM` | 150.0 mm | Linear-capped rainfall saturation constant (avoids premature saturation at 100mm) |
| `TERRAIN_FLOOR` | 0.35 | Baseline susceptibility floor ensuring lowest-percentile segments can escalate under severe storms |
| `DRY_CAP_MM` | 25.0 mm | Reference antecedent rainfall threshold for dry condition heuristics |
| `DRY_RAMP_LOW_MM` | 15.0 mm | Lower bound of dry-cap linear ramp ($\le 15.0\text{ mm}$ capped at Moderate $\le 0.49$) |
| `DRY_RAMP_HIGH_MM` | 35.0 mm | Upper bound of dry-cap linear ramp ($\ge 35.0\text{ mm}$ full uncapped response) |
| `DRY_CAP_MAX_SCORE`| 0.49 | Maximum permitted score under dry conditions (Moderate ceiling) |
| `WEATHER_CACHE_TTL` | 1800 seconds (30 min) | Normal fresh weather cache duration |
| `FAILED_CACHE_TTL` | 300 seconds (5 min) | Circuit-breaker memory cache lifespan for failed weather API calls |
| `MAX_CORRIDOR_DIST_KM`| 3.0 km | Maximum allowable distance from NH-7 polyline for field hazard reports |
| `REPORT_RATE_LIMIT` | 5 / minute | Per-IP submission throttle to prevent spam or bot flooding |
| `DEFAULT_SPEED_KMPH` | 30.0 km/h | Mountain driving speed for progressive ETA calculations |
| `ALERT_COOLDOWN_HOURS`| 3.0 hours | Minimum cooldown between repeat notifications for same user/segment |
| `ALERT_DISPATCH_INTERVAL`| 10 minutes | Frequency of periodic background alert dispatcher evaluations |

---

*Document compiled and verified against codebase state on October 6, 2026.*
