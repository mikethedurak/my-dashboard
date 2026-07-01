from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from services.common.scrape_metadata import run_and_record


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "docs" / "data" / "media"
OUTPUTS = ["watchlist.json", "gameslist.json", "watchlist_movie_details.json", "games_details.json"]
READING_OUTPUTS = [REPO_DIR / "docs" / "data" / "reading_list.json", DATA_DIR / "reading_details.json"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run media/watchlist scrapes.")
    parser.add_argument("--source", choices=["all", "watchlist", "games", "reading"], default="all", help="Which media source to scrape.")
    parser.add_argument("--hard", action="store_true", help="Recreate selected output/cache data from scratch.")
    parser.add_argument("--limit", type=int, default=0, help="Accepted for wrapper consistency; media scrape is not item-limited.")
    parser.add_argument("--max-pages", type=int, default=0, help="Accepted for wrapper consistency; Notion pagination is automatic.")
    parser.add_argument("--type", choices=["all", "movies", "series", "anime", "games"], default="all", help="Which media type to enrich.")
    args = parser.parse_args()

    if args.hard:
        for name in OUTPUTS:
            path = DATA_DIR / name
            if path.exists():
                print(f"Removing stale media output: {path}", flush=True)
                path.unlink()
        if args.source in {"all", "reading"}:
            for path in READING_OUTPUTS:
                if path.exists():
                    print(f"Removing stale reading output: {path}", flush=True)
                    path.unlink()

    if args.source != "reading":
        scope = "both" if args.source == "all" else args.source
        command = [sys.executable, "services/media/scrape_watchlist.py", "--scope", scope, "--type", args.type]
        if args.hard:
            command.append("--hard")
        print(f"Running media scrape: {' '.join(command)}", flush=True)
        outputs = [DATA_DIR / name for name in OUTPUTS]
        if args.source == "watchlist":
            outputs = [DATA_DIR / "watchlist.json", DATA_DIR / "watchlist_movie_details.json"]
        elif args.source == "games":
            outputs = [DATA_DIR / "gameslist.json", DATA_DIR / "games_details.json"]
        run_and_record(command, cwd=REPO_DIR, outputs=outputs, module="media", source=scope)

    if args.source in {"all", "reading"}:
        command = [sys.executable, "services/scrape_reading_list.py"]
        print(f"Running reading scrape: {' '.join(command)}", flush=True)
        run_and_record(command, cwd=REPO_DIR, outputs=READING_OUTPUTS, module="media", source="reading")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
