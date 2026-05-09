#!/usr/bin/env python3
"""妙想 mx-xuangu 适配层"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from backend.integrations.common import load_mx_apikey

MX_XUANGU_DIR = Path(os.environ.get("MX_XUANGU_DIR", "/root/.openclaw/plugin-skills/mx-xuangu"))
MX_XUANGU_SCRIPT = MX_XUANGU_DIR / "mx_xuangu.py"
OUTPUT_DIR = Path("/root/.openclaw/workspace/mx_data/output")


def run_query(query: str, timeout: int = 120) -> Dict[str, Any]:
    env = os.environ.copy()
    apikey = load_mx_apikey()
    if not apikey:
        raise RuntimeError("MX_APIKEY 未设置")
    env["MX_APIKEY"] = apikey

    proc = subprocess.run(
        ["python3", str(MX_XUANGU_SCRIPT), query],
        cwd=str(MX_XUANGU_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if proc.returncode != 0:
        raise RuntimeError(f"mx-xuangu 执行失败: {stderr or stdout}")

    safe_name = query.replace("/", "_").replace(" ", "_")[:80]
    raw_path = OUTPUT_DIR / f"mx_xuangu_{safe_name}_raw.json"
    raw_json = None
    if raw_path.exists():
        try:
            raw_json = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception:
            raw_json = None

    csv_path = OUTPUT_DIR / f"mx_xuangu_{safe_name}.csv"
    desc_path = OUTPUT_DIR / f"mx_xuangu_{safe_name}_description.txt"

    return {
        "stdout": stdout,
        "stderr": stderr,
        "raw_json": raw_json,
        "csv_path": str(csv_path) if csv_path.exists() else "",
        "description_path": str(desc_path) if desc_path.exists() else "",
        "output_dir": str(OUTPUT_DIR),
        "returncode": proc.returncode,
    }
