import pytest
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
