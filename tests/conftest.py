"""Sets up fixtures for Flask application testing"""
import pytest
import sys
import os
sys.path.append(os.path.abspath('../'))
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
