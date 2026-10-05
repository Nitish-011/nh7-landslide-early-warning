import os
import pytest
from app import config
config.ENABLE_SCHEDULER = False
os.environ["ENABLE_SCHEDULER"] = "false"
from app.limiter import limiter
from app.database import init_db

@pytest.fixture(autouse=True)
def reset_limiter_and_db_state():
    """
    Ensure every test gets a clean rate limit quota and initialized DB,
    preventing cross-test rate limit starvation when running in testclient.
    """
    limiter.reset()
    yield
    limiter.reset()
