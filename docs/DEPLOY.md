# Production Deployment & Zero-Downtime Guide

This guide covers production deployment options for the **NH-7 Uttarakhand Real-Time Landslide Risk API**, including Render, Railway, a zero-config ngrok demo fallback, and UptimeRobot keep-warm configuration to eliminate cold starts during live judging.

---

## 📋 Architectural Essentials

1. **Single Uvicorn Worker (`--workers 1`)**:
   The backend includes an in-process APScheduler `BackgroundScheduler` that periodically polls weather for all corridor segments and atomically updates `data/rain_snapshot.json`. Running multiple uvicorn workers would cause duplicated polling jobs. Always maintain `--workers 1` in production container commands.
2. **SQLite Disk Persistence**:
   SQLite stores field reports and subscriptions in `data/landslide_nh7.db`. Cloud free tiers (such as Render Free) utilize ephemeral container filesystems. For production data durability across restarts, attach a persistent volume to `/app/data`.
3. **Sub-Second Health Endpoint (`GET /health`)**:
   Returns container diagnostics (`status`, `db_ok`, `weather_source`, `scheduler_last_run`, `app_version`) in under 10 ms, ideal for uptime monitors and container liveness probes.

---

## 🚀 Option 1: Deploy to Render (Recommended Blueprint)

### Using Blueprint (`render.yaml`)
1. Push your repository to GitHub / GitLab.
2. Log in to [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** ➔ **Blueprint**.
4. Connect your repository. Render automatically reads `render.yaml`.
5. Review the service configuration:
   - **Environment**: Docker
   - **Health Check Path**: `/health`
   - **Auto-Generated Variable**: `ADMIN_API_KEY` (secret string)
   - **Environment Variables**:
     ```env
     ENV=production
     ENABLE_SCHEDULER=true
     WEATHER_POLL_MINUTES=30
     DATA_DIR=/app/data
     DB_PATH=/app/data/landslide_nh7.db
     SNAPSHOT_PATH=/app/data/rain_snapshot.json
     ```
6. Click **Apply**. Render will build the Docker container and start serving.

### Persistent Disk Note (Render)
Render free web services spin down after 15 minutes of inactivity and discard local disk modifications.
- If persistent subscriber/field report history is required across redeploys, upgrade to a Render Starter plan and attach a 1 GB persistent disk mounted to `/app/data` (as documented in `render.yaml`).
- Alternatively, use **Railway** or maintain clean baseline demo data auto-seeded from `app/seed_data.py`.

---

## 🚆 Option 2: Deploy to Railway

Railway natively supports persistent volume mounts with Docker:

1. Log in to [Railway.app](https://railway.app/).
2. Click **New Project** ➔ **Deploy from GitHub repo**.
3. Select your repository. Railway automatically detects the `Dockerfile`.
4. In Railway **Settings** ➔ **Volumes**:
   - Click **Add Volume**.
   - Set **Mount Path** to `/app/data`.
5. In **Variables**, add:
   ```env
   ENV=production
   ADMIN_API_KEY=your-secure-secret-admin-key-here
   ENABLE_SCHEDULER=true
   WEATHER_POLL_MINUTES=30
   DATA_DIR=/app/data
   DB_PATH=/app/data/landslide_nh7.db
   SNAPSHOT_PATH=/app/data/rain_snapshot.json
   ```
6. Generate a public domain under **Networking** ➔ **Generate Domain**.

---

## ⚡ Option 3: Emergency Live-Judging Fallback (ngrok)

If cloud instances experience cold-boot lag, outbound API rate limits, or network restrictions during hackathon evaluation, run the local backend and tunnel it globally via ngrok.

### Prerequisites
Install [ngrok](https://ngrok.com/download):
```bash
# Windows (winget or choco)
winget install ngrok.ngrok
# macOS
brew install ngrok/ngrok/ngrok
# Linux
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
```

### Steps to Expose
1. Start the local server:
   ```bash
   python run.py
   ```
   *(Binds to `http://127.0.0.1:8000`)*
2. In a separate terminal, launch the ngrok tunnel:
   ```bash
   ngrok http 8000
   ```
3. Copy the secure HTTPS forwarding URL (e.g. `https://a1b2-c3d4.ngrok-free.app`).
4. Test the health endpoint:
   ```bash
   curl -s https://a1b2-c3d4.ngrok-free.app/health
   ```
5. Share this URL with teammates and judges. The interactive map UI is live at `https://<ngrok-url>/`.

---

## 🕒 Option 4: UptimeRobot Keep-Warm Setup (Zero Cold Starts)

Free cloud hosting platforms (Render, Koyeb) suspend inactive containers after 15 minutes. Cold restarts can take 30–60 seconds, which hurts live presentations. Configuring UptimeRobot keeps the service active 24/7 with zero latency.

### Setup Instructions
1. Create a free account at [UptimeRobot.com](https://uptimerobot.com/).
2. Click **+ Add New Monitor**.
3. Configure the monitor parameters:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `NH-7 Landslide API Keep-Warm`
   - **URL (or IP)**: `https://<your-app-domain>.onrender.com/health`
   - **Monitoring Interval**: `Every 5 minutes`
   - **Monitor Timeout**: `30 seconds`
   - **HTTP Method**: `GET` or `HEAD`
4. Click **Create Monitor**.

### Why This Works
- Every 5 minutes, UptimeRobot sends an HTTP request to `/health`.
- The `/health` endpoint executes in < 5 ms and verifies SQLite connectivity (`db_ok=true`) and weather status without taxing resources.
- Render detects active traffic, preventing the container from entering dormant sleep mode.
- When judges load the web dashboard or fire API requests, responses return in sub-100 ms.

---

## 🧪 Post-Deployment Verification Checklist

Once deployed, verify the deployment from your local terminal:

1. **Check System Diagnostics**:
   ```bash
   curl -i https://<your-deployed-domain>/health
   ```
   Expected response:
   ```json
   {
     "status": "ok",
     "system": "NH-7 Landslide Risk Backend",
     "corridor": "Rishikesh-Joshimath",
     "app_version": "1.0.0",
     "db_ok": true,
     "weather_source": "snapshot",
     "scheduler_last_run": null
   }
   ```

2. **Run Smoke Test Suite**:
   ```bash
   python scripts/smoke.py https://<your-deployed-domain>
   ```
   All core endpoints must report `PASS` with latencies under 500 ms.

3. **Verify Interactive Workbench**:
   Open `https://<your-deployed-domain>/` in your browser. Verify the Leaflet map renders the NH-7 corridor from Rishikesh to Joshimath with live/cached risk scores.
