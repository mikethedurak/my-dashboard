from __future__ import annotations

import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[2]
LOCAL_SECRETS_FILE = REPO_DIR / "secrets.env"

sys.path.append(str(REPO_DIR))
from env import get as env_get  # noqa: E402


def local_secret(name: str) -> str:
    if not LOCAL_SECRETS_FILE.exists():
        return ""
    for raw_line in LOCAL_SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def secret(name: str, default: str = "") -> str:
    return env_get(name, default) or local_secret(name)
