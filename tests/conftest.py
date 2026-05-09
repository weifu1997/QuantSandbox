"""
Pytest configuration for QuantSandbox tests.
"""
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
def client():
    """Create a test client for API testing."""
    from backend.main import app
    from fastapi.testclient import TestClient
    
    with TestClient(app) as client:
        yield client

