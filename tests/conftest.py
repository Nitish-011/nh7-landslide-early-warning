import os
import pytest
from app import config
config.ENABLE_SCHEDULER = False
os.environ["ENABLE_SCHEDULER"] = "false"
from app.limiter import limiter
from app.database import init_db, get_db

@pytest.fixture(autouse=True)
def reset_limiter_and_db_state():
    """
    Ensure every test gets a clean rate limit quota and clean testclient records,
    preventing cross-test rate limit starvation and 10-minute duplicate report conflicts.
    """
    limiter.reset()
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM field_reports WHERE reporter_ip = 'testclient'")
    except Exception:
        pass
    yield
    limiter.reset()
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM field_reports WHERE reporter_ip = 'testclient'")
    except Exception:
        pass
