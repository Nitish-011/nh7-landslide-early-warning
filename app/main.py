import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app import config
from app.config import (
    CORS_ALLOW_ORIGINS,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_METHODS,
    CORS_ALLOW_HEADERS,
)
from app.database import init_db, get_db
from app.logger import logger
from app.middleware import RequestResponseLoggingMiddleware
from app.limiter import limiter
from app.scheduler import start_scheduler, shutdown_scheduler, get_scheduler_last_run
from app.risk_service import get_current_weather_source

# Import Route Routers
from app.routes.risk import router as risk_router
from app.routes.subscriptions import router as subscriptions_router
from app.routes.reports import router as reports_router
from app.routes.history import router as history_router
from app.routes.closures import router as closures_router
from app.routes.webhooks import router as webhooks_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events: Seeds the SQLite database on startup if empty,
    initializes background scheduler (if enabled), starts Telegram bot polling (if enabled),
    and cleans up on shutdown.
    """
    logger.info("Starting up NH-7 Landslide Risk Backend...")
    if config.ENV == "production" and not config.ADMIN_API_KEY:
        logger.critical("FATAL: ADMIN_API_KEY must be set when ENV=production!")
        raise RuntimeError("FATAL STARTUP CONFIGURATION ERROR: ADMIN_API_KEY must be set in production mode!")
    init_db()
    if config.ENABLE_SCHEDULER:
        start_scheduler()
    if config.ENABLE_TELEGRAM_BOT:
        try:
            from app.bot.telegram_bot import start_telegram_bot
            start_telegram_bot()
        except Exception as e:
            logger.warning("Failed starting Telegram bot in lifespan: %s", e)
    logger.info("NH-7 Landslide Risk Backend initialized successfully and ready for incoming traffic.")
    yield
    if config.ENABLE_TELEGRAM_BOT:
        try:
            from app.bot.telegram_bot import stop_telegram_bot
            stop_telegram_bot()
        except Exception:
            pass
    if config.ENABLE_SCHEDULER:
        shutdown_scheduler()
    logger.info("Shutting down NH-7 Landslide Risk Backend.")

app = FastAPI(
    title="NH-7 Uttarakhand Real-Time Landslide Risk API",
    version="1.0.0",
    description=(
        "Production-grade backend for monitoring real-time landslide risk along the "
        "NH-7 corridor in Uttarakhand, India (Rishikesh to Joshimath, 247.37 km). "
        "Provides highway risk mapping, route forecasting with relative risk indices, subscriber alerts, "
        "crowd-sourced field report processing, and historical hazard records."
    ),
    lifespan=lifespan
)

# Attach slowapi limiter
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"}
    )

# 1. Add CORS Middleware (Essential for mobile apps & web frontend dev servers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

# 2. Add Request/Response Audit Logging Middleware
app.add_middleware(RequestResponseLoggingMiddleware)

# 3. Mount Static Directory
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 4. Include Routers
app.include_router(risk_router)
app.include_router(subscriptions_router)
app.include_router(reports_router)
app.include_router(history_router)
app.include_router(closures_router)
app.include_router(webhooks_router)

# 5. Serve Interactive Test Frontend at Root (/)
@app.get("/", include_in_schema=False)
async def serve_test_ui():
    """Serves the Leaflet.js interactive map and testing workbench."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"status": "healthy", "service": "NH-7 Landslide Risk API"})

@app.get("/health", tags=["System"])
async def health_check():
    """
    Sub-second health check endpoint for container probes, uptime pingers, and load balancers.
    Returns operational diagnostics including DB status, weather source, and scheduler run history.
    """
    db_ok = False
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception as e:
        logger.warning("Health check: DB connectivity probe failed: %s", e)

    weather_source = get_current_weather_source()
    scheduler_last_run = get_scheduler_last_run()

    return {
        "status": "ok",
        "system": "NH-7 Landslide Risk Backend",
        "corridor": "Rishikesh-Joshimath",
        "app_version": app.version,
        "db_ok": db_ok,
        "weather_source": weather_source,
        "scheduler_last_run": scheduler_last_run,
    }
