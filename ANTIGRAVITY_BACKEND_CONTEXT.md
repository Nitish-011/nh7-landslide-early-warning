# 🧠 Antigravity AI Agent Guide: NH-7 Landslide Early Warning Backend

> **Target Agent:** Antigravity 2.0 / Gemini / Claude Coding Agents  
> **Workspace Purpose:** Build new mobile apps (Flutter, React Native, Swift, Kotlin) and web frontends (React, Next.js, Vue, Tailwind) connecting to this FastAPI backend.  
> **Backend Host:** `http://localhost:8000` (Local Dev) | `http://0.0.0.0:8000` (Docker / LAN)  
> **Interactive Swagger OpenAPI:** `http://localhost:8000/docs`  
> **Raw OpenAPI JSON:** `http://localhost:8000/openapi.json`  

---

## 1. Core Mental Model for AI Agents

When building a frontend for this repository, you do **not** need to simulate or mock the backend logic. The backend is a fully functional, production-hardened FastAPI application with real machine learning inference and real-time weather integration.

```
+---------------------------------------------------------------------------------------------------+
|               STATIC TOPOGRAPHY BASELINE (Physical Laws of Nature)                                |
|  - 30-meter Copernicus DEM Topography (Slope, 300m Local Relief, TPI, Curvature)                  |
|  - 247.37 km NH-7 Highway Alignment (Rishikesh to Joshimath, geojson/nh7_route.geojson)          |
|  - 18 Sequence-Ordered Segments (seg_01 to seg_18)                                                |
|  - Random Forest v2 Trained Ensemble (model/nh7_static_model_v2.joblib, Spatial OOF ROC-AUC 0.767)  |
+-------------------------------------------------+-------------------------------------------------+
                                                  |
                                                  v
+---------------------------------------------------------------------------------------------------+
|               DYNAMIC REAL-TIME ENGINE (Live State & Weather)                                     |
|  - Live 3-Day Multi-Station Rainfall (Open-Meteo across 5 corridor stations, 5-min cache TTL)      |
|  - Dynamic Risk Formula: score = min(0.65*terrain + 0.35*min(R_3d/100, 1.0), 1.0)                 |
|  - Dynamic Storm Simulation Overrides (?simulate_rain_mm=...)                                     |
|  - Time-Aware Arrival-Hour Trip Forecasting (POST /trip-planner)                                  |
|  - Active Road Closures & Bypass Routing (GET /closures)                                          |
|  - Crowd-Sourced Field Reports & Validation Flywheel (POST /field-report)                         |
|  - Bilingual English/Hindi Streaming Voice Alerts (GET /voice-alert?lang=hi)                      |
|  - Ultra-Compact Offline Survival Pack with ETag/304 Caching (GET /offline-pack, < 17 KB)        |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Segment Master Registry (18 Segments)

Use these exact IDs, sequence orders, and names in your UI dropdowns, route selectors, and map polylines:

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

When building maps, badges, and progress meters, adhere strictly to these color tokens:

```typescript
export const RISK_COLORS = {
  Low: {
    label: "Low",
    minScore: 0.00,
    maxScore: 0.34,
    color: "#10b981",       // Emerald Green
    bgLight: "rgba(16, 185, 129, 0.15)",
    border: "rgba(16, 185, 129, 0.35)",
  },
  Moderate: {
    label: "Moderate",
    minScore: 0.35,
    maxScore: 0.59,
    color: "#f59e0b",       // Warm Amber
    bgLight: "rgba(245, 158, 11, 0.15)",
    border: "rgba(245, 158, 11, 0.35)",
  },
  High: {
    label: "High",
    minScore: 0.60,
    maxScore: 0.79,
    color: "#f97316",       // Vivid Orange
    bgLight: "rgba(249, 115, 22, 0.15)",
    border: "rgba(249, 115, 22, 0.35)",
  },
  VeryHigh: {
    label: "Very High / Severe",
    minScore: 0.80,
    maxScore: 1.00,
    color: "#ef4444",       // Danger Crimson Red
    bgLight: "rgba(239, 68, 68, 0.15)",
    border: "rgba(239, 68, 68, 0.35)",
  },
  Closed: {
    label: "Closed / Blocked",
    color: "#991b1b",       // Dark Red / Striped Hatched
    bgLight: "rgba(153, 27, 27, 0.25)",
  }
};
```

---

## 4. Complete API Endpoint Specification

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
- **Query Parameters:**
  - `simulate_rain_mm` (*float*, optional): Injects synthetic rainfall (e.g. `40`, `100`, `140`). Overrides live weather for storm stress-testing.
  - `as_of` (*string YYYY-MM-DD*, optional): Replays historical date weather from ERA5-Land reanalysis archive (e.g. `2023-08-14`).
  - `lang` (*string*, optional, default `"en"`): Pass `"hi"` for Hindi Devanagari translation.
  - `refresh_weather` (*bool*, optional, default `false`): Bypasses 5-min cache to force fresh Open-Meteo fetch.
- **Response (200 OK):**
```json
{
  "corridor": "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
  "total_segments": 18,
  "high_or_very_high_risk_count": 2,
  "rain_status": "live",
  "as_of": "2026-10-06T03:00:00Z",
  "is_simulated": false,
  "segments": [
    {
      "id": "seg_01",
      "name": "Rishikesh to Shivpuri",
      "name_en": "Rishikesh to Shivpuri",
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
      "risk_level_en": "Low",
      "risk_score": 0.18,
      "terrain_score": 0.32,
      "r3d_mm": 11.8,
      "rain_24h_mm": 4.2,
      "forecast_24h_mm": 5.1,
      "forecast_72h_mm": 14.8,
      "main_driver": "Mild slope gradient (14°), stable foothill geology",
      "main_driver_en": "Mild slope gradient (14°), stable foothill geology",
      "closure": null,
      "adjusted_risk_level": null,
      "ground_report_count_24h": 0,
      "updated_at": "2026-10-06T03:00:00Z"
    }
  ]
}
```

---

### 3. `POST /trip-planner` — Time-Aware Route & Safe Departure Advisor
- **Method:** `POST`
- **Path:** `/trip-planner`
- **Description:** Analyzes journey between two segments at a specified departure time. Calculates progressive arrival ETAs for every intermediate sector and checks forecasted storm intensity at each ETA.
- **Request Body:**
```json
{
  "origin": "seg_01",
  "destination": "seg_18",
  "depart_time": "2026-10-06T08:00:00Z",
  "speed_kmph": 30.0,
  "simulate_rain_mm": null,
  "lang": "en"
}
```
- **Response (200 OK):**
```json
{
  "recommendation": {
    "action": "CAUTION",
    "headline": "Travel with caution during morning hours; thunderstorm peak expected near Pipalkoti after 14:00.",
    "safe_departure_window": "06:00 - 08:30 IST",
    "total_distance_km": 247.37,
    "estimated_duration_hours": 8.25,
    "max_risk_level": "High",
    "max_risk_segment": "seg_08 (Srinagar to Sirobagarh)",
    "active_closures_encountered": 0
  },
  "departure_timeline": [
    {
      "depart_time": "2026-10-06T06:00:00Z",
      "overall_risk": "Moderate",
      "advisory": "Best window: clears high-gradient sectors before noon rain peak."
    },
    {
      "depart_time": "2026-10-06T08:00:00Z",
      "overall_risk": "High",
      "advisory": "Moderate exposure: expect delay near Sirobagarh."
    },
    {
      "depart_time": "2026-10-06T12:00:00Z",
      "overall_risk": "Very High",
      "advisory": "AVOID: intersects afternoon convective cloudburst in Chamoli gorge."
    }
  ],
  "route_segments": [
    {
      "segment_id": "seg_01",
      "segment_name": "Rishikesh to Shivpuri",
      "sequence_order": 1,
      "eta_ist": "2026-10-06T08:35:00+05:30",
      "rain_at_eta_mm": 2.1,
      "risk_level_at_eta": "Low",
      "risk_score_at_eta": 0.16
    }
  ]
}
```

---

### 4. `GET /priority-list` & `GET /consequence` — BRO Clearing Priorities
- **Method:** `GET`
- **Path:** `/priority-list` or `/consequence`
- **Description:** Pre-positioning priority list for Border Roads Organisation (BRO) and disaster response teams.
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

### 5. `GET /closures` & `POST /admin/closure` — Highway Road Closures
- **`GET /closures`**
  - **Query Params:** `active_only` (*bool*, default `true`), `segment_id` (*string*, optional)
  - **Response (200 OK):**
```json
{
  "active_closures_count": 1,
  "closures": [
    {
      "id": 12,
      "segment_id": "seg_08",
      "segment_name": "Srinagar to Sirobagarh",
      "status": "closed",
      "reason": "Active boulder fall and roadbed breach near km 108",
      "source": "SDRF Control Room",
      "starts_at": "2026-10-06T01:30:00Z",
      "ends_at": null
    }
  ]
}
```

- **`POST /admin/closure`**
  - **Headers:** `X-Admin-Key: admin-dev-secret-key-nh7` (or `X-API-Key`)
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
  - **Response (201 Created):** `{ "success": true, "closure_id": 13, "status": "closed" }`

- **`DELETE /admin/closure/{closure_id}`**
  - **Headers:** `X-Admin-Key: admin-dev-secret-key-nh7`
  - **Response (200 OK):** `{ "success": true, "message": "Closure removed. Highway reopened." }`

---

### 6. `POST /field-report` — Crowd-Sourced Field Hazard Report
- **Method:** `POST`
- **Path:** `/field-report`
- **Rate Limit:** `5 requests / minute` per IP
- **Spatial Validation:** Coordinates must be within **3.0 km** of the NH-7 polyline corridor (otherwise rejected with `422 Unprocessable Entity`).
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
  "id": 1463,
  "segment_id": "seg_01",
  "lat": 30.1357,
  "lng": 78.3892,
  "reporter_name": "Harish Rawat (Taxi Driver)",
  "description": "Loose shale and water overflowing left lane near Shivpuri bend",
  "status": "pending",
  "reported_at": "2026-10-06T03:05:00Z"
}
```
- **Error Responses:**
  - `422 Unprocessable Entity`: Coordinates are outside the 3.0 km corridor buffer.
  - `409 Conflict`: Duplicate report from same IP at same location within 10 minutes.
  - `429 Too Many Requests`: Rate limit exceeded.

---

### 7. `POST /admin/validate-report` — Admin Report Validation & Flywheel
- **Method:** `POST`
- **Path:** `/admin/validate-report`
- **Headers:** `X-Admin-Key: admin-dev-secret-key-nh7`
- **Request Body:**
```json
{
  "report_id": 1463,
  "status": "verified",
  "verified_by": "District Magistrate Control Room"
}
```
- **Response (200 OK):**
```json
{
  "success": true,
  "report_id": 1463,
  "status": "verified",
  "flywheel_triggered": true,
  "message": "Report verified. Logged to validated_reports.csv for model refinement."
}
```

---

### 8. `GET /voice-alert` & `GET /alerts/voice/{id}` — Neural Voice Audio Streaming
- **Method:** `GET`
- **Path:** `/voice-alert` or `/alerts/voice/{alert_id}`
- **Query Parameters:**
  - `segment_id` (*string*, e.g. `"seg_01"`)
  - `lang` (*string*, `"en"` or `"hi"`, default `"en"`)
- **Response:**
  - `Content-Type: audio/mpeg`
  - Audio stream (MP3) generated via neural text-to-speech with sub-15ms cached delivery.
- **Frontend Usage (HTML5 / React):**
```javascript
const audio = new Audio("http://localhost:8000/voice-alert?segment_id=seg_08&lang=hi");
audio.play();
```

---

### 9. `GET /offline-pack` — Mobile Disaster Survivor Pack
- **Method:** `GET`
- **Path:** `/offline-pack`
- **Headers Supported:** `If-None-Match: "<etag>"`
- **Response (200 OK or 304 Not Modified):**
  - `ETag: "w/3a8f9c1..."`
  - `Content-Encoding: gzip` (< 5 KB compressed, < 17 KB uncompressed)
```json
{
  "version": "sha256-4b9e28...",
  "generated_at": "2026-10-06T03:00:00Z",
  "emergency_contacts": [
    { "name": "Uttarakhand State Emergency Hotline", "phone": "112" },
    { "name": "BRO Control Room (Gauchar)", "phone": "+91-1363-240123" },
    { "name": "SDRF Disaster Response Force", "phone": "1070" },
    { "name": "Chamoli Police Control Room", "phone": "+91-1372-252100" }
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

### 10. `POST /webhook/sms` — Two-Way Twilio SMS Query Interface
- **Method:** `POST`
- **Path:** `/webhook/sms`
- **Headers:** `X-Twilio-Signature` (HMAC verification when `TWILIO_AUTH_TOKEN` is set)
- **Form Encoded Body:** `Body=NH7+HELP&From=%2B919876543210`
- **Supported SMS Commands:**
  - `NH7 HELP`: Lists query format.
  - `NH7 SEG08`: Queries Srinagar to Sirobagarh status.
  - `NH7 ROUTE RISHIKESH JOSHIMATH`: Returns route clearance.
- **Response (200 OK):**
  - `Content-Type: application/xml`
  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <Response>
    <Message>NH-7 seg_08 (Srinagar-Sirobagarh): MODERATE RISK (0.42). Rain: 18mm. Road OPEN. Drive carefully in day.</Message>
  </Response>
  ```

---

## 5. Ready-to-Use Frontend Integration Snippets

### TypeScript / Axios Client Boilerplate
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

// 2. Plan a Safe Trip
export async function planTrip(origin: string, destination: string, departTimeIso: string) {
  const res = await api.post('/trip-planner', {
    origin,
    destination,
    depart_time: departTimeIso,
    speed_kmph: 30.0,
  });
  return res.data;
}

// 3. Submit a Field Hazard Report
export async function submitReport(lat: number, lng: number, name: string, desc: string) {
  const res = await api.post('/field-report', {
    lat,
    lng,
    reporter_name: name,
    description: desc,
  });
  return res.data;
}
```

---

*This document is the official Antigravity backend specification. Keep this file updated if new endpoints or parameters are added.*
