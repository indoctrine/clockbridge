"""Sets up fixtures for Flask application testing"""
import pytest
import sys
import os
sys.path.append(os.path.abspath('../'))
from app import app as flask_app

@pytest.fixture
def app():
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()
