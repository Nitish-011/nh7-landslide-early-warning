import os
from pathlib import Path

# Paths (configurable via environment variables)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
LOGS_DIR = Path(os.getenv("LOGS_DIR", str(BASE_DIR / "logs"))).resolve()
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", str(BASE_DIR / "outputs"))).resolve()

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Database & Rain Snapshot paths (configurable via environment variables)
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "landslide_nh7.db"))).resolve()
SNAPSHOT_PATH = Path(os.getenv("SNAPSHOT_PATH", str(DATA_DIR / "rain_snapshot.json"))).resolve()

# Scheduler configuration (Background periodic weather polling)
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "true").lower() in ("true", "1", "yes")
WEATHER_POLL_MINUTES = int(os.getenv("WEATHER_POLL_MINUTES", "30"))

# Task 1: Per-segment hourly rainfall and forecast engine feature flag (default false)
PER_SEGMENT_WEATHER = os.getenv("PER_SEGMENT_WEATHER", "false").lower() in ("true", "1", "yes")

# Task 2: Backtest harness and historical Time Machine replay feature flag (default false)
BACKTEST_ENABLED = os.getenv("BACKTEST_ENABLED", "false").lower() in ("true", "1", "yes")
BACKTEST_CACHE_DIR = Path(os.getenv("BACKTEST_CACHE_DIR", str(DATA_DIR / "backtest_cache"))).resolve()
BACKTEST_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Task 3: Time-aware forecast-based trip planning feature flag (default false)
TIME_AWARE_PLANNER = os.getenv("TIME_AWARE_PLANNER", "false").lower() in ("true", "1", "yes")
DEFAULT_SPEED_KMPH = float(os.getenv("DEFAULT_SPEED_KMPH", "30.0"))

# Logging configuration
LOG_FILE = LOGS_DIR / "backend.log"
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
LOG_BACKUP_COUNT = 5

# Environment mode: 'development' or 'production'
ENV = os.getenv("ENV", "development").lower()

# Admin API Key for /admin/* endpoints
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

# Server binding
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# CORS settings (from env CORS_ORIGINS; default * in dev only)
raw_cors = os.getenv("CORS_ORIGINS", "*" if ENV != "production" else "").strip()
if raw_cors == "*":
    CORS_ALLOW_ORIGINS = ["*"] if ENV != "production" else []
elif raw_cors:
    CORS_ALLOW_ORIGINS = [orig.strip() for orig in raw_cors.split(",") if orig.strip()]
else:
    CORS_ALLOW_ORIGINS = [] if ENV == "production" else ["*"]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# --- Model & Risk Calculation Parameters (Uncalibrated Demo Heuristics) ---
# K_RAIN: Weight of rainfall term in composite relative risk index (0.0 to 1.0)
K_RAIN = 0.4

# K_TERRAIN: Weight of static terrain susceptibility percentile in composite relative risk index
K_TERRAIN = 0.6

# RAIN_REF_MM: 3-day rainfall at which the rain term saturates to 1.0 (demo heuristic)
RAIN_REF_MM = 100.0

# DRY_CAP_MM: 3-day rainfall threshold below which risk is capped at Moderate under dry conditions
DRY_CAP_MM = 25.0

# Risk-level thresholds: maps relative risk index (0.0 to 1.0) to categorical warning tiers
RISK_LEVEL_THRESHOLDS = [
    {"threshold": 0.75, "level": "Very High"},
    {"threshold": 0.50, "level": "High"},
    {"threshold": 0.25, "level": "Moderate"},
    {"threshold": 0.00, "level": "Low"},
]
LEVEL_CUTS = [(item["threshold"], item["level"]) for item in RISK_LEVEL_THRESHOLDS]

