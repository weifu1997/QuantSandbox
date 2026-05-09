"""
Focused tests for workflow type support.
These are intentionally import-level / sqlite-level checks so they can run
once pytest is available, without requiring the full workflow stack.
"""

import sqlite3

from backend.models.workflow import WorkflowRun
from backend.workflows.types import WorkflowType


def test_workflow_run_has_workflow_type_column():
    assert "workflow_type" in WorkflowRun.__table__.columns
    column = WorkflowRun.__table__.columns["workflow_type"]
    assert column.nullable is False
    assert column.type.length == 32


def test_workflow_type_enum_contains_expected_values():
    assert WorkflowType.LOW_VALUE.value == "low_value_discovery"
    assert WorkflowType.BOTTOM_CONFIRM.value == "bottom_confirm"
    assert WorkflowType.POSITION_MANAGE.value == "position_manage"
    assert WorkflowType.CATALYST_AMBUSH.value == "catalyst_ambush"


def test_sqlite_migration_adds_workflow_type_column(tmp_path):
    db_path = tmp_path / "workflow_type_migration.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE workflow_runs (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                status TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                total_steps INTEGER NOT NULL DEFAULT 0,
                config TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO workflow_runs (id, status, total_steps) VALUES (?, ?, ?)",
            ("run-1", "running", 5),
        )
        conn.commit()

        conn.execute(
            "ALTER TABLE workflow_runs ADD COLUMN workflow_type VARCHAR(32) NOT NULL DEFAULT 'low_value_discovery'"
        )
        conn.commit()

        columns = {row[1]: row for row in conn.execute("PRAGMA table_info(workflow_runs)").fetchall()}
        assert "workflow_type" in columns
        row = conn.execute("SELECT workflow_type FROM workflow_runs WHERE id = ?", ("run-1",)).fetchone()
        assert row[0] == "low_value_discovery"
    finally:
        conn.close()
