"""
Pytest configuration for QuantSandbox tests.
"""
import importlib
import os
import sys
import logging
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set up logging
logging.basicConfig(level=logging.INFO)


@pytest.fixture(scope="session")
def test_database_url(tmp_path_factory):
    db_dir = tmp_path_factory.mktemp("db")
    db_path = Path(db_dir) / "quantsandbox_test.sqlite3"
    return f"sqlite:///{db_path}"


# Create test engine
@pytest.fixture(scope="session")
def engine(test_database_url):
    """Create a test database engine."""
    return create_engine(test_database_url)


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
def client(monkeypatch, test_database_url, tmp_path):
    """Create a test client for API testing with isolated test DB and config."""
    monkeypatch.setenv("QUANTSANDBOX_DB_URL", test_database_url)

    isolated_config = tmp_path / "config.yaml"
    isolated_config.write_text(
        yaml.safe_dump(
            {
                "account": {"initial_cash": 100000.0, "commission_rate": 0.00025, "tax_rate": 0.0005},
                "stock_pool": ["sh600901", "sz000883"],
                "strategy": {
                    "name": "multi_factor_target_weight",
                    "parameters": {"rsi_period": 7, "max_target_weight": 0.3, "rebalance_threshold": 0.03},
                },
                "data_source": {"cache": {"enabled": True}, "akshare": {"enabled": False}},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUANTSANDBOX_CONFIG_PATH", str(isolated_config))

    for module_name in [
        "backend.db.session",
        "backend.api.config_endpoints",
        "backend.api.backtest_endpoints",
        "backend.main",
    ]:
        if module_name in sys.modules:
            del sys.modules[module_name]

    main = importlib.import_module("backend.main")
    from fastapi.testclient import TestClient

    with TestClient(main.app) as test_client:
        yield test_client
