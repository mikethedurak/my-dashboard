from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[1]))
from services.common.notion import get_block_children, request as notion_request, rich_text_plain
from services.common.secrets import secret


DEFAULT_READING_PAGE_ID = "2d157df8191880a7a23dfc431800dbe6"
DEFAULT_READING_URL = "https://app.notion.com/p/My-Reading-2d157df8191880a7a23dfc431800dbe6"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"

REPO_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_DIR / "docs" / "data" / "reading_list.json"
DETAILS_OUTPUT_PATH = REPO_DIR / "docs" / "data" / "media" / "reading_details.json"

TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "toggle",
    "callout",
}

OPINION_EMOJI_MAP = {
    "\U0001F525": "Loved",
    "\U0001F44D": "Liked",
    "\U0001F610": "Mixed",
    "\U0001F914": "Mixed",
    "\U0001F44E": "Disliked",
    "\U0001F480": "Hated",
}

FALLBACK_PAYLOAD = {
    "source": DEFAULT_READING_URL,
    "currently_watching": {
        "books": [
            {"title": "Dungeon Crawler Carl", "opinion": ""},
            {"title": "Dark Matter", "opinion": ""},
        ],
        "manga": [
            {"title": "One Piece", "opinion": ""},
            {"title": "Uzumaki", "opinion": ""},
        ],
    },
    "history_by_year": [
        {
            "year": "Read",
            "entries": [
                {"type": "book", "title": "Enders Game", "opinion": "Liked"},
                {"type": "book", "title": "Speaker of the Dead", "opinion": "Disliked"},
                {"type": "book", "title": "Harry Potter and the Philosopher's Stone", "opinion": "Liked"},
                {"type": "book", "title": "The Metamorphosis", "opinion": "Mixed"},
                {"type": "book", "title": "1984", "opinion": "Loved"},
                {"type": "book", "title": "Brave New World", "opinion": "Liked"},
            ],
        }
    ],
}


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "my-dashboard/reading-scraper",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def extract_page_id() -> str:
    explicit = secret("NOTION_READING_PAGE_ID").replace("-", "").strip()
    if explicit:
        return explicit
    url_value = secret("NOTION_READING_PAGE_URL").strip() or DEFAULT_READING_URL
    match = re.search(r"([0-9a-fA-F]{32})", url_value.replace("-", ""))
    return match.group(1) if match else DEFAULT_READING_PAGE_ID


def block_text(block: dict[str, Any]) -> str:
    block_type = str(block.get("type", ""))
    if block_type not in TEXT_BLOCK_TYPES:
        return ""
    value = block.get(block_type, {}) or {}
    text = rich_text_plain(value.get("rich_text", []))
    if block_type == "to_do":
        checked = value.get("checked")
        prefix = "[x] " if checked else "[ ] "
        return f"{prefix}{text}".strip() if text else ""
    return text


def flatten_blocks(blocks: list[dict[str, Any]], token: str, depth: int = 0) -> list[tuple[dict[str, Any], int]]:
    flattened: list[tuple[dict[str, Any], int]] = []
    for block in blocks:
        flattened.append((block, depth))
        if block.get("has_children"):
            children = get_block_children(str(block.get("id", "")), token, "reading children")
            flattened.extend(flatten_blocks(children, token, depth + 1))
    return flattened


def normalize_label(value: str) -> str:
    cleaned = re.sub(r"^\[(?:x| )\]\s*", "", str(value or "").strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"^[\-\*\u2022]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def clean_title(value: str) -> str:
    cleaned = re.sub(r"^\[(?:x| )\]\s*", "", str(value or "").strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"^\d+[\).\-\s]+", "", cleaned)
    cleaned = re.sub(r"^[\-\*\u2022]\s*", "", cleaned)
    return cleaned.strip()


def extract_title_and_opinion(value: str) -> tuple[str, str]:
    title = clean_title(value)
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
    return title.strip(), opinion


def section_for_label(label: str) -> str:
    if label in {"books", "book"}:
        return "books"
    if label in {"manga", "mangas"}:
        return "manga"
    return ""


def parse_reading_list(flat_blocks: list[tuple[dict[str, Any], int]]) -> dict[str, Any]:
    current: dict[str, list[dict[str, str]]] = {"books": [], "manga": []}
    history_entries: list[dict[str, str]] = []
    active_section = ""
    active_depth = -1
    seen: dict[str, set[str]] = {"books": set(), "manga": set()}

    for block, depth in flat_blocks:
        text = block_text(block)
        if not text:
            continue
        block_type = str(block.get("type", ""))
        label = normalize_label(text)
        section = section_for_label(label)
        if section:
            active_section = section
            active_depth = depth
            continue
        if active_section and depth <= active_depth and block_type.startswith("heading"):
            active_section = ""
            active_depth = -1
        if not active_section:
            continue
        if block_type not in {"bulleted_list_item", "numbered_list_item", "to_do", "paragraph", "toggle"}:
            continue
        title, opinion = extract_title_and_opinion(text)
        if not title or normalize_label(title) in {"books", "book", "manga", "mangas"}:
            continue
        key = normalize_label(title)
        if key in seen[active_section]:
            continue
        seen[active_section].add(key)
        item_type = "book" if active_section == "books" else "manga"
        item = {"type": item_type, "title": title, "opinion": opinion}
        if opinion:
            history_entries.append(item)
        else:
            current[active_section].append({"title": title, "opinion": ""})

    history_by_year = [{"year": "Read", "entries": history_entries}] if history_entries else []

    return {
        "source": secret("NOTION_READING_PAGE_URL").strip() or DEFAULT_READING_URL,
        "currently_watching": current,
        "history_by_year": history_by_year,
    }


def detail_key(media_type: str, title: str) -> str:
    normalized = re.sub(r"[^\w\s]", "", str(title or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f"{media_type}:{normalized}"


def cover_url(doc: dict[str, Any]) -> str:
    cover_id = doc.get("cover_i")
    if isinstance(cover_id, int):
        return f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
    isbn = doc.get("isbn")
    if isinstance(isbn, list) and isbn:
        first_isbn = str(isbn[0]).strip()
        if first_isbn:
            return f"https://covers.openlibrary.org/b/isbn/{urllib.parse.quote(first_isbn)}-L.jpg"
    return ""


def fetch_book_detail(title: str, media_type: str) -> dict[str, Any]:
    result: dict[str, Any] = {"title": title, "media_type": media_type}
    params = {
        "title": title,
        "limit": "10",
        "fields": "key,title,author_name,first_publish_year,cover_i,isbn,subject,ratings_average,ratings_count,edition_count,number_of_pages_median",
    }
    try:
        payload = fetch_json(f"{OPEN_LIBRARY_SEARCH_URL}?{urllib.parse.urlencode(params)}")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        return result
    docs = payload.get("docs", []) if isinstance(payload, dict) else []
    if not isinstance(docs, list) or not docs:
        return result
    wanted = re.sub(r"[^\w\s]", " ", title.lower())
    wanted = re.sub(r"\s+", " ", wanted).strip()
    ranked = []
    for index, candidate in enumerate(docs):
        if not isinstance(candidate, dict):
            continue
        candidate_title = re.sub(r"[^\w\s]", " ", str(candidate.get("title") or "").lower())
        candidate_title = re.sub(r"\s+", " ", candidate_title).strip()
        exact = 1 if candidate_title == wanted else 0
        starts = 1 if candidate_title.startswith(wanted) and wanted else 0
        has_cover = 1 if candidate.get("cover_i") else 0
        edition_count = int(candidate.get("edition_count") or 0)
        ratings_count = int(candidate.get("ratings_count") or 0)
        ranked.append((exact, starts, has_cover, edition_count, ratings_count, -index, candidate))
    if not ranked:
        return result
    ranked.sort(reverse=True)
    first = ranked[0][-1]
    if not isinstance(first, dict):
        return result
    authors = [str(author).strip() for author in first.get("author_name", []) if str(author).strip()]
    subjects = [str(subject).strip() for subject in first.get("subject", []) if str(subject).strip()]
    open_library_key = str(first.get("key") or "").strip()
    result["poster_url"] = cover_url(first)
    result["release_date"] = str(first.get("first_publish_year") or "").strip()
    result["description"] = ""
    result["genres"] = subjects[:8]
    result["authors"] = authors[:6]
    result["directors"] = authors[:6]
    result["actors"] = []
    result["rating"] = first.get("ratings_average") if isinstance(first.get("ratings_average"), (int, float)) else None
    result["number_of_pages"] = first.get("number_of_pages_median") if isinstance(first.get("number_of_pages_median"), int) else None
    result["open_library_url"] = f"https://openlibrary.org{open_library_key}" if open_library_key else ""
    return result


def all_reading_titles(payload: dict[str, Any]) -> list[tuple[str, str]]:
    titles: list[tuple[str, str]] = []
    current = payload.get("currently_watching", {})
    if isinstance(current, dict):
        for media_type, key in (("book", "books"), ("manga", "manga")):
            items = current.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                title = str(item.get("title", "") if isinstance(item, dict) else item).strip()
                if title:
                    titles.append((media_type, title))
    for group in payload.get("history_by_year", []):
        if not isinstance(group, dict):
            continue
        entries = group.get("entries", [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            media_type = str(entry.get("type") or "").strip()
            title = str(entry.get("title") or "").strip()
            if media_type in {"book", "manga"} and title:
                titles.append((media_type, title))
    seen = set()
    deduped = []
    for media_type, title in titles:
        key = detail_key(media_type, title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((media_type, title))
    return deduped


def enrich_reading_details(payload: dict[str, Any]) -> None:
    cache: dict[str, Any] = {}
    if DETAILS_OUTPUT_PATH.exists():
        try:
            parsed = json.loads(DETAILS_OUTPUT_PATH.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                cache = {str(key): value for key, value in parsed.items() if isinstance(value, dict)}
        except json.JSONDecodeError:
            cache = {}
    for media_type, title in all_reading_titles(payload):
        key = detail_key(media_type, title)
        existing = cache.get(key, {})
        if existing.get("poster_url") and existing.get("open_library_url"):
            continue
        fetched = fetch_book_detail(title, media_type)
        merged = {**existing, **{k: v for k, v in fetched.items() if v not in ("", None, [])}}
        merged.setdefault("title", title)
        merged.setdefault("media_type", media_type)
        cache[key] = merged
    DETAILS_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DETAILS_OUTPUT_PATH.write_text(json.dumps(dict(sorted(cache.items())), indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    token = secret("NOTION_TOKEN") or secret("NOTION_API_TOKEN")
    if not token:
        raise RuntimeError("Missing NOTION_TOKEN")

    page_id = extract_page_id()
    try:
        root_blocks = get_block_children(page_id, token, "reading root")
    except urllib.error.HTTPError as error:
        if error.code in {403, 404}:
            message = (
                "Notion could not read the My Reading page. Share the exact page with the integration "
                "used by NOTION_TOKEN, then rerun this scraper."
            )
            if OUTPUT_PATH.exists():
                print(f"Warning: {message} Keeping existing {OUTPUT_PATH}.")
                try:
                    existing_payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    existing_payload = FALLBACK_PAYLOAD
                enrich_reading_details(existing_payload)
                return 0
            print(f"Warning: {message} Writing fallback reading list.")
            OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT_PATH.write_text(json.dumps(FALLBACK_PAYLOAD, indent=2, ensure_ascii=False), encoding="utf-8")
            enrich_reading_details(FALLBACK_PAYLOAD)
            return 0
        raise
    flat = flatten_blocks(root_blocks, token)
    payload = parse_reading_list(flat)
    if not payload.get("currently_watching", {}).get("books") and not payload.get("history_by_year"):
        payload = FALLBACK_PAYLOAD

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    enrich_reading_details(payload)
    print(f"Wrote reading list to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
