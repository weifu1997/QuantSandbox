"""
Pytest configuration for QuantSandbox tests.
"""
import importlib
import os
import sys
import logging

import pytest
from sqlalchemy import create_engine

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Test database URL
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")


# Create test engine
@pytest.fixture(scope="session")
def engine():
    """Create a test database engine."""
    return create_engine(TEST_DATABASE_URL)


# Fixture for database session
@pytest.fixture(scope="function")
def db_session(engine):
    """Provide a transactional test database session."""
    from sqlalchemy.orm import Session
    from backend.db.session import Base

    connection = engine.connect()
    transactions = connection.begin()
    session = Session(bind=connection)

    # Create all tables
    Base.metadata.create_all(engine)

    yield session

    # Rollback and clean up
    session.close()
    transactions.rollback()
    connection.close()


# Fixture for test client
@pytest.fixture(scope="function")
def client(monkeypatch):
    """Create a test client for API testing with isolated test DB."""
    monkeypatch.setenv("QUANTSANDBOX_DB_URL", TEST_DATABASE_URL)

    for module_name in [
        "backend.db.session",
        "backend.api.config_endpoints",
        "backend.api.backtest_endpoints",
        "backend.api.workflow_endpoints",
        "backend.main",
    ]:
        if module_name in sys.modules:
            del sys.modules[module_name]

    main = importlib.import_module("backend.main")
    from fastapi.testclient import TestClient

    with TestClient(main.app) as test_client:
        yield test_client
