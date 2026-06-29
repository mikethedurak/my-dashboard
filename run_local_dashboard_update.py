from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from services.write_metadata import write_metadata  # noqa: E402

REPO_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_DIR / "docs" / "data"
SCRAPE_DIR = REPO_DIR / ".scrape"
PREVIOUS_DATA_DIR = SCRAPE_DIR / "previous_data"

TASKS = {
    "cards": [[sys.executable, "services/scrape_one_piece.py"]],
    "specials": [[sys.executable, "services/scrape_events.py", "--source", "specials"]],
    "events": [[sys.executable, "services/scrape_events.py"]],
    "releases": [[sys.executable, "services/scrape_release_radar.py", "--source", "pahe"]],
    "coming-soon": [[sys.executable, "services/scrape_release_radar.py", "--source", "coming-soon"]],
    "game-releases": [[sys.executable, "services/scrape_release_radar.py", "--source", "games"]],
    "galileo": [[sys.executable, "services/scrape_release_radar.py", "--source", "galileo"]],
    "media": [[sys.executable, "services/scrape_media.py"]],
    "watchlist": [[sys.executable, "services/scrape_media.py", "--source", "watchlist"]],
    "gamelist": [[sys.executable, "services/scrape_media.py", "--source", "games", "--type", "games"]],
    "news": [[sys.executable, "services/scrape_news.py"]],
    "youtube": [[sys.executable, "services/scrape_youtube.py", "--mode", "daily"]],
    "reading": [[sys.executable, "services/scrape_reading_list.py"]],
    "digest": [[sys.executable, "services/daily_digest/send_daily_digest.py", "--no-email"]],
}

NEW_MARKER_FILES = [
    "release_radar/pahe_latest.json",
    "release_radar/coming_soon.json",
    "release_radar/game_releases.json",
    "release_radar/imax_waterfront.json",
    "release_radar/galileo_movies.json",
    "news/news.json",
    "events/quicket_events.json",
    "events/bandsintown_events.json",
    "events/webtickets_wc_events.json",
    "events/google_calendar_events.json",
    "media/watchlist.json",
    "media/gameslist.json",
    "youtube/latest_uploads.json",
]


def snapshot_previous_data() -> None:
    if PREVIOUS_DATA_DIR.exists():
        shutil.rmtree(PREVIOUS_DATA_DIR)
    PREVIOUS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    for rel_path in NEW_MARKER_FILES:
        source = DATA_DIR / rel_path
        if not source.exists():
            continue
        target = PREVIOUS_DATA_DIR / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def run_commands(task: str) -> None:
    if task == "all":
        scheduled = [
            (name, command)
            for name, commands in TASKS.items()
            if name != "digest"
            for command in commands
        ]
    else:
        scheduled = [(task, command) for command in TASKS[task]]

    total = len(scheduled)
    for index, (task_name, command) in enumerate(scheduled, start=1):
        command_text = " ".join(str(part) for part in command)
        print(f"[{index}/{total}] Running ({task_name}): {command_text}")
        subprocess.run(command, cwd=REPO_DIR, check=True)
        print(f"[{index}/{total}] Done ({task_name})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run scrapers locally and update docs/data/.")
    parser.add_argument(
        "task",
        nargs="?",
        choices=["all", *TASKS.keys()],
        default="all",
        help="Which scraper to run (default: all).",
    )
    args = parser.parse_args()

    snapshot_previous_data()
    run_commands(args.task)
    subprocess.run([sys.executable, "services/mark_new_items.py"], cwd=REPO_DIR, check=True)
    write_metadata()
    print(f"Done. Data written to {DATA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
