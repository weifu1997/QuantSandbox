from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / 'data' / 'quantsandbox.sqlite3'


def apply_migration(conn: sqlite3.Connection, dry_run: bool = False) -> dict[str, object]:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(watchlist_entries)").fetchall()]
    required = {
        'pool_group': 'VARCHAR(32)',
        'position_age': 'VARCHAR(16)',
        'left_side_grade': 'VARCHAR(8)',
        'stop_loss_price': 'FLOAT',
        'target_price': 'FLOAT',
        'buy_date': 'DATETIME',
        'time_circuit_breaker_start': 'DATETIME',
        'catalyst_signal': 'VARCHAR(256)',
        'exit_condition': 'VARCHAR(256)',
        'review_count': 'INTEGER DEFAULT 0',
        'last_review_at': 'DATETIME',
        'observation_note': 'TEXT',
    }
    statements: list[str] = []
    for column_name, column_type in required.items():
        if column_name not in columns:
            statements.append(f"ALTER TABLE watchlist_entries ADD COLUMN {column_name} {column_type}")
    statements.append(
        """
        UPDATE watchlist_entries
        SET pool_group = COALESCE(NULLIF(pool_group, ''), 'depth_value'),
            review_count = COALESCE(review_count, 0),
            time_circuit_breaker_start = COALESCE(time_circuit_breaker_start, created_at)
        WHERE pool_group IS NULL
           OR pool_group = ''
           OR review_count IS NULL
           OR time_circuit_breaker_start IS NULL
        """.strip()
    )

    if dry_run:
        return {'dry_run': True, 'statements': statements}

    for statement in statements:
        conn.execute(statement)
    conn.commit()
    return {'dry_run': False, 'statements': statements}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='print SQL statements without executing them')
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    try:
        result = apply_migration(conn, dry_run=args.dry_run)
        if args.dry_run:
            print('DRY RUN')
            for stmt in result['statements']:
                print(stmt)
        else:
            print('ok')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
