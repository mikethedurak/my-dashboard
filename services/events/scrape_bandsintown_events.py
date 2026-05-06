from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from env import get as env_get
from event_tags import tag_event, is_excluded_event


SOURCE_URL = env_get("SCRAPE_BANDSINTOWN_EVENTS_URL", "https://www.bandsintown.com/c/cape-town-south-africa")
EVENTS_MAX_ITEMS = int(env_get("SCRAPE_BANDSINTOWN_MAX_ITEMS", "40"))
REPO_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_DIR / "data" / "events"
JSON_OUTPUT = OUTPUT_DIR / "bandsintown_events.json"
LOCAL_TZ = timezone(timedelta(hours=2), "SAST")


class BandsintownCityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_anchor = False
        self.current_href = ""
        self.current_text: list[str] = []
        self.current_image = ""
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag == "a":
            href = attributes.get("href", "")
            if "/e/" in href:
                self.in_anchor = True
                self.current_href = href
                self.current_text = []
                self.current_image = ""
        elif tag == "img" and self.in_anchor:
            self.current_image = normalize_url(attributes.get("src", "") or attributes.get("data-src", ""))
            alt = attributes.get("alt", "")
            if alt:
                self.current_text.append(alt)

    def handle_data(self, data: str) -> None:
        if self.in_anchor:
            text = data.strip()
            if text:
                self.current_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self.in_anchor:
            return
        text = clean_text(" ".join(self.current_text))
        if self.current_href and text:
            self.links.append(
                {
                    "url": normalize_url(self.current_href),
                    "text": text,
                    "image": self.current_image,
                }
            )
        self.in_anchor = False
        self.current_href = ""
        self.current_text = []
        self.current_image = ""


def clean_text(value: str) -> str:
    text = re.sub(r"\s+", " ", html.unescape(value or "")).strip()
    if "Ã" in text or "Â" in text:
        try:
            text = text.encode("latin1").decode("utf-8")
        except UnicodeError:
            pass
    return text


def normalize_url(url: str) -> str:
    raw = html.unescape(str(url or "").strip())
    if not raw:
        return ""
    if raw.startswith("//"):
        return f"https:{raw}"
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return urllib.parse.urljoin(SOURCE_URL, raw)


def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; my-dashboard/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_city_links(page_html: str) -> list[dict[str, str]]:
    parser = BandsintownCityParser()
    parser.feed(page_html)
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for link in parser.links:
        url = link["url"]
        if not url or url in seen:
            continue
        seen.add(url)
        links.append(link)
    return links


def json_ld_payloads(page_html: str) -> list[dict]:
    matches = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    payloads: list[dict] = []
    for match in matches:
        raw = html.unescape(match).strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            payloads.append(parsed)
        elif isinstance(parsed, list):
            payloads.extend(item for item in parsed if isinstance(item, dict))
    return payloads


def find_json_ld_event(page_html: str) -> dict:
    for payload in json_ld_payloads(page_html):
        candidates = []
        if payload.get("@graph") and isinstance(payload["@graph"], list):
            candidates.extend(item for item in payload["@graph"] if isinstance(item, dict))
        candidates.append(payload)
        for item in candidates:
            event_type = item.get("@type")
            event_types = event_type if isinstance(event_type, list) else [event_type]
            if "Event" in event_types or "MusicEvent" in event_types:
                return item
    return {}


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    except ValueError:
        return None


def first_image(value: object) -> str:
    if isinstance(value, str):
        return normalize_url(value)
    if isinstance(value, list):
        for item in value:
            image = first_image(item)
            if image:
                return image
    if isinstance(value, dict):
        return normalize_url(str(value.get("url") or value.get("contentUrl") or ""))
    return ""


def extract_genres(value: object) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"[,/|]", value)
        genres = [clean_text(part) for part in parts if clean_text(part)]
        return genres
    if isinstance(value, list):
        genres: list[str] = []
        for item in value:
            genres.extend(extract_genres(item))
        return list(dict.fromkeys(genres))
    return []


def event_from_json_ld(payload: dict, fallback: dict[str, str]) -> dict:
    location = payload.get("location") if isinstance(payload.get("location"), dict) else {}
    address = location.get("address") if isinstance(location.get("address"), dict) else {}
    start = parse_dt(str(payload.get("startDate") or ""))
    title = clean_text(str(payload.get("name") or fallback.get("text") or ""))
    venue = clean_text(str(location.get("name") or ""))
    title, venue = split_artist_and_venue(title, venue)
    url = normalize_url(str(payload.get("url") or fallback.get("url") or ""))
    image = first_image(payload.get("image")) or fallback.get("image", "")
    locality = clean_text(str(address.get("addressLocality") or "Cape Town"))
    region = clean_text(str(address.get("addressRegion") or "Western Cape"))
    performer = payload.get("performer") if isinstance(payload.get("performer"), dict) else {}
    genre_tags = extract_genres(performer.get("genre", ""))

    return {
        "title": title,
        "artist": title,
        "start": start.isoformat() if start else "",
        "date_text": display_fallback_date(fallback.get("text", "")),
        "venue": venue,
        "locality": locality,
        "region": region,
        "address": clean_text(str(address.get("streetAddress") or "")),
        "image": image,
        "url": url,
        "source": "Bandsintown",
        "genre": ", ".join(genre_tags),
        "genre_tags": genre_tags,
        "categories": tag_event(title, venue),
    }


def display_fallback_date(text: str) -> str:
    match = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?\s+-\s+\d{1,2}:\d{2}\s*(?:AM|PM)\b",
        text,
        flags=re.IGNORECASE,
    )
    return clean_text(match.group(0)) if match else ""


def split_artist_and_venue(title: str, venue: str) -> tuple[str, str]:
    clean_title = clean_text(title)
    clean_venue = clean_text(venue)
    marker = " @ "
    if marker not in clean_title:
        return clean_title, clean_venue
    artist, suffix = clean_title.rsplit(marker, 1)
    if not clean_venue:
        clean_venue = clean_text(suffix)
    if clean_venue and suffix.lower() == clean_venue.lower():
        return clean_text(artist), clean_venue
    return clean_title, clean_venue


def event_from_listing(link: dict[str, str]) -> dict:
    text = clean_text(link.get("text", ""))
    date_text = display_fallback_date(text)
    title = clean_text(text.replace(date_text, "")) if date_text else text
    title, venue = split_artist_and_venue(title, "")
    return {
        "title": title,
        "artist": title,
        "start": "",
        "date_text": date_text,
        "venue": venue,
        "locality": "Cape Town",
        "region": "Western Cape",
        "address": "",
        "image": link.get("image", ""),
        "url": link.get("url", ""),
        "source": "Bandsintown",
        "genre": "",
        "genre_tags": [],
        "categories": tag_event(title, ""),
    }


def scrape(limit: int) -> list[dict]:
    print(f"Scanning Bandsintown: {SOURCE_URL}")
    links = parse_city_links(fetch_html(SOURCE_URL))
    print(f"  Found {len(links)} event link(s), limit {limit}.")
    events: list[dict] = []
    seen_urls: set[str] = set()

    for link in links:
        url = link.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        event = event_from_listing(link)
        try:
            payload = find_json_ld_event(fetch_html(url))
            if payload:
                event = event_from_json_ld(payload, link)
        except Exception:
            pass
        if not event.get("title") or is_excluded_event(event["title"], event.get("venue", "")):
            continue
        events.append(event)
        if len(events) >= limit:
            break
    print(f"Scraped {len(events)} Bandsintown event(s).")
    return events


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Cape Town concerts from Bandsintown.")
    parser.add_argument("--limit", type=int, default=EVENTS_MAX_ITEMS, help="Maximum number of events to collect.")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = scrape(limit=args.limit)
    JSON_OUTPUT.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(events)} Bandsintown event(s) to {JSON_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
