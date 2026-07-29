"""Sets up fixtures for Flask application testing"""
import os
import sys
import pytest
from unittest.mock import MagicMock

# Point app.py at the test config and stop it starting the ES flusher thread
# BEFORE we import it. app.py loads config and (unless told otherwise) kicks
# off the flusher at import time, so these have to be set at the top of the
# file, ahead of any `from app import ...`. setdefault means an explicit
# override from the caller's environment still wins.
_here = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("CLOCKBRIDGE_CONFIG_PATH", os.path.join(_here, "testConfig.yaml"))
os.environ.setdefault("CLOCKBRIDGE_DISABLE_FLUSHER", "1")

sys.path.insert(0, os.path.abspath(os.path.join(_here, "..")))
from app import app as flask_app
from timer_store import TimerStore

@pytest.fixture
def app():
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def timer_store(app):
    """Swap a fresh in-memory TimerStore onto the app config for the test's
    duration, then restore the original. Routes look up their store via
    current_app.config['TIMER_STORE'], so this cleanly isolates each test
    from the module-level store instantiated at import time."""
    original = app.config.get("TIMER_STORE")
    store = TimerStore(":memory:")
    app.config["TIMER_STORE"] = store
    try:
        yield store
    finally:
        store.close()
        app.config["TIMER_STORE"] = original

@pytest.fixture
def es_mock(app):
    """Swap a MagicMock in for the Elastic client. Routes reference the
    module-level `es` global as well as app.config['ES'], so patch both."""
    import app as app_module
    original_config = app.config.get("ES")
    original_module = app_module.es
    mock = MagicMock()
    app.config["ES"] = mock
    app_module.es = mock
    try:
        yield mock
    finally:
        app.config["ES"] = original_config
        app_module.es = original_module

@pytest.fixture(autouse=True)
def _reset_limiter(app):
    """Reset the Flask-Limiter counters between tests so accumulated
    login attempts across tests don't spuriously trip the 10/min cap."""
    import app as app_module
    limiter = getattr(app_module, "limiter", None)
    if limiter is not None:
        limiter.reset()
    yield
