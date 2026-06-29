from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "docs" / "data"


def write_metadata() -> None:
    metadata_path = DATA_DIR / "metadata.json"
    metadata = {"last_scraped_at": datetime.now(timezone.utc).isoformat()}
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


if __name__ == "__main__":
    write_metadata()
