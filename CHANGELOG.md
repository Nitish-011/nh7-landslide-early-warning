# NH-7 Landslide Early Warning System — Changelog & Integration Guide

> **Target Audience:** Frontend, Mobile, and Infrastructure Teammates  
> **Guiding Principle:** **100% Backward Compatibility**. All previously existing keys, endpoints, and behaviors remain intact. Every addition listed below is **additive and optional** for client adoption.

---

## 1. Summary of Changes by Domain

| Feature | New Endpoints | Additive Query Params | New Headers | Optional Env Vars |
|---|---|---|---|---|
| **Weather & Forecast** (Task 1) | — | — | — | `PER_SEGMENT_WEATHER` |
| **Historical Time Machine** (Task 2) | — | `as_of` | — | `BACKTEST_ENABLED` |
| **Time-Aware Trip Planner** (Task 3) | — | `depart_time`, `speed_kmph` | — | `TIME_AWARE_PLANNER` |
| **BRO Consequence & Priority** (Task 4) | `GET /priority-list` | `simulate_rain_mm` | — | `CONSEQUENCE_CSV_PATH` |
| **Closures & Field Flywheel** (Task 5) | `GET /closures`<br>`POST /admin/closure`<br>`DELETE /admin/closure/{id}` | `segment_id`, `active_only` | `X-Admin-Key`<br>`X-API-Key` | `GROUND_TRUTH_LAYER`<br>`ADMIN_API_KEY` |
| **Alert Delivery & Messaging** (Task 6) | `POST /webhook/sms` | — | `X-Twilio-Signature` | `TELEGRAM_BOT_TOKEN`<br>`TWILIO_*` |
| **Localization & Voice** (Task 7) | `GET /voice-alert` | `lang` (`en` / `hi`) | — | `TTS_CACHE_DIR` |
| **Mobile Offline Pack** (Task 8) | `GET /offline-pack`<br>`GET /manifest.json`<br>`GET /sw.js` | `simulate_rain_mm` | `ETag`<br>`If-None-Match` | `EMERGENCY_CONTACTS` |
| **Reproducible Demo Mode** (Task 10) | — | — | — | `DEMO_MODE=true` |

---

## 2. New Endpoints

### Operational & Route Endpoints
- **`GET /priority-list`**
  - **Purpose:** BRO / SDRF pre-positioning operational priority table. Ranks all 18 segments by `priority_score = risk_index * consequence_score`.
  - **Query Params:** `simulate_rain_mm` (optional float).
  - **Status:** Indicative planning tool; does not replace physical reconnaissance.

- **`GET /closures`**
  - **Purpose:** Public query of official road closures and one-way traffic restrictions along NH-7.
  - **Query Params:** `segment_id` (optional string), `active_only` (default `true`).

- **`POST /admin/closure`**
  - **Purpose:** Create an official road closure or transit restriction. Automatically forces `AVOID` recommendations on routes passing through this sector.
  - **Auth:** Requires header `X-Admin-Key` or `X-API-Key`.
  - **Body:** `{ segment_id, status: "closed"|"one_way"|"restricted", reason, source, starts_at?, ends_at? }`.

- **`DELETE /admin/closure/{closure_id}`**
  - **Purpose:** Reopen / remove an official road closure.
  - **Auth:** Requires header `X-Admin-Key` or `X-API-Key`.

### Voice & Localization Endpoints
- **`GET /voice-alert`**
  - **Purpose:** Returns spoken audio alerts (`audio/mpeg`) generated via `gTTS` from localized travel advisories (&le; 300 characters).
  - **Query Params:** `segment_id` OR `from` & `to`, `lang` (`en` or `hi`, default `en`).
  - **Fallback:** If offline or synthesis fails, returns JSON `{ text, tts: "browser", lang }` for Web Speech API playback.
  - **Caching:** Audio files cached by SHA-256 (`lang:text`) in `data/tts_cache/`.

### Mobile Offline Pack & PWA Endpoints
- **`GET /offline-pack`**
  - **Purpose:** Ultra-compact (&lt; 100 KB uncompressed, ~16.5 KB actual; &lt; 5 KB gzipped) self-contained bundle for mobile apps in cellular dead zones.
  - **Contents:** `version` (content hash), `generated_at`, all 18 segments with `simplified_polyline`, current and terrain risk levels, bilingual advisories, `nearest_hospital`, and `emergency_contacts` (default `112`).
  - **HTTP Caching:** Supports `ETag` + `If-None-Match` (returns 0-byte `HTTP 304 Not Modified`).

- **`GET /manifest.json`** & **`GET /sw.js`**
  - **Purpose:** Progressive Web App (PWA) manifest and Service Worker for testbench and web browsers. Pre-caches app shell and `/offline-pack`; strictly excludes map tiles.

### Messaging & Webhook Endpoints
- **`POST /webhook/sms`**
  - **Purpose:** Inbound SMS query webhook for Twilio.
  - **Commands:** `NH7 HELP`, `NH7 SEG08`, `NH7 ROUTE RISHIKESH JOSHIMATH`.
  - **Security:** Verifies `X-Twilio-Signature` HMAC-SHA1 when `TWILIO_AUTH_TOKEN` is set.
  - **Response:** Valid TwiML XML (`<Response><Message>...</Message></Response>`), max 320 characters.

---

## 3. New Query Parameters on Existing Endpoints

### `GET /risk-map`
- **`simulate_rain_mm`** (`float`, optional): Injects synthetic rainfall (e.g. 0, 40, 100 mm) to evaluate risk model behavior.
- **`as_of`** (`string YYYY-MM-DD`, optional): Runs historical Time Machine replay using archived Open-Meteo data (requires `BACKTEST_ENABLED=true`).
- **`lang`** (`string`, optional, default `"en"`): When `lang="hi"`, translates segment names to phonetically transliterated Devanagari and localizes risk levels. English originals preserved in `*_en` fields.

### `GET /route-risk`
- **`depart_time`** (`string ISO`, optional): Departure time (e.g. `2026-10-06T08:00:00`). Evaluates progressive entry ETAs per segment and antecedent rainfall at that exact arrival hour.
- **`speed_kmph`** (`float`, optional, default `30.0`): Assumed average transit speed along the corridor.
- **`lang`** (`string`, optional, default `"en"`): Localizes route recommendations (`action`, `reason`), advisories, and segment names.
- **`simulate_rain_mm`** (`float`, optional).

### `GET /alerts`
- **`lang`** (`string`, optional, default `"en"`): Localizes alert severities, warning texts, and subscribed segment titles. English originals preserved in `*_en` fields.
- **`simulate_rain_mm`** (`float`, optional).

---

## 4. Additive Response Fields (Safe for Existing Clients)

All existing response fields are retained without alteration. The following new fields are additive:

### Segment Objects (`SegmentResponse` & `RouteSegmentRisk`)
- **`r3d_mm`, `rain_24h_mm`, `forecast_24h_mm`, `forecast_72h_mm`, `peak_hour_utc`, `peak_mm`** (Task 1): Per-segment hourly rainfall metrics.
- **`consequence_score`, `nearest_hospital_km`, `nearest_town`, `priority_score`** (Task 4): Physical blockage consequence indicators.
- **`closure`** (Task 5): Official closure object (`status`, `reason`, `source`, `starts_at`, `ends_at`) if active.
- **`adjusted_risk_level`, `ground_report_count_24h`, `adjustment_reason`** (Task 5): Verified ground-truth flywheel escalation (capped at +1 step).
- **`eta_ist`, `rain_72h_at_eta_mm`, `forecast_rain_6h_around_eta_mm`, `risk_level_at_eta`** (Task 3): Time-aware journey parameters.
- **`name_en`, `risk_level_en`, `main_driver_en`** (Task 7): Preserved English strings when `lang="hi"` is requested.

### Route Risk Object (`RouteRiskResponse`)
- **`recommendation`** (Task 3): Top-level recommendation with `{ action: "GO"|"CAUTION"|"DELAY"|"AVOID", reason, best_departure_options: [...] }`.
- **`closure`** (Task 5): Route-level closure object. Forces `action="AVOID"` if any route segment is blocked.
- **`lang`, `from_segment_name_en`, `to_segment_name_en`, `max_risk_level_en`, `advisory_en`** (Task 7): Bilingual compatibility metadata.

---

## 5. HTTP Headers

| Header | Direction | Description |
|---|---|---|
| **`X-API-Key`** / **`X-Admin-Key`** | Request | Required for `/admin/*` operations (`/admin/validate-report`, `/admin/closure`). In dev mode, defaults to `dev-localhost`. |
| **`X-Twilio-Signature`** | Request | HMAC-SHA1 validation header for inbound Twilio SMS webhooks. |
| **`If-None-Match`** | Request | Supported on `/offline-pack`. Send stored ETag to receive `304 Not Modified` (0 bytes). |
| **`ETag`** | Response | Generated on `/offline-pack` as a SHA-256 version hash for client-side caching. |
| **`Accept-Encoding: gzip`** | Request | Triggers Starlette `GZipMiddleware` compression on payloads &gt; 500 bytes. |

---

## 6. Environment Variables Reference

| Variable | Type | Default | Description |
|---|---|---|---|
| **`DEMO_MODE`** | `bool` | `false` | When `true`, pins all weather fetching to the local snapshot (`data/rain_snapshot.json`). Guarantees 100% reproducible, offline-safe presentations. |
| **`ADMIN_API_KEY`** | `str` | `""` | Secret admin key. Required at startup if `ENV=production`. |
| **`TIME_AWARE_PLANNER`** | `bool` | `true` | Enables dynamic arrival-hour rainfall routing when `depart_time` is supplied. |
| **`GROUND_TRUTH_LAYER`** | `bool` | `true` | Enables field report flywheel adjustments (exponential decay with half-life 48h). |
| **`PER_SEGMENT_WEATHER`** | `bool` | `false` | Enables 18-segment batched Open-Meteo hourly precipitation engine. |
| **`BACKTEST_ENABLED`** | `bool` | `false` | Enables historical Time Machine replay (`/risk-map?as_of=...`). |
| **`TTS_CACHE_DIR`** | `path` | `data/tts_cache` | Filesystem cache directory for synthesized MP3 voice files. |
| **`EMERGENCY_CONTACTS`** | `json` | *(Helpline 112)* | Config-driven emergency helplines directory for `/offline-pack`. |
| **`TELEGRAM_BOT_TOKEN`** | `str` | `""` | Bot token for background Telegram long-polling service. |
| **`ENABLE_TELEGRAM_BOT`** | `bool` | `false` | Enables background Telegram long-polling task. |
| **`TWILIO_ACCOUNT_SID`** | `str` | `""` | Twilio Account SID for SMS/WhatsApp notifications. |
| **`TWILIO_AUTH_TOKEN`** | `str` | `""` | Twilio Auth Token for webhook signature validation. |
| **`TWILIO_FROM`** | `str` | `""` | Twilio verified sender phone number. |
| **`ALERT_DISPATCH_INTERVAL_MINUTES`** | `int` | `10` | Evaluation cadence for subscriber alert dispatcher job. |
| **`ALERT_COOLDOWN_HOURS`** | `float` | `3.0` | Alert repeat cooldown window per user and segment. |

---

## 7. Scientific Hardening & Hackathon Audit Calibration

- **0.767 Benchmark Calibration:** Solidified official deployed model baseline as Copernicus 30m DEM + Random Forest v2 with pooled spatial OOF ROC-AUC of **0.767** and spatial block mean AUC of **0.664**. Removed unsupported 0.887 claims.
- **Dynamic Hazard Equation Alignment:** Synchronized documentation across `README.md`, `FEATURES.md`, `ANTIGRAVITY_BACKEND_CONTEXT.md`, and `MODEL_PERFORMANCE.md` with runtime implementation:
  $$\text{risk\_score} = \min\left(0.60 \times \text{terrain\_percentile} + 0.40 \times \min\left(\frac{R_{3\text{d}}}{100.0}, 1.0\right), 1.0\right)$$
- **Reproducible Deterministic Backtest Fallback:** Replaced Python process-randomized `hash()` in `scripts/backtest.py` with deterministic SHA-256 (`hashlib.sha256`) digest.
- **Explicit Synthetic Backtest Labeling:** Relabeled historical disaster backtest in `MODEL_PERFORMANCE.md` to "Synthetic Demonstration Backtest — Not Empirical Multi-Year Validation" with an explicit warning note on harness verification.
- **Environment Configuration Alignment:** Harmonized environment variable naming in `README.md` and `.env.example` with `app/config.py` (`TWILIO_FROM`, `ALERT_DISPATCH_INTERVAL_MINUTES=10`), adding backward-compatible fallbacks for `TWILIO_PHONE_NUMBER` and `ALERT_CHECK_INTERVAL`.
- **Subscriber PII Hardening:** Protected subscriber name privacy in unauthenticated `GET /alerts` via `mask_subscriber_name` to prevent enumeration and harvesting attacks.
- **Codebase Cleanliness:** Retired stale `calculate_risk_level` thresholds in `app/routes/risk.py` by delegating directly to `level_for` and `LEVEL_CUTS`.
- **Pre-Freeze Hackathon Audit Reconciliation:**
  - **Unified Weight Authority:** Authoritative live weights set to $K_{\text{terrain}} = 0.60, K_{\text{rain}} = 0.40$ across all documentation, tests, and backtest configurations.
  - **Single Authoritative Test Count:** Verified 122 collected automated test cases (100% pass rate).
  - **Deployed Model Identity:** Unified references to Copernicus 30m DEM + Random Forest v2 (`nh7_static_model_v2.joblib`), retiring legacy "RF + XGBoost" wording and logistic equation artifacts.
  - **Testing Guide Thresholds:** Corrected risk tier cuts in `TESTING_GUIDE.md` to match runtime configuration: Low (< 0.25), Moderate (0.25–0.49), High (0.50–0.74), Very High ($\ge$ 0.75).
  - **Geofence Boundary Hardening:** Bounded corridor validation check to regional coordinates when polyline is uninitialized.
  - **Telemetry Precision:** Calculated genuine `weather_age_minutes` in `DEMO_MODE` snapshots.

