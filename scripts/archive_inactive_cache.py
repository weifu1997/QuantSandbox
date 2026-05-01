#!/usr/bin/env python3
import os
import sys
import shutil
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
ARCHIVE_DIR = os.path.join(CACHE_DIR, "archive")
DB_PATH = os.path.join(CACHE_DIR, "cache_index.sqlite")


def main():
    apply_mode = "--apply" in sys.argv
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    active_rows = conn.execute(
        """
        SELECT symbol, MAX(end_date) AS max_end
        FROM cache_files
        WHERE is_active = 1
        GROUP BY symbol
        """
    ).fetchall()
    active_end_map = {row["symbol"]: row["max_end"] for row in active_rows}

    cur = conn.execute(
        """
        SELECT id, symbol, file_path, file_name, start_date, end_date
        FROM cache_files
        WHERE is_active = 0
        ORDER BY symbol, updated_at DESC
        """
    )
    rows = cur.fetchall()
    moved = 0
    skipped = 0

    for row in rows:
        _id = row["id"]
        symbol = row["symbol"]
        file_path = row["file_path"]
        file_name = row["file_name"]
        start_date = row["start_date"]
        end_date = row["end_date"]

        active_max_end = active_end_map.get(symbol)
        if active_max_end is None or active_max_end <= end_date:
            skipped += 1
            print(f"skip not replaced: {symbol} {file_name}")
            continue

        if not os.path.exists(file_path):
            skipped += 1
            print(f"skip missing: {symbol} -> {file_name}")
            continue

        target_path = os.path.join(ARCHIVE_DIR, file_name)
        if os.path.abspath(file_path) == os.path.abspath(target_path):
            skipped += 1
            print(f"skip already archived: {symbol} -> {file_name}")
            continue

        if not apply_mode:
            print(f"dry-run: {symbol} {file_name} -> archive/{file_name}")
            skipped += 1
            continue

        shutil.move(file_path, target_path)
        conn.execute(
            "UPDATE cache_files SET file_path = ?, updated_at = datetime('now') WHERE id = ?",
            (target_path, _id),
        )
        moved += 1

    conn.commit()
    conn.close()
    mode = "apply" if apply_mode else "dry-run"
    print(f"mode={mode}, moved={moved}, skipped={skipped}, archive={ARCHIVE_DIR}")


if __name__ == "__main__":
    main()
