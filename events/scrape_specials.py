from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


NOTION_VERSION = "2022-06-28"
PAGE_URL = "https://www.notion.so/Places-082fa9625a9f4f949d03a8d1517c76f8"
PAGE_ID = "082fa9625a9f4f949d03a8d1517c76f8"
SPECIALS_DATABASE_ID = "NOTION_SPECIALS_DATABASE_ID"
SPECIALS_DATABASE_URL = "NOTION_SPECIALS_DATABASE_URL"
DEFAULT_SPECIALS_DATABASE_ID = "35157df8191880f7accedf40168acee7"
REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_FILE = DATA_DIR / "specials.json"
LOCAL_SECRETS_FILE = REPO_DIR / "secrets.env"
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


def rich_text_plain(rich_text: list[dict], include_strikethrough: bool = False) -> str:
    parts: list[str] = []
    for part in rich_text:
        annotations = part.get("annotations") or {}
        if annotations.get("strikethrough") and not include_strikethrough:
            continue
        parts.append(part.get("plain_text", ""))
    return "".join(parts).strip()


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


def notion_post(path: str, token: str, body: dict) -> dict:
    request = urllib.request.Request(
        f"https://api.notion.com/v1/{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
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
    match = re.match(
        r"^\s*(?P<venue>[^:]+):\s*(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lng>-?\d+(?:\.\d+)?)(?:\s*;\s*\((?P<tags>[^)]*)\))?(?:\s*\|\s*(?P<url>https?://\S+))?",
        text,
    )
    if not match:
        return None
    raw_tags = (match.group("tags") or "").strip()
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
        "venue": match.group("venue").strip(),
        "lat": float(match.group("lat")),
        "lng": float(match.group("lng")),
        "types": types,
        "categories": categories,
        "tags": list(dict.fromkeys(types + categories)),
        "url": (match.group("url") or "").strip(),
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
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def scrape_specials() -> dict:
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
        legacy_groups, locations = split_specials_and_locations(specials_from_blocks(blocks))
        database_id = database_id_from_secret_or_url()
        groups = legacy_groups
        if database_id:
            groups = specials_from_database(token, database_id)
        return {
            "source": PAGE_URL,
            "title": page_title(page),
            "locations": locations,
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
    payload = scrape_specials()
    write_payload(payload)
    print(f"Wrote {len(payload.get('groups', []))} special group(s) to {OUTPUT_FILE}")
    if payload.get("error"):
        print(payload["error"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
