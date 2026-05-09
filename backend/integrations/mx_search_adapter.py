#!/usr/bin/env python3
"""妙想 mx-search 适配层"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from backend.integrations.common import load_mx_apikey

MX_SEARCH_DIR = Path(os.environ.get("MX_SEARCH_DIR", "/root/.openclaw/plugin-skills/mx-search"))
MX_SEARCH_SCRIPT = MX_SEARCH_DIR / "mx_search.py"
OUTPUT_DIR = Path("/root/.openclaw/workspace/mx_data/output")


def run_query(query: str, timeout: int = 120) -> Dict[str, Any]:
    env = os.environ.copy()
    apikey = load_mx_apikey()
    if not apikey:
        raise RuntimeError("MX_APIKEY 未设置")
    env["MX_APIKEY"] = apikey

    proc = subprocess.run(
        ["python3", str(MX_SEARCH_SCRIPT), query],
        cwd=str(MX_SEARCH_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if proc.returncode != 0:
        raise RuntimeError(f"mx-search 执行失败: {stderr or stdout}")

    safe_name = query.replace("/", "_").replace(" ", "_")[:80]
    raw_path = OUTPUT_DIR / f"mx_search_{safe_name}.json"
    raw_json = None
    if raw_path.exists():
        try:
            raw_json = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception:
            raw_json = None

    txt_path = OUTPUT_DIR / f"mx_search_{safe_name}.txt"

    return {
        "stdout": stdout,
        "stderr": stderr,
        "raw_json": raw_json,
        "txt_path": str(txt_path) if txt_path.exists() else "",
        "output_dir": str(OUTPUT_DIR),
        "returncode": proc.returncode,
    }
