from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from backend.db.base import Base
from backend.workflows.types import WorkflowType

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "quantsandbox.sqlite3"
DB_URL = os.environ.get("QUANTSANDBOX_DB_URL", f"sqlite:///{DEFAULT_DB_PATH}")

if DB_URL.startswith("sqlite:///"):
    DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DB_URL,
    echo=False,
    future=True,
    poolclass=QueuePool if DB_URL.startswith("sqlite") else None,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
        "detect_types": sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    } if DB_URL.startswith("sqlite") else {},
)

if DB_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

def _ensure_workflow_type_column() -> None:
    if not DB_URL.startswith("sqlite:///"):
        return
    with engine.begin() as conn:
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(workflow_runs)").fetchall()]
        if not columns or "workflow_type" in columns:
            return
        conn.exec_driver_sql(
            "ALTER TABLE workflow_runs ADD COLUMN workflow_type VARCHAR(32) NOT NULL DEFAULT 'low_value_discovery'"
        )
        conn.exec_driver_sql(
            "UPDATE workflow_runs SET workflow_type = ? WHERE workflow_type IS NULL OR workflow_type = ''",
            (WorkflowType.LOW_VALUE.value,),
        )


def _ensure_watchlist_manual_fields() -> None:
    if not DB_URL.startswith("sqlite:///"):
        return
    with engine.begin() as conn:
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(watchlist_entries)").fetchall()]
        if not columns:
            return
        required_columns = {
            'board': 'VARCHAR(32)',
            'pe_ttm': 'VARCHAR(32)',
            'pb': 'VARCHAR(32)',
            'latest_price': 'VARCHAR(32)',
            'dividend_yield': 'VARCHAR(32)',
            'month_return': 'VARCHAR(32)',
            'st_flag': 'VARCHAR(16)',
        }
        for column_name, column_type in required_columns.items():
            if column_name not in columns:
                conn.exec_driver_sql(f"ALTER TABLE watchlist_entries ADD COLUMN {column_name} {column_type}")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)


def init_db() -> None:
    """Create all registered tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_workflow_type_column()
    _ensure_watchlist_manual_fields()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
