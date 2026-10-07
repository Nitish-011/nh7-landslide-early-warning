# 🧠 Antigravity AI Agent Guide: NH-7 Landslide Early Warning Backend

> **Target Agent:** Antigravity 2.0 / Gemini / Claude Coding Agents  
> **Workspace Purpose:** Build new mobile apps (Flutter, React Native, Swift, Kotlin) and web frontends (React, Next.js, Vue, Vanilla JS) connecting directly to this FastAPI backend.  
> **Backend Host:** `http://localhost:8000` (Local Dev) | `http://0.0.0.0:8000` (Docker / LAN)  
> **Interactive Swagger OpenAPI:** `http://localhost:8000/docs`  
> **Raw OpenAPI JSON:** `http://localhost:8000/openapi.json`  

---

## 1. Core Mental Model for AI Agents

When building a client or user interface for this repository, you do **not** need to simulate or mock the backend logic. The backend is a **hackathon-ready, resilience-oriented FastAPI backend** integrating real topographic machine learning inferences with live multi-station meteorological telemetry.

```
+---------------------------------------------------------------------------------------------------+
|               STATIC TOPOGRAPHY BASELINE (Physical Laws of Nature)                                |
|  - 30-meter Copernicus DEM Topography (Slope, 300m Local Relief, TPI, Curvature, Aspect, Elev)    |
|  - 247.37 km NH-7 Highway Alignment (Rishikesh to Joshimath, geojson/nh7_route.geojson)          |
|  - 18 Sequence-Ordered Corridor Segments (seg_01 to seg_18)                                        |
|  - Static Model: Random Forest v2 (model/nh7_static_model_v2.joblib)                              |
|  - Validation: Pooled Spatial OOF ROC-AUC 0.767 | Spatial Block Mean AUC 0.664                     |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|               DYNAMIC REAL-TIME ENGINE (Live State & Weather)                                     |
|  - Weather Source: Open-Meteo Multi-Station Pipeline (Default: 5 corridor reference stations)    |
|  - Caching: 30-minute fresh cache (1800s) | 5-minute circuit breaker (300s) on failure            |
|  - Dynamic Risk Formula: score = min(0.60*terrain + 0.40*min(R_3d/100, 1.0), 1.0)                 |
|  - Dry-Weather Guardrail: If R_3d < 25.0 mm, risk score capped at Moderate (score <= 0.49)         |
|  - Storm Simulation Overrides (?simulate_rain_mm=0..1000)                                         |
|  - Time-Aware Arrival-Hour Route Trip Forecasting (GET /route-risk?depart_time=...)               |
|  - Active Road Closures & Bypass Routing (GET /closures, POST /admin/closure)                     |
|  - Crowd-Sourced Field Reports & Validation Flywheel (POST /field-report, 3.0 km geofence)        |
|  - Bilingual English / Hindi Neural Voice Alerts (GET /voice-alert?lang=hi, MP3 + Web Speech)     |
|  - Ultra-Compact Offline Survival Pack with ETag/304 Caching (GET /offline-pack, < 17 KB)        |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Segment Master Registry (18 Segments)

Use these exact IDs, sequence orders, and chainage boundaries in your UI dropdowns, route selectors, and map polylines:

| Segment ID | Sequence | Segment Name (English) | Segment Name (Hindi Devanagari) | Start Chainage | End Chainage | Length |
|---|:---:|---|---|:---:|:---:|:---:|
| `seg_01` | 1 | Rishikesh to Shivpuri | ऋषिकेश से शिवपुरी | km 0.00 | km 17.43 | 17.43 km |
| `seg_02` | 2 | Shivpuri to Byasi | शिवपुरी से ब्यासी | km 17.43 | km 24.26 | 6.83 km |
| `seg_03` | 3 | Byasi to Kaudiyala | ब्यासी से कौडियाला | km 24.26 | km 38.12 | 13.86 km |
| `seg_04` | 4 | Kaudiyala to Devprayag | कौडियाला से देवप्रयाग | km 38.12 | km 70.63 | 32.51 km |
| `seg_05` | 5 | Devprayag to Teen Dhara | देवप्रयाग से तीन धारा | km 70.63 | km 85.56 | 14.94 km |
| `seg_06` | 6 | Teen Dhara to Kirtinagar | तीन धारा से कीर्तिनगर | km 85.56 | km 98.04 | 12.47 km |
| `seg_07` | 7 | Kirtinagar to Srinagar | कीर्तिनगर से श्रीनगर | km 98.04 | km 102.99 | 4.95 km |
| `seg_08` | 8 | Srinagar to Sirobagarh | श्रीनगर से सिरोबगड़ | km 102.99 | km 112.42 | 9.42 km |
| `seg_09` | 9 | Sirobagarh to Rudraprayag | सिरोबगड़ से रुद्रप्रयाग | km 112.42 | km 136.06 | 23.64 km |
| `seg_10` | 10 | Rudraprayag to Gauchar | रुद्रप्रयाग से गौचर | km 136.06 | km 158.55 | 22.49 km |
| `seg_11` | 11 | Gauchar to Karnaprayag | गौचर से कर्णप्रयाग | km 158.55 | km 168.12 | 9.56 km |
| `seg_12` | 12 | Karnaprayag to Langasu | कर्णप्रयाग से लंगासू | km 168.12 | km 174.18 | 6.07 km |
| `seg_13` | 13 | Langasu to Nandprayag | लंगासू से नंदप्रयाग | km 174.18 | km 187.33 | 13.15 km |
| `seg_14` | 14 | Nandprayag to Chamoli | नंदप्रयाग से चमोली | km 187.33 | km 200.39 | 13.05 km |
| `seg_15` | 15 | Chamoli to Birahi | चमोली से बिरही | km 200.39 | km 205.62 | 5.24 km |
| `seg_16` | 16 | Birahi to Pipalkoti | बिरही से पीपलकोटी | km 205.62 | km 212.36 | 6.74 km |
| `seg_17` | 17 | Pipalkoti to Helang (Tangani) | पीपलकोटी से हेलंग (तांगणी) | km 212.36 | km 241.04 | 28.68 km |
| `seg_18` | 18 | Helang to Joshimath | हेलंग से जोशीमठ | km 241.04 | km 247.37 | 6.33 km |

---

## 3. UI Color Palette & Risk Classification Standards

When rendering maps, badges, and progress meters, adhere strictly to the backend's calibrated threshold cuts (`LEVEL_CUTS` in `app/config.py`):

```typescript
export const RISK_LEVELS = {
  Low: {
    label: "Low",
    minScore: 0.00,
    maxScore: 0.24,
    color: "#10b981",       // Emerald Green
    bgLight: "rgba(16, 185, 129, 0.15)",
    border: "rgba(16, 185, 129, 0.35)",
  },
  Moderate: {
    label: "Moderate",
    minScore: 0.25,
    maxScore: 0.49,
    color: "#f59e0b",       // Warm Amber
    bgLight: "rgba(245, 158, 11, 0.15)",
    border: "rgba(245, 158, 11, 0.35)",
  },
  High: {
    label: "High",
    minScore: 0.50,
    maxScore: 0.74,
    color: "#f97316",       // Vivid Orange
    bgLight: "rgba(249, 115, 22, 0.15)",
    border: "rgba(249, 115, 22, 0.35)",
  },
  VeryHigh: {
    label: "Very High / Severe",
    minScore: 0.75,
    maxScore: 1.00,
    color: "#ef4444",       // Danger Crimson Red
    bgLight: "rgba(239, 68, 68, 0.15)",
    border: "rgba(239, 68, 68, 0.35)",
  },
  Closed: {
    label: "Closed / Blocked",
    color: "#991b1b",       // Dark Red / Striped Hatched
    bgLight: "rgba(153, 27, 27, 0.25)",
    border: "rgba(153, 27, 27, 0.50)",
  }
};
```

---

## 4. Mathematical Hazard Model & Scientific Performance

### 4.1 Deployed Machine Learning Model
- **Algorithm:** Random Forest v2 (`RandomForestClassifier`, 100 estimators, max depth 8).
- **Artifact:** `model/nh7_static_model_v2.joblib` & `model/pipeline_meta_static_v2.json`.
- **Topographic Base:** Copernicus 30-meter Digital Elevation Model (ESA).
- **Features (8 Geomorphic Predictors):** Elevation (`dem_elev_m`), Slope gradient (`dem_slope_deg`), Max slope in 210m (`dem_slope_max_210m`), Aspect East-West (`dem_aspect_sin`), Aspect North-South (`dem_aspect_cos`), Profile Curvature (`dem_curvature`), 300m Local Relief (`dem_relief_300m`), Topographic Position Index (`dem_tpi_300m`).
- **Official Audited Performance:**
  - **Pooled Spatial Out-of-Fold (OOF) ROC-AUC:** **0.767** (95% CI: `[0.680, 0.802]`).
  - **Spatial Block Mean AUC:** **0.664 ± 0.043** across 6 spatial cross-validation blocks.
  - **Top-20% Spatial Capture Rate:** **43.0%** of surveyed historical slides captured in top quintile.
- **Authoritative Deployed Baseline:** The sole official deployed model baseline is Random Forest v2 on Copernicus 30m DEM with Pooled Spatial Out-of-Fold ROC-AUC of **0.767** and spatial block mean AUC of **0.664**.

### 4.2 Dynamic Composite Hazard Formula
At runtime, relative risk is evaluated using a **physics-constrained linear-capped coupling with baseline terrain floor**:

$$\text{effective\_terrain} = \text{TERRAIN\_FLOOR} + (1.0 - \text{TERRAIN\_FLOOR}) \times \text{terrain\_percentile}$$
$$\text{raw\_score} = \min\left(0.60 \times \text{effective\_terrain} + 0.40 \times \min\left(\frac{R_{3\text{d}}}{150.0}, 1.0\right), 1.0\right)$$

- $K_{\text{terrain}} = 0.60$: Weight of static geomorphic susceptibility ranking.
- $K_{\text{rain}} = 0.40$: Weight of hydrologic trigger.
- $\text{TERRAIN\_FLOOR} = 0.35$: Baseline susceptibility floor ensuring even lowest-percentile segments escalate to High under severe rain.
- $R_{3\text{d}}$: 3-day antecedent rainfall (yesterday + today + tomorrow) in mm.
- $R_{\text{ref}} = 150.0\text{ mm}$ (`RAIN_REF_MM`): Rainfall reference saturation constant avoiding premature saturation at 100mm.
- **Dry-Weather Guardrail & Linear Ramp (`DRY_RAMP_LOW_MM = 15.0`, `DRY_RAMP_HIGH_MM = 35.0`, `DRY_CAP_MAX_SCORE = 0.49`):** If valid 3-day rainfall is $\le 15.0\text{ mm}$, categorical risk cannot exceed **Moderate** ($\le 0.49$), preventing false alarms in dry, sunny weather. Between 15 mm and 35 mm, a continuous linear ramp smoothly transitions from the 0.49 ceiling to full uncapped response, eliminating step-discontinuities.

---

## 5. Weather Architecture, Caching & Resilience

The backend implements a **4-tier fault-tolerant weather ingestion pipeline** with automated caching:

1. **Tier 1 (Live Multi-Station Ingestion):** Queries Open-Meteo forecast API with a 4.0-second timeout.
   - **Default Operational Mode (`PER_SEGMENT_WEATHER=false`):** Assimilates weather from 5 major corridor reference stations (Rishikesh, Srinagar, Rudraprayag, Karnaprayag, Joshimath) mapped to nearest segment midpoints. Highly hardened against external rate limits.
   - **Advanced Hourly Mode (`PER_SEGMENT_WEATHER=true`):** Queries midpoints for all 18 segments with hourly precipitation, calculating 24h/72h rainfall, peak hour UTC, and peak hourly mm.
2. **Tier 2 (Corridor Station Fallback):** If full midpoint batch fails, falls back to 5 corridor reference stations.
3. **Tier 3 (Local Rain Snapshot):** If live network is unreachable, loads `data/rain_snapshot.json` (persisted atomically).
4. **Tier 4 (Terrain-Only Neutral Fallback):** If no snapshot exists, scores segments using terrain susceptibility alone (`rain_status="unavailable"`).

### Cache TTL Policies
- **Normal Fresh Cache:** **1800 seconds (30 minutes)**. Subsequent requests within 30 minutes return instantly from memory.
- **Circuit Breaker Failure Cache:** **300 seconds (5 minutes)**. If Open-Meteo fails or times out, the failure is cached for 5 minutes so client requests do not hang.

---

## 6. Complete API Endpoint Specification

---

### 1. `GET /health` — System Health & Service Status
- **Method:** `GET`
- **Path:** `/health`
- **Description:** Verifies database connectivity, memory circuit breaker state, and API uptime.
- **Request:** None
- **Response (200 OK):**
```json
{
  "status": "ok",
  "database": "connected",
  "version": "1.0.0",
  "circuit_breaker": "healthy",
  "timestamp": "2026-10-06T03:00:00Z"
}
```

---

### 2. `GET /risk-map` — Real-Time Highway Corridor Risk Map
- **Method:** `GET`
- **Path:** `/risk-map`
- **Description:** Returns all 18 NH-7 segments between Rishikesh and Joshimath with current risk scores, driver explanations, and weather telemetry.
- **Query Parameters:**
  - `simulate_rain_mm` (*float*, optional): Simulates rainfall (0.0 to 1000.0 mm) for demo and storm stress-testing.
  - `as_of` (*string YYYY-MM-DD*, optional): Historical replay date from ERA5-Land reanalysis archive (requires `BACKTEST_ENABLED=true`).
  - `lang` (*string*, optional, default `"en"`): `"en"` or `"hi"` (Hindi Devanagari transliteration).
- **Response (200 OK):**
```json
{
  "corridor": "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
  "corridor_en": null,
  "total_segments": 18,
  "high_or_very_high_risk_count": 2,
  "weather_source": "live",
  "weather_fetched_at": "2026-10-06T07:00:00Z",
  "weather_age_minutes": 5.2,
  "is_simulated": false,
  "stale_warning": null,
  "mode": "live",
  "as_of": null,
  "lang": "en",
  "segments": [
    {
      "id": "seg_01",
      "name": "Rishikesh to Shivpuri",
      "name_en": null,
      "sequence_order": 1,
      "start_lat": 30.0869,
      "start_lng": 78.2676,
      "end_lat": 30.1357,
      "end_lng": 78.3892,
      "subpoints": [
        [30.0869, 78.2676],
        [30.1157, 78.3245],
        [30.1357, 78.3892]
      ],
      "risk_level": "Low",
      "risk_level_en": null,
      "risk_score": 0.18,
      "risk_index": 0.18,
      "terrain_percentile": 0.76,
      "terrain_level": "Moderate",
      "terrain_status": "ok",
      "rain_mm_3d": 11.8,
      "rain_status": "ok",
      "main_driver": "Mild slope gradient (14°), stable foothill geology",
      "main_driver_en": null,
      "method": "terrain model ranking + live-rainfall heuristic (not calibrated)",
      "closure": null,
      "adjusted_risk_level": null,
      "ground_report_count_24h": 0,
      "updated_at": "2026-10-06T07:00:00Z"
    }
  ]
}
```
> **Degraded Fallback Disclosure:** If the live risk pipeline encounters an unhandled exception, `/risk-map` safely falls back to seeded database state with explicit health telemetry: `"mode": "degraded"`, `"weather_source": "database_fallback"`, and `"stale_warning": "Live risk computation failed; serving last-known database state."`.

---

### 3. `GET /route-risk` — Route Segment Risk Assessment & Trip Planner
- **Method:** `GET`
- **Path:** `/route-risk`
- **Description:** Evaluates landslide hazard for a journey between two segments for a target date. If `depart_time` is supplied, activates the **Time-Aware Trip Planner** to compute progressive segment arrival ETAs and hourly storm risk.
- **Query Parameters:**
  - `from_segment` (*string*, required): Starting segment ID (e.g. `seg_01`).
  - `to_segment` (*string*, required): Destination segment ID (e.g. `seg_09`).
  - `date` (*string YYYY-MM-DD*, required): Travel date.
  - `simulate_rain_mm` (*float*, optional): Rainfall override (0.0 to 1000.0 mm).
  - `depart_time` (*string ISO*, optional): Departure timestamp (e.g. `2026-10-06T08:00:00`). Interpreted as IST (UTC+05:30) if timezone is omitted.
  - `speed_kmph` (*float*, optional, default `30.0`): Travel speed in km/h.
  - `lang` (*string*, optional, default `"en"`): `"en"` or `"hi"`.
- **Response (200 OK):**
```json
{
  "from_segment": "seg_01",
  "to_segment": "seg_09",
  "from_segment_name": "Rishikesh to Shivpuri",
  "to_segment_name": "Sirobagarh to Rudraprayag",
  "date": "2026-10-06",
  "total_segments": 9,
  "max_risk_level": "High",
  "average_risk_score": 0.58,
  "risk_index": 0.58,
  "advisory": "CRITICAL WARNING for 2026-10-06: High susceptibility to slope failure and active shooting stones detected along route sectors. Night travel and heavy vehicles strongly discouraged. Check BRO updates.",
  "weather_source": "live",
  "depart_time": "2026-10-06T08:00:00",
  "speed_kmph": 30.0,
  "recommendation": {
    "action": "CAUTION",
    "action_code": "REC_CAUTION",
    "reason": "Moderate exposure: thunderstorm peak expected near Sirobagarh after 11:30.",
    "best_departure_options": [
      {
        "depart_time": "2026-10-06T06:00:00",
        "max_risk_level": "Moderate",
        "summary": "Best window: clears high-gradient sectors before noon rain peak."
      }
    ]
  },
  "segments": [
    {
      "id": "seg_01",
      "name": "Rishikesh to Shivpuri",
      "sequence_order": 1,
      "subpoints": [
        [30.0869, 78.2676],
        [30.1157, 78.3245],
        [30.1357, 78.3892]
      ],
      "subpoint_risk_scores": [0.18, 0.19, 0.20],
      "visualized_subpoint_risk": [0.18, 0.19, 0.20],
      "risk_level": "Low",
      "risk_score": 0.18,
      "eta_ist": "2026-10-06T08:35:00+05:30",
      "rain_72h_at_eta_mm": 11.8,
      "risk_level_at_eta": "Low"
    }
  ]
}
```
> **Subpoint Methodology Disclosure:** Subpoints along polyline segments are visualization vertices. `subpoint_risk_scores` (also exposed as `visualized_subpoint_risk`) are deterministic spatial interpolations calculated directly from the segment's calibrated Random Forest terrain percentile, live rainfall, and dry-weather cap, enabling smooth client-side polyline gradient rendering.

#### Recommendation Object & Action Enum (`recommendation`)
When evaluating a route with `depart_time`, the `recommendation` payload provides a time-aware decision based on hourly storm simulations over a 48-hour forward horizon.

> **⚠️ Persistent Disclaimer Requirement:**  
> All client interfaces (Web UI, Mobile, SMS reply, Voice alert) MUST display or state:  
> `"Decision-support prototype, not an official warning. Low risk does not mean safe. Landslides also occur in dry weather. Follow BRO/SDRF/police advisories. Emergency: 112"`  
> *(Hindi: "निर्णय-समर्थन प्रोटोटाइप, आधिकारिक चेतावनी नहीं। कम जोखिम का अर्थ सुरक्षित नहीं है। सूखे मौसम में भी भूस्खलन हो सकता है। बीआरओ/एसडीआरएफ/पुलिस सलाह का पालन करें। आपातकाल: 112")*

The engine outputs four canonical actions:
1. **`LOW RISK – proceed with caution`** (`action_code: "REC_LOW_RISK_CAUTION"`):
   - Returned when all segments across the route are evaluated as `Low` risk at the planned departure time.
   - Note: Nothing says `GO` or `safe`; Low risk modeled does not guarantee safety.
2. **`CAUTION`** (`action_code: "REC_CAUTION"`):
   - Returned when moderate landslide risk (`Moderate`, rank 1) is detected along the route, OR when a non-blocking traffic restriction (`one_way` / `restricted`) is active.
3. **`DELAY`** (`action_code: "REC_DELAY"`):
   - **Trigger Condition:** Returned when elevated landslide hazard (`High` or `Very High`, rank $\ge 2$) is modeled along the route at the traveler's planned departure time, **AND** a future departure time within the 48-hour forward forecast search achieves a strictly lower maximum route risk (`best_rank < base_rank`, e.g. dropping to Moderate or Low risk).
   - **Response Payload:** Contains `hours_delay` (hours to wait), `best_depart_time` (recommended departure timestamp), and up to 3 alternate departure options in `best_departure_options`.
4. **`AVOID`** (`action_code: "REC_AVOID"`):
   - Returned when an active official road closure (`status == "closed"`) is in effect along the planned route, OR severe risk (`High` / `Very High`) persists across all 48 hours of the forecast search with no viable lower-risk window.

---

### 4. `POST /subscribe` — Register for Real-Time SMS/Push Alerts
- **Method:** `POST`
- **Path:** `/subscribe`
- **Rate Limit:** `5 requests / minute` per IP
- **Description:** Subscribes a traveler or resident to automated risk notifications for a specific NH-7 highway segment.
- **Request Body:**
```json
{
  "name": "Ramesh Negi",
  "phone_or_email": "+919876543210",
  "segment_id": "seg_08",
  "channel": "SMS",
  "consent": true
}
```
- **Response (201 Created):**
```json
{
  "subscription_id": 42,
  "status": "Active",
  "message": "Successfully subscribed to alerts for 'Srinagar to Sirobagarh' via SMS.",
  "subscription": {
    "id": 42,
    "name": "Ramesh Negi",
    "phone_or_email": "+919876543210",
    "segment_id": "seg_08",
    "segment_name": "Srinagar to Sirobagarh",
    "channel": "SMS",
    "consent": true,
    "created_at": "2026-10-06T07:10:00Z"
  }
}
```

---

### 5. `GET /alerts` — Active Notifications for Subscribed User
- **Method:** `GET`
- **Path:** `/alerts`
- **Rate Limit:** `120 requests / minute`
- **Query Parameters:**
  - `user_id` (*int*, required): Numeric `subscription_id` returned by `/subscribe`.
  - `simulate_rain_mm` (*float*, optional): Rainfall override for alert testing.
  - `lang` (*string*, optional, default `"en"`): `"en"` or `"hi"`.
- **Response (200 OK):**
```json
{
  "user_id": 42,
  "user_name": "R***h N***i",
  "contact": "+91******3210",
  "active_alerts_count": 1,
  "alerts": [
    {
      "alert_id": "ALT-NH7-seg_08-42",
      "segment_id": "seg_08",
      "segment_name": "Srinagar to Sirobagarh",
      "severity": "High",
      "risk_score": 0.72,
      "risk_index": 0.72,
      "message": "HIGH ALERT on Srinagar to Sirobagarh: Heavy rainfall saturation (3-day rain: 38.2 mm). Avoid non-essential travel.",
      "channel": "SMS",
      "issued_at": "2026-10-06T07:10:00Z",
      "rain_mm_3d": 38.2,
      "rain_status": "ok"
    }
  ]
}
```

---

### 6. `GET /priority-list` & `GET /consequence` — BRO Asset Pre-Positioning
- **Method:** `GET`
- **Path:** `/priority-list` or `/consequence`
- **Description:** Ranks all 18 corridor segments by operational clearing priority for the Border Roads Organisation (BRO) and disaster response teams (`priority_score = risk_index * consequence_score`).
- **Query Parameters:**
  - `simulate_rain_mm` (*float*, optional)
  - `sort_by` (*string*, `"priority"` or `"risk"`, default `"priority"`)
- **Response (200 OK):**
```json
{
  "total_segments": 18,
  "top_priority_segment": "seg_04",
  "generated_at": "2026-10-06T03:00:00Z",
  "priority_list": [
    {
      "rank": 1,
      "segment_id": "seg_04",
      "segment_name": "Kaudiyala to Devprayag",
      "priority_score": 0.584,
      "hazard_risk_score": 0.73,
      "hazard_level": "High",
      "consequence_score": 0.80,
      "nearest_hospital_km": 14.2,
      "nearest_town": "Devprayag",
      "has_critical_bridge": true,
      "detour_available": false,
      "recommended_action": "Pre-stage heavy excavator at Devprayag bypass depot."
    }
  ]
}
```

---

### 7. `GET /closures` & `POST /admin/closure` — Official Highway Road Closures
- **`GET /closures` (Public)**
  - **Query Params:** `active_only` (*bool*, default `true`), `segment_id` (*string*, optional)
  - **Response (200 OK):** Returns a JSON list of active road closures:
```json
[
  {
    "id": 12,
    "segment_id": "seg_08",
    "status": "closed",
    "reason": "Active boulder fall and roadbed breach near km 108",
    "source": "SDRF Control Room",
    "starts_at": "2026-10-06T01:30:00Z",
    "ends_at": null,
    "created_by": "admin",
    "created_at": "2026-10-06T01:30:00Z"
  }
]
```

- **`POST /admin/closure` (Admin)**
  - **Headers:** `X-Admin-Key: <ADMIN_API_KEY>` or `X-API-Key: <ADMIN_API_KEY>`
  - **Request Body:**
```json
{
  "segment_id": "seg_08",
  "status": "closed",
  "reason": "Debris clearance underway by BRO Taskforce 66",
  "source": "BRO Official Bulletin",
  "starts_at": "2026-10-06T03:00:00Z",
  "ends_at": null
}
```
  - **Response (201 Created):** Returns the created `RoadClosureResponse` object.

- **`DELETE /admin/closure/{closure_id}` (Admin)**
  - **Headers:** `X-Admin-Key: <ADMIN_API_KEY>`
  - **Response (200 OK):** `{ "ok": true, "deleted_id": 12, "segment_id": "seg_08", "message": "Road closure #12 on seg_08 removed successfully." }`

---

### 8. `POST /field-report` — Crowd-Sourced Field Hazard Report
- **Method:** `POST`
- **Path:** `/field-report`
- **Rate Limit:** `5 requests / minute` per IP
- **Spatial Validation:** Coordinates must be within **3.0 km** of the NH-7 corridor polyline (otherwise rejected with `HTTP 422`).
- **Request Body:**
```json
{
  "lat": 30.1357,
  "lng": 78.3892,
  "reporter_name": "Harish Rawat (Taxi Driver)",
  "description": "Loose shale and water overflowing left lane near Shivpuri bend",
  "photo_url": "https://example.com/photos/slide_01.jpg"
}
```
- **Response (201 Created):**
```json
{
  "report_id": 101,
  "status": "Pending",
  "message": "Field report submitted successfully and queued for admin validation.",
  "submitted_at": "2026-10-06T03:05:00Z"
}
```

---

### 9. `POST /admin/validate-report` — Admin Report Validation & Flywheel
- **Method:** `POST`
- **Path:** `/admin/validate-report`
- **Headers:** `X-Admin-Key: <ADMIN_API_KEY>`
- **Request Body:**
```json
{
  "report_id": 101,
  "decision": "Validated",
  "notes": "Verified by BRO Sector Patrol; road clearing teams deployed."
}
```
- **Response (200 OK):**
```json
{
  "report_id": 101,
  "status": "Validated",
  "updated_at": "2026-10-06T03:10:00Z",
  "message": "Report #101 has been successfully updated to 'Validated'."
}
```

---

### 10. `GET /voice-alert` — Neural Voice Audio Streaming
- **Method:** `GET`
- **Path:** `/voice-alert`
- **Rate Limit:** `60 requests / minute`
- **Query Parameters:**
  - `segment_id` (*string*, optional, e.g. `"seg_08"`)
  - `from` & `to` (*string*, optional, for route voice advisory)
  - `lang` (*string*, `"en"` or `"hi"`, default `"en"`)
  - `simulate_rain_mm` (*float*, optional)
- **Response:**
  - If gTTS is online: `Content-Type: audio/mpeg` (synthesized MP3 binary).
  - If offline/headless: `Content-Type: application/json` returning text payload with `tts: "browser"` for Web Speech API client synthesis.

---

### 11. `GET /offline-pack` — Mobile Disaster Survival Pack
- **Method:** `GET`
- **Path:** `/offline-pack`
- **Headers Supported:** `If-None-Match: "<etag>"`
- **Response (200 OK or 304 Not Modified):**
  - Ultra-lightweight payload (< 5 KB gzipped, < 17 KB uncompressed) containing all 18 simplified segment geometries, local hospitals, and emergency contacts.
```json
{
  "version": "sha256-4b9e28...",
  "generated_at": "2026-10-06T03:00:00Z",
  "emergency_contacts": [
    { "name": "National Emergency Helpline", "number": "112" }
  ],
  "segments": [
    {
      "id": "seg_01",
      "name": "Rishikesh to Shivpuri",
      "name_hi": "ऋषिकेश से शिवपुरी",
      "risk_level": "Low",
      "risk_score": 0.18,
      "nearest_hospital": "AIIMS Rishikesh (5.2 km)",
      "advisory_en": "Normal transit conditions.",
      "advisory_hi": "सामान्य यातायात स्थिति।"
    }
  ]
}
```

---

### 12. `POST /webhook/sms` — Two-Way Twilio SMS Query Interface
- **Method:** `POST`
- **Path:** `/webhook/sms`
- **Headers:** `X-Twilio-Signature` (HMAC verification when `TWILIO_AUTH_TOKEN` is configured)
- **Form-Encoded Body:** `Body=NH7+SEG08&From=%2B919876543210`
- **Response (200 OK):** Returns TwiML XML `<Response><Message>...</Message></Response>`.

---

## 7. Background Workers & Alert Dispatcher Engine

The automated notifier worker (`app/alert_dispatcher.py`) runs periodically via APScheduler:
- **Interval:** Every 10 minutes (`ALERT_DISPATCH_INTERVAL_MINUTES = 10`, fallback `ALERT_CHECK_INTERVAL`).
- **Data Source:** Evaluates live risk using **real weather only** (simulation parameters are ignored).
- **Severity Trigger Condition:** Alerts dispatch ONLY when a subscriber's monitored segment reaches **High** or **Very High** ($\text{score} \ge 0.50$).
- **Escalation-Only Guardrail:** Implements severity ranking (`Low: 0`, `Moderate: 1`, `High: 2`, `Very High: 3`). Subsequent alerts are only sent if the risk level escalates to a higher severity tier (`SEVERITY_RANK[current] > SEVERITY_RANK[last]`). When risk subsides to Moderate or Low, the downgrade is recorded silently without sending misleading warning messages.
- **Cooldown Constraint:** Enforces a strict **3-hour cooldown** (`ALERT_COOLDOWN_HOURS = 3.0`) per user and segment to prevent notification fatigue.
- **Hazard Driver Messaging:** Messages dynamically cite heavy rain if $R_{3\text{d}} \ge 25\text{ mm}$ or geological slope instability during dry weather conditions.

---

## 8. Environment Configuration Reference

All configuration is managed centrally in `app/config.py`. Key operational variables:

| Variable | Type | Default | Description |
|---|:---:|:---:|---|
| **`ENV`** | `str` | `"development"` | Set to `"production"` to enforce secret keys and strict CORS. |
| **`PORT`** | `int` | `8000` | Backend HTTP listening port. |
| **`ADMIN_API_KEY`** | `str` | `""` | Secret admin key. Required at startup if `ENV=production`. |
| **`PER_SEGMENT_WEATHER`** | `bool` | `false` | `false` = 5-station corridor mode (hardened default); `true` = 18-segment hourly engine. |
| **`BACKTEST_ENABLED`** | `bool` | `false` | Enables `as_of` historical Time Machine parameter on `/risk-map`. |
| **`TIME_AWARE_PLANNER`** | `bool` | `true` | Enables arrival ETA forecasting on `/route-risk`. |
| **`DEMO_MODE`** | `bool` | `false` | Pins weather strictly to local snapshot for 100% offline, reproducible demos. |
| **`ENABLE_SCHEDULER`** | `bool` | `true` | Runs background weather and alert dispatcher workers. |
| **`ALERT_DISPATCH_INTERVAL_MINUTES`** | `int` | `10` | Frequency of automated alert dispatcher check (compat: `ALERT_CHECK_INTERVAL`). |
| **`ALERT_COOLDOWN_HOURS`** | `float` | `3.0` | Minimum interval between repeat notifications for same segment. |
| **`DRY_RUN`** | `bool` | `true` | When `true`, simulates notification delivery without consuming Twilio SMS credits. |
| **`TWILIO_FROM`** | `str` | `""` | Registered Twilio phone number (compat: `TWILIO_PHONE_NUMBER`). |
| **`TWILIO_ACCOUNT_SID`** | `str` | `""` | Twilio account identifier. |
| **`TWILIO_AUTH_TOKEN`** | `str` | `""` | Twilio authorization secret. |
| **`TELEGRAM_BOT_TOKEN`** | `str` | `""` | Bot token for Telegram alert integration. |

---

## 9. Synthetic Replay & Demo Mode Guardrails

1. **`DEMO_MODE=true`:** When set, the risk engine bypasses the network entirely and loads `data/rain_snapshot.json`. All responses include genuine `weather_age_minutes` telemetry.
2. **Synthetic Backtest Disclosure:** `GET /backtest-summary` and `scripts/backtest.py` execute deterministic validation harness tests. When synthetic event mode is active, results are explicitly labeled as **Synthetic Demonstration Backtest** to prevent confusion with empirical multi-year geological field studies.

---

## 10. Ready-to-Use Frontend Integration Snippets

### TypeScript / Axios Client
```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000,
});

// 1. Fetch Corridor Risk Map
export async function getRiskMap(simulateRainMm?: number, lang: 'en' | 'hi' = 'en') {
  const params: Record<string, any> = { lang };
  if (simulateRainMm !== undefined) params.simulate_rain_mm = simulateRainMm;
  const res = await api.get('/risk-map', { params });
  return res.data;
}

// 2. Evaluate Route Risk & Time-Aware Trip Plan
export async function planTrip(fromSeg: string, toSeg: string, date: string, departTimeIso?: string) {
  const params: Record<string, any> = {
    from_segment: fromSeg,
    to_segment: toSeg,
    date: date,
    speed_kmph: 30.0,
  };
  if (departTimeIso) params.depart_time = departTimeIso;
  const res = await api.get('/route-risk', { params });
  return res.data;
}

// 3. Register SMS / Push Alert Subscription
export async function subscribeToAlerts(name: string, contact: string, segmentId: string, channel: 'SMS' | 'WhatsApp' | 'Email' = 'SMS') {
  const res = await api.post('/subscribe', {
    name,
    phone_or_email: contact,
    segment_id: segmentId,
    channel,
    consent: true,
  });
  return res.data;
}

// 4. Submit Crowd-Sourced Field Report
export async function submitReport(lat: number, lng: number, name: string, desc: string, photoUrl?: string) {
  const res = await api.post('/field-report', {
    lat,
    lng,
    reporter_name: name,
    description: desc,
    photo_url: photoUrl || null,
  });
  return res.data;
}
```

---

*This document is the authoritative Antigravity backend specification. Synchronized with the live FastAPI implementation.*
