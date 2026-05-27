from __future__ import annotations

import json
import argparse
import os
import urllib.parse
import urllib.error
import urllib.request
import time
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from env import get as env_get


API_URL = env_get("SCRAPE_RAWG_GAMES_API_URL", "https://api.rawg.io/api/games")
SITE_GAME_BASE_URL = env_get("SCRAPE_RAWG_SITE_GAME_BASE_URL", "https://rawg.io/games")
DATA_DIR = Path(__file__).resolve().parents[2] / "docs" / "data" / "release_radar"
OUTPUT_FILE = DATA_DIR / "game_releases.json"
FETCH_LIMIT = max(1, int(env_get("SCRAPE_GAME_RELEASES_FETCH_LIMIT", "20") or "20"))
MAX_ITEMS = max(FETCH_LIMIT, int(env_get("SCRAPE_GAME_RELEASES_MAX_ITEMS", "80") or "80"))
FUTURE_WINDOW_DAYS = max(1, int(env_get("SCRAPE_GAME_RELEASES_WINDOW_DAYS", "90") or "90"))
PAST_WINDOW_DAYS = max(1, int(env_get("SCRAPE_GAME_RELEASES_PAST_DAYS", "45") or "45"))
MAX_PAGES = max(1, int(env_get("SCRAPE_GAME_RELEASES_MAX_PAGES", "6") or "6"))
PLATFORMS = (env_get("SCRAPE_GAME_RELEASES_PLATFORMS", "") or "").strip()
RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
REQUEST_RETRIES = max(1, int(env_get("SCRAPE_GAME_RELEASES_REQUEST_RETRIES", "3") or "3"))
REQUEST_RETRY_DELAY_SECONDS = max(0.0, float(env_get("SCRAPE_GAME_RELEASES_RETRY_DELAY_SECONDS", "2") or "2"))

REPO_DIR = Path(__file__).resolve().parents[2]
LOCAL_SECRETS_FILE = REPO_DIR / "secrets.env"


def local_secret(name: str) -> str:
    if not LOCAL_SECRETS_FILE.exists():
        return ""
    for line in LOCAL_SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def secret(name: str) -> str:
    return (os.environ.get(name, "") or local_secret(name) or "").strip()


def fetch_games(page: int, start: date, end: date, ordering: str) -> dict:
    params: dict[str, str] = {
        "page": str(page),
        "page_size": "40",
        "ordering": ordering,
        "dates": f"{start.isoformat()},{end.isoformat()}",
    }
    api_key = secret("RAWG_API_KEY")
    if api_key:
        params["key"] = api_key
    if PLATFORMS:
        params["platforms"] = PLATFORMS

    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    for attempt in range(1, REQUEST_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code not in RETRYABLE_HTTP_CODES or attempt >= REQUEST_RETRIES:
                raise
            print(
                f"RAWG request failed with HTTP {error.code}; retrying "
                f"{attempt}/{REQUEST_RETRIES} after {REQUEST_RETRY_DELAY_SECONDS:g}s...",
                flush=True,
            )
        except urllib.error.URLError as error:
            if attempt >= REQUEST_RETRIES:
                raise
            print(
                f"RAWG request failed: {error.reason}; retrying "
                f"{attempt}/{REQUEST_RETRIES} after {REQUEST_RETRY_DELAY_SECONDS:g}s...",
                flush=True,
            )
        if REQUEST_RETRY_DELAY_SECONDS:
            time.sleep(REQUEST_RETRY_DELAY_SECONDS)
    raise RuntimeError("RAWG request failed after retries")


def to_item(game: dict) -> dict[str, str] | None:
    game_id = game.get("id")
    name = str(game.get("name") or "").strip()
    if not game_id or not name:
        return None

    image = str(game.get("background_image") or "").strip()
    if not image:
        return None
    released = str(game.get("released") or "").strip()
    rating = game.get("rating")
    rating_text = ""
    if isinstance(rating, (int, float)):
        rating_text = f"{float(rating):.1f}"

    slug = str(game.get("slug") or "").strip()
    url = f"{SITE_GAME_BASE_URL}/{slug}" if slug else f"{SITE_GAME_BASE_URL}/{game_id}"

    platforms: list[str] = []
    for entry in game.get("platforms") or []:
        platform = entry.get("platform") if isinstance(entry, dict) else None
        platform_name = str((platform or {}).get("name") or "").strip() if isinstance(platform, dict) else ""
        if platform_name:
            platforms.append(platform_name)

    return {
        "title": name,
        "url": url,
        "image": image,
        "release_date": released,
        "rating": rating_text,
        "platforms": ", ".join(platforms[:4]),
    }


def normalize_games(results: list[dict], limit: int) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for game in results:
        item = to_item(game)
        if not item:
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return items


def load_existing_payload() -> dict:
    if not OUTPUT_FILE.exists():
        return {}
    try:
        payload = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def item_key(item: dict[str, str]) -> str:
    return str(item.get("url") or item.get("title") or "").strip()


def parse_release_date(value: str) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def filter_items_by_date(items: list[dict[str, str]], start: date, end: date) -> list[dict[str, str]]:
    filtered: list[dict[str, str]] = []
    for item in items:
        released = parse_release_date(str(item.get("release_date") or ""))
        if released and start <= released <= end:
            filtered.append(item)
    return filtered


def merge_items(new_items: list[dict[str, str]], existing_items: list[dict[str, str]], max_items: int) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in [*new_items, *existing_items]:
        key = item_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= max_items:
            break
    return merged


def write_payload(new_releases: list[dict[str, str]], coming_soon: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": API_URL,
        "new_releases": new_releases,
        "coming_soon": coming_soon,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def scrape_range(start: date, end: date, ordering: str) -> list[dict[str, str]]:
    all_results: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        try:
            payload = fetch_games(page=page, start=start, end=end, ordering=ordering)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                break
            if error.code == 401:
                raise RuntimeError("RAWG API returned 401 Unauthorized. Check RAWG_API_KEY in secrets.env.") from error
            raise
        page_results = payload.get("results", [])
        if not isinstance(page_results, list):
            break
        all_results.extend(page_results)
        if len(normalize_games(all_results, MAX_ITEMS)) >= MAX_ITEMS:
            break
    return normalize_games(all_results, MAX_ITEMS)[:FETCH_LIMIT]


def main() -> int:
    global FETCH_LIMIT, MAX_ITEMS, MAX_PAGES

    parser = argparse.ArgumentParser(description="Scrape game releases from RAWG.")
    parser.add_argument("--hard", action="store_true", help="Recreate output from scratch before writing.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum fetched game items per bucket (0 = configured default).")
    parser.add_argument("--max-pages", type=int, default=0, help="Maximum RAWG pages to scan (0 = configured default).")
    args = parser.parse_args()

    if args.limit > 0:
        FETCH_LIMIT = args.limit
        MAX_ITEMS = max(FETCH_LIMIT, args.limit)
    if args.max_pages > 0:
        MAX_PAGES = args.max_pages
    if args.hard and OUTPUT_FILE.exists():
        print(f"Removing stale game release output: {OUTPUT_FILE}")
        OUTPUT_FILE.unlink()

    api_key = secret("RAWG_API_KEY")
    if not api_key:
        raise RuntimeError("Missing RAWG_API_KEY in environment or secrets.env")

    today = date.today()
    new_start = today - timedelta(days=PAST_WINDOW_DAYS)
    new_end = today
    soon_start = today + timedelta(days=1)
    soon_end = today + timedelta(days=FUTURE_WINDOW_DAYS)

    new_candidates = scrape_range(start=new_start, end=new_end, ordering="-released")
    soon_candidates = scrape_range(start=soon_start, end=soon_end, ordering="released")

    existing_payload = load_existing_payload()
    existing_new = existing_payload.get("new_releases", [])
    existing_soon = existing_payload.get("coming_soon", [])
    if not isinstance(existing_new, list):
        existing_new = []
    if not isinstance(existing_soon, list):
        existing_soon = []

    merged_new = merge_items(filter_items_by_date(new_candidates, new_start, new_end), filter_items_by_date(existing_new, new_start, new_end), MAX_ITEMS)
    merged_soon_candidates = merge_items(
        filter_items_by_date(soon_candidates, soon_start, soon_end),
        filter_items_by_date(existing_soon, soon_start, soon_end),
        MAX_ITEMS,
    )
    merged_soon = sorted(merged_soon_candidates, key=lambda item: str(item.get("release_date") or "9999-12-31"))
    write_payload(merged_new, merged_soon)
    print(
        f"Wrote {len(merged_new)} new game release(s) and {len(merged_soon)} coming soon game(s) to {OUTPUT_FILE} "
        f"(fetched {len(new_candidates)} new-release candidates, {len(soon_candidates)} coming-soon candidates)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
