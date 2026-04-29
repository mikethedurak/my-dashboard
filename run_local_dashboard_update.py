from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
DOCS_DATA_DIR = REPO_DIR / "docs" / "data"

TASKS = {
    "cards": [[sys.executable, "one-piece/notify_new_cards.py", "--store", "all", "--mode", "all", "--no-email"]],
    "specials": [[sys.executable, "events/scrape_specials.py"]],
    "events": [
        [sys.executable, "events/scrape_quicket_events.py"],
        [sys.executable, "events/scrape_webtickets_events.py"],
    ],
    "releases": [[sys.executable, "release-radar/scrape_releases.py"]],
    "coming-soon": [[sys.executable, "release-radar/scrape_coming_soon.py"]],
}


def run_commands(task: str) -> None:
    if task == "all":
        commands = [command for commands in TASKS.values() for command in commands]
    else:
        commands = TASKS[task]

    for command in commands:
        subprocess.run(command, cwd=REPO_DIR, check=True)


def copy_outputs() -> None:
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for source_dir in [
        REPO_DIR / "one-piece" / "data",
        REPO_DIR / "release-radar" / "data",
        REPO_DIR / "events" / "data",
    ]:
        if not source_dir.exists():
            continue
        for path in source_dir.glob("*"):
            if path.suffix.lower() in {".csv", ".json"}:
                shutil.copy2(path, DOCS_DATA_DIR / path.name)
    metadata_path = DOCS_DATA_DIR / "metadata.json"
    metadata = {"last_scraped_at": datetime.now(timezone.utc).isoformat()}
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local scrapers and update docs/data.")
    parser.add_argument(
        "task",
        nargs="?",
        choices=["all", *TASKS.keys()],
        default="all",
        help="Which scraper set to run.",
    )
    args = parser.parse_args()

    run_commands(args.task)
    copy_outputs()
    print(f"Updated dashboard data in {DOCS_DATA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
