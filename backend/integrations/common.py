from __future__ import annotations

import os
from pathlib import Path


def load_shell_export(name: str) -> str:
    env_value = os.environ.get(name, "").strip()
    if env_value:
        return env_value
    for path in (Path.home() / ".profile", Path.home() / ".bashrc"):
        if not path.exists():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(f"export {name}="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value:
                        return value
        except Exception:
            continue
    return ""


def load_mx_apikey() -> str:
    return load_shell_export("MX_APIKEY")


def load_mx_api_url(default: str = "https://mkapi2.dfcfs.com/finskillshub") -> str:
    return load_shell_export("MX_API_URL") or default
