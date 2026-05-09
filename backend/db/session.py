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

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)


def init_db() -> None:
    """Create all registered tables."""
    Base.metadata.create_all(bind=engine)


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
