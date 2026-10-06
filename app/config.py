import json
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

# Task 3: Time-aware forecast-based trip planning feature flag (default true)
TIME_AWARE_PLANNER = os.getenv("TIME_AWARE_PLANNER", "true").lower() in ("true", "1", "yes")
DEFAULT_SPEED_KMPH = float(os.getenv("DEFAULT_SPEED_KMPH", "30.0"))

# Task 10: Demo Mode (pins weather to local snapshot so demo is 100% reproducible and never depends on live internet)
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

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

# --- Task 4: Consequence & BRO Operational Priority Weights (Indicative Heuristic) ---
# Isolation penalty based on distance to nearest hospital/clinic (normalized to HOSPITAL_REF_KM)
W_CONSEQUENCE_HOSPITAL = 0.40
HOSPITAL_REF_KM = 30.0

# Blockage penalty when no alternate route exists (1.0 if no bypass, 0.0 if alternate detour exists)
W_CONSEQUENCE_ALTERNATE = 0.35

# Highway traffic importance index penalty (traffic_index 1-5, normalized)
W_CONSEQUENCE_TRAFFIC = 0.25

CONSEQUENCE_CSV_PATH = Path(os.getenv("CONSEQUENCE_CSV_PATH", str(DATA_DIR / "segment_consequence.csv"))).resolve()

# --- Task 5: Official Closures & Ground Truth Flywheel Configuration ---
GROUND_TRUTH_LAYER = os.getenv("GROUND_TRUTH_LAYER", "true").lower() in ("true", "1", "yes")
GROUND_REPORT_HALF_LIFE_HOURS = float(os.getenv("GROUND_REPORT_HALF_LIFE_HOURS", "48.0"))
GROUND_REPORT_ESCALATE_THRESHOLD = float(os.getenv("GROUND_REPORT_ESCALATE_THRESHOLD", "0.75"))
GROUND_REPORT_MAX_ESCALATION_STEPS = int(os.getenv("GROUND_REPORT_MAX_ESCALATION_STEPS", "1"))
VALIDATED_REPORTS_CSV_PATH = Path(os.getenv("VALIDATED_REPORTS_CSV_PATH", str(DATA_DIR / "validated_reports.csv"))).resolve()

# --- Task 6: Real Alert Delivery & Notifier Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM = os.getenv("TWILIO_FROM", os.getenv("TWILIO_PHONE_NUMBER", "")).strip()
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")
ENABLE_TELEGRAM_BOT = os.getenv("ENABLE_TELEGRAM_BOT", "false").lower() in ("true", "1", "yes")

# Dispatch interval: prefers ALERT_DISPATCH_INTERVAL_MINUTES (minutes), falls back to ALERT_CHECK_INTERVAL (seconds // 60)
_interval_min_str = os.getenv("ALERT_DISPATCH_INTERVAL_MINUTES")
if not _interval_min_str and os.getenv("ALERT_CHECK_INTERVAL"):
    try:
        _interval_min_str = str(max(1, int(os.getenv("ALERT_CHECK_INTERVAL")) // 60))
    except (ValueError, TypeError):
        _interval_min_str = "10"
ALERT_DISPATCH_INTERVAL_MINUTES = int(_interval_min_str or "10")
ALERT_COOLDOWN_HOURS = float(os.getenv("ALERT_COOLDOWN_HOURS", "3.0"))

# --- Task 7: Localization & Voice Alert Configuration ---
TTS_CACHE_DIR = Path(os.getenv("TTS_CACHE_DIR", str(DATA_DIR / "tts_cache"))).resolve()
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# --- Task 8: Offline Pack & Emergency Contacts Configuration ---
# National emergency number 112 is included by default; other numbers left blank for manual configuration.
DEFAULT_EMERGENCY_CONTACTS = [
    {"name": "National Emergency Helpline", "number": "112"},
    {"name": "State Disaster Management (SDMA Uttarakhand)", "number": ""},
    {"name": "Highway Police Control Room", "number": ""},
    {"name": "Border Roads Organisation (BRO) Control Room", "number": ""},
    {"name": "Ambulance / Medical Emergency", "number": ""},
]

try:
    _env_contacts = os.getenv("EMERGENCY_CONTACTS")
    EMERGENCY_CONTACTS = json.loads(_env_contacts) if _env_contacts else DEFAULT_EMERGENCY_CONTACTS
except Exception:
    EMERGENCY_CONTACTS = DEFAULT_EMERGENCY_CONTACTS

OFFLINE_PACK_SIMPLIFY_TOLERANCE = float(os.getenv("OFFLINE_PACK_SIMPLIFY_TOLERANCE", "0.0005"))
