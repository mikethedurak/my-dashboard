from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_DIR / "services" / "events"))

import scrape_bandsintown_events as bt  # noqa: E402

CACHE_PATH = REPO_DIR / "tests" / "bandsintown_genre_catalog.json"


def load_catalog() -> dict:
    if not CACHE_PATH.exists():
        return {"genres": {}, "runs": []}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"genres": {}, "runs": []}
    if not isinstance(payload, dict):
        return {"genres": {}, "runs": []}
    payload.setdefault("genres", {})
    payload.setdefault("runs", [])
    return payload


def save_catalog(payload: dict) -> None:
    CACHE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_artist_and_event_name(payload: dict, resolved_event: dict) -> tuple[str, str]:
    artist = bt.clean_text(str(resolved_event.get("artist") or resolved_event.get("title") or ""))
    raw_name = bt.clean_text(str(payload.get("name") or ""))
    event_name = ""
    if " @ " in raw_name:
        left, right = raw_name.rsplit(" @ ", 1)
        if bt.clean_text(left).lower() == artist.lower():
            event_name = bt.clean_text(right)
    if not event_name:
        event_name = bt.clean_text(str(resolved_event.get("venue") or ""))
    return artist, event_name


def extract_event_name_from_listing_text(listing_text: str, artist: str) -> str:
    text = bt.clean_text(listing_text or "")
    if not text:
        return ""
    # Strip trailing date/attendance UI text fragments.
    text = text.split(" calendarIcon ", 1)[0].strip()
    text = text.split(" peopleIcon ", 1)[0].strip()
    if not artist:
        return text
    artist_clean = bt.clean_text(artist)
    if text.lower().startswith(artist_clean.lower()):
        tail = bt.clean_text(text[len(artist_clean):])
        if tail:
            return tail
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Debug-scrape a single Bandsintown listing page and print event titles.",
    )
    parser.add_argument("--page", type=int, default=1, help="Listing page number to scrape.")
    parser.add_argument("--genre", default="", help="Optional genre slug/name, e.g. metal.")
    parser.add_argument("--source-url", default="", help="Optional full source URL override.")
    parser.add_argument("--show-urls", action="store_true", help="Print event URLs with titles.")
    parser.add_argument(
        "--no-resolve-details",
        action="store_true",
        help="Do not open each event page for JSON-LD title resolution.",
    )
    parser.add_argument(
        "--no-catalog",
        action="store_true",
        help="Do not update tests/bandsintown_genre_catalog.json for this run.",
    )
    args = parser.parse_args()

    page = max(1, int(args.page))
    source_url = args.source_url.strip() or (bt.genre_url(args.genre) if args.genre.strip() else bt.SOURCE_URL)
    url = bt.paged_url(source_url, page)
    html_text = bt.fetch_html(url)
    links = bt.parse_city_links(html_text)

    print(f"Source URL: {source_url}")
    print(f"Page URL:   {url}")
    print(f"Found {len(links)} event link(s) on page {page}.")

    if not links:
        return 0

    resolve_details = not args.no_resolve_details
    run_genres: set[str] = set()
    for idx, link in enumerate(links, start=1):
        event = bt.event_from_listing(link)
        title = event.get("title") or "(untitled)"
        artist_name = ""
        event_name = ""
        event_genres: list[str] = []
        if resolve_details:
            try:
                payload = bt.find_json_ld_event(bt.fetch_html(link.get("url", "")))
                if payload:
                    resolved = bt.event_from_json_ld(payload, link)
                    title = resolved.get("title") or title
                    artist_name, event_name = parse_artist_and_event_name(payload, resolved)
                    listing_event_name = extract_event_name_from_listing_text(link.get("text", ""), artist_name)
                    if listing_event_name:
                        event_name = listing_event_name
                    event_genres = [bt.clean_text(str(genre)) for genre in (resolved.get("genre_tags", []) or []) if bt.clean_text(str(genre))]
                    for genre in resolved.get("genre_tags", []) or []:
                        clean = bt.clean_text(str(genre))
                        if clean:
                            run_genres.add(clean)
            except Exception:
                pass
        display_title = title
        if resolve_details and event_name:
            display_title = f"{event_name} - {artist_name or title}"
        if resolve_details and event_genres:
            display_title = f"{display_title} [{', '.join(event_genres)}]"
        if args.show_urls:
            print(f"{idx:03d}. {display_title} | {link.get('url', '')}")
        else:
            print(f"{idx:03d}. {display_title}")

    if not args.no_catalog:
        catalog = load_catalog()
        genres = catalog.setdefault("genres", {})
        for genre in sorted(run_genres):
            entry = genres.setdefault(
                genre,
                {"count": 0, "sources": [], "pages": [], "examples": []},
            )
            entry["count"] = int(entry.get("count", 0)) + 1
            if source_url not in entry["sources"]:
                entry["sources"].append(source_url)
            if page not in entry["pages"]:
                entry["pages"].append(page)
            if len(entry["examples"]) < 5:
                entry["examples"].append({"source_url": source_url, "page": page})
        catalog.setdefault("runs", []).append(
            {
                "source_url": source_url,
                "page": page,
                "resolve_details": resolve_details,
                "links_found": len(links),
                "genres_found": sorted(run_genres),
            }
        )
        save_catalog(catalog)
        print(f"Updated genre catalog: {CACHE_PATH}")
        print(f"Genres found this run: {len(run_genres)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
