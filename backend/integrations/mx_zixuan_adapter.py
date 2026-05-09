#!/usr/bin/env python3
"""妙想 mx-zixuan 适配层"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

MX_ZIXUAN_DIR = Path(os.environ.get("MX_ZIXUAN_DIR", "/root/.openclaw/plugin-skills/mx-zixuan"))
MX_ZIXUAN_SCRIPT = MX_ZIXUAN_DIR / "mx_zixuan.py"
OUTPUT_DIR = Path("/root/.openclaw/workspace/mx_data/output")


def _load_mx_apikey() -> str:
    env_key = os.environ.get("MX_APIKEY", "").strip()
    if env_key:
        return env_key
    for path in (Path.home() / ".profile", Path.home() / ".bashrc"):
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("export MX_APIKEY="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
        except Exception:
            continue
    return ""


def _safe_name(query: str) -> str:
    return query.replace("/", "_").replace(" ", "_")[:80]


def run_query(query: str, timeout: int = 120) -> Dict[str, Any]:
    env = os.environ.copy()
    apikey = _load_mx_apikey()
    if not apikey:
        raise RuntimeError("MX_APIKEY 未设置")
    env["MX_APIKEY"] = apikey

    proc = subprocess.run(
        ["python3", str(MX_ZIXUAN_SCRIPT), query],
        cwd=str(MX_ZIXUAN_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if proc.returncode != 0:
        raise RuntimeError(f"mx-zixuan 执行失败: {stderr or stdout}")

    safe_name = _safe_name(query)
    raw_json_candidates = [
        OUTPUT_DIR / f"mx_zixuan_{safe_name}_raw.json",
        OUTPUT_DIR / "mx_zixuan_我的自选股列表_raw.json",
    ]
    csv_candidates = [
        OUTPUT_DIR / f"mx_zixuan_{safe_name}.csv",
        OUTPUT_DIR / "mx_zixuan_我的自选股列表.csv",
    ]

    raw_json = None
    raw_path = ""
    for p in raw_json_candidates:
        if p.exists():
            raw_path = str(p)
            try:
                raw_json = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                raw_json = None
            break

    csv_path = ""
    for p in csv_candidates:
        if p.exists():
            csv_path = str(p)
            break

    return {
        "stdout": stdout,
        "stderr": stderr,
        "raw_json": raw_json,
        "raw_json_path": raw_path,
        "csv_path": csv_path,
        "output_dir": str(OUTPUT_DIR),
        "returncode": proc.returncode,
    }
