from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from services.common.scrape_metadata import run_and_record


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "docs" / "data" / "release_radar"

SOURCES = {
    "pahe": {
        "command": ["services/release_radar/scrape_releases.py"],
        "output": "pahe_latest.json",
    },
    "coming-soon": {
        "command": ["services/release_radar/scrape_coming_soon.py"],
        "output": "coming_soon.json",
    },
    "games": {
        "command": ["services/release_radar/scrape_game_releases.py"],
        "output": "game_releases.json",
    },
    "imax": {
        "command": ["services/release_radar/scrape_imax.py"],
        "output": "imax_waterfront.json",
    },
    "galileo": {
        "command": ["services/release_radar/scrape_galileo.py"],
        "output": "galileo_movies.json",
    },
    "labia": {
        "command": ["services/release_radar/scrape_labia_showtimes.py"],
        "output": "labia_showtimes.json",
    },
}




def selected_sources(source: str) -> list[str]:
    return list(SOURCES) if source == "all" else [source]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release radar scrapes.")
    parser.add_argument("--source", choices=["all", *SOURCES], default="all", help="Which release source to scrape.")
    parser.add_argument("--hard", action="store_true", help="Remove selected release output before scraping.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum fetched items per source (0 = source default).")
    parser.add_argument("--max-pages", type=int, default=0, help="Maximum pages per source where supported (0 = source default).")
    args = parser.parse_args()

    for source in selected_sources(args.source):
        config = SOURCES[source]
        output = DATA_DIR / config["output"]
        if args.hard and output.exists():
            print(f"Removing stale release output: {output}", flush=True)
            output.unlink()

        command = [sys.executable, *config["command"]]
        if args.hard:
            command.append("--hard")
        if args.limit > 0:
            command.extend(["--limit", str(args.limit)])
        if args.max_pages > 0:
            command.extend(["--max-pages", str(args.max_pages)])
        print(f"Running release radar scrape: {' '.join(command)}", flush=True)
        run_and_record(
            command,
            cwd=REPO_DIR,
            outputs=[output],
            module="release-radar",
            source=source,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
