#!/usr/bin/env python3
"""妙想 mx-data 适配层：调用 skill 脚本并返回结构化结果"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[2]
MX_DATA_DIR = Path("/root/.openclaw/workspace/skills/mx-data")
MX_DATA_SCRIPT = MX_DATA_DIR / "mx_data.py"
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


def run_query(query: str, timeout: int = 120) -> Dict[str, Any]:
    env = os.environ.copy()
    apikey = _load_mx_apikey()
    if not apikey:
        raise RuntimeError("MX_APIKEY 未设置")
    env["MX_APIKEY"] = apikey

    proc = subprocess.run(
        ["python3", str(MX_DATA_SCRIPT), query],
        cwd=str(MX_DATA_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if proc.returncode != 0:
        raise RuntimeError(f"mx-data 执行失败: {stderr or stdout}")

    # 尝试读取原始 JSON 输出文件
    safe_name = query.replace("/", "_").replace(" ", "_")[:80]
    raw_path = OUTPUT_DIR / f"mx_data_{safe_name}_raw.json"
    raw_json = None
    if raw_path.exists():
        try:
            raw_json = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception:
            raw_json = None

    return {
        "stdout": stdout,
        "stderr": stderr,
        "raw_json": raw_json,
        "output_dir": str(OUTPUT_DIR),
        "returncode": proc.returncode,
    }
