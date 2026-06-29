from __future__ import annotations

import argparse
import html
import json
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from env import get as env_get
from services.common.notion import get_block_children, request as notion_request, rich_text_plain
from services.common.secrets import secret


DEFAULT_WATCHLIST_PAGE_ID = "1d757df8191880aeb859c1402a2154c8"
DEFAULT_WATCHLIST_URL = "https://www.notion.so/My-Watchlist-1d757df8191880aeb859c1402a2154c8"
DEFAULT_GAMES_PAGE_ID = "3c29c9884aae41859c33bdafcc1de628"
DEFAULT_GAMES_URL = "https://www.notion.so/My-Games-3c29c9884aae41859c33bdafcc1de628"

REPO_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_DIR / "docs" / "data" / "media"
OUTPUT_FILE = DATA_DIR / "watchlist.json"
GAMES_OUTPUT_FILE = DATA_DIR / "gameslist.json"
MOVIE_DETAILS_CACHE_FILE = DATA_DIR / "watchlist_movie_details.json"
GAMES_DETAILS_CACHE_FILE = DATA_DIR / "games_details.json"
TMDB_MANUAL_OVERRIDES_FILE = DATA_DIR / "tmdb_manual_overrides.json"
TMDB_API_BASE_URL = env_get("SCRAPE_TMDB_API_BASE_URL", "https://api.themoviedb.org/3")
TMDB_IMAGE_BASE = env_get("SCRAPE_TMDB_IMAGE_BASE_URL", "https://image.tmdb.org/t/p/w342")
TMDB_SITE_MOVIE_BASE = env_get("SCRAPE_TMDB_SITE_MOVIE_BASE_URL", "https://www.themoviedb.org/movie")
TMDB_SITE_TV_BASE = env_get("SCRAPE_TMDB_SITE_TV_BASE_URL", "https://www.themoviedb.org/tv")
RAWG_API_BASE_URL = env_get("SCRAPE_RAWG_GAMES_API_URL", "https://api.rawg.io/api/games")
RAWG_SITE_GAME_BASE_URL = env_get("SCRAPE_RAWG_SITE_GAME_BASE_URL", "https://rawg.io/games")
YOUTUBE_WATCH_BASE_URL = env_get("SCRAPE_YOUTUBE_WATCH_BASE_URL", "https://www.youtube.com/watch?v=")
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
GAME_DETAIL_FIELDS = {
    "media_type",
    "rating",
    "poster_url",
    "release_date",
    "description",
    "genres",
    "platforms",
    "publishers",
    "developers",
    "playtime_hours",
    "metacritic",
    "website_url",
    "rawg_url",
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

OPINION_EMOJI_MAP = {
    "\U0001F525": "Loved",
    "\U0001F44D": "Liked",
    "\U0001F914": "Mixed",
    "\U0001F610": "Mixed",
    "\U0001F44E": "Disliked",
    "\U0001F480": "Hated",
}


def rich_text_has_bold(rich_text: list[dict]) -> bool:
    for part in rich_text:
        annotations = part.get("annotations") or {}
        if annotations.get("bold"):
            return True
    return False


def tmdb_request(path: str, token: str, query: dict[str, str] | None = None) -> dict:
    query_string = ""
    if query:
        query_string = "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(
        f"{TMDB_API_BASE_URL}/{path}{query_string}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def rawg_request(query: dict[str, str], path_suffix: str = "") -> dict:
    api_key = secret("RAWG_API_KEY").strip()
    if not api_key:
        return {}
    params = dict(query)
    params["key"] = api_key
    query_string = urllib.parse.urlencode(params)
    base = RAWG_API_BASE_URL.rstrip("/")
    suffix = f"/{path_suffix.lstrip('/')}" if path_suffix else ""
    request = urllib.request.Request(
        f"{base}{suffix}?{query_string}",
        headers={
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


def console_text(value: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return str(value).encode(encoding, errors="replace").decode(encoding, errors="replace")


def should_descend(block: dict, depth: int, mode: str) -> bool:
    if not block.get("has_children"):
        return False
    block_type = str(block.get("type", ""))
    if block_type not in {"toggle", "bulleted_list_item", "numbered_list_item", "paragraph", "heading_1", "heading_2", "heading_3"}:
        return False

    text = block_text(block)
    label = normalize_label(clean_title(text))

    # Always explore first/root level so we can find section anchors.
    if depth <= 0:
        return True

    if mode == "watchlist":
        if label == "maybe":
            return False
        if label in {
            "movies",
            "movie",
            "series",
            "tv series",
            "tv shows",
            "shows",
            "anime",
            "now",
            "backlog",
            "watched",
            "must watch",
        }:
            return True
        if is_year_heading(text):
            return True
        if re.match(r"^anime\b", label):
            return True
        return False

    if mode == "games":
        if label in {"now", "now playing", "currently playing", "before", "backlog", "coming soon"}:
            return True
        if is_year_heading(text):
            return True
        if game_type_from_label(label):
            return True
        return False

    return True


def flatten_blocks(blocks: list[dict], token: str, depth: int = 0, log_prefix: str = "", mode: str = "watchlist") -> list[tuple[dict, int]]:
    flattened: list[tuple[dict, int]] = []
    for block in blocks:
        flattened.append((block, depth))
        name = block_text(block) or "(no text)"
        block_type = str(block.get("type", "unknown"))
        indent = "  " * max(0, depth)
        if log_prefix:
            print(console_text(f"[notion] {log_prefix} {indent}- {block_type}: {name[:140]}"))
        else:
            print(console_text(f"[notion] {indent}- {block_type}: {name[:140]}"))
        if should_descend(block, depth, mode):
            children = get_block_children(block.get("id", ""), token, f"{log_prefix} children".strip())
            flattened.extend(flatten_blocks(children, token, depth + 1, log_prefix=log_prefix, mode=mode))
    return flattened


def normalize_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_page_id(id_key: str, url_key: str, default_id: str) -> str:
    explicit = secret(id_key).replace("-", "").strip()
    if explicit:
        return explicit
    url_value = secret(url_key).strip()
    if url_value:
        match = re.search(r"([0-9a-fA-F]{32})", url_value.replace("-", ""))
        if match:
            return match.group(1)
    return default_id


def is_year_heading(text: str) -> str:
    match = re.match(r"^(20\d{2})\b", text.strip())
    return match.group(1) if match else ""


def normalize_year_label(text: str) -> str:
    year = is_year_heading(text)
    if year:
        return year
    label = normalize_label(text)
    if label == "before":
        return "Before"
    return ""


def clean_title(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\[(?:x| )\]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\d+[\).\-\s]+", "", cleaned)
    cleaned = cleaned.strip("- ").strip()
    return cleaned


def extract_title_and_opinion(text: str) -> tuple[str, str]:
    title = clean_title(text)
    opinion = ""
    while title:
        matched = False
        for emoji, mapped in OPINION_EMOJI_MAP.items():
            if title.endswith(emoji):
                title = title[: -len(emoji)].rstrip()
                if not opinion:
                    opinion = mapped
                matched = True
                break
        if not matched:
            break
    title = re.sub(r"\s*\[\d{4}\]\s*$", "", title).strip()
    return title, opinion


def movie_key(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(title or ""))
    normalized = "".join(part for part in normalized if not unicodedata.combining(part))
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def rawg_title_key(title: str) -> str:
    normalized = re.sub(r"[^\w\s]", " ", str(title or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def detail_key(media_type: str, title: str) -> str:
    return f"{media_type}:{movie_key(title)}"


def metadata_query_title(title: str, media_type: str) -> str:
    cleaned = str(title or "").strip()
    if media_type not in {"series", "anime", "anime_series"}:
        return cleaned
    cleaned = re.sub(r"\s+S\d{2}(?:(?:\s*,\s*(?:S)?\d{2})|(?:\s*-\s*(?:S)?\d{2}))*\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() or str(title or "").strip()


def normalize_watch_title(title: str, media_type: str) -> str:
    cleaned = str(title or "").strip()
    if media_type in {"series", "anime", "anime_series"}:
        return metadata_query_title(cleaned, media_type)
    return cleaned


def metadata_query_titles(title: str, media_type: str) -> list[str]:
    original = str(title or "").strip()
    if media_type not in {"series", "anime", "anime_series"}:
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


def parse_tmdb_url(tmdb_url: str) -> tuple[str, int] | None:
    match = re.search(r"/(movie|tv)/(\d+)", str(tmdb_url or "").strip(), flags=re.IGNORECASE)
    if not match:
        return None
    kind = match.group(1).lower()
    tmdb_id = int(match.group(2))
    return kind, tmdb_id


def override_match_types(media_type: str) -> list[str]:
    normalized = str(media_type or "").strip().lower()
    if normalized == "movie":
        return ["movie"]
    if normalized == "series":
        return ["series"]
    if normalized == "anime":
        return ["anime_movie", "anime_series", "anime"]
    if normalized in {"anime_movie", "anime_series"}:
        return [normalized]
    return []


def load_tmdb_manual_overrides() -> dict[str, dict]:
    if not TMDB_MANUAL_OVERRIDES_FILE.exists():
        return {}
    try:
        payload = json.loads(TMDB_MANUAL_OVERRIDES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    if isinstance(payload, dict):
        entries = payload.get("entries", [])
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = []

    if not isinstance(entries, list):
        return {}

    overrides: dict[str, dict] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        media_type = str(raw.get("media_type") or "").strip().lower()
        tmdb_url = str(raw.get("tmdb_url") or "").strip()
        if not title or not media_type or not tmdb_url:
            continue

        parsed = parse_tmdb_url(tmdb_url)
        if not parsed:
            continue
        tmdb_kind, tmdb_id = parsed
        match_types = override_match_types(media_type)
        if not match_types:
            continue

        for match_type in match_types:
            key = detail_key(match_type, title)
            overrides[key] = {
                "title": title,
                "media_type": match_type,
                "tmdb_id": tmdb_id,
                "tmdb_kind": tmdb_kind,
                "tmdb_url": tmdb_url,
            }
    return overrides


def parse_watchlist(flat_blocks: list[tuple[dict, int]]) -> dict:
    current_domain = "movie"
    parent_domain = "movie"
    parent_domain_depth = 0
    anime_root_depth: int | None = None
    in_currently_watching = False
    in_now_section = False
    in_backlog_section = False
    backlog_container_depth: int | None = None
    in_watched_section = False
    watched_container_depth: int | None = None
    in_must_watch = False
    domain_started: dict[str, bool] = {"movie": False, "series": False}
    skip_until_anime_for_parent: str | None = None
    active_year = ""
    skip_children_below_depth: int | None = None
    years: dict[str, list[dict]] = {}
    anime_ungrouped: list[dict] = []
    current = {"movies": [], "series": [], "anime_movies": [], "anime_series": []}
    backlog = {"movies": [], "series": [], "anime_movies": [], "anime_series": []}

    for block, depth in flat_blocks:
        if skip_children_below_depth is not None:
            if depth > skip_children_below_depth:
                continue
            skip_children_below_depth = None

        block_type = block.get("type", "")
        text = block_text(block)
        is_bold = block_is_bold(block)
        if not text:
            continue

        normalized_text = clean_title(text)
        label = normalize_label(normalized_text)
        year = is_year_heading(text)
        in_anime_root = anime_root_depth is not None and depth > anime_root_depth
        is_section_like = bool(block.get("has_children")) or block_type.startswith("heading")

        is_anime_heading = label in {"anime", "anime movies", "anime series"}

        if anime_root_depth is not None and depth <= anime_root_depth and not is_anime_heading:
            anime_root_depth = None

        # Backlog should only include descendants of the Backlog toggle/list.
        # If we return to the same depth (or higher) on another label, backlog ends.
        if (
            in_backlog_section
            and backlog_container_depth is not None
            and depth <= backlog_container_depth
            and label != "backlog"
        ):
            in_backlog_section = False
            backlog_container_depth = None
        if (
            in_watched_section
            and watched_container_depth is not None
            and depth <= watched_container_depth
            and label != "watched"
        ):
            in_watched_section = False
            watched_container_depth = None

        if label in {"movies", "movie"}:
            if in_anime_root:
                current_domain = "anime_movie"
            else:
                parent_domain = "movie"
                parent_domain_depth = depth
                current_domain = "movie"
            in_currently_watching = False
            in_now_section = False
            in_backlog_section = False
            backlog_container_depth = None
            in_must_watch = False
            skip_until_anime_for_parent = None
            active_year = ""
            continue
        if label in {"series", "tv series", "tv shows", "shows"}:
            if in_anime_root:
                current_domain = "anime_series"
            else:
                parent_domain = "series"
                parent_domain_depth = depth
                current_domain = "series"
            in_currently_watching = False
            in_now_section = False
            in_backlog_section = False
            backlog_container_depth = None
            in_watched_section = False
            watched_container_depth = None
            in_must_watch = False
            skip_until_anime_for_parent = None
            active_year = ""
            continue
        if is_anime_heading:
            if skip_until_anime_for_parent == parent_domain and depth > parent_domain_depth:
                current_domain = "anime_movie" if parent_domain == "movie" else "anime_series"
            else:
                anime_root_depth = depth
                current_domain = ""
            skip_until_anime_for_parent = None
            in_currently_watching = False
            in_now_section = False
            in_backlog_section = False
            backlog_container_depth = None
            in_watched_section = False
            watched_container_depth = None
            in_must_watch = False
            active_year = ""
            continue
        if (
            is_section_like
            and (
                "now watching" in label
                or "currently watching" in label
                or "currently showing" in label
                or (("currently" in label or "current" in label) and ("watch" in label or "show" in label))
            )
        ):
            in_currently_watching = True
            in_now_section = False
            in_backlog_section = False
            backlog_container_depth = None
            in_watched_section = False
            watched_container_depth = None
            in_must_watch = False
            active_year = ""
            continue
        if label == "now":
            in_currently_watching = True
            in_now_section = True
            in_backlog_section = False
            backlog_container_depth = None
            in_watched_section = False
            watched_container_depth = None
            in_must_watch = False
            if current_domain in {"movie", "series"}:
                skip_until_anime_for_parent = parent_domain
            active_year = ""
            continue
        if label == "watched":
            in_currently_watching = False
            in_now_section = False
            in_backlog_section = False
            backlog_container_depth = None
            in_watched_section = True
            watched_container_depth = depth
            in_must_watch = False
            active_year = ""
            continue
        if label == "backlog":
            in_currently_watching = False
            in_now_section = False
            in_backlog_section = True
            backlog_container_depth = depth
            in_watched_section = False
            watched_container_depth = None
            in_must_watch = False
            active_year = ""
            continue
        if in_now_section and label == "must watch":
            in_currently_watching = True
            in_backlog_section = False
            backlog_container_depth = None
            in_watched_section = False
            watched_container_depth = None
            in_must_watch = True
            active_year = ""
            continue
        if in_now_section and label == "maybe":
            in_currently_watching = False
            in_backlog_section = False
            backlog_container_depth = None
            in_watched_section = False
            watched_container_depth = None
            in_must_watch = False
            active_year = ""
            continue
        if year:
            if current_domain in {"movie", "series"}:
                domain_started[current_domain] = True
            in_currently_watching = False
            in_now_section = False
            in_backlog_section = False
            backlog_container_depth = None
            in_watched_section = False
            watched_container_depth = None
            in_must_watch = False
            active_year = year
            years.setdefault(active_year, [])
            continue

        # For top-level movie/series lists: parse watched years plus Now/Backlog,
        # while skipping non-selected helper lists under Now such as Maybe.
        if current_domain in {"movie", "series"}:
            if skip_until_anime_for_parent == current_domain and not in_currently_watching and not in_backlog_section:
                continue
            if not domain_started[current_domain] and not in_now_section and not in_backlog_section:
                continue

        if block_type not in {"bulleted_list_item", "numbered_list_item", "to_do", "paragraph", "toggle"}:
            continue

        title, opinion = extract_title_and_opinion(text)
        title = normalize_watch_title(title, current_domain)
        if not title:
            continue

        if current_domain in {"anime_movie", "anime_series"} and block.get("has_children") and block_type in {"toggle", "bulleted_list_item", "numbered_list_item", "paragraph"}:
            skip_children_below_depth = depth

        if in_currently_watching:
            if current_domain == "series":
                current["series"].append({"title": title, "opinion": opinion})
            elif current_domain == "anime_movie":
                current["anime_movies"].append({"title": title, "opinion": opinion})
            elif current_domain == "anime_series":
                current["anime_series"].append({"title": title, "opinion": opinion})
            else:
                current["movies"].append({"title": title, "opinion": opinion})
            continue

        if in_backlog_section and backlog_container_depth is not None and depth > backlog_container_depth:
            if current_domain == "series":
                backlog["series"].append({"title": title, "opinion": opinion})
            elif current_domain == "anime_movie":
                backlog["anime_movies"].append({"title": title, "opinion": opinion})
            elif current_domain == "anime_series":
                backlog["anime_series"].append({"title": title, "opinion": opinion})
            else:
                backlog["movies"].append({"title": title, "opinion": opinion})
            continue

        if in_watched_section and watched_container_depth is not None and depth > watched_container_depth:
            if current_domain in {"anime_movie", "anime_series"}:
                anime_ungrouped.append({"type": current_domain, "title": title, "opinion": opinion})
            elif current_domain in {"movie", "series"}:
                years.setdefault("Watched", []).append({"type": current_domain, "title": title, "opinion": opinion})
            continue

        if active_year:
            years.setdefault(active_year, []).append({"type": current_domain, "title": title, "opinion": opinion})
            continue

        if current_domain in {"anime_movie", "anime_series"}:
            anime_ungrouped.append({"type": current_domain, "title": title, "opinion": opinion})

    history_by_year: list[dict] = []
    for year in sorted(years.keys(), reverse=True):
        entries = years[year]
        if entries:
            history_by_year.append({"year": year, "entries": entries})
    if anime_ungrouped:
        history_by_year.append({"year": "Anime", "entries": anime_ungrouped})

    return {
        "source": secret("NOTION_WATCHLIST_PAGE_URL").strip() or DEFAULT_WATCHLIST_URL,
        "currently_watching": current,
        "backlog": backlog,
        "history_by_year": history_by_year,
    }


def game_type_from_label(label: str) -> str:
    normalized = normalize_label(label)
    if normalized in {"single-player", "single player", "aaa", "triple aaa"}:
        return "game_aaa"
    if normalized == "indie":
        return "game_indie"
    if ("couch" in normalized) and re.search(r"\bco[\s-]?op\b", normalized):
        return "game_couch_coop"
    if re.search(r"\bco[\s-]?op\b", normalized):
        return "game_coop"
    if normalized == "lan":
        return "game_lan"
    return ""


def parse_games(flat_blocks: list[tuple[dict, int]]) -> dict:
    current_type = ""
    active_year = ""
    in_now_playing = False
    in_backlog_section = False
    backlog_container_depth: int | None = None
    in_coming_soon_section = False
    coming_soon_container_depth: int | None = None
    seen_now_by_type = {
        "game_aaa": False,
        "game_indie": False,
        "game_coop": False,
        "game_couch_coop": False,
        "game_lan": False,
    }
    current_games = {"aaa": [], "indie": [], "coop": [], "couch_coop": [], "lan": []}
    backlog_games = {"game_aaa": [], "game_indie": [], "game_coop": [], "game_couch_coop": []}
    years: dict[str, list[dict]] = {}
    skip_children_below_depth: int | None = None
    in_lan_flat_mode = False
    structural_labels = {
        "now",
        "now playing",
        "currently playing",
        "before",
        "backlog",
        "coming soon",
        "maybe",
    }

    for block, depth in flat_blocks:
        if skip_children_below_depth is not None:
            if depth > skip_children_below_depth:
                continue
            skip_children_below_depth = None

        block_type = block.get("type", "")
        text = block_text(block)
        is_bold = block_is_bold(block)
        if not text:
            continue

        cleaned_text = clean_title(text)
        label = normalize_label(cleaned_text)
        mapped_type = game_type_from_label(label)

        if (
            in_backlog_section
            and backlog_container_depth is not None
            and depth <= backlog_container_depth
            and label != "backlog"
        ):
            in_backlog_section = False
            backlog_container_depth = None
        if (
            in_coming_soon_section
            and coming_soon_container_depth is not None
            and depth <= coming_soon_container_depth
            and label != "coming soon"
        ):
            in_coming_soon_section = False
            coming_soon_container_depth = None

        is_section_label_block = block_type in {"heading_1", "heading_2", "heading_3", "toggle", "paragraph"} and (
            block.get("has_children") or block_type.startswith("heading")
        )
        if mapped_type and is_section_label_block:
            current_type = mapped_type
            in_now_playing = False
            in_backlog_section = False
            backlog_container_depth = None
            in_coming_soon_section = False
            coming_soon_container_depth = None
            in_lan_flat_mode = False
            active_year = ""
            continue

        if label in {"lan games", "lan game"} and is_section_label_block:
            current_type = "game_lan"
            in_now_playing = False
            in_backlog_section = False
            backlog_container_depth = None
            in_coming_soon_section = False
            coming_soon_container_depth = None
            in_lan_flat_mode = True
            active_year = ""
            continue

        if "now playing" in label or "currently playing" in label or label == "now":
            in_now_playing = True
            in_backlog_section = False
            backlog_container_depth = None
            in_coming_soon_section = False
            coming_soon_container_depth = None
            in_lan_flat_mode = False
            if current_type in seen_now_by_type:
                seen_now_by_type[current_type] = True
            active_year = ""
            continue

        if label == "coming soon":
            in_now_playing = False
            in_backlog_section = False
            backlog_container_depth = None
            in_coming_soon_section = True
            coming_soon_container_depth = depth
            in_lan_flat_mode = False
            active_year = ""
            continue

        if label == "backlog":
            in_now_playing = False
            in_backlog_section = True
            backlog_container_depth = depth
            in_coming_soon_section = False
            coming_soon_container_depth = None
            in_lan_flat_mode = False
            active_year = ""
            continue

        maybe_year = normalize_year_label(cleaned_text)
        if maybe_year:
            if in_lan_flat_mode:
                continue
            # Only capture historical buckets before the first "Now Playing" in a section.
            if current_type and seen_now_by_type.get(current_type, False):
                in_now_playing = False
                in_backlog_section = False
                backlog_container_depth = None
                in_coming_soon_section = False
                coming_soon_container_depth = None
                active_year = ""
                continue
            in_now_playing = False
            in_backlog_section = False
            backlog_container_depth = None
            in_coming_soon_section = False
            coming_soon_container_depth = None
            active_year = maybe_year
            years.setdefault(active_year, [])
            continue

        if block_type not in {"bulleted_list_item", "numbered_list_item", "to_do", "paragraph", "toggle"}:
            continue
        if not current_type:
            continue

        title, opinion = extract_title_and_opinion(text)
        if not title:
            continue
        if normalize_label(title) in structural_labels:
            continue

        entry = {"type": current_type, "title": title, "opinion": opinion}
        if in_coming_soon_section:
            continue
        if in_backlog_section and backlog_container_depth is not None and depth > backlog_container_depth:
            if current_type in backlog_games:
                backlog_games[current_type].append({"title": title, "opinion": opinion})
            continue
        if in_now_playing or in_lan_flat_mode:
            if current_type == "game_aaa":
                current_games["aaa"].append({"title": title, "opinion": opinion})
            elif current_type == "game_indie":
                current_games["indie"].append({"title": title, "opinion": opinion})
            elif current_type == "game_coop":
                current_games["coop"].append({"title": title, "opinion": opinion})
            elif current_type == "game_couch_coop":
                current_games["couch_coop"].append({"title": title, "opinion": opinion})
            elif current_type == "game_lan":
                current_games["lan"].append({"title": title, "opinion": opinion})
            continue

        if active_year:
            years.setdefault(active_year, []).append(entry)

    history_by_year: list[dict] = []
    ordered_years = sorted(
        [year for year in years.keys() if year.isdigit()],
        key=lambda value: int(value),
        reverse=True,
    )
    for year in ordered_years:
        entries = years.get(year, [])
        if entries:
            history_by_year.append({"year": year, "entries": entries})
    if years.get("Before"):
        history_by_year.append({"year": "Before", "entries": years["Before"]})

    return {
        "source": secret("NOTION_GAMES_PAGE_URL").strip() or DEFAULT_GAMES_URL,
        "currently_watching": {"games": current_games},
        "backlog": backlog_games,
        "history_by_year": history_by_year,
    }


def merge_payloads(watchlist_payload: dict, games_payload: dict) -> dict:
    merged = dict(watchlist_payload)
    merged_current = dict(merged.get("currently_watching", {}))
    games_current = games_payload.get("currently_watching", {}).get("games", {})
    merged_current["games"] = games_current if isinstance(games_current, dict) else {}
    merged["currently_watching"] = merged_current

    history = list(merged.get("history_by_year", []))
    history.extend(games_payload.get("history_by_year", []))
    merged["history_by_year"] = history
    merged["games_source"] = games_payload.get("source", "")
    return merged


def load_movie_details_cache() -> dict[str, dict]:
    if not MOVIE_DETAILS_CACHE_FILE.exists():
        return {}
    try:
        payload = json.loads(MOVIE_DETAILS_CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    cache: dict[str, dict] = {}
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        raw_key = str(key)
        media_type = str(value.get("media_type") or "").strip()
        title = str(value.get("title") or "").strip()
        if media_type and title:
            cache[detail_key(media_type, title)] = value
        elif ":" in raw_key:
            prefix, raw_title = raw_key.split(":", 1)
            cache[f"{prefix}:{movie_key(raw_title)}"] = value
        else:
            cache[movie_key(raw_key)] = value
    return cache


def write_movie_details_cache(cache: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ordered = {key: cache[key] for key in sorted(cache.keys())}
    MOVIE_DETAILS_CACHE_FILE.write_text(json.dumps(ordered, indent=2, ensure_ascii=False), encoding="utf-8")


def load_games_details_cache() -> dict[str, dict]:
    if not GAMES_DETAILS_CACHE_FILE.exists():
        return {}
    try:
        payload = json.loads(GAMES_DETAILS_CACHE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def write_games_details_cache(cache: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ordered = {key: cache[key] for key in sorted(cache.keys())}
    GAMES_DETAILS_CACHE_FILE.write_text(json.dumps(ordered, indent=2, ensure_ascii=False), encoding="utf-8")


def write_payload(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean_payload = dict(payload)
    clean_payload.pop("movie_details", None)
    clean_payload.pop("watchlist_details", None)
    clean_payload.pop("game_details", None)
    clean_payload.pop("enrichment_progress", None)
    clean_payload.pop("enrichment_progress_games", None)
    serialized = json.dumps(clean_payload, indent=2, ensure_ascii=False)
    OUTPUT_FILE.write_text(serialized, encoding="utf-8")


def write_games_payload(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean_payload = dict(payload)
    clean_payload.pop("movie_details", None)
    clean_payload.pop("watchlist_details", None)
    clean_payload.pop("game_details", None)
    clean_payload.pop("enrichment_progress", None)
    clean_payload.pop("enrichment_progress_games", None)
    serialized = json.dumps(clean_payload, indent=2, ensure_ascii=False)
    GAMES_OUTPUT_FILE.write_text(serialized, encoding="utf-8")


def progress_bar(processed: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "]"
    ratio = max(0.0, min(1.0, processed / total))
    filled = int(round(ratio * width))
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def extract_titles(payload: dict, media_type: str) -> list[str]:
    titles: list[str] = []
    if media_type == "movie":
        current_key = "movies"
    elif media_type == "series":
        current_key = "series"
    elif media_type == "anime_movie":
        current_key = "anime_movies"
    elif media_type == "anime_series":
        current_key = "anime_series"
    elif media_type == "anime":
        current_key = "anime"
    elif media_type == "game_aaa":
        current_key = "game_aaa"
    elif media_type == "game_indie":
        current_key = "game_indie"
    elif media_type == "game_coop":
        current_key = "game_coop"
    elif media_type == "game_couch_coop":
        current_key = "game_couch_coop"
    elif media_type == "game_lan":
        current_key = "game_lan"
    else:
        current_key = "movies"
    current = payload.get("currently_watching", {})
    game_bucket = current.get("games", {}) if isinstance(current.get("games", {}), dict) else {}
    if media_type == "game_aaa":
        current_items = game_bucket.get("aaa", [])
    elif media_type == "game_indie":
        current_items = game_bucket.get("indie", [])
    elif media_type == "game_coop":
        current_items = game_bucket.get("coop", [])
    elif media_type == "game_couch_coop":
        current_items = game_bucket.get("couch_coop", [])
    elif media_type == "game_lan":
        current_items = game_bucket.get("lan", [])
    else:
        current_items = current.get(current_key, [])
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

    backlog = payload.get("backlog", {}) if isinstance(payload.get("backlog", {}), dict) else {}
    backlog_key_map = {
        "movie": "movies",
        "series": "series",
        "anime_movie": "anime_movies",
        "anime_series": "anime_series",
        "game_aaa": "game_aaa",
        "game_indie": "game_indie",
        "game_coop": "game_coop",
        "game_couch_coop": "game_couch_coop",
    }
    backlog_key = backlog_key_map.get(media_type, "")
    backlog_items = backlog.get(backlog_key, []) if backlog_key else []
    if isinstance(backlog_items, list):
        for item in backlog_items:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
            else:
                title = str(item).strip()
            if title:
                titles.append(title)
    return sorted(set(titles))


def fetch_title_detail(title: str, media_type: str, tmdb_token: str) -> dict:
    result = {"title": title, "media_type": media_type}
    is_tv = media_type in {"series", "anime", "anime_series"}
    search_path = "search/tv" if is_tv else "search/movie"
    detail_path = "tv" if is_tv else "movie"
    site_base = TMDB_SITE_TV_BASE if is_tv else TMDB_SITE_MOVIE_BASE
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
    if is_tv and not isinstance(runtime, (int, float)):
        runtimes = details_payload.get("episode_run_time", []) if isinstance(details_payload, dict) else []
        if isinstance(runtimes, list) and runtimes:
            runtime = runtimes[0]
    if is_tv and not isinstance(number_of_seasons, (int, float)):
        number_of_seasons = details_payload.get("number_of_seasons") if isinstance(details_payload, dict) else None

    credits = details_payload.get("credits", {}) if isinstance(details_payload, dict) else {}
    cast = credits.get("cast", []) if isinstance(credits, dict) else []
    crew = credits.get("crew", []) if isinstance(credits, dict) else []
    videos = details_payload.get("videos", {}) if isinstance(details_payload, dict) else {}
    video_results = videos.get("results", []) if isinstance(videos, dict) else []
    genres = details_payload.get("genres", []) if isinstance(details_payload, dict) else []

    if is_tv:
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
            trailer_url = f"{YOUTUBE_WATCH_BASE_URL}{key}"
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


def fetch_title_detail_by_tmdb_id(title: str, media_type: str, tmdb_token: str, tmdb_id: int, tmdb_kind: str = "") -> dict:
    result = {"title": title, "media_type": media_type, "tmdb_id": tmdb_id}
    tmdb_kind_normalized = str(tmdb_kind or "").strip().lower()
    if tmdb_kind_normalized == "tv":
        is_tv = True
    elif tmdb_kind_normalized == "movie":
        is_tv = False
    else:
        is_tv = media_type in {"series", "anime", "anime_series"}

    detail_path = "tv" if is_tv else "movie"
    site_base = TMDB_SITE_TV_BASE if is_tv else TMDB_SITE_MOVIE_BASE
    first: dict = {}
    try:
        first = tmdb_request(
            f"{detail_path}/{tmdb_id}",
            tmdb_token,
            {
                "language": "en-US",
            },
        )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        first = {}

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
        details_payload = first

    chosen = details_payload if isinstance(details_payload, dict) and details_payload else first
    if not isinstance(chosen, dict) or not chosen:
        result["tmdb_url"] = f"{site_base}/{tmdb_id}"
        return result

    poster_path = str(chosen.get("poster_path") or "").strip()
    vote_average = chosen.get("vote_average")
    release_date = str(chosen.get("release_date") or chosen.get("first_air_date") or "").strip()
    overview = str(chosen.get("overview") or "").strip()
    runtime = chosen.get("runtime")
    number_of_seasons = chosen.get("number_of_seasons")
    if is_tv and not isinstance(runtime, (int, float)):
        runtimes = details_payload.get("episode_run_time", []) if isinstance(details_payload, dict) else []
        if isinstance(runtimes, list) and runtimes:
            runtime = runtimes[0]
    if is_tv and not isinstance(number_of_seasons, (int, float)):
        number_of_seasons = details_payload.get("number_of_seasons") if isinstance(details_payload, dict) else None

    credits = details_payload.get("credits", {}) if isinstance(details_payload, dict) else {}
    cast = credits.get("cast", []) if isinstance(credits, dict) else []
    crew = credits.get("crew", []) if isinstance(credits, dict) else []
    videos = details_payload.get("videos", {}) if isinstance(details_payload, dict) else {}
    video_results = videos.get("results", []) if isinstance(videos, dict) else []
    genres = details_payload.get("genres", []) if isinstance(details_payload, dict) else []

    if is_tv:
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
            trailer_url = f"{YOUTUBE_WATCH_BASE_URL}{key}"
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
        fetched_value = fetched.get(key)
        existing_value = merged.get(key)
        if fetched_value not in (None, "", []):
            merged[key] = fetched_value
            continue
        if key not in merged:
            merged[key] = fetched_value
        elif existing_value in ("", []):
            merged[key] = fetched_value
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
            base = TMDB_SITE_TV_BASE if normalized["media_type"] in {"series", "anime", "anime_series"} else TMDB_SITE_MOVIE_BASE
            normalized["tmdb_url"] = f"{base}/{tmdb_id}"

    return normalized


def movie_detail_needs_fetch(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return True
    if any(field not in entry for field in DETAIL_FIELDS):
        return True
    # Treat entries without a resolved TMDB id as incomplete.
    if not isinstance(entry.get("tmdb_id"), int):
        return True
    # Keep refetching when key descriptive fields are still empty.
    if not str(entry.get("description") or entry.get("overview") or "").strip():
        return True
    if not str(entry.get("poster_url") or "").strip():
        return True
    if not str(entry.get("tmdb_url") or "").strip():
        return True
    return False


def fetch_game_detail(title: str, media_type: str) -> dict:
    result = {"title": title, "media_type": media_type}
    payload = rawg_request(
        {
            "search": title,
            "page_size": "10",
        }
    )
    candidates = payload.get("results", []) if isinstance(payload, dict) else []
    if not isinstance(candidates, list) or not candidates:
        return result

    wanted = rawg_title_key(title)
    ranked = []
    for index, candidate in enumerate(candidates):
        candidate_name = rawg_title_key(candidate.get("name") or "")
        exact = 1 if candidate_name == wanted else 0
        starts = 1 if candidate_name.startswith(wanted) and wanted else 0
        rating_count = int(candidate.get("ratings_count") or 0)
        ranked.append((exact, starts, rating_count, -index, candidate))
    ranked.sort(reverse=True)
    first = ranked[0][4]

    slug = str(first.get("slug") or "").strip()
    details = rawg_request({}, path_suffix=slug) if slug else {}
    chosen = details if isinstance(details, dict) and details else first

    image = str(chosen.get("background_image") or first.get("background_image") or "").strip()
    released = str(chosen.get("released") or first.get("released") or "").strip()
    rating = chosen.get("rating", first.get("rating"))
    playtime = chosen.get("playtime", first.get("playtime"))
    metacritic = chosen.get("metacritic", first.get("metacritic"))
    website = str(chosen.get("website") or "").strip()
    genres = [
        str(item.get("name") or "").strip()
        for item in (chosen.get("genres") or first.get("genres") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    platforms = []
    for entry in (chosen.get("platforms") or first.get("platforms") or []):
        if not isinstance(entry, dict):
            continue
        platform = entry.get("platform")
        if not isinstance(platform, dict):
            continue
        platform_name = str(platform.get("name") or "").strip()
        if platform_name:
            platforms.append(platform_name)
    publishers = [
        str(item.get("name") or "").strip()
        for item in (chosen.get("publishers") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    developers = [
        str(item.get("name") or "").strip()
        for item in (chosen.get("developers") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]

    description = sanitize_html_text(chosen.get("description_raw") or chosen.get("description") or "")
    if isinstance(rating, (int, float)):
        result["rating"] = round(float(rating), 1)
    else:
        result["rating"] = None
    result["poster_url"] = image
    result["release_date"] = released
    result["description"] = description
    result["genres"] = genres
    result["platforms"] = platforms[:8]
    result["publishers"] = list(dict.fromkeys(publishers))[:6]
    result["developers"] = list(dict.fromkeys(developers))[:6]
    result["playtime_hours"] = int(playtime) if isinstance(playtime, (int, float)) else None
    result["metacritic"] = int(metacritic) if isinstance(metacritic, (int, float)) else None
    result["website_url"] = website
    result["rawg_url"] = f"{RAWG_SITE_GAME_BASE_URL}/{slug}" if slug else ""
    return result


def merge_game_details(existing: dict, fetched: dict) -> dict:
    merged = dict(existing)
    merged.setdefault("title", str(existing.get("title") or fetched.get("title") or "").strip())
    for key in GAME_DETAIL_FIELDS:
        if not is_empty_detail_value(merged.get(key)):
            continue
        merged[key] = fetched.get(key)
    return merged


def is_empty_detail_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def sanitize_html_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_cached_game_detail(entry: dict, media_type: str, title: str) -> dict:
    normalized = dict(entry) if isinstance(entry, dict) else {}
    normalized["title"] = str(normalized.get("title") or title).strip()
    normalized["media_type"] = str(normalized.get("media_type") or media_type).strip() or media_type
    return normalized


def game_detail_needs_fetch(entry: dict) -> bool:
    if not isinstance(entry, dict):
        return True
    # Mirror movie caching behavior: only refetch if required keys are missing.
    # Some RAWG fields are legitimately empty for many games (e.g. website/publishers/metacritic).
    return any(field not in entry for field in GAME_DETAIL_FIELDS)


def enrich_payload_with_movie_details(payload: dict, selected_types: set[str] | None = None, hard: bool = False) -> dict:
    tmdb_token = secret("TMDB_BEARER_TOKEN")
    manual_overrides = load_tmdb_manual_overrides()
    movie_titles = extract_titles(payload, "movie")
    series_titles = extract_titles(payload, "series")
    anime_movie_titles = extract_titles(payload, "anime_movie")
    anime_series_titles = extract_titles(payload, "anime_series")
    legacy_anime_titles = extract_titles(payload, "anime")
    all_titles = (
        [("movie", title) for title in movie_titles]
        + [("series", title) for title in series_titles]
        + [("anime_movie", title) for title in anime_movie_titles]
        + [("anime_series", title) for title in anime_series_titles]
        + [("anime_series", title) for title in legacy_anime_titles]
    )
    selected = selected_types if selected_types is not None else {"movie", "series", "anime_movie", "anime_series"}
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
        if key in keys_in_use
        or (not key.startswith(("movie:", "series:", "anime:", "anime_movie:", "anime_series:")) and f"movie:{key}" in keys_in_use)
    }

    total = len(titles)
    processed = 0

    def persist(status: str, current_title: str) -> None:
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
                override = manual_overrides.get(key)
                override_forces_fetch = False
                if override:
                    override_tmdb_id = int(override.get("tmdb_id") or 0)
                    existing_tmdb_id = existing.get("tmdb_id")
                    override_forces_fetch = not isinstance(existing_tmdb_id, int) or existing_tmdb_id != override_tmdb_id
                if (needs_fetch or override_forces_fetch) and tmdb_token:
                    if override:
                        fetched = fetch_title_detail_by_tmdb_id(
                            title,
                            media_type,
                            tmdb_token,
                            int(override.get("tmdb_id") or 0),
                            str(override.get("tmdb_kind") or ""),
                        )
                        source = "override"
                    else:
                        fetched = fetch_title_detail(title, media_type, tmdb_token)
                        source = "fetched"
                    cache[key] = merge_movie_details(existing, fetched)
                else:
                    cache[key] = existing
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


def enrich_payload_with_game_details(payload: dict, selected_types: set[str] | None = None, hard: bool = False) -> dict:
    all_game_titles = (
        [("game_aaa", title) for title in extract_titles(payload, "game_aaa")]
        + [("game_indie", title) for title in extract_titles(payload, "game_indie")]
        + [("game_coop", title) for title in extract_titles(payload, "game_coop")]
        + [("game_couch_coop", title) for title in extract_titles(payload, "game_couch_coop")]
        + [("game_lan", title) for title in extract_titles(payload, "game_lan")]
    )
    selected = selected_types if selected_types is not None else {"game_aaa", "game_indie", "game_coop", "game_couch_coop", "game_lan"}
    titles = [(media_type, title) for media_type, title in all_game_titles if media_type in selected]
    keys_in_use = {
        detail_key(media_type, title)
        for media_type, title in all_game_titles
        if movie_key(title)
    }
    cache = load_games_details_cache()
    cache = {key: value for key, value in cache.items() if key in keys_in_use}

    total = len(titles)
    processed = 0

    def persist(status: str, current_title: str) -> None:
        write_games_details_cache(cache)
        write_games_payload(payload)

    persist("running", "")

    try:
        for media_type, title in titles:
            key = detail_key(media_type, title)
            source = "cached"
            existing = cache.get(key) or {
                "title": title,
                "media_type": media_type,
            }
            existing = normalize_cached_game_detail(existing, media_type, title)
            needs_fetch = hard or game_detail_needs_fetch(existing)
            if needs_fetch:
                fetched = fetch_game_detail(title, media_type)
                cache[key] = merge_game_details(existing, fetched)
                source = "fetched"
            else:
                cache[key] = existing
            processed += 1
            persist("running", title)
            print(f"{progress_bar(processed, total)} {processed}/{total} {source}: {media_type} {title}")
    except KeyboardInterrupt:
        persist("interrupted", "")
        print("Interrupted: partial game details were saved.")
        return payload

    persist("completed", "")
    return payload


def scrape_watchlist(
    selected_types: set[str] | None = None,
    selected_game_types: set[str] | None = None,
    hard: bool = False,
    scrape_watchlist_page: bool = True,
    scrape_games_page: bool = True,
) -> dict:
    token = secret("NOTION_TOKEN") or secret("NOTION_API_TOKEN")
    page_id = extract_page_id("NOTION_WATCHLIST_PAGE_ID", "NOTION_WATCHLIST_PAGE_URL", DEFAULT_WATCHLIST_PAGE_ID)
    games_page_id = extract_page_id("NOTION_GAMES_PAGE_ID", "NOTION_GAMES_PAGE_URL", DEFAULT_GAMES_PAGE_ID)
    page_url = secret("NOTION_WATCHLIST_PAGE_URL").strip() or DEFAULT_WATCHLIST_URL
    games_page_url = secret("NOTION_GAMES_PAGE_URL").strip() or DEFAULT_GAMES_URL

    if not token:
        return {
            "source": page_url,
            "games_source": games_page_url,
            "error": "Missing NOTION_TOKEN",
            "currently_watching": {"movies": [], "series": [], "anime_movies": [], "anime_series": []},
            "history_by_year": [],
        }

    watchlist_payload = {
        "source": page_url,
        "page_id": page_id,
        "currently_watching": {"movies": [], "series": [], "anime_movies": [], "anime_series": []},
        "backlog": {"movies": [], "series": [], "anime_movies": [], "anime_series": []},
        "history_by_year": [],
    }
    if scrape_watchlist_page:
        try:
            print("[notion] Reading watchlist page blocks...")
            root_blocks = get_block_children(page_id, token, "watchlist root")
            flat = flatten_blocks(root_blocks, token, 0, log_prefix="watchlist", mode="watchlist")
            print(f"[notion] Watchlist flattened blocks: {len(flat)}")
            watchlist_payload = parse_watchlist(flat)
            watchlist_payload["source"] = page_url
            watchlist_payload["page_id"] = page_id
            current = watchlist_payload.get("currently_watching", {})
            print(
                "[watchlist] Parsed current counts: "
                f"movies={len(current.get('movies', []))}, "
                f"series={len(current.get('series', []))}, "
                f"anime_movies={len(current.get('anime_movies', []))}, "
                f"anime_series={len(current.get('anime_series', []))}"
            )
            # Persist watchlist immediately so later game/detail failures cannot wipe it.
            write_payload(watchlist_payload)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            return {
                "source": page_url,
                "games_source": games_page_url,
                "error": f"Notion API error {error.code}: {detail}",
                "currently_watching": {"movies": [], "series": [], "anime_movies": [], "anime_series": []},
                "history_by_year": [],
            }
        except (urllib.error.URLError, TimeoutError) as error:
            return {
                "source": page_url,
                "games_source": games_page_url,
                "error": f"Notion API network error: {error}",
                "currently_watching": {"movies": [], "series": [], "anime_movies": [], "anime_series": []},
                "history_by_year": [],
            }

    # Games scrape is best-effort and must not clobber a valid watchlist scrape.
    if scrape_games_page:
        try:
            print("[notion] Reading games page blocks...")
            games_root_blocks = get_block_children(games_page_id, token, "games root")
            games_flat = flatten_blocks(games_root_blocks, token, 0, log_prefix="games", mode="games")
            print(f"[notion] Games flattened blocks: {len(games_flat)}")
            games_payload = parse_games(games_flat)
            games_payload["source"] = games_page_url
            games_payload["page_id"] = games_page_id
            print("[rawg] Starting game enrichment...")
            games_payload = enrich_payload_with_game_details(games_payload, selected_types=selected_game_types, hard=hard)
            write_games_payload(games_payload)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
            print(f"[warn] Games scrape skipped: {error}")

    payload = watchlist_payload
    if scrape_watchlist_page:
        print("[tmdb] Starting media enrichment...")
        payload = enrich_payload_with_movie_details(payload, selected_types=selected_types, hard=hard)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape watchlist from Notion and enrich titles from TMDB.")
    parser.add_argument(
        "--type",
        choices=["all", "movies", "series", "anime", "games"],
        default="all",
        help="Which media type to enrich.",
    )
    parser.add_argument(
        "--hard",
        action="store_true",
        help="Re-fetch selected entries even if cached details already exist.",
    )
    parser.add_argument(
        "--scope",
        choices=["both", "watchlist", "games"],
        default="both",
        help="Choose which Notion page(s) to read.",
    )
    args = parser.parse_args()

    selected_types = {"movie", "series", "anime_movie", "anime_series"}
    selected_game_types = {"game_aaa", "game_indie", "game_coop", "game_couch_coop", "game_lan"}
    if args.type == "movies":
        selected_types = {"movie"}
        selected_game_types = set()
    elif args.type == "series":
        selected_types = {"series"}
        selected_game_types = set()
    elif args.type == "anime":
        selected_types = {"anime_movie", "anime_series"}
        selected_game_types = set()
    elif args.type == "games":
        selected_types = set()
        selected_game_types = {"game_aaa", "game_indie", "game_coop", "game_couch_coop", "game_lan"}
    scrape_watchlist_page = args.scope in {"both", "watchlist"}
    scrape_games_page = args.scope in {"both", "games"}
    if not scrape_watchlist_page:
        selected_types = set()
    if not scrape_games_page:
        selected_game_types = set()

    payload = scrape_watchlist(
        selected_types=selected_types,
        selected_game_types=selected_game_types,
        hard=args.hard,
        scrape_watchlist_page=scrape_watchlist_page,
        scrape_games_page=scrape_games_page,
    )
    if payload.get("error"):
        print(f"Watchlist scrape failed: {payload['error']}")
        print(f"Keeping existing watchlist file at {OUTPUT_FILE}")
        return 1

    if scrape_watchlist_page:
        write_payload(payload)
        total_entries = sum(len(group.get("entries", [])) for group in payload.get("history_by_year", []))
        print(
            f"Wrote watchlist to {OUTPUT_FILE} "
            f"({len(payload.get('currently_watching', {}).get('movies', []))} current movies, "
            f"{len(payload.get('currently_watching', {}).get('series', []))} current series, "
            f"{len(payload.get('currently_watching', {}).get('anime_movies', []))} current anime movies, "
            f"{len(payload.get('currently_watching', {}).get('anime_series', []))} current anime series, "
            f"{total_entries} watched entries)"
        )
    if payload.get("error"):
        print(payload["error"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
