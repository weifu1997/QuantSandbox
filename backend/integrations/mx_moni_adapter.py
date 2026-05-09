#!/usr/bin/env python3
"""妙想 mx-moni 适配层"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

MX_MONI_DIR = Path(os.environ.get("MX_MONI_DIR", "/root/.openclaw/plugin-skills/mx-moni"))
MX_MONI_SCRIPT = MX_MONI_DIR / "mx_moni.py"
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


def _load_mx_api_url() -> str:
    env_url = os.environ.get("MX_API_URL", "").strip()
    if env_url:
        return env_url
    for path in (Path.home() / ".profile", Path.home() / ".bashrc"):
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("export MX_API_URL="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
        except Exception:
            continue
    return "https://mkapi2.dfcfs.com/finskillshub"


def run_query(query: str, timeout: int = 120) -> Dict[str, Any]:
    env = os.environ.copy()
    apikey = _load_mx_apikey()
    if not apikey:
        raise RuntimeError("MX_APIKEY 未设置")
    env["MX_APIKEY"] = apikey
    env["MX_API_URL"] = _load_mx_api_url()

    proc = subprocess.run(
        ["python3", str(MX_MONI_SCRIPT), query],
        cwd=str(MX_MONI_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()
    if proc.returncode != 0:
        raise RuntimeError(f"mx-moni 执行失败: {stderr or stdout}")

    safe_name = query.replace("/", "_").replace(" ", "_")[:80]
    raw_path = OUTPUT_DIR / f"mx_moni_{safe_name}_raw.json"
    raw_json = None
    if raw_path.exists():
        try:
            raw_json = json.loads(raw_path.read_text(encoding="utf-8"))
        except Exception:
            raw_json = None

    txt_path = OUTPUT_DIR / f"mx_moni_{safe_name}.txt"
    json_path = OUTPUT_DIR / f"mx_moni_{safe_name}.json"

    return {
        "stdout": stdout,
        "stderr": stderr,
        "raw_json": raw_json,
        "txt_path": str(txt_path) if txt_path.exists() else "",
        "json_path": str(json_path) if json_path.exists() else "",
        "output_dir": str(OUTPUT_DIR),
        "returncode": proc.returncode,
    }
