from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))
from env import get as env_get
from services.common.notion import get_block_children, post as notion_post, request as notion_request, rich_text_plain
from services.common.secrets import secret
from sync_docs import sync_events_data_to_docs


PAGE_URL = env_get("NOTION_SPECIALS_PAGE_URL", "https://www.notion.so/Places-082fa9625a9f4f949d03a8d1517c76f8")
GOOGLE_PLACES_SEARCH_URL = env_get("SCRAPE_GOOGLE_PLACES_SEARCH_URL", "https://places.googleapis.com/v1/places:searchText")
PAGE_ID = "082fa9625a9f4f949d03a8d1517c76f8"
SPECIALS_DATABASE_ID = "NOTION_SPECIALS_DATABASE_ID"
SPECIALS_DATABASE_URL = "NOTION_SPECIALS_DATABASE_URL"
DEFAULT_SPECIALS_DATABASE_ID = "35157df8191880f7accedf40168acee7"
REPO_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_DIR / "docs" / "data" / "events"
OUTPUT_FILE = DATA_DIR / "specials.json"
PLACES_OUTPUT_FILE = DATA_DIR / "places.json"
TAGS_CONFIG_FILE = Path(__file__).resolve().parent / "allowed_location_tags.json"
CATEGORY_TAGS_CONFIG_FILE = Path(__file__).resolve().parent / "allowed_location_category_tags.json"

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

DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

SECTION_TITLES = {
    "Everyday",
    "Monday to Thursday",
    "Location",
    "Locations",
    *DAY_ORDER,
}
DAY_ALIASES = {
    "mon": "Monday",
    "monday": "Monday",
    "tue": "Tuesday",
    "tues": "Tuesday",
    "tuesday": "Tuesday",
    "wed": "Wednesday",
    "weds": "Wednesday",
    "wednesday": "Wednesday",
    "thu": "Thursday",
    "thur": "Thursday",
    "thurs": "Thursday",
    "thursday": "Thursday",
    "fri": "Friday",
    "friday": "Friday",
    "sat": "Saturday",
    "saturday": "Saturday",
    "sun": "Sunday",
    "sunday": "Sunday",
}

def allowed_location_tags() -> set[str]:
    if TAGS_CONFIG_FILE.exists():
        try:
            payload = json.loads(TAGS_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return {str(item).strip().lower() for item in payload if str(item).strip()}
        except json.JSONDecodeError:
            pass

    raw = secret("ALLOWED_LOCATION_TAGS")
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def allowed_location_category_tags() -> set[str]:
    if CATEGORY_TAGS_CONFIG_FILE.exists():
        try:
            payload = json.loads(CATEGORY_TAGS_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return {str(item).strip().lower() for item in payload if str(item).strip()}
        except json.JSONDecodeError:
            pass

    raw = secret("ALLOWED_LOCATION_CATEGORY_TAGS")
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def fetch_json_url(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_json_post(url: str, headers: dict[str, str], body: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            **headers,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def page_title(page: dict) -> str:
    for property_value in page.get("properties", {}).values():
        if property_value.get("type") == "title":
            return rich_text_plain(property_value.get("title", []))
    return "Specials"


def property_plain_text(value: dict) -> str:
    prop_type = (value or {}).get("type")
    if prop_type == "title":
        return rich_text_plain((value or {}).get("title", []))
    if prop_type == "rich_text":
        return rich_text_plain((value or {}).get("rich_text", []))
    if prop_type == "select":
        selected = (value or {}).get("select") or {}
        return (selected.get("name") or "").strip()
    if prop_type == "status":
        selected = (value or {}).get("status") or {}
        return (selected.get("name") or "").strip()
    if prop_type == "number":
        number = (value or {}).get("number")
        return "" if number is None else str(number)
    if prop_type == "phone_number":
        return str((value or {}).get("phone_number") or "").strip()
    if prop_type == "url":
        return str((value or {}).get("url") or "").strip()
    if prop_type == "email":
        return str((value or {}).get("email") or "").strip()
    if prop_type == "date":
        date_value = (value or {}).get("date") or {}
        return str(date_value.get("start") or "").strip()
    if prop_type == "formula":
        formula = (value or {}).get("formula") or {}
        formula_type = formula.get("type")
        if formula_type == "string":
            return (formula.get("string") or "").strip()
        if formula_type == "number":
            number = formula.get("number")
            return "" if number is None else str(number)
    return ""


def property_multi_select_names(value: dict) -> list[str]:
    prop_type = (value or {}).get("type")
    if prop_type != "multi_select":
        return []
    tags = (value or {}).get("multi_select") or []
    return [str(tag.get("name") or "").strip() for tag in tags if str(tag.get("name") or "").strip()]


def property_by_name(properties: dict, names: list[str]) -> dict:
    lookup = {key.lower().strip(): val for key, val in (properties or {}).items()}
    for name in names:
        value = lookup.get(name.lower().strip())
        if value is not None:
            return value
    return {}


def normalize_day_tag(day_value: str) -> str:
    cleaned = (day_value or "").strip().lower().replace(".", "")
    if not cleaned:
        return ""
    return DAY_ALIASES.get(cleaned, "")


def database_id_from_secret_or_url() -> str:
    direct = secret(SPECIALS_DATABASE_ID)
    if direct:
        return direct.replace("-", "").strip()
    url_value = secret(SPECIALS_DATABASE_URL)
    if not url_value:
        return DEFAULT_SPECIALS_DATABASE_ID
    match = re.search(r"([0-9a-fA-F]{32})", url_value.replace("-", ""))
    return match.group(1) if match else DEFAULT_SPECIALS_DATABASE_ID


def block_text(block: dict) -> str:
    block_type = block.get("type", "")
    if block_type not in TEXT_BLOCK_TYPES:
        return ""
    value = block.get(block_type, {})
    text = rich_text_plain(value.get("rich_text", []))
    if block_type == "to_do":
        checked = "x" if value.get("checked") else " "
        return f"[{checked}] {text}" if text else ""
    return text


def flatten_blocks(blocks: list[dict], token: str) -> list[dict]:
    flattened: list[dict] = []
    stack = list(blocks)
    while stack:
        block = stack.pop(0)
        flattened.append(block)
        if block.get("has_children"):
            children = get_block_children(block.get("id", ""), token)
            if children:
                stack[0:0] = children
    return flattened


def plain_text_from_block(block: dict) -> str:
    block_type = block.get("type", "")
    if block_type not in TEXT_BLOCK_TYPES:
        return ""
    return rich_text_plain((block.get(block_type, {}) or {}).get("rich_text", []))


def item_from_text(text: str, default_venue: str = "") -> dict[str, str]:
    urls = re.findall(r"https?://\S+", text)
    url = urls[0].rstrip(").,") if urls else ""
    parts = re.split(r"\s+[-–]\s+", text, maxsplit=1)
    if len(parts) == 2:
        venue = parts[0].strip()
        deal = parts[1].strip()
    else:
        venue = default_venue or text
        deal = text

    if venue.endswith(":"):
        venue = venue[:-1].strip()
    return {
        "venue": venue,
        "title": venue,
        "deal": deal,
        "description": f"{venue} - {deal}" if default_venue and venue == default_venue else text,
        "url": url,
    }


def normalized_section_title(text: str) -> str:
    cleaned = text.strip().strip("*").strip()
    cleaned = cleaned.rstrip(":").strip()
    for title in SECTION_TITLES:
        if cleaned.lower() == title.lower():
            return title
    return ""


def days_for_group(title: str) -> list[str]:
    if title == "Everyday":
        return DAY_ORDER[:]
    if title == "Monday to Thursday":
        return DAY_ORDER[:4]
    if title in DAY_ORDER:
        return [title]
    return []


def parse_location(text: str) -> dict | None:
    cleaned = text.strip().lstrip("-").strip()
    main_match = re.match(r"^(?P<venue>[^:]+):\s*(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lng>-?\d+(?:\.\d+)?)", cleaned)
    if not main_match:
        return None
    venue = main_match.group("venue").strip()
    lat = float(main_match.group("lat"))
    lng = float(main_match.group("lng"))

    tags_match = re.search(r"\((?P<tags>[^)]*)\)", cleaned)
    raw_tags = (tags_match.group("tags") if tags_match else "").strip()
    url_match = re.search(r"(https?://\S+)", cleaned)
    raw_url = (url_match.group(1) if url_match else "").strip()
    raw_url = raw_url.rstrip(").,")

    tags = [tag.strip().lower() for tag in raw_tags.split(",") if tag.strip()]
    allowed_types = allowed_location_tags()
    allowed_categories = allowed_location_category_tags()
    if allowed_types or allowed_categories:
        types = [tag for tag in tags if tag in allowed_types] if allowed_types else []
        categories = [tag for tag in tags if tag in allowed_categories] if allowed_categories else []
    else:
        types = tags[:]
        categories = []
    return {
        "venue": venue,
        "name": venue,
        "lat": lat,
        "lng": lng,
        "types": types,
        "categories": categories,
        "tags": list(dict.fromkeys(types + categories)),
        "url": raw_url,
        "google_maps_url": raw_url,
    }


def specials_from_blocks(blocks: list[dict]) -> list[dict]:
    groups: list[dict] = []
    current_group: dict | None = None
    current_venue = ""

    for block in blocks:
        text = plain_text_from_block(block)
        block_type = block.get("type", "")
        if not text:
            continue

        section_title = normalized_section_title(text)
        if block_type in {"heading_1", "heading_2", "heading_3"} or section_title:
            current_group = {
                "title": section_title or text,
                "days": days_for_group(section_title or text),
                "items": [],
            }
            current_venue = ""
            groups.append(current_group)
            continue

        if block_type in {"paragraph", "quote", "callout"} and re.search(r"https?://", text):
            if current_group is None:
                current_group = {"title": "General", "days": [], "items": []}
                groups.append(current_group)
            current_group["items"].append(item_from_text(text, current_venue))
            continue

        if block_type in {"bulleted_list_item", "numbered_list_item", "to_do", "paragraph"}:
            if current_group is None:
                current_group = {"title": "General", "days": [], "items": []}
                groups.append(current_group)
            if text.endswith(":"):
                current_venue = text[:-1].strip()
                continue
            current_group["items"].append(item_from_text(text, current_venue))

    return [group for group in groups if group["items"]]


def split_specials_and_locations(groups: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    locations: dict[str, dict] = {}
    special_groups: list[dict] = []

    for group in groups:
        if group["title"] in {"Location", "Locations"}:
            for item in group["items"]:
                location = parse_location(item["description"])
                if location:
                    locations[location["venue"]] = location
            continue
        special_groups.append(group)

    return special_groups, locations


def text_query_from_maps_url(url: str, fallback_name: str, lat: float, lng: float) -> str:
    if url:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query).get("query", [""])[0].strip()
        if query:
            return urllib.parse.unquote_plus(query)
    return f"{fallback_name} {lat},{lng}"


def google_places_search_text_new(api_key: str, text_query: str, lat: float, lng: float) -> dict:
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.rating,places.userRatingCount,"
            "places.formattedAddress,places.googleMapsUri,places.websiteUri"
        ),
    }
    body = {
        "textQuery": text_query,
        "pageSize": 1,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 600.0,
            }
        },
    }
    payload = fetch_json_post(GOOGLE_PLACES_SEARCH_URL, headers, body)
    places = payload.get("places", []) if isinstance(payload, dict) else []
    return places[0] if places else {}


def enrich_locations_with_ratings(locations: dict[str, dict]) -> dict[str, dict]:
    api_key = secret("GOOGLE_PLACES_API_KEY") or secret("GOOGLE_MAPS_API_KEY") or secret("GOOGLE_API_KEY")
    if not api_key:
        return locations

    enriched: dict[str, dict] = {}
    for venue, location in locations.items():
        lat = location.get("lat")
        lng = location.get("lng")
        if not isinstance(lat, (float, int)) or not isinstance(lng, (float, int)):
            enriched[venue] = location
            continue
        try:
            query = text_query_from_maps_url(str(location.get("url", "")), venue, float(lat), float(lng))
            place = google_places_search_text_new(api_key, query, float(lat), float(lng))
            if not place:
                enriched[venue] = location
                continue
            merged = dict(location)
            merged["google_place_id"] = place.get("id", "")
            merged["google_name"] = (place.get("displayName") or {}).get("text", "")
            if place.get("rating") is not None:
                merged["rating"] = place.get("rating")
            if place.get("userRatingCount") is not None:
                merged["user_ratings_total"] = place.get("userRatingCount")
            merged["formatted_address"] = place.get("formattedAddress", "")
            merged["google_maps_url"] = place.get("googleMapsUri", "") or str(location.get("url", ""))
            merged["website"] = place.get("websiteUri", "")
            enriched[venue] = merged
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
            enriched[venue] = location
    return enriched


def normalize_place_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def place_address(place: dict) -> str:
    address = (
        place.get("address")
        or place.get("formatted_address")
        or place.get("google_name")
        or place.get("venue")
        or place.get("name")
        or ""
    )
    address = " ".join(str(address).split())
    if address and "south africa" not in address.lower():
        address = f"{address}, Cape Town, South Africa"
    return address


def load_existing_places() -> dict[str, dict]:
    if not PLACES_OUTPUT_FILE.exists():
        return {}
    try:
        payload = json.loads(PLACES_OUTPUT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    places: dict[str, dict] = {}
    for _, value in payload.items():
        if not isinstance(value, dict):
            continue
        name = str(value.get("name") or value.get("venue") or "").strip()
        if not name:
            continue
        record = {
            "name": name,
            "address": str(value.get("address") or "").strip(),
            "tags": value.get("tags", []),
            "url": str(value.get("url") or "").strip(),
            "google_maps_url": str(value.get("google_maps_url") or "").strip(),
        }
        tags = record["tags"]
        if not isinstance(tags, list):
            tags = []
        record["tags"] = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
        places[name] = record
    return places


def attach_places_to_specials(groups: list[dict], places: dict[str, dict]) -> list[dict]:
    updated_groups: list[dict] = []
    for group in groups:
        updated_group = {key: value for key, value in group.items() if key != "source"}
        updated_items = []
        for item in group.get("items", []):
            venue = str(item.get("venue") or item.get("title") or "").strip()
            place = location_for_venue_name(venue, places)
            print(f"Processing special: {venue or item.get('title') or 'Special'}")
            clean_item = {key: value for key, value in item.items() if key != "url"}
            clean_item["place"] = place["name"] if place else ""
            clean_item["place_key"] = place["name"] if place else ""
            clean_item["missing_place"] = not bool(place)
            updated_items.append(clean_item)
        updated_group["items"] = updated_items
        updated_groups.append(updated_group)
    return updated_groups


def location_for_venue_name(venue: str, places: dict[str, dict]) -> dict | None:
    normalized_venue = re.sub(r"[^a-z0-9]", "", str(venue or "").lower())
    if not normalized_venue:
        return None
    for place in places.values():
        normalized_place = re.sub(r"[^a-z0-9]", "", str(place.get("name") or "").lower())
        normalized_address = re.sub(r"[^a-z0-9]", "", str(place.get("address") or "").lower())
        if (
            normalized_venue == normalized_place
            or normalized_venue.startswith(normalized_place)
            or normalized_place.startswith(normalized_venue)
            or (normalized_address and normalized_venue in normalized_address)
        ):
            return place
    return None


def specials_from_database(token: str, database_id: str) -> list[dict]:
    results: list[dict] = []
    cursor = ""
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        payload = notion_post(f"databases/{database_id}/query", token, body)
        results.extend(payload.get("results", []))
        if not payload.get("has_more"):
            break
        cursor = payload.get("next_cursor") or ""

    per_day: dict[str, list[dict]] = {day: [] for day in DAY_ORDER}

    for row in results:
        properties = row.get("properties", {}) or {}
        location = property_plain_text(property_by_name(properties, ["Location", "Venue", "Place", "Name"]))
        details = property_plain_text(property_by_name(properties, ["Details", "Detail", "Special", "Deal"]))
        price = property_plain_text(property_by_name(properties, ["Price", "Cost"]))
        time_text = property_plain_text(property_by_name(properties, ["Time", "Hours"]))
        days_raw = property_multi_select_names(
            property_by_name(properties, ["Multi-select", "Days", "Day", "Weekdays"])
        )
        days = [normalize_day_tag(day) for day in days_raw]
        days = [day for day in days if day]
        if not location or not days:
            continue

        deal_parts = [details.strip()]
        if price.strip():
            deal_parts.append(price.strip())
        if time_text.strip():
            deal_parts.append(time_text.strip())
        deal_text = " | ".join([part for part in deal_parts if part])

        item = {
            "venue": location.strip(),
            "title": location.strip(),
            "deal": deal_text or details.strip() or "Special",
            "description": deal_text or details.strip() or "Special",
            "details": details.strip(),
            "price": price.strip(),
            "time": time_text.strip(),
            "url": row.get("url", ""),
        }
        for day in days:
            per_day[day].append(item)

    groups: list[dict] = []
    for day in DAY_ORDER:
        items = per_day[day]
        if items:
            groups.append({"title": day, "days": [day], "items": items})
    return groups


def write_payload(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_places(places: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PLACES_OUTPUT_FILE.write_text(json.dumps(places, indent=2, ensure_ascii=False), encoding="utf-8")


def scrape_specials(enrich_places: bool = False) -> dict:
    token = secret("NOTION_TOKEN") or secret("NOTION_API_TOKEN")
    if not token:
        return {
            "source": PAGE_URL,
            "title": "Specials",
            "error": "Missing NOTION_TOKEN",
            "groups": [],
        }

    try:
        page = notion_request(f"pages/{PAGE_ID}", token)
        blocks = flatten_blocks(get_block_children(PAGE_ID, token), token)
        legacy_groups, _locations = split_specials_and_locations(specials_from_blocks(blocks))
        database_id = database_id_from_secret_or_url()
        groups = legacy_groups
        if database_id:
            groups = specials_from_database(token, database_id)
        places = load_existing_places()
        if enrich_places:
            print("Place enrichment is ignored here because places.json is now manually maintained.")
        groups = attach_places_to_specials(groups, places)
        return {
            "title": page_title(page),
            "groups": groups,
        }
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        return {
            "source": PAGE_URL,
            "title": "Specials",
            "error": f"Notion API error {error.code}: {detail}",
            "groups": [],
        }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Scrape specials and places from Notion.")
    parser.add_argument("--hard", action="store_true", help="Recreate specials output from scratch before writing.")
    parser.add_argument("--limit", type=int, default=0, help="Accepted for wrapper consistency; specials are not item-limited.")
    parser.add_argument("--max-pages", type=int, default=0, help="Accepted for wrapper consistency; Notion pagination is automatic.")
    parser.add_argument(
        "--enrich-places",
        action="store_true",
        help="Optionally enrich place details using Google Places (slower).",
    )
    args = parser.parse_args()

    if args.hard:
        if OUTPUT_FILE.exists():
            print(f"Removing stale specials output: {OUTPUT_FILE}")
            OUTPUT_FILE.unlink()
    payload = scrape_specials(enrich_places=bool(args.enrich_places))
    write_payload(payload)
    sync_events_data_to_docs()
    print(f"Wrote {len(payload.get('groups', []))} special group(s) to {OUTPUT_FILE}")
    print(f"Using manual places file: {PLACES_OUTPUT_FILE}")
    if payload.get("error"):
        print(payload["error"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
