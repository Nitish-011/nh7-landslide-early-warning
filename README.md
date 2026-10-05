# NH-7 Real-Time Landslide Risk Backend

> **Corridor Scope**: NH-7 Highway, Uttarakhand, India (Rishikesh to Joshimath, 247.37 km across 18 road segments)
> **Route Progression**: Rishikesh ➔ Devprayag ➔ Srinagar ➔ Rudraprayag ➔ Karnaprayag ➔ Nandprayag ➔ Chamoli ➔ Pipalkoti ➔ Joshimath

A production-grade, hackathon-ready FastAPI backend serving real-time landslide risk assessments, route forecasting, subscriber alerts, crowd-sourced field hazard reporting, and historical slope failure records.

Built with stable API contracts so mobile app and web frontend teams can integrate against realistic mock data today, with zero API shape changes when the machine learning prediction model is plugged in.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.11+ (tested on Python 3.14)
- Pip dependencies installed:

```bash
pip install -r requirements.txt
```

### 2. Run the Server
Launch the server using the companion launcher script:

```bash
python run.py
```

Or using Uvicorn directly:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server binds to `0.0.0.0:8000`. On startup, `run.py` detects your local network IP (e.g. `http://192.168.1.15:8000`) so you can share it immediately with teammates testing from mobile phones or other laptops.

---

## 🗺️ Interactive Test Frontend & Documentation

- **Interactive Map & Test Workbench**: [http://localhost:8000/](http://localhost:8000/)  
  *Features a full Leaflet.js map with color-coded risk polylines, historical landslide pins, and test forms to hit every API endpoint with live JSON response visualization.*
- **Swagger Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Reference**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔄 Resetting the Database

The SQLite database is located at `data/landslide_nh7.db`. It auto-seeds on first startup.

To wipe and re-seed the database back to clean demo data at any time:

```bash
python reset_db.py
```

This restores:
- All 18 NH-7 road segments with authentic coordinates and hazard ratings
- 3 sample alert subscriptions (WhatsApp, Email, SMS)
- 3 sample field reports (Pending and Validated)
- 7 verified historical landslide incidents along NH-7

---

## 📝 Logging & Demo Audit Trail

Every incoming request and outgoing response is automatically logged to both **console (stdout)** and a **rotating log file**:

- **Log File Location**: `logs/backend.log` (Rotates at 5 MB, keeps 5 backups, UTF-8 encoded).
- **Log Format**:
  ```
  YYYY-MM-DD HH:MM:SS | LEVEL   | [logger.name] [REQ_ID] DETAILS
  ```
- **Recorded Data**:
  - **Incoming**: HTTP Method, URL Path, Client IP, Query parameters, and JSON Request Body payload.
  - **Outgoing**: HTTP Status Code and Response Execution Time in milliseconds.
  - **Exceptions**: Full Python stack traces for unhandled errors.

Open `logs/backend.log` after your demo to inspect the exact chronological execution record.

---

## 📡 API Endpoints Specification

### 1. `GET /risk-map`
Returns all 18 segments along NH-7 with current `risk_level` and `risk_score`.
- **Response**:
```json
{
  "corridor": "NH-7 Uttarakhand (Rishikesh - Karnaprayag - Joshimath)",
  "total_segments": 18,
  "high_or_very_high_risk_count": 7,
  "segments": [
    {
      "id": "seg_01",
      "name": "Rishikesh to Shivpuri",
      "sequence_order": 1,
      "start_lat": 30.0869,
      "start_lng": 78.2676,
      "end_lat": 30.1357,
      "end_lng": 78.3892,
      "subpoints": [[30.0869, 78.2676], [30.098, 78.305], ...],
      "risk_level": "Low",
      "risk_score": 0.15,
      "updated_at": "2026-10-02T10:00:00Z"
    }
  ]
}
```

### 2. `GET /route-risk?from_segment=&to_segment=&date=`
Calculates route risk for travel between two segments on a target date.
- **Query Params**:
  - `from_segment` (e.g. `seg_01`)
  - `to_segment` (e.g. `seg_09`)
  - `date` (`YYYY-MM-DD`, e.g. `2026-10-15`)
- **Determinism**: Uses `hashlib.md5` so results are guaranteed stable across restarts and different client requests.
- **Aggregation**: Evaluates fine-grained sub-points (2–4 km) and computes segment risk as `max(subpoint_scores)`.
- **Response**: Returns route summary, maximum risk, average risk, travel advisory, and ordered segments.

### 3. `POST /subscribe`
Registers a traveler or resident for alerts on a specific highway segment.
- **Body**:
```json
{
  "name": "Gaurav Bhatt",
  "phone_or_email": "+919876543210",
  "segment_id": "seg_08",
  "channel": "WhatsApp"
}
```
*(Channel must be `"WhatsApp"`, `"SMS"`, or `"Email"`)*
- **Response (201 Created)**: Returns `{ "subscription_id": 4, "status": "Active", "message": "...", "subscription": { ... } }`

### 4. `GET /alerts?user_id=`
Retrieves active hazard warnings for a user's subscription.
- **Query Param**: `user_id` (integer `subscription_id` returned by `POST /subscribe`).
- **Response**:
```json
{
  "user_id": 1,
  "subscriber_name": "Amit Rawat",
  "subscribed_segment": "seg_08 (Srinagar to Sirobagarh)",
  "active_alerts_count": 1,
  "alerts": [
    {
      "alert_id": "ALT-NH7-SEG_08-01",
      "segment_id": "seg_08",
      "segment_name": "Srinagar to Sirobagarh",
      "severity": "Very High",
      "risk_score": 0.92,
      "message": "HIGH ALERT on Srinagar to Sirobagarh: Geological instability & active rockfall hazard...",
      "channel": "WhatsApp",
      "issued_at": "2026-10-02T14:30:00Z"
    }
  ]
}
```

### 5. `POST /field-report`
Submits crowd-sourced or patrol field observations of landslides, falling rocks, or road damage.
- **Body**:
```json
{
  "lat": 30.2392,
  "lng": 78.8544,
  "description": "Continuous rockfall and debris rolling onto uphill lane near milestone 114.",
  "photo_url": "https://example.com/photos/rockfall.jpg",
  "reporter_name": "Driver Suresh"
}
```
- **Response (201 Created)**: Returns `{ "report_id": 4, "status": "Pending", "message": "Field report submitted successfully..." }`

### 6. `POST /admin/validate-report`
Admin endpoint to review and validate or reject a pending field report.
- **Body**:
```json
{
  "report_id": 4,
  "decision": "Validated",
  "notes": "Verified by BRO highway patrol unit."
}
```
*(Decision must be `"Validated"` or `"Rejected"`)*
- **Response**: `{ "report_id": 4, "status": "Validated", "updated_at": "...", "message": "..." }`

### 7. `GET /history`
Returns verified historical landslide incidents along NH-7 (Sirobagarh, Chamoli, Pipalkoti, Tangani, Byasi, Nandprayag, Teen Dhara).
- **Response**: `{ "total_events": 7, "events": [ ... ] }`

### 8. `GET /model-info`
Returns complete, verifiable transparency metadata regarding the trained landslide susceptibility model:
- **Features Used**: Topographic and hydrological DEM features (`dem_slope_deg`, `dem_relief_300m`, `dem_curvature`, etc.)
- **Coefficients / Importance**: Held-out spatial block permutation importance ($\Delta\text{AUC}$)
- **Sample Sizes**: 309 observed landslide scars (presence) and 927 sampled road background negatives (absence) across 247.37 km
- **Out-of-Fold Validation Metrics**: Pooled AUC (`0.767` [95% CI: `0.680` – `0.802`]), Block AUC Mean (`0.664` [95% CI: `0.630` – `0.701`]), Spearman rank correlation ($\rho = 0.653$, $p = 0.0033$)
- **Heuristic Parameters**: $k_{\text{rain}} = 0.4$, $k_{\text{terrain}} = 0.6$, $\text{DRY\_CAP\_MM} = 25.0\text{ mm}$, categorical risk-level thresholds
- **Limitations**: Comprehensive operational constraints and data boundaries
- **Data Sources**: Official citations for the Mey et al. (2024) inventory, Copernicus 30m DEM, and Open-Meteo forecasts
- **Scope**: Evaluated corridor alignment (`Rishikesh to Joshimath, 247.37 km`)

---

## ⚠️ Limitations & Scientific Boundaries

1. **Single-Season Inventory**: The baseline terrain susceptibility model was trained and cross-validated on post-monsoon 2022 survey data (Mey et al., 2024, $N = 309$ road-blocking landslides). It does not capture multi-year, decadal, or extreme epochal recurrence intervals.
2. **18-Segment Spatial Evaluation**: While the underlying highway alignment features 990 deduplicated evaluation points at 250 m resolution, backend hazard reporting aggregates these into 18 operational segments using the 90th percentile ($p_{90}$) worst-stretch rule. This aggregation may smooth over localized, micro-scale slope cuts.
3. **Coarse Numerical Weather Forecast Grid**: Precipitation forecasts are obtained from Open-Meteo at ~11 km spatial resolution. While effective for synoptic monsoon fronts, this resolution cannot resolve localized convective cloudburst cells in steep Himalayan tributary valleys.
4. **Uncalibrated Dynamic Rainfall Term**: The rainfall coupling term weight ($k_{\text{rain}} = 0.4$) and 100 mm saturation reference are demo heuristics rather than empirically calibrated rainfall-duration-intensity thresholds.
5. **Not an Official Warning System**: All scores and advisories represent physically motivated statistical relative risk indices designed for research, verification, and technical demonstration. They do not constitute official statutory emergency warnings from the Geological Survey of India (GSI) or the National Disaster Management Authority (NDMA).

---

## 🧠 Model Integration Architecture

The corridor is modeled as 18 human-readable display segments along the 247.37 km Rishikesh to Joshimath highway. Underneath each segment, 2–4 km checkpoint coordinates are embedded in `subpoints`. 

The machine learning pipeline combines the static Copernicus 30m DEM Random Forest susceptibility model with live antecedent precipitation to produce the `risk_index` (0.0 to 1.0 relative risk index), while maintaining legacy `risk_score` fields for 100% backwards compatibility.

