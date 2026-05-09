import sqlite3

from backend.models import WatchlistEntry, WorkflowRun, WorkflowRunStatus
from backend.repositories.watchlist_repo import WatchlistRepository


def test_watchlist_numeric_fields_persist_on_create_and_update(db_session):
    run = WorkflowRun(user_id='u1', workflow_type='low_value_discovery', status=WorkflowRunStatus.COMPLETED)
    db_session.add(run)
    db_session.flush()

    repo = WatchlistRepository(db_session)
    entry = repo.create(
        WatchlistEntry(
            workflow_run_id=run.id,
            symbol='603166',
            name='福达股份',
            pe_ttm='31.38',
            pe_ttm_num=31.38,
            pb='3.6164',
            pb_num=3.6164,
            latest_price='14.60',
            latest_price_num=14.60,
            dividend_yield='0.6754',
            dividend_yield_num=0.6754,
            month_return='13.00',
            month_return_num=13.00,
        )
    )
    db_session.flush()

    assert entry.pe_ttm_num == 31.38
    assert entry.pb_num == 3.6164
    assert entry.latest_price_num == 14.60
    assert entry.dividend_yield_num == 0.6754
    assert entry.month_return_num == 13.00

    updated = repo.update(
        entry,
        pb='--',
        pb_num=None,
        latest_price='15.80',
        latest_price_num=15.80,
    )
    db_session.flush()

    assert updated.pb == '--'
    assert updated.pb_num is None
    assert updated.latest_price == '15.80'
    assert updated.latest_price_num == 15.80


def test_watchlist_numeric_field_backfill_sqlite_cast(tmp_path):
    db_path = tmp_path / 'watchlist_numeric_backfill.sqlite3'
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE watchlist_entries (
                id TEXT PRIMARY KEY,
                workflow_run_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                pe_ttm VARCHAR(32),
                pb VARCHAR(32),
                latest_price VARCHAR(32),
                dividend_yield VARCHAR(32),
                month_return VARCHAR(32)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO watchlist_entries (id, workflow_run_id, symbol, name, pe_ttm, pb, latest_price, dividend_yield, month_return)
            VALUES ('w1', 'r1', '603166', '福达股份', '31.38', '3.6164', '14.60', '0.6754', '13.00')
            """
        )
        for col in ['pe_ttm_num', 'pb_num', 'latest_price_num', 'dividend_yield_num', 'month_return_num']:
            conn.execute(f"ALTER TABLE watchlist_entries ADD COLUMN {col} REAL")
        for text_col, num_col in [
            ('pe_ttm', 'pe_ttm_num'),
            ('pb', 'pb_num'),
            ('latest_price', 'latest_price_num'),
            ('dividend_yield', 'dividend_yield_num'),
            ('month_return', 'month_return_num'),
        ]:
            conn.execute(
                f"""
                UPDATE watchlist_entries
                SET {num_col} = CAST({text_col} AS REAL)
                WHERE {num_col} IS NULL
                  AND {text_col} IS NOT NULL
                  AND TRIM({text_col}) != ''
                """
            )
        conn.commit()

        row = conn.execute(
            "SELECT pe_ttm_num, pb_num, latest_price_num, dividend_yield_num, month_return_num FROM watchlist_entries WHERE id = 'w1'"
        ).fetchone()
        assert row == (31.38, 3.6164, 14.6, 0.6754, 13.0)
    finally:
        conn.close()
