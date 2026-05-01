#!/usr/bin/env python3
import os
import re
import sqlite3
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR = os.path.join(BASE_DIR, "data", "cache")
DB_PATH = os.path.join(CACHE_DIR, "cache_index.sqlite")

LEGACY_RE = re.compile(r"^(?P<symbol>[^_]+)_(?P<start>\d{8})_(?P<end>\d{8})\.parquet$")
NEW_RE = re.compile(r"^(?P<symbol>[^_]+)\.parquet$")


def ensure_db(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            data_source TEXT,
            version INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            is_complete INTEGER DEFAULT 1,
            file_size INTEGER,
            file_hash TEXT,
            created_at TEXT,
            updated_at TEXT,
            remark TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_files_symbol ON cache_files(symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_files_active ON cache_files(symbol, is_active)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_files_range ON cache_files(symbol, start_date, end_date)")
    conn.commit()


def get_date_range_from_parquet(path: str):
    try:
        df = pd.read_parquet(path, columns=["date"])
        if df.empty:
            return None, None
        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if dates.empty:
            return None, None
        return dates.min().strftime("%Y%m%d"), dates.max().strftime("%Y%m%d")
    except Exception:
        return None, None


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_db(conn)

    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".parquet")]
    migrated = 0

    # 按 symbol 收集候选文件
    grouped = {}
    for filename in files:
        full_path = os.path.join(CACHE_DIR, filename)
        symbol = None
        start_date = None
        end_date = None

        m = LEGACY_RE.match(filename)
        if m:
            symbol = m.group("symbol")
            start_date = m.group("start")
            end_date = m.group("end")
        else:
            m = NEW_RE.match(filename)
            if m:
                symbol = m.group("symbol")
                start_date, end_date = get_date_range_from_parquet(full_path)

        if not symbol or not start_date or not end_date:
            print(f"skip: {filename}")
            continue

        grouped.setdefault(symbol, []).append((filename, full_path, start_date, end_date))

    for symbol, items in grouped.items():
        # 选区间最长的作为 active
        items_sorted = sorted(items, key=lambda x: (x[2], x[3]))
        best = max(items_sorted, key=lambda x: (x[2], x[3]))

        for filename, full_path, start_date, end_date in items_sorted:
            is_active = 1 if full_path == best[1] else 0
            remark = "migrated_legacy" if filename != f"{symbol}.parquet" else "migrated_new"
            file_size = os.path.getsize(full_path)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                """
                INSERT INTO cache_files (
                    symbol, file_path, file_name, start_date, end_date,
                    data_source, version, is_active, is_complete,
                    file_size, file_hash, created_at, updated_at, remark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    full_path,
                    filename,
                    start_date,
                    end_date,
                    "legacy",
                    1,
                    is_active,
                    1,
                    file_size,
                    None,
                    now,
                    now,
                    remark,
                ),
            )
            migrated += 1

    conn.commit()
    conn.close()
    print(f"migrated records: {migrated}")
    print(f"db: {DB_PATH}")


if __name__ == "__main__":
    main()
