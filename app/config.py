import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = DATA_DIR / "landslide_nh7.db"

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

