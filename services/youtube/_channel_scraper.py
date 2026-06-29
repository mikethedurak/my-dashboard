"""Shared logic for per-channel YouTube RSS scrapers."""
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


DATA_DIR = Path(__file__).resolve().parents[2] / "docs" / "data" / "youtube"
CACHE_PATH = DATA_DIR / "channel_cache.json"

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


# ── cache ─────────────────────────────────────────────────────────────────────

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


# ── channel ID resolution ─────────────────────────────────────────────────────

def resolve_channel_id_via_ytdlp(channel_url: str, timeout: int) -> str:
    command = ["python", "-m", "yt_dlp", "--flat-playlist", "--dump-single-json", "--playlist-end", "1", channel_url]
    completed = subprocess.run(
        command, check=True, capture_output=True, text=True,
        timeout=max(30, timeout * 10),
    )
    payload = json.loads(completed.stdout)
    channel_id = str(payload.get("channel_id", "")).strip() or str(payload.get("id", "")).strip()
    if not channel_id:
        raise ValueError(f"yt-dlp could not resolve channel id from {channel_url}")
    return channel_id


def resolve_channel_id_via_html(channel_url: str, timeout: int) -> str:
    request = urllib.request.Request(
        channel_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; my-dashboard-youtube/1.0)", "Accept": "text/html,*/*"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    for pattern in [
        r'"channelId"\s*:\s*"([^"]+)"',
        r'<meta\s+itemprop="channelId"\s+content="([^"]+)"',
        r'"externalId"\s*:\s*"([^"]+)"',
    ]:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    raise ValueError(f"Could not resolve channel id from {channel_url}")


def get_channel_id(channel_name: str, channel_url: str, timeout: int) -> str:
    cache = load_cache()
    cached_id = str(cache.get(channel_url, {}).get("channel_id", "")).strip()
    if cached_id:
        print(f"Using cached channel id: {cached_id}", flush=True)
        return cached_id
    print(f"Resolving channel id for {channel_name}...", flush=True)
    try:
        channel_id = resolve_channel_id_via_html(channel_url, timeout)
    except (urllib.error.URLError, TimeoutError, ValueError):
        channel_id = resolve_channel_id_via_ytdlp(channel_url, timeout)
    cache[channel_url] = {
        "channel_id": channel_id,
        "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    save_cache(cache)
    return channel_id


# ── feed helpers ──────────────────────────────────────────────────────────────

def atom_text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    found = node.find(path, ATOM_NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def iso_from_upload_date(raw: str) -> str:
    value = str(raw or "").strip()
    if len(value) == 8 and value.isdigit():
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}T00:00:00+00:00"
    return ""


def iso_from_unix(raw: object) -> str:
    try:
        timestamp = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


# ── RSS scrape (daily) ────────────────────────────────────────────────────────

def is_short_item(item: dict) -> bool:
    url = str(item.get("url", "")).strip().lower()
    title = str(item.get("title", "")).strip().lower()
    return "/shorts/" in url or re.search(r"#shorts?\b", title) is not None


def normal_video_items(items: list[dict]) -> list[dict]:
    return [item for item in items if not is_short_item(item)]


def fetch_rss_items(channel_id: str, limit: int, timeout: int) -> list[dict]:
    feed_url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + urllib.parse.quote(channel_id, safe="")
    request = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; my-dashboard-youtube/1.0)", "Accept": "application/xml,*/*"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        xml_text = resp.read().decode("utf-8", errors="replace")
    root = ET.fromstring(xml_text)
    items: list[dict] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        video_id = atom_text(entry, "yt:videoId")
        title = atom_text(entry, "atom:title")
        published_at = atom_text(entry, "atom:published")
        updated_at = atom_text(entry, "atom:updated")
        link = ""
        entry_link = entry.find("atom:link[@rel='alternate']", ATOM_NS)
        if entry_link is not None:
            link = (entry_link.attrib.get("href") or "").strip()
        if not link and video_id:
            link = f"https://www.youtube.com/watch?v={video_id}"
        item = {
            "id": f"yt-{video_id}" if video_id else "",
            "video_id": video_id,
            "title": title,
            "url": link,
            "published_at": published_at,
            "updated_at": updated_at,
            "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
        }
        if is_short_item(item):
            continue
        items.append(item)
        if limit > 0 and len(items) >= limit:
            break
    return items


# ── yt-dlp full scrape (backfill) ────────────────────────────────────────────

def fetch_full_via_ytdlp(channel_name: str, channel_id: str, timeout: int, start: int, end: int | None) -> list[dict]:
    videos_url = f"https://www.youtube.com/channel/{channel_id}/videos"
    start_index = max(1, start)
    end_index = end if end is not None else 99999
    command = [
        "python", "-m", "yt_dlp",
        "--flat-playlist", "--dump-single-json",
        "--playlist-start", str(start_index),
        "--playlist-end", str(end_index),
        videos_url,
    ]
    print(f"Fetching full history for {channel_name} (items {start_index}–{end_index}) via yt-dlp...", flush=True)
    completed = subprocess.run(
        command, check=True, stdout=subprocess.PIPE, stderr=None, text=True,
        timeout=max(60, timeout * 20),
    )
    payload = json.loads(completed.stdout)
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return []
    items: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id", "")).strip()
        title = str(entry.get("title", "")).strip()
        video_url = str(entry.get("url", "")).strip()
        if not video_url and video_id:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        upload_date = str(entry.get("upload_date", "")).strip()
        published_at = (
            iso_from_upload_date(upload_date)
            or iso_from_unix(entry.get("release_timestamp"))
            or iso_from_unix(entry.get("timestamp"))
        )
        items.append({
            "id": f"yt-{video_id}" if video_id else "",
            "video_id": video_id,
            "title": title,
            "url": video_url,
            "published_at": published_at,
            "updated_at": "",
            "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
        })
    return items


# ── payload helpers ───────────────────────────────────────────────────────────

def empty_payload(channel_name: str, channel_url: str) -> dict:
    return {
        "source": "youtube-rss",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "channel_name": channel_name,
        "channel_id": "",
        "channel_url": channel_url,
        "items_count": 0,
        "items": [],
    }


def load_existing(output_path: Path, channel_name: str, channel_url: str) -> dict:
    if not output_path.exists():
        return empty_payload(channel_name, channel_url)
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_payload(channel_name, channel_url)
    return payload if isinstance(payload, dict) else empty_payload(channel_name, channel_url)


def write_payload(payload: dict, output_path: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {payload['items_count']} item(s) to {output_path}", flush=True)


def merge_items(existing_items: list[dict], new_items: list[dict]) -> list[dict]:
    existing_items = normal_video_items(existing_items)
    new_items = normal_video_items(new_items)
    seen: set[str] = {str(item.get("video_id", "")).strip() for item in existing_items if item.get("video_id")}
    added = 0
    for item in new_items:
        vid = str(item.get("video_id", "")).strip()
        if vid and vid not in seen:
            existing_items.append(item)
            seen.add(vid)
            added += 1
    if added:
        existing_items.sort(key=lambda i: str(i.get("published_at", "")), reverse=True)
        print(f"Added {added} new item(s).", flush=True)
    else:
        print("No new items found.", flush=True)
    return existing_items


# ── entry point ───────────────────────────────────────────────────────────────

def run_channel_scraper(channel_name: str, channel_url: str, output_path: Path) -> int:
    parser = argparse.ArgumentParser(description=f"Scrape uploads from {channel_name}.")
    parser.add_argument("--mode", choices=["daily", "backfill"], default="daily",
                        help="daily=RSS merge (default), backfill=full yt-dlp history.")
    parser.add_argument("--limit", type=int, default=15, help="RSS item limit for daily mode (default: 15).")
    parser.add_argument("--start", type=int, default=1, help="Playlist start index for backfill (default: 1).")
    parser.add_argument("--end", type=int, default=0, help="Playlist end index for backfill. 0 = all.")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout in seconds (default: 20).")
    args = parser.parse_args()

    timeout = max(5, args.timeout)

    try:
        channel_id = get_channel_id(channel_name, channel_url, timeout)

        if args.mode == "backfill":
            print("Backfill mode: fetching full video history via yt-dlp...", flush=True)
            end = args.end if args.end > 0 else None
            items = fetch_full_via_ytdlp(channel_name, channel_id, timeout, start=max(1, args.start), end=end)
            items.sort(key=lambda i: str(i.get("published_at", "")), reverse=True)
            payload = {
                "source": "youtube-ytdlp",
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "channel_name": channel_name,
                "channel_id": channel_id,
                "channel_url": channel_url,
                "items_count": len(items),
                "items": items,
            }
        else:
            print("Daily mode: fetching recent videos via RSS and merging...", flush=True)
            rss_items = fetch_rss_items(channel_id, limit=max(1, args.limit), timeout=timeout)
            payload = load_existing(output_path, channel_name, channel_url)
            payload["channel_id"] = payload.get("channel_id") or channel_id
            merged = merge_items(list(payload.get("items", [])), rss_items)
            payload["items"] = merged
            payload["items_count"] = len(merged)
            payload["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            payload["source"] = "youtube-rss"

        write_payload(payload, output_path)
    except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"Error scraping {channel_name}: {error}", flush=True)
        return 1
    return 0
