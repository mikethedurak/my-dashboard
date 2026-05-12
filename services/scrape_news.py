from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "data" / "news"
DOCS_DIR = REPO_DIR / "docs" / "data" / "news"
NEWS_FILE = DATA_DIR / "news.json"
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "sources": ["rss"],
    "categories": ["Global", "South Africa", "Cape Town", "Cape Town Events", "Games", "F1", "Entertainment", "Climbing"],
    "max_items_per_category": 10,
    "max_top_items_per_category": 5,
    "importance_mode": "balanced",
    "importance_threshold": 5,
    "breaking_threshold": 8,
    "max_article_age_hours": 72,
    "category_max_age_hours": {
        "Global": 48,
        "South Africa": 48,
        "Cape Town": 48,
        "Cape Town Events": 168,
        "Games": 72,
        "F1": 72,
        "Entertainment": 72,
        "Climbing": 168,
    },
    "source_weights": {
        "BBC World": 2,
        "Al Jazeera": 2,
        "The Guardian World": 2,
        "GroundUp": 2,
        "IOL South Africa": 1,
        "GameSpot": 1,
        "PC Gamer": 1,
        "PlayStation Blog": 1,
        "BBC Sport F1": 2,
        "Motorsport.com F1": 2,
        "Variety": 2,
        "The Hollywood Reporter": 2,
        "Deadline": 2,
        "Cape Town ETC": 1,
        "IOL Cape Times": 1,
        "What's On in Cape Town Events": 2,
        "What's On Weekend": 3,
        "Events in Cape Town": 2,
        "Wesgro Travel Events": 2,
        "Gripped": 1,
        "GearJunkie Climbing": 1,
        "Alpinist": 1,
    },
    "importance_keywords": {
        "high": [
            "breaking",
            "just in",
            "live updates",
            "earthquake",
            "flood",
            "wildfire",
            "evacuation",
            "election",
            "court",
            "ruling",
            "parliament",
            "sanction",
            "war",
            "ceasefire",
            "attack",
            "security breach",
            "outage",
            "shutdown",
            "recall",
            "merger",
            "acquisition",
            "bankruptcy",
            "strike",
            "protest",
            "death",
            "killed",
            "missing",
        ],
        "medium": [
            "policy",
            "regulation",
            "investigation",
            "launch",
            "release date",
            "confirmed",
            "delay",
            "lawsuit",
            "trial",
            "injury",
            "record",
            "forecast",
            "inflation",
            "interest rate",
            "power cuts",
            "load shedding",
            "eskom",
            "weekend",
            "this week",
            "festival",
            "live music",
            "concert",
            "market",
            "exhibition",
            "workshop",
            "tickets",
        ],
    },
    "request_timeout_seconds": 25,
    "feeds": [
        {
            "name": "BBC World",
            "category": "Global",
            "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        },
        {
            "name": "Al Jazeera",
            "category": "Global",
            "url": "https://www.aljazeera.com/xml/rss/all.xml",
        },
        {
            "name": "The Guardian World",
            "category": "Global",
            "url": "https://www.theguardian.com/world/rss",
        },
        {
            "name": "GroundUp",
            "category": "South Africa",
            "url": "https://groundup.news/sitenews/rss/",
        },
        {
            "name": "IOL South Africa",
            "category": "South Africa",
            "url": "https://www.iol.co.za/rss/iol/news/south-africa",
        },
        {
            "name": "GameSpot",
            "category": "Games",
            "url": "https://www.gamespot.com/feeds/news/",
        },
        {
            "name": "PC Gamer",
            "category": "Games",
            "url": "https://www.pcgamer.com/rss/",
        },
        {
            "name": "PlayStation Blog",
            "category": "Games",
            "url": "https://blog.playstation.com/feed/",
        },
        {
            "name": "BBC Sport F1",
            "category": "F1",
            "url": "https://feeds.bbci.co.uk/sport/formula1/rss.xml",
        },
        {
            "name": "Motorsport.com F1",
            "category": "F1",
            "url": "https://www.motorsport.com/rss/f1/news/",
        },
        {
            "name": "Variety",
            "category": "Entertainment",
            "url": "https://variety.com/feed/",
        },
        {
            "name": "The Hollywood Reporter",
            "category": "Entertainment",
            "url": "https://www.hollywoodreporter.com/feed/",
        },
        {
            "name": "Deadline",
            "category": "Entertainment",
            "url": "https://deadline.com/feed/",
        },
        {
            "name": "Cape Town ETC",
            "category": "Cape Town",
            "url": "https://www.capetownetc.com/feed/",
        },
        {
            "name": "IOL Cape Times",
            "category": "Cape Town",
            "url": "https://www.iol.co.za/rss/iol/news/south-africa/western-cape",
        },
        {
            "name": "What's On in Cape Town Events",
            "category": "Cape Town Events",
            "url": "https://whatsonincapetown.com/event/feed/",
        },
        {
            "name": "Events in Cape Town",
            "category": "Cape Town Events",
            "url": "https://eventsincapetown.com/feed/",
        },
        {
            "name": "Gripped",
            "category": "Climbing",
            "url": "https://gripped.com/feed/",
        },
        {
            "name": "GearJunkie Climbing",
            "category": "Climbing",
            "url": "https://gearjunkie.com/climbing/feed",
        },
        {
            "name": "Alpinist",
            "category": "Climbing",
            "url": "https://alpinist.com/feed/",
        },
    ],
}

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
F1_DRIVER_STANDINGS_URL = "https://api.jolpi.ca/ergast/f1/current/driverStandings.json"
F1_CONSTRUCTOR_STANDINGS_URL = "https://api.jolpi.ca/ergast/f1/current/constructorStandings.json"
F1_NEXT_RACE_URL = "https://api.jolpi.ca/ergast/f1/current/next.json"
F1_LAST_RESULTS_URL = "https://api.jolpi.ca/ergast/f1/current/last/results.json"
F1_SEASON_SCHEDULE_URL = "https://api.jolpi.ca/ergast/f1/current.json"
F1_HIGHLIGHT_FEEDS = [
    ("Autosport F1", "https://www.autosport.com/rss/f1/news/"),
    ("RaceFans F1", "https://www.racefans.net/category/formula-1/feed/"),
    ("RACER F1", "https://racer.com/f1/feed/"),
    ("Motorsport.com F1", "https://www.motorsport.com/rss/f1/news/"),
]
F1_HIGHLIGHT_KEYWORDS = [
    "battle",
    "collision",
    "crash",
    "crashed",
    "damage",
    "disqualified",
    "dnf",
    "incident",
    "investigation",
    "lead",
    "overtake",
    "penalty",
    "pit",
    "podium",
    "red flag",
    "restart",
    "retired",
    "safety car",
    "spin",
    "strategy",
    "tyre",
    "winner",
    "won",
]
F1_DRIVER_WIKI_TITLES = {
    "andrea kimi antonelli": "Kimi Antonelli",
    "george russell": "George Russell (racing driver)",
    "carlos sainz": "Carlos Sainz Jr.",
    "alexander albon": "Alex Albon",
}
F1_CONSTRUCTOR_WIKI_TITLES = {
    "mercedes": "Mercedes-Benz in Formula One",
    "ferrari": "Ferrari SF-25",
    "mclaren": "McLaren",
    "red bull": "Red Bull Racing",
    "aston martin": "Aston Martin in Formula One",
    "williams": "Williams Racing",
    "racing bulls": "Racing Bulls S.p.A.",
    "haas f1 team": "Haas F1 Team",
    "haas": "Haas F1 Team",
    "alpine f1 team": "Alpine F1 Team",
    "alpine": "Alpine F1 Team",
    "kick sauber": "Sauber Motorsport",
}


@dataclass(frozen=True)
class FeedSource:
    name: str
    category: str
    url: str
    priority: int


def parse_iso_datetime(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def sync_outputs() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for path in DATA_DIR.glob("*.json"):
        shutil.copy2(path, DOCS_DIR / path.name)
    print(f"Synced news data to dashboard: {DOCS_DIR}", flush=True)


def read_config() -> dict:
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG
    try:
        existing = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_CONFIG
    merged = {**DEFAULT_CONFIG, **existing}
    if not isinstance(merged.get("feeds"), list) or not merged["feeds"]:
        merged["feeds"] = DEFAULT_CONFIG["feeds"]
    return merged


def write_default_config_if_missing() -> None:
    if CONFIG_FILE.exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")


def text_from_node(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return WHITESPACE_RE.sub(" ", "".join(node.itertext())).strip()


def child(node: ET.Element, *names: str) -> ET.Element | None:
    wanted = {name.lower() for name in names}
    for item in list(node):
        if item.tag.rsplit("}", 1)[-1].lower() in wanted:
            return item
    return None


def children(node: ET.Element, *names: str) -> list[ET.Element]:
    wanted = {name.lower() for name in names}
    return [item for item in list(node) if item.tag.rsplit("}", 1)[-1].lower() in wanted]


def clean_text(value: str) -> str:
    text = html.unescape(value or "")
    if "â" in text or "Â" in text:
        try:
            text = text.encode("cp1252").decode("utf-8")
        except UnicodeError:
            pass
    text = TAG_RE.sub(" ", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def parse_date(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/") or parts.path, "", ""))


def stable_id(source: str, url: str, title: str) -> str:
    basis = canonical_url(url) or f"{source}|{title}".lower()
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def item_link(item: ET.Element) -> str:
    link = child(item, "link")
    if link is None:
        return ""
    href = link.attrib.get("href", "").strip()
    if href:
        return href
    return text_from_node(link)


def item_categories(item: ET.Element, category: str, source_name: str) -> list[str]:
    tags = [category, source_name]
    for node in children(item, "category"):
        value = node.attrib.get("term", "") or text_from_node(node)
        if value:
            tags.append(clean_text(value))
    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            unique.append(tag)
    return unique[:5]


def item_image(item: ET.Element) -> str:
    for node in item.iter():
        local = node.tag.rsplit("}", 1)[-1].lower()
        if local in {"thumbnail", "content"} and node.attrib.get("url"):
            return node.attrib["url"].strip()
        if local == "enclosure" and node.attrib.get("url", "").strip():
            mime_type = node.attrib.get("type", "").lower()
            if mime_type.startswith("image/"):
                return node.attrib["url"].strip()
    return ""


def parse_feed(source: FeedSource, xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    root_name = root.tag.rsplit("}", 1)[-1].lower()
    if root_name == "rss":
        channel = child(root, "channel")
        if channel is None:
            channel = root
        raw_items = children(channel, "item")
    else:
        raw_items = children(root, "entry")

    items: list[dict] = []
    for raw_item in raw_items:
        title = clean_text(text_from_node(child(raw_item, "title")))
        url = item_link(raw_item)
        summary = clean_text(
            text_from_node(child(raw_item, "description", "summary", "subtitle"))
            or text_from_node(child(raw_item, "encoded", "content"))
        )
        published = parse_date(
            text_from_node(child(raw_item, "pubDate", "published", "updated", "date"))
        )
        if not title or not url:
            continue
        items.append(
            {
                "id": stable_id(source.name, url, title),
                "title": title,
                "source": source.name,
                "category": source.category,
                "published_at": published,
                "url": url,
                "image_url": item_image(raw_item),
                "summary": summary,
                "body": summary,
                "tags": item_categories(raw_item, source.category, source.name),
                "_priority": source.priority,
            }
        )
    return items


def fetch_url(url: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "User-Agent": "Mozilla/5.0 (compatible; my-dashboard-news/1.0)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int) -> dict:
    return json.loads(fetch_url(url, timeout))


def parse_wesgro_travel_events(html_text: str, timeout: int) -> list[dict]:
    card_pattern = re.compile(
        r'<span class="mb-lastchild-0 text-travel small mb-2">\s*(?P<date>.*?)\s*</span>.*?'
        r'<h5 class="mb-lastchild-0 mb-2">\s*(?P<title>.*?)\s*</h5>.*?'
        r'<li class="mb-2">\s*.*?</span>\s*(?P<location>.*?)\s*</li>.*?'
        r'href="(?P<url>https://www\.wesgro\.co\.za/travel/events/[^"]+)"',
        re.IGNORECASE | re.DOTALL,
    )
    items: list[dict] = []
    seen_urls: set[str] = set()
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for match in card_pattern.finditer(html_text):
        title = clean_text(match.group("title"))
        location = clean_text(match.group("location"))
        url = match.group("url").strip()
        date_text = clean_text(match.group("date"))
        if not title or not url or url in seen_urls:
            continue
        # Keep this topic focused on Cape Town happenings.
        if "cape town" not in location.lower():
            continue
        seen_urls.add(url)
        summary = f"{date_text} | {location}".strip(" |")
        items.append(
            {
                "id": stable_id("Wesgro Travel Events", url, title),
                "title": title,
                "source": "Wesgro Travel Events",
                "category": "Cape Town Events",
                "published_at": now_iso,
                "url": url,
                "image_url": "",
                "summary": summary,
                "body": summary,
                "tags": ["Cape Town Events", "Wesgro", "Travel"],
                "_priority": 0,
            }
        )
        if len(items) >= 20:
            break
    return items


def title_from_slug(url: str) -> str:
    path = urlsplit(url).path.strip("/")
    slug = path.rsplit("/", 1)[-1]
    words = [part for part in re.split(r"[-_]+", slug) if part]
    return " ".join(word.capitalize() for word in words).strip()


def parse_whatson_weekend_page(html_text: str) -> list[dict]:
    main_match = re.search(r"<main\b.*?</main>", html_text, re.IGNORECASE | re.DOTALL)
    scope = main_match.group(0) if main_match else html_text
    card_link_pattern = re.compile(
        r'<a[^>]*class="[^"]*elementor-button-link[^"]*"[^>]*href="(https://whatsonincapetown\.com/[^"#?]+/?)"[^>]*>',
        re.IGNORECASE,
    )
    seen: set[str] = set()
    items: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for match in card_link_pattern.finditer(scope):
        url = match.group(1).strip()
        lower = url.lower()
        if lower in seen:
            continue
        seen.add(lower)
        title = title_from_slug(url)
        if not title:
            continue
        items.append(
            {
                "id": stable_id("What's On Weekend", url, title),
                "title": title,
                "source": "What's On Weekend",
                "category": "Cape Town Events",
                "published_at": now_iso,
                "url": url,
                "image_url": "",
                "summary": "Weekend picks from What's On in Cape Town.",
                "body": "Weekend picks from What's On in Cape Town.",
                "tags": ["Cape Town Events", "Weekend", "What's On"],
                "_priority": 0,
            }
        )
        if len(items) >= 6:
            break
    return items


def fetch_wesgro_travel_events(timeout: int) -> list[dict]:
    url = "https://www.wesgro.co.za/travel/events"
    html_text = fetch_url(url, timeout)
    return parse_wesgro_travel_events(html_text, timeout)


def fetch_whatson_weekend_events(timeout: int) -> list[dict]:
    url = "https://whatsonincapetown.com/things-to-do-this-weekend-in-cape-town/"
    html_text = fetch_url(url, timeout)
    return parse_whatson_weekend_page(html_text)


def race_round_from_payload(payload: dict) -> dict:
    races = (
        payload.get("MRData", {})
        .get("RaceTable", {})
        .get("Races", [])
    )
    if not races:
        return {}
    return races[0] if isinstance(races[0], dict) else {}


def races_from_payload(payload: dict) -> list[dict]:
    races = payload.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    return [race for race in races if isinstance(race, dict)]


def f1_driver_name(driver: dict) -> str:
    return " ".join(
        part
        for part in [
            str(driver.get("givenName", "")).strip(),
            str(driver.get("familyName", "")).strip(),
        ]
        if part
    ).strip() or "Unknown"


def fetch_wikipedia_thumbnails(names: list[str], timeout: int, aliases: dict[str, str] | None = None) -> dict[str, str]:
    unique_names = []
    seen: set[str] = set()
    for name in names:
        cleaned = str(name or "").strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            unique_names.append(cleaned)

    titles_by_name = {
        name: (aliases or {}).get(name.lower(), name)
        for name in unique_names
    }
    unique_titles = []
    seen_titles: set[str] = set()
    for title in titles_by_name.values():
        key = title.lower()
        if key not in seen_titles:
            seen_titles.add(key)
            unique_titles.append(title)

    images_by_title: dict[str, str] = {}
    for start in range(0, len(unique_titles), 40):
        batch = unique_titles[start:start + 40]
        titles = "|".join(batch)
        url = (
            "https://en.wikipedia.org/w/api.php"
            "?action=query&format=json&origin=*&prop=pageimages&pithumbsize=180&titles="
            + quote(titles)
        )
        try:
            payload = fetch_json(url, timeout)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            continue
        pages = payload.get("query", {}).get("pages", {})
        if not isinstance(pages, dict):
            continue
        for page in pages.values():
            if not isinstance(page, dict):
                continue
            title = str(page.get("title", "")).strip()
            thumbnail = page.get("thumbnail", {}) if isinstance(page.get("thumbnail", {}), dict) else {}
            source = str(thumbnail.get("source", "")).strip()
            if title and source:
                images_by_title[title.lower()] = source
    images: dict[str, str] = {}
    for name, title in titles_by_name.items():
        images[name.lower()] = images_by_title.get(title.lower(), "")
    return images


def standings_list_from_payload(payload: dict, key: str) -> list[dict]:
    standings_table = payload.get("MRData", {}).get("StandingsTable", {})
    lists = standings_table.get("StandingsLists", [])
    if not lists:
        return []
    first = lists[0] if isinstance(lists[0], dict) else {}
    values = first.get(key, [])
    return [item for item in values if isinstance(item, dict)]


def sentence_fragments(value: str) -> list[str]:
    cleaned = clean_text(value)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip(" -") for part in parts if 35 <= len(part.strip()) <= 240]


def f1_race_terms(race_name: str) -> list[str]:
    raw = clean_text(race_name).lower()
    short = raw.replace("grand prix", "").strip()
    terms = [raw]
    if short:
        terms.extend([short, f"{short} gp"])
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        key = WHITESPACE_RE.sub(" ", term).strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def fetch_f1_highlight_articles(timeout: int) -> list[dict]:
    articles: list[dict] = []
    for index, (name, url) in enumerate(F1_HIGHLIGHT_FEEDS):
        source = FeedSource(name=name, category="F1", url=url, priority=index)
        try:
            articles.extend(parse_feed(source, fetch_url(url, timeout)))
        except (ET.ParseError, urllib.error.URLError, TimeoutError, ValueError):
            continue
    return articles


def fetch_wikipedia_race_extract(season: str, race_name: str, timeout: int) -> str:
    title = f"{season} {race_name}".strip()
    if not season or not race_name:
        return ""
    url = (
        "https://en.wikipedia.org/w/api.php"
        "?action=query&format=json&origin=*&prop=extracts&explaintext=1&exintro=1&titles="
        + quote(title)
    )
    try:
        payload = fetch_json(url, timeout)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return ""
    pages = payload.get("query", {}).get("pages", {})
    if not isinstance(pages, dict):
        return ""
    for page in pages.values():
        if isinstance(page, dict):
            return clean_text(str(page.get("extract", "")).strip())
    return ""


def article_matches_race(article: dict, terms: list[str]) -> bool:
    haystack = clean_text(f"{article.get('title', '')} {article.get('summary', '')}").lower()
    if not haystack:
        return False
    return any(term in haystack for term in terms)


def extract_f1_highlight_sentences(text: str, terms: list[str], limit: int = 5) -> list[str]:
    highlights: list[str] = []
    seen: set[str] = set()
    for sentence in sentence_fragments(text):
        lowered = sentence.lower()
        is_boilerplate = (
            "officially known as" in lowered
            or "was a formula one motor race" in lowered
            or "was a formula one race" in lowered
            or ("held on" in lowered and "grand prix" in lowered and "won" not in lowered)
        )
        if is_boilerplate:
            continue
        has_race_context = any(term in lowered for term in terms)
        has_highlight_signal = any(keyword in lowered for keyword in F1_HIGHLIGHT_KEYWORDS)
        if not has_highlight_signal and not has_race_context:
            continue
        if "standings" in lowered and not has_highlight_signal:
            continue
        key = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
        if key in seen:
            continue
        seen.add(key)
        highlights.append(sentence)
        if len(highlights) >= limit:
            break
    return highlights


def build_f1_highlights_for_race(
    season: str,
    race_name: str,
    articles: list[dict],
    timeout: int,
) -> tuple[list[str], list[str]]:
    terms = f1_race_terms(race_name)
    highlights: list[str] = []
    sources: list[str] = []

    wiki_extract = fetch_wikipedia_race_extract(season, race_name, timeout)
    for sentence in extract_f1_highlight_sentences(wiki_extract, terms, limit=4):
        highlights.append(sentence)
        sources.append("Wikipedia")

    matched_articles = [article for article in articles if article_matches_race(article, terms)]
    matched_articles.sort(key=lambda article: str(article.get("published_at", "")), reverse=True)
    for article in matched_articles[:4]:
        text = f"{article.get('title', '')}. {article.get('summary', '')}"
        for sentence in extract_f1_highlight_sentences(text, terms, limit=3):
            highlights.append(sentence)
            sources.append(str(article.get("source", "")).strip() or "F1 report")

    deduped: list[str] = []
    deduped_sources: list[str] = []
    seen_highlights: set[str] = set()
    for index, highlight in enumerate(highlights):
        key = re.sub(r"[^a-z0-9]+", " ", highlight.lower()).strip()
        if not key or key in seen_highlights:
            continue
        seen_highlights.add(key)
        deduped.append(highlight)
        deduped_sources.append(sources[index])
        if len(deduped) >= 6:
            break

    unique_sources: list[str] = []
    for source in deduped_sources:
        if source and source not in unique_sources:
            unique_sources.append(source)
    return deduped, unique_sources


def build_f1_snapshot(timeout: int) -> dict | None:
    try:
        driver_payload = fetch_json(F1_DRIVER_STANDINGS_URL, timeout)
        constructor_payload = fetch_json(F1_CONSTRUCTOR_STANDINGS_URL, timeout)
        next_payload = fetch_json(F1_NEXT_RACE_URL, timeout)
        last_payload = fetch_json(F1_LAST_RESULTS_URL, timeout)
        schedule_payload = fetch_json(F1_SEASON_SCHEDULE_URL, timeout)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None

    drivers = standings_list_from_payload(driver_payload, "DriverStandings")
    constructors = standings_list_from_payload(constructor_payload, "ConstructorStandings")
    next_race = race_round_from_payload(next_payload)
    last_race = race_round_from_payload(last_payload)
    season_races = races_from_payload(schedule_payload)
    season = str(driver_payload.get("MRData", {}).get("StandingsTable", {}).get("season", "")).strip() or "current"
    highlight_articles = fetch_f1_highlight_articles(timeout)

    if not drivers and not constructors and not next_race and not last_race and not season_races:
        return None

    top_drivers = []
    driver_names_for_images: list[str] = []
    driver_table: list[dict] = []
    for row in drivers[:3]:
        driver = row.get("Driver", {})
        first = str(driver.get("givenName", "")).strip()
        last = str(driver.get("familyName", "")).strip()
        name = " ".join(part for part in [first, last] if part).strip() or "Unknown"
        points = str(row.get("points", "")).strip()
        pos = str(row.get("position", "")).strip()
        top_drivers.append(f"{pos}. {name} ({points})")
    for row in drivers:
        driver = row.get("Driver", {})
        constructors_for_driver = row.get("Constructors", [])
        team = ""
        if isinstance(constructors_for_driver, list) and constructors_for_driver:
            first_team = constructors_for_driver[0] if isinstance(constructors_for_driver[0], dict) else {}
            team = str(first_team.get("name", "")).strip()
        name = f1_driver_name(driver)
        driver_names_for_images.append(name)
        driver_table.append(
            {
                "position": str(row.get("position", "")).strip(),
                "name": name,
                "team": team,
                "points": str(row.get("points", "")).strip(),
                "wins": str(row.get("wins", "")).strip(),
            }
        )

    top_constructors = []
    constructor_names_for_images: list[str] = []
    constructor_table: list[dict] = []
    for row in constructors[:3]:
        constructor = row.get("Constructor", {})
        name = str(constructor.get("name", "")).strip() or "Unknown"
        points = str(row.get("points", "")).strip()
        pos = str(row.get("position", "")).strip()
        top_constructors.append(f"{pos}. {name} ({points})")
    for row in constructors:
        constructor = row.get("Constructor", {})
        constructor_name = str(constructor.get("name", "")).strip() or "Unknown"
        constructor_names_for_images.append(constructor_name)
        constructor_table.append(
            {
                "position": str(row.get("position", "")).strip(),
                "name": constructor_name,
                "nationality": str(constructor.get("nationality", "")).strip(),
                "points": str(row.get("points", "")).strip(),
                "wins": str(row.get("wins", "")).strip(),
            }
        )

    next_name = str(next_race.get("raceName", "")).strip() or "TBA"
    next_date = str(next_race.get("date", "")).strip()
    next_time = str(next_race.get("time", "")).strip()
    next_when = " ".join(bit for bit in [next_date, next_time] if bit).strip() or "TBA"

    last_name = str(last_race.get("raceName", "")).strip() or "TBA"
    results = last_race.get("Results", [])
    last_race_results_table: list[dict] = []
    race_results_by_round: dict[str, dict] = {}
    winner = "TBA"
    if isinstance(results, list) and results:
        first = results[0] if isinstance(results[0], dict) else {}
        driver = first.get("Driver", {}) if isinstance(first.get("Driver", {}), dict) else {}
        given = str(driver.get("givenName", "")).strip()
        family = str(driver.get("familyName", "")).strip()
        constructor = first.get("Constructor", {}) if isinstance(first.get("Constructor", {}), dict) else {}
        team = str(constructor.get("name", "")).strip()
        winner_name = " ".join(part for part in [given, family] if part).strip() or "Unknown"
        winner = f"{winner_name} ({team})" if team else winner_name
    for row in results if isinstance(results, list) else []:
        if not isinstance(row, dict):
            continue
        driver = row.get("Driver", {}) if isinstance(row.get("Driver", {}), dict) else {}
        constructor = row.get("Constructor", {}) if isinstance(row.get("Constructor", {}), dict) else {}
        last_race_results_table.append(
            {
                "position": str(row.get("position", "")).strip(),
                "name": f1_driver_name(driver),
                "team": str(constructor.get("name", "")).strip(),
                "points": str(row.get("points", "")).strip(),
                "status": str(row.get("status", "")).strip(),
            }
        )

    next_round = int(str(next_race.get("round", "0")).strip() or "0")
    schedule_rows: list[dict] = []
    for race in season_races:
        round_number = int(str(race.get("round", "0")).strip() or "0")
        race_date = str(race.get("date", "")).strip()
        race_time = str(race.get("time", "")).strip()
        circuit_obj = race.get("Circuit", {}) if isinstance(race.get("Circuit", {}), dict) else {}
        location_obj = circuit_obj.get("Location", {}) if isinstance(circuit_obj.get("Location", {}), dict) else {}
        schedule_rows.append(
            {
                "round": round_number,
                "race_name": str(race.get("raceName", "")).strip() or f"Round {round_number}",
                "date": race_date,
                "time": race_time,
                "when_utc": " ".join(bit for bit in [race_date, race_time] if bit).strip(),
                "circuit": str(circuit_obj.get("circuitName", "")).strip(),
                "locality": str(location_obj.get("locality", "")).strip(),
                "country": str(location_obj.get("country", "")).strip(),
                "is_next": next_round > 0 and round_number == next_round,
                "is_past": next_round > 0 and round_number < next_round,
            }
        )
        if next_round > 0 and round_number >= next_round:
            continue
        round_results_url = f"https://api.jolpi.ca/ergast/f1/{season}/{round_number}/results.json"
        try:
            round_payload = fetch_json(round_results_url, timeout)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            continue
        round_races = races_from_payload(round_payload)
        if not round_races:
            continue
        round_race = round_races[0]
        race_rows: list[dict] = []
        constructor_points: dict[str, float] = {}
        constructor_wins: dict[str, int] = {}
        for row in round_race.get("Results", []) if isinstance(round_race.get("Results", []), list) else []:
            if not isinstance(row, dict):
                continue
            driver = row.get("Driver", {}) if isinstance(row.get("Driver", {}), dict) else {}
            constructor = row.get("Constructor", {}) if isinstance(row.get("Constructor", {}), dict) else {}
            team_name = str(constructor.get("name", "")).strip() or "Unknown"
            points_text = str(row.get("points", "")).strip() or "0"
            try:
                points_val = float(points_text)
            except ValueError:
                points_val = 0.0
            constructor_points[team_name] = constructor_points.get(team_name, 0.0) + points_val
            if str(row.get("position", "")).strip() == "1":
                constructor_wins[team_name] = constructor_wins.get(team_name, 0) + 1
            name = f1_driver_name(driver)
            driver_names_for_images.append(name)
            race_rows.append(
                {
                    "position": str(row.get("position", "")).strip(),
                    "name": name,
                    "team": team_name,
                    "points": points_text,
                    "status": str(row.get("status", "")).strip(),
                }
            )
        constructor_rows = sorted(
            (
                {
                    "name": team,
                    "nationality": "",
                    "points": f"{pts:g}",
                    "wins": str(constructor_wins.get(team, 0)),
                }
                for team, pts in constructor_points.items()
            ),
            key=lambda row: float(row["points"]),
            reverse=True,
        )
        for index, row in enumerate(constructor_rows, start=1):
            row["position"] = str(index)
            constructor_names_for_images.append(row["name"])

        race_name = str(round_race.get("raceName", "")).strip() or f"Race {round_number}"
        highlights, highlight_sources = build_f1_highlights_for_race(season, race_name, highlight_articles, timeout)
        race_results_by_round[str(round_number)] = {
            "race_name": race_name,
            "date": str(round_race.get("date", "")).strip(),
            "time": str(round_race.get("time", "")).strip(),
            "results": race_rows,
            "constructors": constructor_rows,
            "highlights": highlights,
            "highlight_sources": highlight_sources,
        }

    driver_images = fetch_wikipedia_thumbnails(driver_names_for_images, timeout, F1_DRIVER_WIKI_TITLES)
    constructor_images = fetch_wikipedia_thumbnails(constructor_names_for_images, timeout, F1_CONSTRUCTOR_WIKI_TITLES)
    for row in driver_table:
        row["image_url"] = driver_images.get(str(row.get("name", "")).strip().lower(), "")
    for row in constructor_table:
        row["image_url"] = constructor_images.get(str(row.get("name", "")).strip().lower(), "")
    for row in last_race_results_table:
        row["image_url"] = driver_images.get(str(row.get("name", "")).strip().lower(), "")
    for race_result in race_results_by_round.values():
        for row in race_result.get("results", []):
            row["image_url"] = driver_images.get(str(row.get("name", "")).strip().lower(), "")
        for row in race_result.get("constructors", []):
            row["image_url"] = constructor_images.get(str(row.get("name", "")).strip().lower(), "")

    summary = (
        f"Drivers: {' | '.join(top_drivers)}. "
        f"Constructors: {' | '.join(top_constructors)}. "
        f"Next GP: {next_name} ({next_when}). "
        f"Last GP winner: {winner} at {last_name}."
    ).strip()
    body = (
        f"Drivers Championship Top 3: {' | '.join(top_drivers)}\n"
        f"Constructors Championship Top 3: {' | '.join(top_constructors)}\n"
        f"Next GP: {next_name} on {next_when}\n"
        f"Last GP: {last_name} winner {winner}"
    )
    return {
        "id": "f1-snapshot-current-season",
        "title": "F1 Standings",
        "source": "F1 Snapshot",
        "category": "F1",
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "url": "https://www.formula1.com/",
        "image_url": "",
        "summary": summary,
        "body": body,
        "tags": ["F1", "Standings", "Schedule", "Results"],
        "is_pinned_module": True,
        "hide_in_all": True,
        "f1_snapshot": {
            "season": season,
            "next_round": next_round,
            "next_race_name": next_name,
            "last_race_name": last_name,
            "drivers": driver_table,
            "constructors": constructor_table,
            "last_race_results": last_race_results_table,
            "schedule": schedule_rows,
            "race_results_by_round": race_results_by_round,
        },
        "always_featured": True,
        "_priority": -1000,
        "_sticky_rank": 1000,
    }


def published_sort_key(item: dict) -> tuple[int, str, int]:
    sticky = int(item.get("_sticky_rank", 0))
    return (sticky, str(item.get("published_at") or ""), -int(item.get("_priority", 0)))


def dedupe_items(items: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    deduped: list[dict] = []
    for item in sorted(items, key=published_sort_key, reverse=True):
        url_key = canonical_url(str(item.get("url", "")))
        title_key = WHITESPACE_RE.sub(" ", str(item.get("title", "")).strip().lower())
        if url_key and url_key in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url_key:
            seen_urls.add(url_key)
        if title_key:
            seen_titles.add(title_key)
        deduped.append(item)
    return deduped


def limit_by_category(items: list[dict], max_items: int) -> list[dict]:
    if max_items <= 0:
        return items
    counts: dict[str, int] = {}
    limited: list[dict] = []
    for item in items:
        category = str(item.get("category") or "Global")
        if counts.get(category, 0) >= max_items:
            continue
        counts[category] = counts.get(category, 0) + 1
        limited.append(item)
    return limited


def age_hours(item: dict, now: datetime) -> float | None:
    published = parse_iso_datetime(str(item.get("published_at", "")))
    if published is None:
        return None
    delta = now - published
    return delta.total_seconds() / 3600


def recency_score(hours_old: float | None) -> int:
    if hours_old is None:
        return 0
    if hours_old <= 3:
        return 4
    if hours_old <= 8:
        return 3
    if hours_old <= 24:
        return 2
    if hours_old <= 48:
        return 1
    return 0


def keyword_score(text: str, keywords: dict) -> tuple[int, list[str], bool]:
    normalized = text.lower()
    score = 0
    matched: list[str] = []
    breaking = False
    for term in keywords.get("high", []):
        if term in normalized:
            score += 3
            matched.append(term)
    for term in keywords.get("medium", []):
        if term in normalized:
            score += 1
            matched.append(term)
    if "breaking" in normalized or "just in" in normalized or "live updates" in normalized:
        breaking = True
    return score, matched[:5], breaking


def within_age_window(item: dict, config: dict, now: datetime) -> bool:
    hours_old = age_hours(item, now)
    if hours_old is None:
        return True
    category = str(item.get("category") or "Global")
    default_max = int(config.get("max_article_age_hours") or 72)
    per_category = config.get("category_max_age_hours", {})
    max_age = int(per_category.get(category, default_max))
    return hours_old <= max_age


def score_importance(items: list[dict], config: dict) -> list[dict]:
    now = datetime.now(timezone.utc)
    source_weights = config.get("source_weights", {})
    keywords = config.get("importance_keywords", {})
    scored: list[dict] = []
    for item in items:
        if not within_age_window(item, config, now):
            continue
        title = str(item.get("title", ""))
        summary = str(item.get("summary", ""))
        source = str(item.get("source", ""))
        hours_old = age_hours(item, now)
        key_score, matched_terms, breaking_hint = keyword_score(f"{title} {summary}", keywords)
        total_score = (
            int(source_weights.get(source, 0))
            + recency_score(hours_old)
            + key_score
        )
        if item.get("always_featured"):
            total_score += 100
        is_breaking = breaking_hint or total_score >= int(config.get("breaking_threshold") or 8)
        scored_item = dict(item)
        scored_item["importance_score"] = total_score
        scored_item["is_breaking"] = is_breaking
        scored_item["matched_terms"] = matched_terms
        scored.append(scored_item)
    return sorted(
        scored,
        key=lambda item: (
            int(item.get("importance_score", 0)),
            str(item.get("published_at", "")),
            item.get("is_breaking", False),
        ),
        reverse=True,
    )


def select_top_items(scored_items: list[dict], config: dict) -> list[dict]:
    threshold = int(config.get("importance_threshold") or 5)
    per_category = int(config.get("max_top_items_per_category") or 5)
    passing = [item for item in scored_items if int(item.get("importance_score", 0)) >= threshold]
    return limit_by_category(passing, per_category)


def scrape_rss(limit: int = 0) -> dict:
    config = read_config()
    timeout = int(config.get("request_timeout_seconds") or 25)
    per_category = limit or int(config.get("max_items_per_category") or 10)
    feeds = [
        FeedSource(
            name=str(feed.get("name", "")).strip(),
            category=str(feed.get("category", "Global")).strip() or "Global",
            url=str(feed.get("url", "")).strip(),
            priority=index,
        )
        for index, feed in enumerate(config.get("feeds", []))
        if str(feed.get("name", "")).strip() and str(feed.get("url", "")).strip()
    ]

    all_items: list[dict] = []
    f1_snapshot = build_f1_snapshot(timeout)
    if f1_snapshot is not None:
        all_items.append(f1_snapshot)
    errors: list[str] = []
    for source in feeds:
        try:
            all_items.extend(parse_feed(source, fetch_url(source.url, timeout)))
            print(f"Fetched {source.name}", flush=True)
        except (ET.ParseError, urllib.error.URLError, TimeoutError, ValueError) as error:
            errors.append(f"{source.name}: {error}")
            print(f"Skipped {source.name}: {error}", flush=True)
    try:
        all_items.extend(fetch_wesgro_travel_events(timeout))
        print("Fetched Wesgro Travel Events", flush=True)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        errors.append(f"Wesgro Travel Events: {error}")
        print(f"Skipped Wesgro Travel Events: {error}", flush=True)
    try:
        all_items.extend(fetch_whatson_weekend_events(timeout))
        print("Fetched What's On Weekend", flush=True)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        errors.append(f"What's On Weekend: {error}")
        print(f"Skipped What's On Weekend: {error}", flush=True)

    items = limit_by_category(dedupe_items(all_items), per_category)
    scored_items = score_importance(items, config)
    top_items = select_top_items(scored_items, config)
    for item in items:
        item.pop("_priority", None)
    for item in top_items:
        item.pop("_priority", None)

    return {
        "source": "rss",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "categories": config.get("categories", DEFAULT_CONFIG["categories"]),
        "importance_mode": config.get("importance_mode", "balanced"),
        "importance_threshold": int(config.get("importance_threshold") or 5),
        "breaking_threshold": int(config.get("breaking_threshold") or 8),
        "source_count": len(feeds),
        "error_count": len(errors),
        "errors": errors,
        "top_items_count": len(top_items),
        "top_items": top_items,
        "items": items,
    }


def write_payload(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(payload.get('items', []))} news articles to {NEWS_FILE}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run news scrape/sync.")
    parser.add_argument("--source", choices=["all", "rss", "local-file"], default="all", help="Which news source to scrape.")
    parser.add_argument("--hard", action="store_true", help="Remove generated news output before scraping/syncing.")
    parser.add_argument("--limit", type=int, default=0, help="Max items per category. 0 uses config default.")
    parser.add_argument("--max-pages", type=int, default=0, help="Accepted for wrapper consistency; RSS sources are not paged.")
    args = parser.parse_args()

    write_default_config_if_missing()
    if args.hard and NEWS_FILE.exists():
        NEWS_FILE.unlink()

    if args.source in {"all", "rss"}:
        payload = scrape_rss(limit=args.limit)
        if payload["items"]:
            write_payload(payload)
        elif NEWS_FILE.exists():
            print("No RSS items fetched; keeping existing news.json.", flush=True)
        else:
            write_payload(payload)
    elif not NEWS_FILE.exists():
        print(f"Missing local news file: {NEWS_FILE}", file=sys.stderr)
        return 1

    sync_outputs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
