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
