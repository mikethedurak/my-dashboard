from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.youtube._channel_scraper import run_channel_scraper

CHANNEL_NAME = "gameranx"
CHANNEL_URL = "https://www.youtube.com/@gameranxTV"
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "docs" / "data" / "youtube" / "gameranx_tv.json"

if __name__ == "__main__":
    raise SystemExit(run_channel_scraper(CHANNEL_NAME, CHANNEL_URL, OUTPUT_PATH))
