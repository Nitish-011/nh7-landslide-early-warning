# AGENTS.md — Antigravity Agent Guidelines for NH-7 Landslide System

Welcome, Antigravity Agent! This document defines the workspace context and engineering rules when building applications or extending the NH-7 Landslide Early Warning platform.

---

## 🎯 Workspace Overview

- **Primary Mission:** Real-time geohazard early warning, safe route planning, and disaster resilience for National Highway 7 (Rishikesh to Joshimath, Uttarakhand, 247.37 km, 18 segments).
- **Backend Framework:** FastAPI (Python 3.11+) running at `http://localhost:8000`.
- **Complete Route & Contract Reference:** See [`ANTIGRAVITY_BACKEND_CONTEXT.md`](ANTIGRAVITY_BACKEND_CONTEXT.md) for every single endpoint, parameter, request body, and response JSON schema.
- **Frontend Architecture:** The existing workbench is served from [`app/static/index.html`](app/static/index.html). If you are building a new React / Next.js / Flutter / Mobile client, connect directly to `http://localhost:8000`.

---

## 🧭 Key Rules for Building Frontends & Features

1. **Do NOT mock the backend:** The backend is fully live and operational. Use `http://localhost:8000/risk-map`, `http://localhost:8000/trip-planner`, etc.
2. **Corridor Geofence Guardrail:** Any crowd-sourced field report (`POST /field-report`) MUST have coordinates within 3.0 km of the highway polyline (`geojson/nh7_route.geojson`). Points further away will receive `HTTP 422`.
3. **Dry Weather Cap:** Risk cannot exceed "Moderate" if 3-day antecedent rainfall is under 25mm (`DRY_CAP_MM = 25.0`), preventing false alarms during dry weather.
4. **Storm Simulation:** To test disaster responses, use `?simulate_rain_mm=120` on `/risk-map`, `/route-risk`, and `/alerts`.
5. **Bilingual Support:** All route risk, alerts, and segment names support Hindi Devanagari by passing `lang=hi`.
6. **Voice Alerts:** Spoken neural audio alerts are streamed from `GET /voice-alert?lang=hi` or `lang=en`.
7. **Offline Mode:** Mobile apps can download `GET /offline-pack` (< 17 KB) and use `ETag` + `If-None-Match` for `304 Not Modified` bandwidth-saving checks.

---

## 🚀 Running & Verifying the Backend

```bash
# Start backend server
python run.py

# Run complete 122 automated test suite
python -m pytest

# Run pre-flight demo verification script
python scripts/demo_check.py
```

For complete technical and model specifications:
- [ANTIGRAVITY_BACKEND_CONTEXT.md](ANTIGRAVITY_BACKEND_CONTEXT.md) — Exhaustive API routes, request/response contracts & code snippets.
- [FEATURES.md](FEATURES.md) — 12 feature domains and database schemas.
- [MODEL_PERFORMANCE.md](MODEL_PERFORMANCE.md) — Spatial cross-validation benchmarks and model card.
- [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) — Browser UI testing walkthrough.
