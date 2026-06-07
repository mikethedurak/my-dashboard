from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "docs" / "data" / "youtube"
OUTPUT_PATH = DATA_DIR / "latest_uploads.json"
CACHE_PATH = DATA_DIR / "channel_cache.json"
MANUAL_CHAPTERS_PATH = DATA_DIR / "manual_chapters.json"

DEFAULT_CHANNELS = [
    {
        "name": "PlotArmor",
        "url": "https://www.youtube.com/@PlotArmor",
    }
]

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}
ONE_PIECE_CHAPTER_PATTERNS = [
    re.compile(r"\bone\s*piece\b.*?\bchapter\s*(\d{3,4})\b", re.IGNORECASE),
    re.compile(r"\bone\s*piece\b[^0-9]{0,20}(\d{3,4})\b", re.IGNORECASE),
]
ONE_PIECE_TITLE_RE = re.compile(r"\bone\s*piece\b", re.IGNORECASE)


def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def load_manual_chapters() -> list[dict]:
    if not MANUAL_CHAPTERS_PATH.exists():
        return []
    try:
        payload = json.loads(MANUAL_CHAPTERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    items = payload.get("items", []) if isinstance(payload, dict) else []
    return [item for item in items if isinstance(item, dict)]


def save_manual_chapters(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "items": items,
    }
    MANUAL_CHAPTERS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def video_id_from_url(url: str) -> str:
    value = str(url or "").strip()
    match = re.search(r"[?&]v=([a-zA-Z0-9_-]{6,})", value)
    if match:
        return match.group(1).strip()
    shorts_match = re.search(r"/shorts/([a-zA-Z0-9_-]{6,})", value)
    if shorts_match:
        return shorts_match.group(1).strip()
    return ""


def fetch_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; my-dashboard-youtube/1.0)",
            "Accept": "application/xml,text/xml,text/html,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def resolve_channel_id(channel_url: str, timeout: int) -> str:
    html = fetch_text(channel_url, timeout)
    patterns = [
        r'"channelId"\s*:\s*"([^"]+)"',
        r'<meta\s+itemprop="channelId"\s+content="([^"]+)"',
        r'"externalId"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    raise ValueError(f"Could not resolve channel id from {channel_url}")


def resolve_channel_id_via_ytdlp(channel_url: str, timeout: int) -> str:
    command = [
        "python",
        "-m",
        "yt_dlp",
        "--flat-playlist",
        "--dump-single-json",
        channel_url,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=max(30, timeout * 10),
    )
    payload = json.loads(completed.stdout)
    channel_id = str(payload.get("channel_id", "")).strip() or str(payload.get("id", "")).strip()
    if not channel_id:
        raise ValueError(f"yt-dlp could not resolve channel id from {channel_url}")
    return channel_id


def atom_text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    found = node.find(path, ATOM_NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def item_search_text(item: dict) -> str:
    parts = [
        str(item.get("title", "") or ""),
        str(item.get("description", "") or ""),
    ]
    tags = item.get("tags", [])
    if isinstance(tags, list):
        parts.extend(str(tag) for tag in tags)
    elif tags:
        parts.append(str(tags))
    return "\n".join(part for part in parts if part).strip()


def one_piece_chapter_from_item(item: dict) -> int | None:
    search_text = item_search_text(item)
    if not search_text:
        return None
    for pattern in ONE_PIECE_CHAPTER_PATTERNS:
        match = pattern.search(search_text)
        if match:
            return int(match.group(1))
    return None


def parse_feed(channel_name: str, channel_id: str, xml_text: str, limit: int) -> dict:
    root = ET.fromstring(xml_text)
    feed_title = atom_text(root, "atom:title") or channel_name
    channel_link = ""
    link_node = root.find("atom:link[@rel='alternate']", ATOM_NS)
    if link_node is not None:
        channel_link = (link_node.attrib.get("href") or "").strip()

    items: list[dict] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        video_id = atom_text(entry, "yt:videoId")
        title = atom_text(entry, "atom:title")
        description = atom_text(entry, "media:group/media:description") or atom_text(entry, "atom:summary")
        published_at = atom_text(entry, "atom:published")
        updated_at = atom_text(entry, "atom:updated")
        link = ""
        entry_link = entry.find("atom:link[@rel='alternate']", ATOM_NS)
        if entry_link is not None:
            link = (entry_link.attrib.get("href") or "").strip()
        if not link and video_id:
            link = f"https://www.youtube.com/watch?v={video_id}"
        items.append(
            {
                "id": f"yt-{video_id}" if video_id else "",
                "video_id": video_id,
                "title": title,
                "description": description,
                "url": link,
                "published_at": published_at,
                "updated_at": updated_at,
                "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
            }
        )
        if limit > 0 and len(items) >= limit:
            break

    return {
        "channel_name": feed_title,
        "channel_id": channel_id,
        "channel_url": channel_link,
        "items": items,
    }


def one_piece_chapter_entry(item: dict, channel: dict) -> dict | None:
    title = str(item.get("title", "")).strip()
    if not title:
        return None
    chapter_number = one_piece_chapter_from_item(item)
    if chapter_number is None:
        return None
    return {
        "id": item.get("id", ""),
        "video_id": item.get("video_id", ""),
        "title": title,
        "description": item.get("description", ""),
        "url": item.get("url", ""),
        "published_at": item.get("published_at", ""),
        "updated_at": item.get("updated_at", ""),
        "thumbnail_url": item.get("thumbnail_url", ""),
        "chapter": chapter_number,
        "channel_name": channel.get("channel_name", ""),
        "channel_id": channel.get("channel_id", ""),
    }


def one_piece_video_entry(item: dict, channel: dict) -> dict | None:
    title = str(item.get("title", "")).strip()
    tags = item.get("tags", [])
    if not title:
        return None
    if not ONE_PIECE_TITLE_RE.search(item_search_text(item)):
        return None
    return {
        "id": item.get("id", ""),
        "video_id": item.get("video_id", ""),
        "title": title,
        "description": item.get("description", ""),
        "url": item.get("url", ""),
        "published_at": item.get("published_at", ""),
        "updated_at": item.get("updated_at", ""),
        "thumbnail_url": item.get("thumbnail_url", ""),
        "tags": tags if isinstance(tags, list) else [],
        "channel_name": channel.get("channel_name", ""),
        "channel_id": channel.get("channel_id", ""),
    }


def metadata_for_video_url(url: str, timeout: int) -> dict:
    command = [
        "python",
        "-m",
        "yt_dlp",
        "--dump-single-json",
        "--skip-download",
        url,
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=max(30, timeout * 10),
        )
        payload = json.loads(completed.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        payload = {}

    video_id = str(payload.get("id", "")).strip() or video_id_from_url(url)
    title = str(payload.get("title", "")).strip() or f"One Piece Chapter"
    channel_name = str(payload.get("channel", "")).strip() or "Plot Armor"
    channel_id = str(payload.get("channel_id", "")).strip()
    upload_date = str(payload.get("upload_date", "")).strip()
    published_at = ""
    if len(upload_date) == 8 and upload_date.isdigit():
        published_at = f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00+00:00"
    thumbnail_url = str(payload.get("thumbnail", "")).strip()
    if not thumbnail_url and video_id:
        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    description = str(payload.get("description", "")).strip()

    return {
        "id": f"yt-{video_id}" if video_id else "",
        "video_id": video_id,
        "title": title,
        "description": description,
        "url": url,
        "published_at": published_at,
        "updated_at": "",
        "thumbnail_url": thumbnail_url,
        "tags": payload.get("tags", []) if isinstance(payload.get("tags", []), list) else [],
        "channel_name": channel_name,
        "channel_id": channel_id,
    }


def scrape_channels(channels: list[dict], timeout: int, limit: int, start: int, end: int | None) -> dict:
    channel_payloads: list[dict] = []
    errors: list[str] = []
    cache = load_cache()
    for channel in channels:
        name = str(channel.get("name", "")).strip() or "YouTube Channel"
        url = str(channel.get("url", "")).strip()
        if not url:
            continue
        try:
            cached_id = str(cache.get(url, {}).get("channel_id", "")).strip()
            channel_id = cached_id
            if channel_id:
                print(f"Using cached channel id for {name}: {channel_id}", flush=True)
            else:
                print(f"Resolving channel id for {name}...", flush=True)
                try:
                    channel_id = resolve_channel_id_via_ytdlp(url, timeout)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, ValueError):
                    channel_id = resolve_channel_id(url, timeout)
                cache[url] = {
                    "channel_id": channel_id,
                    "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                save_cache(cache)
            payload = scrape_channel_via_ytdlp(name, url, channel_id, limit, timeout, start, end)
            if payload is None:
                feed_url = (
                    "https://www.youtube.com/feeds/videos.xml?channel_id="
                    + urllib.parse.quote(channel_id, safe="")
                )
                payload = parse_feed(name, channel_id, fetch_text(feed_url, timeout), limit)
            channel_payloads.append(payload)
            print(f"Fetched {payload['channel_name']} ({channel_id})", flush=True)
        except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as error:
            errors.append(f"{name}: {error}")
            print(f"Skipped {name}: {error}", flush=True)

    one_piece_videos: list[dict] = []
    one_piece_chapters: list[dict] = []
    for channel in channel_payloads:
        for item in channel.get("items", []):
            if not isinstance(item, dict):
                continue
            video_item = one_piece_video_entry(item, channel)
            if video_item is not None:
                one_piece_videos.append(video_item)
            chapter_item = one_piece_chapter_entry(item, channel)
            if chapter_item is not None:
                one_piece_chapters.append(chapter_item)
    one_piece_videos.sort(key=lambda item: str(item.get("published_at", "")), reverse=True)
    one_piece_chapters.sort(
        key=lambda item: (
            int(item.get("chapter", 0)),
            str(item.get("published_at", "")),
        ),
        reverse=True,
    )
    chapter_keys = {
        (str(item.get("video_id", "")).strip(), str(item.get("url", "")).strip())
        for item in one_piece_chapters
    }
    one_piece_other = [
        item
        for item in one_piece_videos
        if (str(item.get("video_id", "")).strip(), str(item.get("url", "")).strip()) not in chapter_keys
    ]
    latest_one_piece_chapters = one_piece_chapters[:10]
    latest_one_piece_videos = one_piece_videos[:10]
    latest_one_piece_other = one_piece_other[:10]
    chapter_numbers = sorted({int(item.get("chapter", 0)) for item in one_piece_chapters if int(item.get("chapter", 0)) > 0})
    missing_chapters: list[int] = []
    chapter_range_start = chapter_numbers[0] if chapter_numbers else 0
    chapter_range_end = chapter_numbers[-1] if chapter_numbers else 0
    if chapter_numbers:
        existing = set(chapter_numbers)
        missing_chapters = [value for value in range(chapter_range_start, chapter_range_end + 1) if value not in existing]

    return {
        "source": "youtube-ytdlp",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "channels_count": len(channel_payloads),
        "error_count": len(errors),
        "errors": errors,
        "series": {
            "one_piece": {
                "label": "One Piece",
                "videos_count": len(one_piece_videos),
                "videos": one_piece_videos,
                "latest_videos_count": len(latest_one_piece_videos),
                "latest_videos": latest_one_piece_videos,
                "chapters_count": len(one_piece_chapters),
                "chapters": one_piece_chapters,
                "latest_episodes_count": len(latest_one_piece_chapters),
                "latest_episodes": latest_one_piece_chapters,
                "other_count": len(one_piece_other),
                "other": one_piece_other,
                "latest_other_count": len(latest_one_piece_other),
                "latest_other": latest_one_piece_other,
                "chapter_range_start": chapter_range_start,
                "chapter_range_end": chapter_range_end,
                "missing_chapters_count": len(missing_chapters),
                "missing_chapters": missing_chapters,
            }
        },
    }


def apply_manual_chapters(payload: dict, timeout: int) -> dict:
    one_piece = payload.get("series", {}).get("one_piece", {})
    videos = one_piece.get("videos", []) if isinstance(one_piece.get("videos", []), list) else []
    chapters = one_piece.get("chapters", []) if isinstance(one_piece.get("chapters", []), list) else []
    manual_items = load_manual_chapters()
    if not manual_items:
        return payload

    video_index = {
        (str(item.get("video_id", "")).strip(), str(item.get("url", "")).strip()): item
        for item in videos
        if isinstance(item, dict)
    }
    chapter_index = {
        (str(item.get("video_id", "")).strip(), str(item.get("url", "")).strip()): item
        for item in chapters
        if isinstance(item, dict)
    }

    for manual in manual_items:
        url = str(manual.get("url", "")).strip()
        chapter_value = int(manual.get("chapter", 0) or 0)
        if not url or chapter_value <= 0:
            continue
        video_id = video_id_from_url(url)
        key = (video_id, url)

        base = video_index.get(key)
        if base is None:
            base = metadata_for_video_url(url, timeout)
            if not str(base.get("url", "")).strip():
                base["url"] = url
            if not str(base.get("video_id", "")).strip():
                base["video_id"] = video_id
            videos.append(base)
            video_index[key] = base

        chapter_item = dict(base)
        chapter_item["chapter"] = chapter_value
        chapter_item["title"] = str(base.get("title", "")).strip() or f"One Piece Chapter {chapter_value}"
        chapter_item["manual_override"] = True

        if key in chapter_index:
            chapter_index[key].update(chapter_item)
        else:
            chapters.append(chapter_item)
            chapter_index[key] = chapter_item

    chapters.sort(
        key=lambda item: (
            int(item.get("chapter", 0)),
            str(item.get("published_at", "")),
        ),
        reverse=True,
    )
    videos.sort(key=lambda item: str(item.get("published_at", "")), reverse=True)

    chapter_keys = {
        (str(item.get("video_id", "")).strip(), str(item.get("url", "")).strip())
        for item in chapters
    }
    other = [
        item
        for item in videos
        if (str(item.get("video_id", "")).strip(), str(item.get("url", "")).strip()) not in chapter_keys
    ]
    chapter_numbers = sorted({int(item.get("chapter", 0)) for item in chapters if int(item.get("chapter", 0)) > 0})
    missing_chapters: list[int] = []
    chapter_range_start = chapter_numbers[0] if chapter_numbers else 0
    chapter_range_end = chapter_numbers[-1] if chapter_numbers else 0
    if chapter_numbers:
        existing = set(chapter_numbers)
        missing_chapters = [value for value in range(chapter_range_start, chapter_range_end + 1) if value not in existing]

    one_piece.update(
        {
            "videos_count": len(videos),
            "videos": videos,
            "latest_videos_count": len(videos[:10]),
            "latest_videos": videos[:10],
            "chapters_count": len(chapters),
            "chapters": chapters,
            "latest_episodes_count": len(chapters[:10]),
            "latest_episodes": chapters[:10],
            "other_count": len(other),
            "other": other,
            "latest_other_count": len(other[:10]),
            "latest_other": other[:10],
            "chapter_range_start": chapter_range_start,
            "chapter_range_end": chapter_range_end,
            "missing_chapters_count": len(missing_chapters),
            "missing_chapters": missing_chapters,
        }
    )
    payload.setdefault("series", {})["one_piece"] = one_piece
    return payload


def empty_payload() -> dict:
    return {
        "source": "youtube-ytdlp",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "channels_count": 0,
        "error_count": 0,
        "errors": [],
        "series": {
            "one_piece": {
                "label": "One Piece",
                "videos_count": 0,
                "videos": [],
                "latest_videos_count": 0,
                "latest_videos": [],
                "chapters_count": 0,
                "chapters": [],
                "latest_episodes_count": 0,
                "latest_episodes": [],
                "other_count": 0,
                "other": [],
                "latest_other_count": 0,
                "latest_other": [],
                "chapter_range_start": 0,
                "chapter_range_end": 0,
                "missing_chapters_count": 0,
                "missing_chapters": [],
            }
        },
    }


def load_existing_payload() -> dict:
    if not OUTPUT_PATH.exists():
        return empty_payload()
    try:
        payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_payload()
    if not isinstance(payload, dict):
        return empty_payload()
    payload.setdefault("series", {})
    payload["series"].setdefault("one_piece", empty_payload()["series"]["one_piece"])
    return payload


def scrape_recent_channels(channels: list[dict], timeout: int, limit: int) -> list[dict]:
    recent_payloads: list[dict] = []
    cache = load_cache()
    for channel in channels:
        name = str(channel.get("name", "")).strip() or "YouTube Channel"
        url = str(channel.get("url", "")).strip()
        if not url:
            continue
        channel_id = str(cache.get(url, {}).get("channel_id", "")).strip()
        if not channel_id:
            print(f"Resolving channel id for {name}...", flush=True)
            try:
                channel_id = resolve_channel_id_via_ytdlp(url, timeout)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, ValueError):
                channel_id = resolve_channel_id(url, timeout)
            cache[url] = {
                "channel_id": channel_id,
                "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            save_cache(cache)
        print(f"Fetching recent uploads via RSS for {name} ({channel_id})...", flush=True)
        feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + urllib.parse.quote(channel_id, safe="")
        payload = parse_feed(name, channel_id, fetch_text(feed_url, timeout), limit=max(1, limit))
        payload["channel_name"] = re.sub(r"\s*-\s*videos\s*$", "", str(payload.get("channel_name", "")).strip(), flags=re.IGNORECASE).strip() or name
        recent_payloads.append(payload)
    return recent_payloads


def merge_recent_into_payload(payload: dict, recent_channels: list[dict]) -> dict:
    one_piece = payload.get("series", {}).get("one_piece", {})
    videos = one_piece.get("videos", []) if isinstance(one_piece.get("videos", []), list) else []
    chapters = one_piece.get("chapters", []) if isinstance(one_piece.get("chapters", []), list) else []
    videos_by_key = {
        (str(item.get("video_id", "")).strip(), str(item.get("url", "")).strip()): item
        for item in videos
        if isinstance(item, dict)
    }
    chapters_by_key = {
        (str(item.get("video_id", "")).strip(), str(item.get("url", "")).strip()): item
        for item in chapters
        if isinstance(item, dict)
    }
    for channel in recent_channels:
        for item in channel.get("items", []):
            if not isinstance(item, dict):
                continue
            video_item = one_piece_video_entry(item, channel)
            chapter_item = one_piece_chapter_entry(item, channel)
            if video_item:
                key = (str(video_item.get("video_id", "")).strip(), str(video_item.get("url", "")).strip())
                if key not in videos_by_key:
                    videos.append(video_item)
                    videos_by_key[key] = video_item
            if chapter_item:
                key = (str(chapter_item.get("video_id", "")).strip(), str(chapter_item.get("url", "")).strip())
                if key not in chapters_by_key:
                    chapters.append(chapter_item)
                    chapters_by_key[key] = chapter_item
    one_piece["videos"] = videos
    one_piece["chapters"] = chapters
    payload.setdefault("series", {})["one_piece"] = one_piece
    return apply_manual_chapters(payload, timeout=20)


def scrape_channel_via_ytdlp(
    channel_name: str,
    channel_url: str,
    channel_id: str,
    limit: int,
    timeout: int,
    start: int,
    end: int | None,
) -> dict | None:
    videos_url = f"https://www.youtube.com/channel/{channel_id}/videos"
    start_index = max(1, start)
    end_index = end if end is not None else max(start_index, start_index + max(1, limit) - 1)
    command = [
        "python",
        "-m",
        "yt_dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--playlist-start",
        str(start_index),
        "--playlist-end",
        str(max(start_index, end_index)),
        videos_url,
    ]
    print(
        f"Scraping {channel_name} videos {start_index} to {max(start_index, end_index)} with yt-dlp...",
        flush=True,
    )
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            timeout=max(30, timeout * 10),
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None

    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return None

    items: list[dict] = []

    def iso_from_upload_date(raw: str) -> str:
        value = str(raw or "").strip()
        if len(value) == 8 and value.isdigit():
            return f"{value[0:4]}-{value[4:6]}-{value[6:8]}T00:00:00+00:00"
        return ""

    def iso_from_unix(raw: object) -> str:
        try:
            timestamp = int(raw)
        except (TypeError, ValueError):
            return ""
        if timestamp <= 0:
            return ""
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id", "")).strip()
        title = str(entry.get("title", "")).strip()
        description = str(entry.get("description", "")).strip()
        video_url = str(entry.get("url", "")).strip()
        if not video_url and video_id:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        upload_date = str(entry.get("upload_date", "")).strip()
        published_at = (
            iso_from_upload_date(upload_date)
            or iso_from_unix(entry.get("release_timestamp"))
            or iso_from_unix(entry.get("timestamp"))
        )
        items.append(
            {
                "id": f"yt-{video_id}" if video_id else "",
                "video_id": video_id,
                "title": title,
                "description": description,
                "url": video_url,
                "published_at": published_at,
                "updated_at": "",
                "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
            }
        )

    channel_title = str(payload.get("title", "")).strip() or channel_name
    channel_title = re.sub(r"\s*-\s*videos\s*$", "", channel_title, flags=re.IGNORECASE).strip()
    return {
        "channel_name": channel_title,
        "channel_id": channel_id,
        "channel_url": channel_url,
        "items": items,
    }


def write_payload(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    total_items = len(payload.get("series", {}).get("one_piece", {}).get("videos", []))
    print(f"Wrote {total_items} video item(s) to {OUTPUT_PATH}", flush=True)
    one_piece = payload.get("series", {}).get("one_piece", {})
    start = int(one_piece.get("chapter_range_start") or 0)
    end = int(one_piece.get("chapter_range_end") or 0)
    missing = one_piece.get("missing_chapters", [])
    if start and end:
        if missing:
            full_list = ", ".join(str(value) for value in missing)
            print(f"Missing chapter numbers between {start} and {end}: {full_list} (total {len(missing)})", flush=True)
        else:
            print(f"No missing chapter numbers between {start} and {end}.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape latest uploads from YouTube channels via RSS.")
    parser.add_argument("--channel-url", default="", help="Optional channel URL to scrape (e.g. https://www.youtube.com/@PlotArmor).")
    parser.add_argument("--channel-name", default="", help="Optional display name when --channel-url is used.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum videos per channel (default: 10).")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout in seconds (default: 20).")
    parser.add_argument("--start", type=int, default=1, help="1-based playlist start index (default: 1).")
    parser.add_argument("--end", type=int, default=0, help="1-based playlist end index. 0 means derive from --limit.")
    parser.add_argument("--manual-only", action="store_true", help="Skip channel scrape and only merge/enrich manual chapters.")
    parser.add_argument("--mode", choices=["daily", "backfill"], default="daily", help="daily=RSS incremental + manual merge (default), backfill=full channel scrape + manual merge.")
    parser.add_argument(
        "--add-manual",
        nargs=2,
        action="append",
        metavar=("VIDEO_URL", "CHAPTER"),
        help="Add manual chapter mapping (can be passed multiple times).",
    )
    args = parser.parse_args()

    channels = DEFAULT_CHANNELS
    if args.channel_url.strip():
        channels = [
            {
                "name": args.channel_name.strip() or "YouTube Channel",
                "url": args.channel_url.strip(),
            }
        ]

    if args.add_manual:
        existing = load_manual_chapters()
        by_url = {str(item.get("url", "")).strip(): item for item in existing if str(item.get("url", "")).strip()}
        for pair in args.add_manual:
            url = str(pair[0] or "").strip()
            try:
                chapter_value = int(str(pair[1] or "0").strip())
            except ValueError:
                chapter_value = 0
            if not url or chapter_value <= 0:
                continue
            by_url[url] = {"url": url, "chapter": chapter_value}
        updated = sorted(by_url.values(), key=lambda item: int(item.get("chapter", 0)))
        save_manual_chapters(updated)
        print(f"Saved {len(updated)} manual chapter mapping(s) to {MANUAL_CHAPTERS_PATH}", flush=True)

    end = args.end if args.end > 0 else None
    if args.manual_only:
        print("Manual-only mode: skipping full channel scrape.", flush=True)
        payload = load_existing_payload()
    elif args.mode == "daily":
        print("Daily mode: recent uploads + manual merge.", flush=True)
        payload = load_existing_payload()
        recent = scrape_recent_channels(channels, timeout=max(5, args.timeout), limit=max(1, args.limit))
        payload = merge_recent_into_payload(payload, recent)
    else:
        print("Backfill mode: full channel scrape + manual merge.", flush=True)
        payload = scrape_channels(
            channels,
            timeout=max(5, args.timeout),
            limit=max(1, args.limit),
            start=max(1, args.start),
            end=end,
        )
        payload = apply_manual_chapters(payload, timeout=max(5, args.timeout))
    if args.manual_only:
        payload = apply_manual_chapters(payload, timeout=max(5, args.timeout))
    write_payload(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
