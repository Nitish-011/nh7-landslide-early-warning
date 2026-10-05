import logging
import sys
from logging.handlers import RotatingFileHandler
from app.config import LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT

LOGGER_NAME = "nh7.backend"

def setup_logger() -> logging.Logger:
    """
    Configures and returns the standard application logger.
    Directs structured logs to both stdout (console) and a rotating file in logs/backend.log.
    """
    logger = logging.getLogger(LOGGER_NAME)
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Rotating File Handler
    file_handler = RotatingFileHandler(
        filename=str(LOG_FILE),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()
