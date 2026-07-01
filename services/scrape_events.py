from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from services.common.scrape_metadata import run_and_record


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "docs" / "data" / "events"

SOURCES = {
    "specials": {
        "command": ["services/events/scrape_specials.py"],
        "outputs": ["specials.json", "places.json"],
    },
    "bandsintown": {
        "command": ["services/events/scrape_bandsintown_events.py"],
        "outputs": ["bandsintown_events.json"],
    },
    "quicket": {
        "command": ["services/events/scrape_quicket_events.py"],
        "outputs": ["quicket_events.json"],
    },
    "webtickets": {
        "command": ["services/events/scrape_webtickets_events.py"],
        "outputs": ["webtickets_wc_events.json"],
    },
    "google-calendar": {
        "command": ["services/events/scrape_google_calendar.py"],
        "outputs": ["google_calendar_events.json"],
    },
}


def selected_sources(source: str) -> list[str]:
    if source == "all":
        return list(SOURCES)
    return [source]


def remove_outputs(source_names: list[str]) -> None:
    output_names = {"locations.json"} if set(source_names) == set(SOURCES) else set()
    for source in source_names:
        output_names.update(SOURCES[source]["outputs"])
    for name in output_names:
        path = DATA_DIR / name
        if path.exists():
            print(f"Removing stale output: {path}", flush=True)
            path.unlink()


def run_source(source: str, args: argparse.Namespace) -> None:
    command = [sys.executable, *SOURCES[source]["command"]]
    if args.hard:
        command.append("--hard")
    if source in {"bandsintown", "quicket", "webtickets"}:
        command.extend(["--limit", str(args.limit)])
    if source in {"bandsintown", "quicket", "webtickets"} and args.max_pages > 0:
        page_flag = "--pages" if source == "quicket" else "--max-pages"
        command.extend([page_flag, str(args.max_pages)])
    if source == "bandsintown" and args.genre:
        command.extend(["--genre", args.genre])
    if source == "bandsintown" and args.places_limit > 0:
        command.extend(["--places-limit", str(args.places_limit)])

    print(f"\nRunning {source}: {' '.join(command)}", flush=True)
    run_and_record(
        command,
        cwd=REPO_DIR,
        outputs=[DATA_DIR / name for name in SOURCES[source]["outputs"]],
        module="events",
        source=source,
    )


def run_geocode_pass(args: argparse.Namespace) -> None:
    command = [sys.executable, "services/events/geocode_event_locations.py"]
    if args.hard:
        command.append("--hard")
    print(f"\nRunning geocode pass: {' '.join(command)}", flush=True)
    run_and_record(
        command,
        cwd=REPO_DIR,
        outputs=[DATA_DIR / "locations.json"],
        module="events",
        source="geocode",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run event/special scrape sources.")
    parser.add_argument("--source", choices=["all", *SOURCES], default="all", help="Which event source to scrape.")
    parser.add_argument("--hard", action="store_true", help="Recreate selected source output from scratch.")
    parser.add_argument("--skip-geocode", action="store_true", help="Skip the final geocode pass after source scraping.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum items per source (0 = no limit where supported).")
    parser.add_argument("--max-pages", type=int, default=0, help="Maximum listing pages per source (0 = source default/all).")
    parser.add_argument("--genre", default="", help="Bandsintown genre filter. Use 'all' for the all-genre Bandsintown listing.")
    parser.add_argument("--places-limit", type=int, default=0, help="Bandsintown only: maximum new Google Places lookups to make (0 = no limit).")
    args = parser.parse_args()

    source_names = selected_sources(args.source)
    if args.hard:
        remove_outputs(source_names)
    for source in source_names:
        run_source(source, args)
    if args.source == "all" and not args.skip_geocode:
        run_geocode_pass(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
