from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


NOTION_VERSION = "2022-06-28"
DEFAULT_WATCHLIST_PAGE_ID = "1d757df8191880aeb859c1402a2154c8"
DEFAULT_WATCHLIST_URL = "https://www.notion.so/My-Watchlist-1d757df8191880aeb859c1402a2154c8"

REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_FILE = DATA_DIR / "watchlist.json"
MOVIE_DETAILS_CACHE_FILE = DATA_DIR / "watchlist_movie_details.json"
DOCS_DATA_DIR = REPO_DIR / "docs" / "data"
DOCS_OUTPUT_FILE = DOCS_DATA_DIR / "watchlist.json"
LOCAL_SECRETS_FILE = REPO_DIR / "secrets.env"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w342"
TMDB_SITE_MOVIE_BASE = "https://www.themoviedb.org/movie"
TMDB_SITE_TV_BASE = "https://www.themoviedb.org/tv"
DETAIL_FIELDS = {
    "tmdb_id",
    "media_type",
    "rating",
    "poster_url",
    "release_date",
    "overview",
    "description",
    "runtime_minutes",
    "number_of_seasons",
    "directors",
    "actors",
    "trailer_url",
    "genres",
    "tmdb_url",
}

TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "quote",
    "callout",
    "toggle",
}


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
    return os.environ.get(name, "").strip() or local_secret(name)


def rich_text_plain(rich_text: list[dict]) -> str:
    return "".join(part.get("plain_text", "") for part in rich_text).strip()


def rich_text_has_bold(rich_text: list[dict]) -> bool:
    for part in rich_text:
        annotations = part.get("annotations") or {}
        if annotations.get("bold"):
            return True
    return False


def notion_request(path: str, token: str) -> dict:
    request = urllib.request.Request(
        f"https://api.notion.com/v1/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def tmdb_request(path: str, token: str, query: dict[str, str] | None = None) -> dict:
    query_string = ""
    if query:
        query_string = "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(
        f"https://api.themoviedb.org/3/{path}{query_string}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def block_text(block: dict) -> str:
    block_type = block.get("type", "")
    if block_type not in TEXT_BLOCK_TYPES:
        return ""
    value = block.get(block_type, {}) or {}
    text = rich_text_plain(value.get("rich_text", []))
    if block_type == "to_do":
        checked = value.get("checked")
        prefix = "[x] " if checked else "[ ] "
        return f"{prefix}{text}".strip() if text else ""
    return text


def block_is_bold(block: dict) -> bool:
    block_type = block.get("type", "")
    if block_type not in TEXT_BLOCK_TYPES:
        return False
    value = block.get(block_type, {}) or {}
    return rich_text_has_bold(value.get("rich_text", []))


def get_block_children(block_id: str, token: str) -> list[dict]:
    blocks: list[dict] = []
    cursor = ""
    while True:
        query = f"?page_size=100&start_cursor={cursor}" if cursor else "?page_size=100"
        payload = notion_request(f"blocks/{block_id}/children{query}", token)
        blocks.extend(payload.get("results", []))
        if not payload.get("has_more"):
            return blocks
        cursor = payload.get("next_cursor") or ""


def flatten_blocks(blocks: list[dict], token: str, depth: int = 0) -> list[tuple[dict, int]]:
    flattened: list[tuple[dict, int]] = []
    for block in blocks:
        flattened.append((block, depth))
        if block.get("has_children"):
            children = get_block_children(block.get("id", ""), token)
            flattened.extend(flatten_blocks(children, token, depth + 1))
    return flattened


def normalize_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_page_id() -> str:
    explicit = secret("NOTION_WATCHLIST_PAGE_ID").replace("-", "").strip()
    if explicit:
        return explicit
    url_value = secret("NOTION_WATCHLIST_PAGE_URL").strip()
    if url_value:
        match = re.search(r"([0-9a-fA-F]{32})", url_value.replace("-", ""))
        if match:
            return match.group(1)
    return DEFAULT_WATCHLIST_PAGE_ID


def is_year_heading(text: str) -> str:
    match = re.match(r"^(20\d{2})\b", text.strip())
    return match.group(1) if match else ""


def clean_title(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\[(?:x| )\]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\d+[\).\-\s]+", "", cleaned)
    cleaned = cleaned.strip("- ").strip()
    return cleaned


def movie_key(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title).strip().lower()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    return normalized


def detail_key(media_type: str, title: str) -> str:
    return f"{media_type}:{movie_key(title)}"


def metadata_query_title(title: str, media_type: str) -> str:
    cleaned = str(title or "").strip()
    if media_type != "series":
        return cleaned
    cleaned = re.sub(r"\s+S\d{2}(?:(?:\s*,\s*(?:S)?\d{2})|(?:\s*-\s*(?:S)?\d{2}))*\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or str(title or "").strip()


def normalize_watch_title(title: str, media_type: str) -> str:
    cleaned = str(title or "").strip()
    if media_type == "series":
        return metadata_query_title(cleaned, media_type)
    return cleaned


def metadata_query_titles(title: str, media_type: str) -> list[str]:
    original = str(title or "").strip()
    if media_type != "series":
        return [original] if original else []

    variants = []
    season_stripped = metadata_query_title(original, media_type)
    if season_stripped:
        variants.append(season_stripped)

    # Handle more casual suffixes like "Show S01, 02", "Show Season 1", or repeated spaces.
    variants.append(re.sub(r"\s+season\s+\d+(?:\s*-\s*\d+)?\s*$", "", original, flags=re.IGNORECASE).strip())
    variants.append(re.sub(r"\s+s\d{1,2}(?:[,\-\s]+(?:s)?\d{1,2})*\s*$", "", original, flags=re.IGNORECASE).strip())
    variants.append(original)

    deduped = []
    seen = set()
    for value in variants:
      normalized = re.sub(r"\s+", " ", value).strip()
      if normalized and normalized.lower() not in seen:
          seen.add(normalized.lower())
          deduped.append(normalized)
    return deduped


def parse_watchlist(flat_blocks: list[tuple[dict, int]]) -> dict:
    current_domain = "movie"
    in_currently_watching = False
    in_now_section = False
    in_must_watch = False
    active_year = ""
    years: dict[str, list[dict]] = {}
    current = {"movies": [], "series": []}

    for block, _depth in flat_blocks:
        block_type = block.get("type", "")
        text = block_text(block)
        is_bold = block_is_bold(block)
        if not text:
            continue

        normalized_text = clean_title(text)
        label = normalize_label(normalized_text)
        year = is_year_heading(text)

        if label in {"movies", "movie"}:
            current_domain = "movie"
            in_currently_watching = False
            in_now_section = False
            in_must_watch = False
            active_year = ""
            continue
        if label in {"series", "tv series", "tv shows", "shows"}:
            current_domain = "series"
            in_currently_watching = False
            in_now_section = False
            in_must_watch = False
            active_year = ""
            continue
        if "now watching" in label or "currently watching" in label:
            in_currently_watching = True
            in_now_section = False
            in_must_watch = False
            active_year = ""
            continue
        if label == "now":
            in_currently_watching = False
            in_now_section = True
            in_must_watch = False
            active_year = ""
            continue
        if in_now_section and label == "must watch":
            in_currently_watching = True
            in_must_watch = True
            active_year = ""
            continue
        if in_now_section and label == "maybe":
            in_currently_watching = False
            in_must_watch = False
            active_year = ""
            continue
        if year:
            in_currently_watching = False
            in_now_section = False
            in_must_watch = False
            active_year = year
            years.setdefault(active_year, [])
            continue

        if block_type not in {"bulleted_list_item", "numbered_list_item", "to_do", "paragraph"}:
            continue

        title = clean_title(text)
        title = normalize_watch_title(title, current_domain)
        if not title:
            continue

        if in_currently_watching and ((not in_now_section) or in_must_watch):
            if current_domain == "series":
                current["series"].append({"title": title, "loved": is_bold})
            else:
                current["movies"].append({"title": title, "loved": is_bold})
            continue

        if active_year:
            years.setdefault(active_year, []).append({"type": current_domain, "title": title, "loved": is_bold})

    history_by_year: list[dict] = []
    for year in sorted(years.keys(), reverse=True):
        entries = years[year]
        if entries:
            history_by_year.append({"year": year, "entries": entries})

    return {
        "source": secret("NOTION_WATCHLIST_PAGE_URL").strip() or DEFAULT_WATCHLIST_URL,
        "currently_watching": current,
        "history_by_year": history_by_year,
    }


def load_movie_details_cache() -> dict[str, dict]:
    if not MOVIE_DETAILS_CACHE_FILE.exists():
        return {}
    try:
        payload = json.loads(MOVIE_DETAILS_CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def write_movie_details_cache(cache: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ordered = {key: cache[key] for key in sorted(cache.keys())}
    MOVIE_DETAILS_CACHE_FILE.write_text(json.dumps(ordered, indent=2, ensure_ascii=False), encoding="utf-8")


def write_payload(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    OUTPUT_FILE.write_text(serialized, encoding="utf-8")
    DOCS_OUTPUT_FILE.write_text(serialized, encoding="utf-8")


def progress_bar(processed: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "]"
    ratio = max(0.0, min(1.0, processed / total))
    filled = int(round(ratio * width))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def extract_titles(payload: dict, media_type: str) -> list[str]:
    titles: list[str] = []
    current_key = "series" if media_type == "series" else "movies"
    current_items = payload.get("currently_watching", {}).get(current_key, [])
    if isinstance(current_items, list):
        for item in current_items:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
            else:
                title = str(item).strip()
            if title:
                titles.append(title)

    for group in payload.get("history_by_year", []):
        entries = group.get("entries", [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if str(entry.get("type", "")).strip().lower() != media_type:
                continue
            title = str(entry.get("title", "")).strip()
            if title:
                titles.append(title)
    return sorted(set(titles))


def fetch_title_detail(title: str, media_type: str, tmdb_token: str) -> dict:
    result = {"title": title, "media_type": media_type}
    search_path = "search/tv" if media_type == "series" else "search/movie"
    detail_path = "tv" if media_type == "series" else "movie"
    site_base = TMDB_SITE_TV_BASE if media_type == "series" else TMDB_SITE_MOVIE_BASE
    results = []
    for query_title in metadata_query_titles(title, media_type):
        try:
            search_payload = tmdb_request(
                search_path,
                tmdb_token,
                {
                    "query": query_title,
                    "include_adult": "false",
                    "language": "en-US",
                    "page": "1",
                },
            )
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            continue

        results = search_payload.get("results", [])
        if isinstance(results, list) and results:
            break

    if not isinstance(results, list) or not results:
        return result
    first = results[0]
    tmdb_id = first.get("id")
    if not isinstance(tmdb_id, int):
        return result

    result["tmdb_id"] = tmdb_id

    try:
        details_payload = tmdb_request(
            f"{detail_path}/{tmdb_id}",
            tmdb_token,
            {
                "language": "en-US",
                "append_to_response": "credits,videos",
            },
        )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        details_payload = {}

    chosen = details_payload if isinstance(details_payload, dict) and details_payload else first
    poster_path = str(chosen.get("poster_path") or "").strip()
    vote_average = chosen.get("vote_average")
    release_date = str(chosen.get("release_date") or chosen.get("first_air_date") or "").strip()
    overview = str(chosen.get("overview") or "").strip()
    runtime = chosen.get("runtime")
    number_of_seasons = chosen.get("number_of_seasons")
    if media_type == "series" and not isinstance(runtime, (int, float)):
        runtimes = details_payload.get("episode_run_time", []) if isinstance(details_payload, dict) else []
        if isinstance(runtimes, list) and runtimes:
            runtime = runtimes[0]
    if media_type == "series" and not isinstance(number_of_seasons, (int, float)):
        number_of_seasons = details_payload.get("number_of_seasons") if isinstance(details_payload, dict) else None

    credits = details_payload.get("credits", {}) if isinstance(details_payload, dict) else {}
    cast = credits.get("cast", []) if isinstance(credits, dict) else []
    crew = credits.get("crew", []) if isinstance(credits, dict) else []
    videos = details_payload.get("videos", {}) if isinstance(details_payload, dict) else {}
    video_results = videos.get("results", []) if isinstance(videos, dict) else []
    genres = details_payload.get("genres", []) if isinstance(details_payload, dict) else []

    if media_type == "series":
        directors = [
            str(person.get("name") or "").strip()
            for person in details_payload.get("created_by", [])
            if str(person.get("name") or "").strip()
        ] if isinstance(details_payload, dict) else []
    else:
        directors = [
            str(person.get("name") or "").strip()
            for person in crew
            if str(person.get("job") or "").strip().lower() == "director" and str(person.get("name") or "").strip()
        ]
    actors = [
        str(person.get("name") or "").strip()
        for person in cast[:8]
        if str(person.get("name") or "").strip()
    ]
    trailer_url = ""
    for video in video_results:
        if str(video.get("site") or "").strip().lower() != "youtube":
            continue
        video_type = str(video.get("type") or "").strip().lower()
        if video_type not in {"trailer", "teaser"}:
            continue
        key = str(video.get("key") or "").strip()
        if key:
            trailer_url = f"https://www.youtube.com/watch?v={key}"
            break

    genre_names = [
        str(genre.get("name") or "").strip()
        for genre in genres
        if str(genre.get("name") or "").strip()
    ]

    if isinstance(vote_average, (int, float)):
        result["rating"] = round(float(vote_average), 1)
    else:
        result["rating"] = None
    result["poster_url"] = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else ""
    result["release_date"] = release_date
    result["overview"] = overview
    result["description"] = overview
    result["runtime_minutes"] = int(runtime) if isinstance(runtime, (int, float)) else None
    result["number_of_seasons"] = int(number_of_seasons) if isinstance(number_of_seasons, (int, float)) else None
    result["directors"] = list(dict.fromkeys(directors))
    result["actors"] = actors
    result["trailer_url"] = trailer_url
    result["genres"] = genre_names
    result["tmdb_url"] = f"{site_base}/{tmdb_id}"
    return result


def merge_movie_details(existing: dict, fetched: dict) -> dict:
    merged = dict(existing)
    merged.setdefault("title", str(existing.get("title") or fetched.get("title") or "").strip())
    for key in DETAIL_FIELDS:
        if key in merged:
            continue
        merged[key] = fetched.get(key)
    return merged


def normalize_cached_detail(entry: dict, media_type: str, title: str) -> dict:
    normalized = dict(entry) if isinstance(entry, dict) else {}
    normalized["title"] = str(normalized.get("title") or title).strip()
    normalized["media_type"] = str(normalized.get("media_type") or media_type).strip() or media_type

    if not normalized.get("description") and normalized.get("overview"):
        normalized["description"] = normalized.get("overview")

    if not normalized.get("tmdb_url") and normalized.get("tmdb_id"):
        tmdb_id = normalized.get("tmdb_id")
        if isinstance(tmdb_id, int):
            base = TMDB_SITE_TV_BASE if normalized["media_type"] == "series" else TMDB_SITE_MOVIE_BASE
            normalized["tmdb_url"] = f"{base}/{tmdb_id}"

    return normalized


def movie_detail_needs_fetch(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return True
    return any(field not in entry for field in DETAIL_FIELDS)


def enrich_payload_with_movie_details(payload: dict, selected_types: set[str] | None = None, hard: bool = False) -> dict:
    tmdb_token = secret("TMDB_BEARER_TOKEN")
    movie_titles = extract_titles(payload, "movie")
    series_titles = extract_titles(payload, "series")
    all_titles = [("movie", title) for title in movie_titles] + [("series", title) for title in series_titles]
    selected = selected_types or {"movie", "series"}
    titles = [(media_type, title) for media_type, title in all_titles if media_type in selected]
    keys_in_use = {
        detail_key(media_type, title)
        for media_type, title in all_titles
        if movie_key(title)
    }
    cache = load_movie_details_cache()

    # Remove cache entries no longer present in watchlist.
    cache = {
        key: value
        for key, value in cache.items()
        if key in keys_in_use or (not key.startswith(("movie:", "series:")) and f"movie:{key}" in keys_in_use)
    }

    total = len(titles)
    processed = 0

    def persist(status: str, current_title: str) -> None:
        percent = int(round((processed / total) * 100)) if total else 100
        payload["movie_details"] = cache
        payload["watchlist_details"] = cache
        payload["enrichment_progress"] = {
            "status": status,
            "processed": processed,
            "total": total,
            "percent": percent,
            "current_title": current_title,
        }
        write_movie_details_cache(cache)
        write_payload(payload)

    persist("running", "")

    try:
        for media_type, title in titles:
            key = detail_key(media_type, title)
            source = "cached"
            if key:
                fallback_key = movie_key(title) if media_type == "movie" else ""
                existing = cache.get(key) or (cache.get(fallback_key) if fallback_key else None) or {
                    "title": title,
                    "media_type": media_type,
                }
                existing = normalize_cached_detail(existing, media_type, title)
                needs_fetch = hard or movie_detail_needs_fetch(existing)
                if needs_fetch and tmdb_token:
                    fetched = fetch_title_detail(title, media_type, tmdb_token)
                    cache[key] = merge_movie_details(existing, fetched)
                else:
                    cache[key] = existing
                source = "fetched"
                if not needs_fetch:
                    source = "cached"
            processed += 1
            persist("running", title)
            print(f"{progress_bar(processed, total)} {processed}/{total} {source}: {media_type} {title}")
    except KeyboardInterrupt:
        persist("interrupted", "")
        print("Interrupted: partial watchlist details were saved.")
        return payload

    persist("completed", "")
    return payload


def scrape_watchlist(selected_types: set[str] | None = None, hard: bool = False) -> dict:
    token = secret("NOTION_TOKEN") or secret("NOTION_API_TOKEN")
    page_id = extract_page_id()
    page_url = secret("NOTION_WATCHLIST_PAGE_URL").strip() or DEFAULT_WATCHLIST_URL

    if not token:
        return {
            "source": page_url,
            "error": "Missing NOTION_TOKEN",
            "currently_watching": {"movies": [], "series": []},
            "history_by_year": [],
            "movie_details": {},
            "enrichment_progress": {"status": "idle", "processed": 0, "total": 0, "percent": 0, "current_title": ""},
        }

    try:
        root_blocks = get_block_children(page_id, token)
        flat = flatten_blocks(root_blocks, token, 0)
        payload = parse_watchlist(flat)
        payload["source"] = page_url
        payload["page_id"] = page_id
        return enrich_payload_with_movie_details(payload, selected_types=selected_types, hard=hard)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        return {
            "source": page_url,
            "error": f"Notion API error {error.code}: {detail}",
            "currently_watching": {"movies": [], "series": []},
            "history_by_year": [],
            "movie_details": {},
            "enrichment_progress": {"status": "idle", "processed": 0, "total": 0, "percent": 0, "current_title": ""},
        }
    except urllib.error.URLError as error:
        return {
            "source": page_url,
            "error": f"Notion API network error: {error}",
            "currently_watching": {"movies": [], "series": []},
            "history_by_year": [],
            "movie_details": {},
            "enrichment_progress": {"status": "idle", "processed": 0, "total": 0, "percent": 0, "current_title": ""},
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape watchlist from Notion and enrich titles from TMDB.")
    parser.add_argument(
        "--type",
        choices=["all", "movies", "series"],
        default="all",
        help="Which media type to enrich.",
    )
    parser.add_argument(
        "--hard",
        action="store_true",
        help="Re-fetch selected entries even if cached details already exist.",
    )
    args = parser.parse_args()

    selected_types = {"movie", "series"}
    if args.type == "movies":
        selected_types = {"movie"}
    elif args.type == "series":
        selected_types = {"series"}

    payload = scrape_watchlist(selected_types=selected_types, hard=args.hard)
    write_payload(payload)
    total_entries = sum(len(group.get("entries", [])) for group in payload.get("history_by_year", []))
    print(
        f"Wrote watchlist to {OUTPUT_FILE} "
        f"({len(payload.get('currently_watching', {}).get('movies', []))} current movies, "
        f"{len(payload.get('currently_watching', {}).get('series', []))} current series, "
        f"{total_entries} watched entries)"
    )
    if payload.get("error"):
        print(payload["error"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
