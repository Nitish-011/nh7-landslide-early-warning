# 🖥️ NH-7 Workbench: Complete Frontend Testing & Verification Guide

> **Target Audience:** Hackathon Judges, Evaluators, Frontend Developers, Teammates & Friends  
> **Testing Environment:** Interactive Web Workbench at `http://localhost:8000`  
> **Prerequisites:** Python 3.11+, Chrome/Edge/Firefox/Safari browser  
> **Zero Coding Required:** Every single feature can be tested and verified directly through the browser!

---

## 1. Getting Started: Booting the Server

1. Open your terminal in the project directory:
   ```bash
   python run.py
   ```
2. You will see the server initialization log:
   ```
   INFO: Uvicorn running on http://0.0.0.0:8000
   INFO: Local Network Access: http://192.168.1.XX:8000
   ```
3. Open your browser and navigate to:  
   👉 **`http://localhost:8000`**

---

## 2. Interface Anatomy Overview

The workbench has three primary visual zones:

```
+---------------------------------------------------------------------------------------------------+
| [TOP FLOATING HUD]  Corridor: NH-7 (247 km) | Segments: 18 | High/Severe: 0 | Weather: Live [●]   |
+-------------------------------------------------------------------+-------------------------------+
|                                                                   |  [SIDEBAR HEADER & LANG]      |
|                                                                   |  ⛰️ NH-7 Risk API Workbench   |
|                                                                   |  [🇬🇧 EN / 🇮🇳 HI Toggle]     |
|                                                                   +-------------------------------+
|                                                                   |  [9 NAVIGATION TABS]          |
|                                                                   |  🗺️ 🚗 🚧 🚜 🌧️ 📢 🔔 🛡️ 📦    |
|                      LEAFLET 2D/3D GIS MAP                        +-------------------------------+
|                                                                   |                               |
|        - Interactive 18 Segment Polylines                         |       ACTIVE TAB PANE         |
|        - Risk Color Coding (Green, Amber, Red, Purple)           |                               |
|        - 309 Historical Landslide Scars Pins                      |   Interactive Controls,       |
|        - Crowd Report & Closure Markers                           |   Forms, Sliders, Audio       |
|                                                                   |                               |
+-------------------------------------------------------------------+-------------------------------+
| [BOTTOM LIVE JSON CONSOLE]                                                                        |
| HTTP GET /risk-map | Status: [200 OK] | Duration: 14.2ms | { "corridor": "NH-7", ... }             |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Step-by-Step Testing Scenarios

---

### 🧪 Scenario 1: Corridor Risk Map & Segment Deep Inspector
*Goal: Verify baseline 18-segment risk scores, geomorphological drivers, and historical landslide scars.*

1. Click the **🗺️ Risk Map** tab in the sidebar.
2. Click the **⚡ Fetch Live Risk Map** button.
   - **What to look for on the Map:** The 247 km highway corridor lights up in 18 color-coded segments (Green for Low risk, Yellow for Moderate, Orange for High, Red for Severe).
   - **What to look for in the Top HUD:** `Segments: 18` and `Weather: Live` with a glowing green pulse dot.
   - **What to look for in the Bottom Console:** `GET /risk-map` with a green `[200 OK]` pill and response latency `< 25ms`.
3. Click any polyline directly on the map (for example, near Devprayag or Sirobagarh).
   - **What to look for:** An interactive Leaflet popup opens showing:
     - Segment Name & ID (e.g. `seg_04: Kaudiyala to Devprayag`)
     - Risk Score & Classified Level
     - 3-Day Antecedent Rainfall ($R_{3\text{d}}$ in mm)
     - Primary Hazard Driver (e.g. *Steep road cut gradient ($> 34^\circ$)*)
4. Click the **📍 Mey Scars (309)** button.
   - **What to look for:** 309 discrete markers appear along the highway corridor representing verified historical landslide scars from the 2022 monsoon field survey (*Mey et al., 2024*).
   - Click any red pin to inspect its historical chainage marker and distance from the road centerline.

---

### 🧪 Scenario 2: Historical Disaster Time Machine Replay
*Goal: Replay the catastrophic August 12–14, 2023 Chamoli/Rishikesh cloudburst event using archived ERA5 weather.*

1. Under the **🗺️ Risk Map** tab, locate the **⏳ Time Machine Replay** card.
2. Ensure the historical date input is set to: **`2023-08-14`**.
3. Click **⏳ Replay Historical Date**.
   - **What to look for in the UI:** A purple **Freshness / Replay Banner** appears above the tabs:  
     `⏳ Historical Replay Mode: Simulating conditions as of 2023-08-14`.
   - **What to look for on the Map:** Segments along Chamoli and Kaudiyala turn fiery Red and Orange, reflecting the extreme historical downpours.
   - **What to look for in the Bottom Console:** `GET /risk-map?as_of=2023-08-14` returning cached ERA5 reanalysis data.

---

### 🧪 Scenario 3: Smart Safe Trip Planner & Departure Advisor
*Goal: Verify time-aware route risk forecasting, progressive waypoint ETAs, and departure window recommendations.*

1. Click the **🚗 Route Planner** tab in the sidebar.
2. Configure the trip parameters:
   - **Origin Segment:** `seg_01 (Rishikesh to Shivpuri)`
   - **Destination Segment:** `seg_18 (Helang to Joshimath)`
   - **Departure Time:** Leave as current time or select tomorrow morning.
   - **Average Transit Speed:** `30 km/h`
3. Click **🚗 Analyze Route Risk**.
   - **What to look for in the Result Box:**
     - Overall Recommendation Badge: `RECOMMENDED`, `CAUTION`, or `AVOID`.
     - Total Route Distance (~247.4 km) and Estimated Travel Duration (~8.2 hours).
     - Maximum Risk Segment along the journey.
     - **Progressive Waypoint ETAs:** Detailed schedule showing arrival hour at each town (e.g., Devprayag at 10:15, Srinagar at 11:30, Rudraprayag at 12:45).
     - **Departure Timeline Advisor:** Evaluates earlier and later departure slots (e.g., "Departing 2 hours earlier reduces cumulative storm exposure by 40%").

---

### 🧪 Scenario 4: Dynamic Road Closures & Live Detour Routing
*Goal: Report an emergency highway blockage and verify that the route planner immediately updates.*

1. Click the **🚧 Closures** tab in the sidebar.
2. In the **Report New Road Closure** form:
   - **Segment:** Select `seg_08 (Srinagar to Sirobagarh)`
   - **Closure Status:** `closed`
   - **Blockage Reason:** `Heavy debris and boulder fall blocking both lanes`
   - **Official Source:** `SDRF Field Unit 4`
3. Click **🚨 Submit Road Closure**.
   - **What to look for on the Map:** Segment 8 instantly turns into a flashing red hatched closure line with a hazard barrier icon.
   - **What to look for in the Closures list:** The new incident appears with an "Active" badge.
4. Now switch back to **🚗 Route Planner** (Tab 2) and hit **Analyze Route Risk**:
   - **What to look for:** The trip advisory immediately switches to **`AVOID`** or **`DETOUR REQUIRED`**, warning that `seg_08` is completely blocked!
5. Return to **🚧 Closures** and click **Reopen Road**:
   - **What to look for:** The segment clears from active closures and normal traffic resumes.

---

### 🧪 Scenario 5: BRO & SDRF Infrastructure Priority Engine
*Goal: Verify civil infrastructure consequence ranking and emergency bulldozer/excavator pre-staging order.*

1. Click the **🚜 BRO Priority** tab in the sidebar.
2. Click **⚡ Load BRO Operational Priority List**.
   - **What to look for in the Table:** All 18 highway segments are sorted by **Priority Score** ($\text{Risk} \times \text{Consequence}$):
     - **Rank #1–#3:** Segments with major bridges (Alaknanda confluence at Devprayag, Rudraprayag), high population centers, or zero alternative detour routes.
     - **Critical Assets Shown:** Distance to nearest trauma hospital (km), presence of major suspension bridges, and bypass road availability.
   - **Operational Takeaway:** Demonstrates to disaster authorities exactly where heavy clearing machinery should be stationed *before* a storm hits.

---

### 🧪 Scenario 6: Monsoon Storm & Cloudburst Weather Simulator
*Goal: Stress-test the entire 247 km highway by injecting synthetic rainfall intensities.*

1. Click the **🌧️ Weather Sim** tab in the sidebar.
2. Drag the **Simulated Rainfall Slider**:
   - **At 0 mm (Bone Dry):** Notice all segments drop to Low/Moderate. The `DRY_CAP_MM = 25.0` rule prevents false alarms.
   - **Click Preset "Moderate 35mm":** Sensitive slopes around Kaudiyala and Byasi elevate to Yellow/Amber.
   - **Click Preset "Severe 85mm":** Multiple high-gradient segments turn Orange/Red.
   - **Click Preset "Cloudburst 140mm":**
     - Watch the highway explode into fiery Red and Purple (Severe)!
     - In the Top HUD, `High/Severe` count jumps from `0` to `7+` segments.
     - A dynamic yellow warning banner appears: `⚠️ Simulated Storm Override: 140.0 mm rainfall active`.
3. Click **Reset to Live Weather**:
   - The simulation clears and the map restores real-time Open-Meteo weather data.

---

### 🧪 Scenario 7: Crowd-Sourced Field Report Submission
*Goal: Submit a road hazard report with interactive map coordinate clicking and verify spatial geofencing.*

1. Click the **📢 Field Reports** tab in the sidebar.
2. In the submission form, click the **📍 Pick on Map** button.
3. Click anywhere directly along the highway near Rishikesh or Shivpuri.
   - **What to look for:** The Latitude and Longitude input fields are automatically populated with the exact coordinates!
4. Fill in:
   - **Reporter Name:** `Sub-Inspector Negi (Patrol 7)`
   - **Description:** `Active gravel slide and water runoff spilling onto uphill lane`
5. Click **📢 Submit Field Report**.
   - **What to look for:** A confirmation toast appears, and a new amber warning pin drops onto the map at that exact GPS coordinate.
   - **What to look for in the Bottom Console:** `POST /field-report` with status `[201 Created]`.

---

### 🧪 Scenario 8: Admin Verification & Ground-Truth Flywheel
*Goal: Verify administrative authorization and escalate risk when multiple ground reports are confirmed.*

1. Under the **📢 Field Reports** tab, scroll to the **Recent Field Reports** list.
2. Locate the report submitted in Scenario 7.
3. Click **Validate / Verify**:
   - An Admin Key prompt appears (pre-filled with `admin-dev-secret-key-nh7`).
   - Select Status: **Verified**.
   - Click **Submit Validation**.
   - **What to look for:** The badge changes from `Pending` (amber) to `Verified` (green).
   - **What happens behind the scenes:** The report is saved to `data/validated_reports.csv`. When 5 verified reports accumulate on a segment within 24h, the automated flywheel escalates the segment's operational risk tier by +1 step!

---

### 🧪 Scenario 9: Multi-Channel Alert Subscriptions & Live SMS Simulator
*Goal: Test traveler SMS subscriptions and two-way SMS query bot using the in-browser simulator.*

1. Click the **🔔 Alerts & SMS** tab in the sidebar.
2. Scroll to the **📱 In-Browser Twilio SMS Simulator** widget.
3. Test Command 1: Type `NH7 HELP` and click **Send Simulated SMS**.
   - **What to look for in the Output:** You receive an immediate TwiML mobile message detailing how to query segments and routes.
4. Test Command 2: Type `NH7 SEG08` and click **Send Simulated SMS**.
   - **What to look for:** You receive the exact status, rainfall, and hazard level for Srinagar to Sirobagarh formatted for a simple feature phone screen!
5. Test Command 3: Type `NH7 ROUTE RISHIKESH JOSHIMATH` and click **Send Simulated SMS**.
   - **What to look for:** You receive a concise (< 320 char) route safety clearance message.

---

### 🧪 Scenario 10: Vernacular Hindi & English Neural Voice Alerts
*Goal: Listen to real-time speech alerts synthesized in fluent Hindi and English.*

1. Look at the top right of the sidebar header. Click the **[🇬🇧 EN]** button:
   - **What to look for:** The flag toggles to **`🇮🇳 HI`**!
   - All segment names on the map and labels translate into phonetically natural Hindi (Devanagari) (e.g., ऋषिकेश से शिवपुरी, श्रीनगर से सिरोबगड़).
2. Click the **📦 Offline & Voice** tab in the sidebar.
3. In the **Localized Voice Alert** card, click **🔊 Play Localized Voice Audio**.
   - **What to look for:** An HTML5 audio player activates and speaks out the official highway safety advisory in natural Hindi!
   - **What to look for in the Bottom Console:** `GET /voice-alert?lang=hi` returning `audio/mpeg` with sub-15ms cached streaming.
4. Toggle back to **[🇬🇧 EN]** and click the audio button again to hear the English voice alert.

---

### 🧪 Scenario 11: Guardrails & Attack Resistance Lab
*Goal: Prove that the backend is hardened against DDoS, malicious injection, and coordinate spoofing.*

1. Click the **🛡️ Guardrails Lab** tab in the sidebar.
2. **Test 1: Corridor Distance Geofence (422 Rejection)**
   - Click **Run Corridor Distance Test**.
   - The lab sends coordinates in Delhi (~28.61, 77.20), > 200 km away from NH-7.
   - **Result:** Card turns **GREEN (PASS)**! Backend responds with `HTTP 422 Unprocessable Entity` ("Point is outside the 3.0 km corridor buffer").
3. **Test 2: Rapid Flood Rate Limiter (429 Throttle)**
   - Click **Run Rate Limiting Test**.
   - The lab fires 10 rapid POST requests within 1 second.
   - **Result:** Card turns **GREEN (PASS)**! SlowAPI kicks in and responds with `HTTP 429 Too Many Requests`.
4. **Test 3: XSS Script Injection Sanitization**
   - Click **Run XSS Sanitization Test**.
   - The lab sends `<script>alert('pwned')</script>` in a report description.
   - **Result:** Card turns **GREEN (PASS)**! All tags are stripped, preserving only safe plaintext.
5. **Test 4: Timing-Safe Admin Key Verification**
   - Click **Run Timing-Safe Auth Test**.
   - The lab submits an invalid `X-Admin-Key`.
   - **Result:** Card turns **GREEN (PASS)**! Unauthorized access is rejected with `HTTP 401 Unauthorized` using `secrets.compare_digest`.

---

### 🧪 Scenario 12: Offline Survival Mode & PWA Service Worker
*Goal: Simulate total cellular network failure in deep mountain gorges.*

1. Click the **📦 Offline & Voice** tab in the sidebar.
2. Click **📦 Inspect Offline Survival Pack**.
   - **What to look for:** Inspect the ultra-compact JSON payload (< 17 KB). Notice it includes simplified highway geometry, hospital contacts, and emergency phone numbers (112, BRO Control Room).
3. **Simulate Cellular Blackout in Chrome / Edge / Firefox:**
   - Press **F12** on your keyboard to open **Developer Tools**.
   - Click the **Network** tab in DevTools.
   - In the throttling dropdown (usually set to *No throttling*), select **Offline**.
   - Press **Ctrl + R** (or **Cmd + R**) to refresh the page.
   - **WHAT HAPPENS (The Magic of PWA):**
     - The page loads completely! It does NOT show the browser "No Internet" dinosaur!
     - A bright orange banner appears at the top of the map:  
       `⚡ Offline Mode: Operating from cached offline pack. Last updated: ...`
     - The highway corridor and emergency phone numbers remain fully visible and operational!
4. Remember to switch throttling back to **No throttling** in DevTools when finished.

---

## 4. Live JSON Console Reference

At the bottom of the workbench, the **Live JSON Console** (`#console-pane`) continuously monitors every network interaction:

| Pill Color | Status Range | Example Codes | Meaning |
|---|---|---|---|
| 🟢 **Green** | `2xx` | `200 OK`, `201 Created` | Successful query or creation |
| 🔵 **Blue** | `3xx` | `304 Not Modified` | ETag cache match (0 bytes downloaded) |
| 🟠 **Orange**| `4xx` | `401 Unauthorized`, `422 Validation Error`, `429 Rate Limited` | Guardrail enforcement |
| 🔴 **Red** | `5xx` | `500 Internal Server Error` | Unhandled server exception |

Click **Clear** in the console header at any time to wipe the log for your next demonstration.

---

*Happy Testing! You are now fully equipped to demonstrate every capability of the NH-7 Landslide Early Warning Network.*
