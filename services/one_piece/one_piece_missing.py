from __future__ import annotations

import csv
import html
import json
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import io
from pathlib import Path
from zipfile import ZipFile

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except Exception:  # noqa: BLE001
    Image = None  # type: ignore[assignment]
    ImageEnhance = None  # type: ignore[assignment]
    ImageFilter = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]

try:
    import pytesseract
except Exception:  # noqa: BLE001
    pytesseract = None  # type: ignore[assignment]

sys.path.append(str(Path(__file__).resolve().parents[2]))
from env import get as env_get


ONE_PIECE_DIR = Path(__file__).resolve().parent
WORKBOOK = ONE_PIECE_DIR / "One Piece Cards.xlsx"
ONE_PIECE_DATA_DIR = Path(__file__).resolve().parents[2] / "docs" / "data" / "one_piece"
REPO_DIR = Path(__file__).resolve().parents[2]
LOCAL_SECRETS_FILE = REPO_DIR / "secrets.env"

KNIGHTLY_COLLECTION_URL = env_get("SCRAPE_OP_KNIGHTLY_COLLECTION_URL", "https://www.knightlygaming.co.za/collections/one-piece-singles")
KNIGHTLY_PRODUCTS_URL = KNIGHTLY_COLLECTION_URL + "/products.json?limit=250&page={page}"

MARVELLOUS_COLLECTION_URL = env_get("SCRAPE_OP_MARVELLOUS_COLLECTION_URL", "https://marvelloushobbies.com/one-piece-singles/")
MARVELLOUS_PRODUCTS_URL = (
    env_get("SCRAPE_OP_MARVELLOUS_PRODUCTS_URL_TEMPLATE", "https://marvelloushobbies.com/wp-json/wc/store/v1/products?per_page=100&page={page}&category_ids[]=36")
)

TANUKI_COLLECTION_URL = env_get("SCRAPE_OP_TANUKI_COLLECTION_URL", "https://tanukitrader.co.za/")
TANUKI_PRODUCTS_URL = (
    env_get("SCRAPE_OP_TANUKI_PRODUCTS_URL_TEMPLATE", "https://tanukitrader.co.za/wp-json/wc/store/v1/products?per_page=100&page={page}")
)

TOAD_COLLECTION_URL = env_get("SCRAPE_OP_TOAD_COLLECTION_URL", "https://www.toadtradertcg.com/category/one-piece-tcg")
TOAD_PRODUCTS_URL = env_get("SCRAPE_OP_TOAD_PRODUCTS_URL_TEMPLATE", "")

GEEK_HAVEN_COLLECTION_URL = env_get("SCRAPE_OP_GEEK_HAVEN_COLLECTION_URL", "https://www.bobshop.co.za/seller/5031053/GeekHaven")
GEEK_HAVEN_PAGE_URL = env_get(
    "SCRAPE_OP_GEEK_HAVEN_PAGE_URL_TEMPLATE",
    "https://www.bobshop.co.za/mobilejquery/jsp/userprofile/UserTradeList.jsp?User_UserId=5031053&pageNo={page}",
)

BIG_BANG_COLLECTION_URL = env_get("SCRAPE_OP_BIG_BANG_COLLECTION_URL", "https://bigbangshop.co.za/collections/one-piece-single-cards")
BIG_BANG_PRODUCTS_URL = BIG_BANG_COLLECTION_URL + "/products.json?limit=250&page={page}"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

TAG_RE = re.compile(r"<[^>]+>")
DRIVE_FILE_ID_RE = re.compile(r"/d/([a-zA-Z0-9_-]+)")

RARITY_NAMES = [
    "Super Rare",
    "Secret Rare",
    "Uncommon",
    "Common",
    "Leader",
    "Rare",
    "DON!!",
]


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


def setting(name: str) -> str:
    return (env_get(name, "") or local_secret(name)).strip()


def drive_file_id_from_url(url: str) -> str:
    if not url:
        return ""
    match = DRIVE_FILE_ID_RE.search(url)
    if match:
        return match.group(1)
    marker = "id="
    if marker in url:
        return url.split(marker, 1)[1].split("&", 1)[0].strip()
    return ""


def drive_download_url() -> str:
    workbook_drive_url = setting("SCRAPE_OP_MISSING_CARDS_DRIVE_URL")
    workbook_drive_file_id = setting("SCRAPE_OP_MISSING_CARDS_DRIVE_FILE_ID")

    if workbook_drive_url:
        if "export=download" in workbook_drive_url:
            return workbook_drive_url
        file_id = drive_file_id_from_url(workbook_drive_url)
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        return workbook_drive_url
    if workbook_drive_file_id:
        return f"https://drive.google.com/uc?export=download&id={workbook_drive_file_id}"
    return ""


def drive_download_candidates() -> list[str]:
    workbook_drive_url = setting("SCRAPE_OP_MISSING_CARDS_DRIVE_URL")
    workbook_drive_file_id = setting("SCRAPE_OP_MISSING_CARDS_DRIVE_FILE_ID")

    urls: list[str] = []
    if workbook_drive_url:
        urls.append(workbook_drive_url)
        if "docs.google.com/spreadsheets" in workbook_drive_url:
            file_id = drive_file_id_from_url(workbook_drive_url)
            if file_id:
                urls.append(f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx")
        converted = drive_download_url()
        if converted and converted not in urls:
            urls.append(converted)
    elif workbook_drive_file_id:
        urls.append(f"https://drive.google.com/uc?export=download&id={workbook_drive_file_id}")
        urls.append(f"https://docs.google.com/spreadsheets/d/{workbook_drive_file_id}/export?format=xlsx")

    # Keep order while removing duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def workbook_from_drive() -> Path | None:
    candidates = drive_download_candidates()
    if not candidates:
        return None

    errors: list[str] = []
    for url in candidates:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                content_type = str(response.headers.get("Content-Type", "")).lower()
                content = response.read()
        except urllib.error.HTTPError as error:
            errors.append(f"{url} -> HTTP {error.code}")
            continue
        except urllib.error.URLError as error:
            errors.append(f"{url} -> URL error: {error.reason}")
            continue

        if not content:
            errors.append(f"{url} -> empty response")
            continue

        # Drive permission/login pages return HTML, not a workbook.
        if "text/html" in content_type:
            errors.append(f"{url} -> returned HTML instead of .xlsx (check sharing/permissions)")
            continue
        if not content.startswith(b"PK"):
            errors.append(f"{url} -> response was not an .xlsx file")
            continue

        temp_dir = Path(tempfile.gettempdir()) / "one_piece_scraper"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_workbook = temp_dir / "missing_cards_from_drive.xlsx"
        temp_workbook.write_bytes(content)
        return temp_workbook

    details = "\n".join(f"- {entry}" for entry in errors) if errors else "- no download candidates generated"
    raise RuntimeError(
        "Failed to download missing-cards workbook from Google Drive.\n"
        "Make sure the file is shared with Viewer access and link access is enabled.\n"
        f"Tried:\n{details}"
    )


def resolve_workbook_path(local_workbook: Path = WORKBOOK) -> Path:
    drive_workbook = workbook_from_drive()
    if drive_workbook:
        print(f"Using missing-cards workbook from Google Drive: {drive_workbook}")
        return drive_workbook
    if not local_workbook.exists():
        raise FileNotFoundError(
            "Missing workbook. Set SCRAPE_OP_MISSING_CARDS_DRIVE_URL (or SCRAPE_OP_MISSING_CARDS_DRIVE_FILE_ID) "
            "in environment/secrets.env, or restore local file services/one_piece/One Piece Cards.xlsx"
        )
    print(f"Using missing-cards workbook from local file: {local_workbook}")
    return local_workbook


def column_number(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    number = 0
    for ch in letters:
        number = number * 26 + ord(ch.upper()) - 64
    return number


def clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_card_number(value: object) -> str | None:
    if value is None:
        return None

    text = clean_text(value).upper()
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("OP-", "OP").replace("ST-", "ST")
    text = text.replace("EB-", "EB").replace("PRB-", "PRB")

    match = re.search(r"\b(OP|ST|EB|PRB)(\d{1,2})-(\d{1,3})\b", text)
    if not match:
        return None

    prefix, set_number, card_number = match.groups()
    return f"{prefix}{int(set_number):02d}-{int(card_number):03d}"


def load_sheet_rows(path: Path, sheet_name: str) -> list[dict[int, str]]:
    with ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", NS):
                shared_strings.append("".join(t.text or "" for t in item.findall(".//a:t", NS)))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

        target = None
        for sheet in workbook.findall("a:sheets/a:sheet", NS):
            if sheet.attrib["name"] == sheet_name:
                rel_id = sheet.attrib[
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                ]
                target = targets[rel_id]
                break

        if target is None:
            raise ValueError(f"Could not find sheet named {sheet_name!r}")

        sheet_path = "xl/" + target if not target.startswith("/") else target[1:]
        root = ET.fromstring(archive.read(sheet_path))

        rows: list[dict[int, str]] = []
        for row in root.findall("a:sheetData/a:row", NS):
            values: dict[int, str] = {}
            for cell in row.findall("a:c", NS):
                value = cell.find("a:v", NS)
                if value is None:
                    continue
                cell_value = value.text or ""
                if cell.attrib.get("t") == "s":
                    cell_value = shared_strings[int(cell_value)]
                values[column_number(cell.attrib["r"])] = cell_value
            rows.append(values)
        return rows


def missing_card_numbers(workbook: Path = WORKBOOK) -> set[str]:
    workbook = resolve_workbook_path(workbook)
    missing: set[str] = set()
    for row in load_sheet_rows(workbook, "Missing"):
        for value in row.values():
            card_number = normalize_card_number(value)
            if card_number:
                missing.add(card_number)
    return missing


def print_found_listings(store: str, matches: list[dict[str, object]]) -> None:
    print(f"Found missing-card listings on {store}: {len(matches)}")
    if not matches:
        print("Found listings: (none)")
        return
    print("Found listings:")
    for row in sorted_matches(matches):
        print(
            f"{row.get('card_number', '')} | "
            f"R {float(row.get('price') or 0):.2f} | "
            f"{row.get('title', '')} | "
            f"{row.get('store', '')} | "
            f"{row.get('url', '')}"
        )


def fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_woo_page(url: str) -> tuple[list[dict], int, int]:
    """Fetch a WooCommerce Store API page. Returns (products, total_items, total_pages)."""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        total_items = int(response.headers.get("X-WP-Total") or 0)
        total_pages = int(response.headers.get("X-WP-TotalPages") or 0)
        data = json.loads(response.read().decode("utf-8"))
    products = data if isinstance(data, list) else []
    return products, total_items, total_pages


def body_field(body_html: str, label: str) -> str:
    pattern = re.compile(
        r"<td>\s*" + re.escape(label) + r":\s*</td>\s*<td>\s*(.*?)\s*</td>",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(body_html or "")
    if not match:
        return ""
    return clean_text(match.group(1))


def sorted_matches(matches: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        matches,
        key=lambda item: (
            float(item["price"]),
            str(item["card_number"]),
            str(item["store"]),
            str(item["title"]),
        ),
    )


_LISTING_FIELDS = [
    "card_number", "price", "title", "rarity", "store",
    "set_name", "condition", "stock", "available_variants", "url", "image_url",
    "scraped_at",
]

COMBINED_JSON = ONE_PIECE_DATA_DIR / "missing_cards.json"
COLLECTION_JSON = ONE_PIECE_DATA_DIR / "collection.json"

_IMAGE_MATCH_CACHE_RUNTIME: dict[str, dict[str, str]] | None = None
_COLLECTION_HASHES_RUNTIME: dict[str, dict[str, str]] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json_dict(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_json_dict(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _listing_dict(match: dict[str, object]) -> dict[str, object]:
    return {field: match.get(field, "") for field in _LISTING_FIELDS}


def _listing_key(listing: dict[str, object]) -> str:
    return f"{listing.get('card_number', '')}|{listing.get('url', '')}"


def _apply_scraped_at(
    new_listings: list[dict[str, object]],
    old_listings: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Preserve scraped_at for existing listings; set now for new ones."""
    now = _now_iso()
    old_map = {_listing_key(r): str(r.get("scraped_at") or "") for r in old_listings}
    for listing in new_listings:
        listing["scraped_at"] = old_map.get(_listing_key(listing)) or now
    return new_listings


def _write_json(listings: list[dict[str, object]]) -> None:
    ONE_PIECE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"listings": [_listing_dict(m) for m in listings]}
    COMBINED_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote missing_cards.json ({len(listings)} listings)", flush=True)


def update_store_in_combined_json(store_name: str, matches: list[dict[str, object]]) -> None:
    """Replace this store's entries in missing_cards.json, keeping all other stores intact."""
    old_all: list[dict[str, object]] = []
    old_store: list[dict[str, object]] = []
    if COMBINED_JSON.exists():
        data = json.loads(COMBINED_JSON.read_text(encoding="utf-8"))
        for r in data.get("listings", []):
            (old_store if r.get("store") == store_name else old_all).append(r)
    matches = _apply_scraped_at(list(matches), old_store)
    _write_json(sorted_matches(old_all + matches))


def write_combined_json(listings: list[dict[str, object]]) -> None:
    old_listings: list[dict[str, object]] = []
    if COMBINED_JSON.exists():
        data = json.loads(COMBINED_JSON.read_text(encoding="utf-8"))
        old_listings = data.get("listings", [])
    listings = _apply_scraped_at(sorted_matches(listings), old_listings)
    _write_json(listings)


def _geek_cache_key(product: dict) -> str:
    url = str(product.get("permalink") or "").strip()
    if url:
        return url
    return _title_lookup_key(str(product.get("name") or ""))


def load_geek_haven_ocr_cache() -> dict[str, dict[str, str]]:
    # Deprecated file-based cache; kept as in-memory compatibility wrapper.
    return {}


def save_geek_haven_ocr_cache(cache: dict[str, dict[str, str]]) -> None:
    # Deprecated file-based cache; listing match cache is stored in collection.json.
    _ = cache


def seed_geek_cache_from_previous_matches(cache: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    if not COMBINED_JSON.exists():
        return cache
    try:
        payload = json.loads(COMBINED_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return cache
    rows = payload.get("listings", []) if isinstance(payload, dict) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("store") or "").strip() != "GeekHaven":
            continue
        url = str(row.get("url") or "").strip()
        card_number = str(row.get("card_number") or "").strip()
        if not url or not card_number:
            continue
        cache[url] = {
            "card_number": card_number,
            "rarity": str(row.get("rarity") or "").strip(),
            "image_url": "",
            "updated_at": _now_iso(),
        }
    return cache


def load_collection_image_hashes() -> dict[str, dict[str, str]]:
    global _COLLECTION_HASHES_RUNTIME
    if _COLLECTION_HASHES_RUNTIME is not None:
        return _COLLECTION_HASHES_RUNTIME
    payload = _load_json_dict(COLLECTION_JSON)
    sets = payload.get("sets", {}) if isinstance(payload, dict) else {}
    out: dict[str, dict[str, str]] = {}
    if isinstance(sets, dict):
        for set_payload in sets.values():
            if not isinstance(set_payload, dict):
                continue
            for row in set_payload.get("cards", []):
                if not isinstance(row, dict):
                    continue
                card_number = str(row.get("card_number") or "").strip().upper()
                digest = str(row.get("image_hash") or "").strip()
                if not card_number or not digest:
                    continue
                out[card_number] = {
                    "hash": digest,
                    "rarity": str(row.get("rarity") or "").strip(),
                    "image_url": str(row.get("image_url") or "").strip(),
                }
    _COLLECTION_HASHES_RUNTIME = out
    return out


def load_image_match_cache() -> dict[str, dict[str, str]]:
    global _IMAGE_MATCH_CACHE_RUNTIME
    if _IMAGE_MATCH_CACHE_RUNTIME is not None:
        return _IMAGE_MATCH_CACHE_RUNTIME
    collection_payload = _load_json_dict(COLLECTION_JSON)
    cache = collection_payload.get("_listing_match_cache", {}) if isinstance(collection_payload, dict) else {}
    out: dict[str, dict[str, str]] = {}
    for key, value in cache.items():
        if not isinstance(value, dict):
            continue
        out[str(key)] = {
            "card_number": str(value.get("card_number") or "").strip(),
            "rarity": str(value.get("rarity") or "").strip(),
            "image_url": str(value.get("image_url") or "").strip(),
            "updated_at": str(value.get("updated_at") or "").strip(),
        }
    # Seed from previous successful listings so rescrapes skip rematching.
    if COMBINED_JSON.exists():
        try:
            payload = json.loads(COMBINED_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        rows = payload.get("listings", []) if isinstance(payload, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            card_number = str(row.get("card_number") or "").strip()
            if not url or not card_number:
                continue
            if url in out and out[url].get("card_number"):
                continue
            out[url] = {
                "card_number": card_number,
                "rarity": str(row.get("rarity") or "").strip(),
                "image_url": str(row.get("image_url") or "").strip(),
                "updated_at": _now_iso(),
            }
    _IMAGE_MATCH_CACHE_RUNTIME = out
    return out


def save_image_match_cache() -> None:
    if _IMAGE_MATCH_CACHE_RUNTIME is None:
        return
    collection_payload = _load_json_dict(COLLECTION_JSON)
    collection_payload["_listing_match_cache"] = _IMAGE_MATCH_CACHE_RUNTIME
    _save_json_dict(COLLECTION_JSON, collection_payload)


def _avg_hash_from_bytes(image_bytes: bytes, hash_size: int = 16) -> str:
    if Image is None:
        return ""
    img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    mean = sum(pixels) / len(pixels)
    bits = ["1" if p >= mean else "0" for p in pixels]
    hex_len = (hash_size * hash_size) // 4
    return f"{int(''.join(bits), 2):0{hex_len}x}"


def _hamming_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def resolve_card_info_from_image(product: dict, card_number: str = "", rarity: str = "") -> tuple[str, str]:
    current_card = str(card_number or "").strip().upper()
    current_rarity = str(rarity or "").strip()
    if current_card:
        return current_card, current_rarity

    image_cache = load_image_match_cache()
    collection_hashes = load_collection_image_hashes()
    if not collection_hashes:
        return "", ""

    images = product.get("images") or []
    image_url = str(images[0].get("src") or "") if images else ""
    url_key = str(product.get("permalink") or "").strip()
    if not image_url or not url_key:
        return "", ""

    cached = image_cache.get(url_key) or {}
    if cached.get("card_number") and (
        not cached.get("image_url")
        or not image_url
        or str(cached.get("image_url") or "") == image_url
    ):
        return str(cached.get("card_number") or "").strip(), str(cached.get("rarity") or "").strip()

    try:
        req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            source_bytes = response.read()
        source_hash = _avg_hash_from_bytes(source_bytes)
    except Exception:
        source_hash = ""
    if not source_hash:
        image_cache[url_key] = {
            "card_number": "",
            "rarity": "",
            "image_url": image_url,
            "updated_at": _now_iso(),
        }
        return "", ""

    best_card = ""
    best_rarity = ""
    best_distance = 10_000
    for candidate_card, row in collection_hashes.items():
        digest = str(row.get("hash") or "").strip()
        if not digest:
            continue
        try:
            distance = _hamming_hex(source_hash, digest)
        except Exception:
            continue
        if distance < best_distance:
            best_distance = distance
            best_card = candidate_card
            best_rarity = str(row.get("rarity") or "").strip()

    max_distance = int(setting("SCRAPE_OP_IMAGE_MATCH_MAX_DISTANCE") or "26")
    if not best_card or best_distance > max_distance:
        image_cache[url_key] = {
            "card_number": "",
            "rarity": "",
            "image_url": image_url,
            "updated_at": _now_iso(),
        }
        return "", ""

    image_cache[url_key] = {
        "card_number": best_card,
        "rarity": best_rarity,
        "image_url": image_url,
        "updated_at": _now_iso(),
    }
    return best_card, best_rarity


_OCR_CARD_RE = re.compile(r"\b(?:OP|ST|EB|PRB)\d{1,2}-\d{1,3}\b", re.IGNORECASE)
_OCR_CODE_RE = re.compile(r"\b(?:C|UC|R|SR|SEC|L)\b", re.IGNORECASE)
_RARITY_CODE_MAP = {
    "C": "Common",
    "UC": "Uncommon",
    "R": "Rare",
    "SR": "Super Rare",
    "SEC": "Secret Rare",
    "L": "Leader",
}


def _ocr_available() -> bool:
    if Image is None or pytesseract is None:
        return False
    try:
        _ = pytesseract.get_tesseract_version()  # type: ignore[union-attr]
    except Exception:
        return False
    return True


def _configure_tesseract_cmd() -> None:
    if pytesseract is None:
        return
    configured = setting("SCRAPE_TESSERACT_CMD")
    if configured:
        pytesseract.pytesseract.tesseract_cmd = configured  # type: ignore[union-attr]
        return
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in common_paths:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path  # type: ignore[union-attr]
            return


def _extract_card_and_rarity_from_text(text: str) -> tuple[str, str]:
    card = ""
    rarity = ""
    card_match = _OCR_CARD_RE.search(text or "")
    if card_match:
        card = normalize_card_number(card_match.group(0)) or ""
    if card:
        tail = (text or "")[card_match.end() : card_match.end() + 10]
        rarity_match = _OCR_CODE_RE.search(tail)
        if rarity_match:
            rarity = _RARITY_CODE_MAP.get(rarity_match.group(0).upper(), "")
    return card, rarity


def _ocr_card_from_geek_image(image_url: str) -> tuple[str, str]:
    if not _ocr_available() or not image_url:
        return "", ""
    req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        image_bytes = response.read()

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    crop = img.crop((int(w * 0.68), int(h * 0.78), w, h))

    gray = ImageOps.grayscale(crop)
    variants = [
        gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS),
        gray.resize((gray.width * 3, gray.height * 3), Image.Resampling.LANCZOS),
    ]
    variants.append(variants[-1].filter(ImageFilter.SHARPEN))
    variants.append(ImageEnhance.Contrast(variants[-1]).enhance(2.4))
    variants.append(variants[-1].point(lambda p: 255 if p > 145 else 0))

    for variant in variants:
        for psm in (6, 7, 11, 13):
            config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist=OPSTEBPRBCUL0123456789-"
            text = pytesseract.image_to_string(variant, config=config)  # type: ignore[union-attr]
            card, rarity = _extract_card_and_rarity_from_text(text)
            if card:
                return card, rarity
    return "", ""


def fetch_knightly_products() -> list[dict]:
    products: list[dict] = []
    for page in range(1, 50):
        print(f"Knightly Gaming: fetching page {page}...", flush=True)
        data = fetch_json(KNIGHTLY_PRODUCTS_URL.format(page=page))
        page_products = data.get("products", [])
        print(f"Knightly Gaming: page {page} -> {len(page_products)} products", flush=True)
        if not page_products:
            break
        products.extend(page_products)
    print(f"Knightly Gaming: {len(products)} products total", flush=True)
    return products


def match_knightly(missing: set[str], products: list[dict]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for product in products:
        body = product.get("body_html") or ""
        card_number = normalize_card_number(body_field(body, "Card Number"))
        rarity = body_field(body, "Rarity")
        if not card_number:
            card_number, inferred_rarity = resolve_card_info_from_image(product, card_number="", rarity=rarity)
            if inferred_rarity and not rarity:
                rarity = inferred_rarity
        if not card_number or card_number not in missing:
            continue

        available_variants = [
            variant for variant in product.get("variants", []) if variant.get("available")
        ]
        if not available_variants:
            continue

        cheapest = min(available_variants, key=lambda item: float(item.get("price") or 0))
        images = product.get("images") or []
        matches.append(
            {
                "store": "Knightly Gaming",
                "card_number": card_number,
                "title": product.get("title") or "",
                "set_name": body_field(body, "Set Name"),
                "rarity": rarity,
                "condition": cheapest.get("title") or "",
                "stock": "In stock",
                "price": float(cheapest.get("price") or 0),
                "available_variants": "; ".join(
                    f"{variant.get('title')} R{float(variant.get('price') or 0):.2f}"
                    for variant in available_variants
                ),
                "url": f"{KNIGHTLY_COLLECTION_URL}/products/{product.get('handle', '')}",
                "image_url": str(images[0].get("src") or "") if images else "",
            }
        )
    return matches


def run_knightly() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_knightly_products()
    matches = sorted_matches(match_knightly(missing, products))
    save_image_match_cache()
    update_store_in_combined_json("Knightly Gaming", matches)
    print_store_summary("Knightly Gaming", missing, products, matches)
    print_found_listings("Knightly Gaming", matches)
    return matches


def fetch_big_bang_products() -> list[dict]:
    products: list[dict] = []
    for page in range(1, 50):
        print(f"Big Bang Shop: fetching page {page}...", flush=True)
        data = fetch_json(BIG_BANG_PRODUCTS_URL.format(page=page))
        page_products = data.get("products", [])
        print(f"Big Bang Shop: page {page} -> {len(page_products)} products", flush=True)
        if not page_products:
            break
        products.extend(page_products)
    print(f"Big Bang Shop: {len(products)} products total", flush=True)
    return products


def match_big_bang(missing: set[str], products: list[dict]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for product in products:
        body = product.get("body_html") or ""
        card_number = normalize_card_number(body_field(body, "Card Number"))
        rarity = body_field(body, "Rarity")
        if not card_number:
            card_number, inferred_rarity = resolve_card_info_from_image(product, card_number="", rarity=rarity)
            if inferred_rarity and not rarity:
                rarity = inferred_rarity
        if not card_number or card_number not in missing:
            continue

        available_variants = [
            variant for variant in product.get("variants", []) if variant.get("available")
        ]
        if not available_variants:
            continue

        cheapest = min(available_variants, key=lambda item: float(item.get("price") or 0))
        images = product.get("images") or []
        matches.append(
            {
                "store": "Big Bang Shop",
                "card_number": card_number,
                "title": product.get("title") or "",
                "set_name": body_field(body, "Set Name"),
                "rarity": rarity,
                "condition": cheapest.get("title") or "",
                "stock": "In stock",
                "price": float(cheapest.get("price") or 0),
                "available_variants": "; ".join(
                    f"{variant.get('title')} R{float(variant.get('price') or 0):.2f}"
                    for variant in available_variants
                ),
                "url": f"{BIG_BANG_COLLECTION_URL}/products/{product.get('handle', '')}",
                "image_url": str(images[0].get("src") or "") if images else "",
            }
        )
    return matches


def run_big_bang() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_big_bang_products()
    matches = sorted_matches(match_big_bang(missing, products))
    save_image_match_cache()
    update_store_in_combined_json("Big Bang Shop", matches)
    print_store_summary("Big Bang Shop", missing, products, matches)
    print_found_listings("Big Bang Shop", matches)
    return matches


def _discover_marvellous_category_id() -> str:
    """Discover the right category_id for One Piece singles by listing all categories."""
    # Try WooCommerce Store API categories (product_cat taxonomy)
    try:
        data = fetch_json("https://marvelloushobbies.com/wp-json/wc/store/v1/products/categories?per_page=100&_fields=id,name,slug,parent")
        if isinstance(data, list):
            print(f"Marvellous Hobbies: {len(data)} product categories found:", flush=True)
            match_id = ""
            for cat in sorted(data, key=lambda c: str(c.get("name") or "")):
                name = str(cat.get("name") or "").strip()
                slug = str(cat.get("slug") or "").strip()
                cat_id = cat.get("id")
                print(f"  [{cat_id}] {name!r} (slug={slug!r})", flush=True)
                if re.search(r"one.piece", name, re.IGNORECASE) or re.search(r"one.piece", slug, re.IGNORECASE):
                    match_id = str(cat_id or "")
            if match_id:
                print(f"Marvellous Hobbies: auto-matched One Piece category id={match_id}", flush=True)
                return match_id
            print("Marvellous Hobbies: no 'one piece' category found in product_cat taxonomy", flush=True)
    except Exception as error:
        print(f"Marvellous Hobbies: Store API categories failed: {error}", flush=True)

    # Try WordPress REST API universe taxonomy as fallback
    try:
        data = fetch_json("https://marvelloushobbies.com/wp-json/wp/v2/universe?slug=one-piece&_fields=id,slug,name")
        if isinstance(data, list) and data:
            term = data[0]
            print(f"Marvellous Hobbies: found universe taxonomy term {term.get('name')!r} id={term.get('id')} — but WooCommerce Store API cannot filter by custom taxonomies", flush=True)
    except Exception:
        pass

    return ""


def _marvellous_url_template() -> str:
    """Build a URL filtered to One Piece products, or fall back to full catalog."""
    cat_id = _discover_marvellous_category_id()
    if cat_id:
        base = "https://marvelloushobbies.com/wp-json/wc/store/v1/products"
        return f"{base}?per_page=100&page={{page}}&category_ids[]={cat_id}"
    print("Marvellous Hobbies: WARNING — no category filter found, fetching full catalog (slow)", flush=True)
    return "https://marvelloushobbies.com/wp-json/wc/store/v1/products?per_page=100&page={page}"


def fetch_marvellous_products() -> list[dict]:
    url_template = _marvellous_url_template()
    products: list[dict] = []
    total_pages = 0
    for page in range(1, 200):
        print(f"Marvellous Hobbies: fetching page {page}{f'/{total_pages}' if total_pages else ''}...", flush=True)
        page_products, total_items, total_pages = fetch_woo_page(url_template.format(page=page))
        print(f"Marvellous Hobbies: page {page}/{total_pages} -> {len(page_products)} products (total: {total_items})", flush=True)
        if not page_products:
            break
        products.extend(page_products)
        if total_pages and page >= total_pages:
            break
    print(f"Marvellous Hobbies: {len(products)} products total", flush=True)
    return products


def woo_price(product: dict) -> float:
    prices = product.get("prices") or {}
    minor_unit = int(prices.get("currency_minor_unit") or 2)
    return int(prices.get("price") or 0) / (10**minor_unit)


def woo_category_names(product: dict) -> list[str]:
    return [clean_text(category.get("name")) for category in product.get("categories", [])]


def category_rarity(product: dict) -> str:
    category_text = " ".join(woo_category_names(product))
    for rarity in RARITY_NAMES:
        if re.search(r"\b" + re.escape(rarity) + r"\b", category_text, re.IGNORECASE):
            return rarity
    return ""


def category_set_name(product: dict) -> str:
    for name in woo_category_names(product):
        if re.search(r"\((OP|ST|EB|PRB)\d{1,2}\)", name, re.IGNORECASE):
            return name
    return ""


def match_marvellous(missing: set[str], products: list[dict]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for product in products:
        permalink = str(product.get("permalink") or "").lower()
        if "one-piece" not in permalink and "one_piece" not in permalink:
            continue
        search_text = " ".join(
            str(product.get(key) or "")
            for key in ["name", "sku", "description", "short_description", "permalink"]
        )
        card_number = normalize_card_number(search_text)
        rarity = category_rarity(product)
        if not card_number:
            card_number, inferred_rarity = resolve_card_info_from_image(product, card_number="", rarity=rarity)
            if inferred_rarity and not rarity:
                rarity = inferred_rarity
        if not card_number or card_number not in missing:
            continue
        if not product.get("is_in_stock") or not product.get("is_purchasable"):
            continue

        stock = clean_text((product.get("stock_availability") or {}).get("text"))
        images = product.get("images") or []
        matches.append(
            {
                "store": "Marvellous Hobbies",
                "card_number": card_number,
                "title": clean_text(product.get("name")),
                "set_name": "",
                "rarity": rarity,
                "condition": "",
                "stock": stock,
                "price": woo_price(product),
                "available_variants": stock,
                "url": product.get("permalink") or MARVELLOUS_COLLECTION_URL,
                "image_url": str(images[0].get("src") or "") if images else "",
            }
        )
    return matches


def run_marvellous() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_marvellous_products()
    matches = sorted_matches(match_marvellous(missing, products))
    save_image_match_cache()
    update_store_in_combined_json("Marvellous Hobbies", matches)
    print_store_summary("Marvellous Hobbies", missing, products, matches)
    print_found_listings("Marvellous Hobbies", matches)
    return matches


def fetch_tanuki_products() -> list[dict]:
    products: list[dict] = []
    for page in range(1, 100):
        print(f"Tanuki Trader: fetching page {page}...", flush=True)
        page_products = fetch_json(TANUKI_PRODUCTS_URL.format(page=page))
        count = len(page_products) if isinstance(page_products, list) else 0
        print(f"Tanuki Trader: page {page} -> {count} products", flush=True)
        if not page_products:
            break
        products.extend(page_products)
    print(f"Tanuki Trader: {len(products)} products total", flush=True)
    return products


def match_tanuki(missing: set[str], products: list[dict]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for product in products:
        search_text = " ".join(
            str(product.get(key) or "")
            for key in ["sku", "name", "description", "short_description", "permalink"]
        )
        card_number = normalize_card_number(search_text)
        rarity = category_rarity(product)
        if not card_number:
            card_number, inferred_rarity = resolve_card_info_from_image(product, card_number="", rarity=rarity)
            if inferred_rarity and not rarity:
                rarity = inferred_rarity
        if not card_number or card_number not in missing:
            continue
        if not product.get("is_in_stock") or not product.get("is_purchasable"):
            continue

        stock = clean_text((product.get("stock_availability") or {}).get("text"))
        images = product.get("images") or []
        matches.append(
            {
                "store": "Tanuki Trader",
                "card_number": card_number,
                "title": clean_text(product.get("name")),
                "set_name": category_set_name(product),
                "rarity": rarity,
                "condition": "",
                "stock": stock,
                "price": woo_price(product),
                "available_variants": stock,
                "url": product.get("permalink") or TANUKI_COLLECTION_URL,
                "image_url": str(images[0].get("src") or "") if images else "",
            }
        )
    return matches


def run_tanuki() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_tanuki_products()
    matches = sorted_matches(match_tanuki(missing, products))
    save_image_match_cache()
    update_store_in_combined_json("Tanuki Trader", matches)
    print_store_summary("Tanuki Trader", missing, products, matches)
    print_found_listings("Tanuki Trader", matches)
    return matches


def _discover_toad_category_id() -> str:
    try:
        data = fetch_json("https://www.toadtradertcg.com/wp-json/wc/store/v1/products/categories?per_page=100")
    except Exception as error:
        print(f"Toad Trader TCG: category discovery failed: {error}", flush=True)
        return ""
    if not isinstance(data, list):
        return ""

    for category in data:
        slug = str(category.get("slug") or "").strip().lower()
        name = str(category.get("name") or "").strip().lower()
        if slug == "one-piece-tcg" or "one piece" in name:
            category_id = str(category.get("id") or "").strip()
            if category_id:
                print(f"Toad Trader TCG: auto-matched category id={category_id} (slug={slug})", flush=True)
                return category_id
    return ""


def _toad_url_template() -> str:
    configured = TOAD_PRODUCTS_URL.strip()
    if configured:
        return configured
    category_id = _discover_toad_category_id()
    if category_id:
        return f"https://www.toadtradertcg.com/wp-json/wc/store/v1/products?per_page=100&page={{page}}&category_ids[]={category_id}"
    print("Toad Trader TCG: category not discovered, falling back to full products feed", flush=True)
    return "https://www.toadtradertcg.com/wp-json/wc/store/v1/products?per_page=100&page={page}"


_TOAD_NOISE_TITLES = {"quick view", "add to cart", "buy now", "view product"}


def _extract_toad_products_from_html(html_text: str) -> list[dict]:
    products: list[dict] = []
    seen_urls: set[str] = set()
    # Wix stores use /product-page/ (not /product/)
    for match in re.finditer(r'(?is)<a[^>]+href="([^"]*?/product-page/[^"]+)"[^>]*>(.*?)</a>', html_text):
        url = clean_text(match.group(1))
        if not url:
            continue
        if url.startswith("/"):
            url = f"https://www.toadtradertcg.com{url}"
        inner = match.group(2)
        title = clean_text(inner)
        # Skip navigation/button labels without reserving the URL, so the real
        # title link (which appears next) can still be picked up.
        if not title or title.lower() in _TOAD_NOISE_TITLES:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        # Extract price from text like "Sanji OP06-119 Price R 120,00"
        price_str = "0"
        price_match = re.search(r'\bPrice\s+R\s*([\d\s,]+)', title, re.IGNORECASE)
        if price_match:
            raw = price_match.group(1).strip().replace(" ", "").replace(",", ".")
            try:
                price_str = str(int(round(float(raw) * 100)))
            except ValueError:
                pass
            title = title[: price_match.start()].strip()
        products.append(
            {
                "name": title,
                "permalink": url,
                "sku": "",
                "description": "",
                "short_description": "",
                "is_in_stock": True,
                "is_purchasable": True,
                "stock_availability": {"text": ""},
                "prices": {"price": price_str, "currency_minor_unit": 2},
                "images": [],
                "categories": [{"name": "One Piece TCG"}],
            }
        )
    return products


def _fetch_toad_products_from_category_pages() -> list[dict]:
    products: list[dict] = []
    seen: set[str] = set()
    for page in range(1, 100):
        page_url = f"{TOAD_COLLECTION_URL}?page={page}"
        print(f"Toad Trader TCG: scraping category page {page}...", flush=True)
        try:
            html_text = fetch_text(page_url)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                print(f"Toad Trader TCG: category page {page} returned 404, stopping.", flush=True)
                break
            raise
        page_products = _extract_toad_products_from_html(html_text)
        page_products = [item for item in page_products if str(item.get("permalink") or "") not in seen]
        for item in page_products:
            seen.add(str(item.get("permalink") or ""))
        print(f"Toad Trader TCG: category page {page} -> {len(page_products)} products", flush=True)
        if not page_products:
            break
        products.extend(page_products)
    return products


def fetch_toad_products() -> list[dict]:
    products: list[dict] = []

    fetch_errors: list[str] = []
    wc_candidates = [
        _toad_url_template(),
        "https://www.toadtradertcg.com/wp-json/wc/store/products?per_page=100&page={page}",
    ]

    for url_template in wc_candidates:
        if products:
            break
        try:
            total_pages = 0
            for page in range(1, 200):
                print(f"Toad Trader TCG: fetching page {page}{f'/{total_pages}' if total_pages else ''}...", flush=True)
                page_products, total_items, total_pages = fetch_woo_page(url_template.format(page=page))
                print(
                    f"Toad Trader TCG: page {page}/{total_pages} -> {len(page_products)} products (total: {total_items})",
                    flush=True,
                )
                if not page_products:
                    break
                products.extend(page_products)
                if total_pages and page >= total_pages:
                    break
        except Exception as error:
            fetch_errors.append(f"{url_template}: {error}")
            products = []

    if not products:
        try:
            products = _fetch_toad_products_from_category_pages()
        except Exception as error:
            fetch_errors.append(f"{TOAD_COLLECTION_URL}?page={{n}}: {error}")

    if not products and fetch_errors:
        print("Toad Trader TCG: all fetch strategies failed:", flush=True)
        for error in fetch_errors:
            print(f"- {error}", flush=True)
    print(f"Toad Trader TCG: {len(products)} products total", flush=True)
    return products


def match_toad(missing: set[str], products: list[dict]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for product in products:
        permalink = str(product.get("permalink") or "").lower()
        category_names = " ".join(woo_category_names(product)).lower()
        if "one-piece" not in permalink and "one piece" not in category_names:
            continue
        search_text = " ".join(
            str(product.get(key) or "")
            for key in ["sku", "name", "description", "short_description", "permalink"]
        )
        card_number = normalize_card_number(search_text)
        rarity = category_rarity(product)
        if not card_number:
            card_number, inferred_rarity = resolve_card_info_from_image(product, card_number="", rarity=rarity)
            if inferred_rarity and not rarity:
                rarity = inferred_rarity
        if not card_number or card_number not in missing:
            continue
        if not product.get("is_in_stock") or not product.get("is_purchasable"):
            continue

        stock = clean_text((product.get("stock_availability") or {}).get("text"))
        images = product.get("images") or []
        matches.append(
            {
                "store": "Toad Trader TCG",
                "card_number": card_number,
                "title": clean_text(product.get("name")),
                "set_name": category_set_name(product),
                "rarity": rarity,
                "condition": "",
                "stock": stock,
                "price": woo_price(product),
                "available_variants": stock,
                "url": product.get("permalink") or TOAD_COLLECTION_URL,
                "image_url": str(images[0].get("src") or "") if images else "",
            }
        )
    return matches


def run_toad() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_toad_products()
    matches = sorted_matches(match_toad(missing, products))
    save_image_match_cache()
    update_store_in_combined_json("Toad Trader TCG", matches)
    print_store_summary("Toad Trader TCG", missing, products, matches)
    print_found_listings("Toad Trader TCG", matches)
    return matches


def _parse_geek_haven_page(html: str) -> list[dict]:
    """Parse product JSON blobs from a BobShop seller page.

    BobShop embeds each product as a JSON object inside
    <script type="application/json"> inside <product-card> elements.
    Only Bandai-branded products are returned — the seller carries One Piece
    first and then VTES/Jyhad (no Brand attribute) later.
    """
    products: list[dict] = []
    for match in re.finditer(r'<script\s+type="application/json">\s*(.*?)\s*</script>', html, re.S):
        try:
            data = json.loads(match.group(1))
        except Exception:
            continue
        if "title" not in data or "amount" not in data:
            continue
        if data.get("status") != "OPEN":
            continue
        attrs = {a.get("name", ""): a.get("values", []) for a in data.get("productAttributes", [])}
        brand = (attrs.get("Brand") or [""])[0]
        if brand != "Bandai":
            continue
        title = clean_text(str(data.get("title") or ""))
        price_rand = float(data.get("amount") or 0)
        url = str(data.get("url") or "")
        images = data.get("images") or []
        image_url = str(images[0].get("image") or "") if images else ""
        products.append(
            {
                "name": title,
                "permalink": url,
                "sku": "",
                "description": "",
                "short_description": "",
                "is_in_stock": True,
                "is_purchasable": True,
                "stock_availability": {"text": ""},
                "prices": {"price": str(int(round(price_rand * 100))), "currency_minor_unit": 2},
                "images": [{"src": image_url}] if image_url else [],
                "categories": [{"name": "One Piece TCG"}],
            }
        )
    return products


def fetch_geek_haven_products() -> list[dict]:
    """Fetch One Piece listings from GeekHaven on BobShop.

    GeekHaven lists One Piece (Bandai) cards first, then switches to VTES.
    Scraping stops as soon as a page returns no Bandai products.
    Note: most listings don't include the card number in the title, so only
    products whose title contains e.g. '(OP09-005)' can be matched.
    """
    products: list[dict] = []
    for page in range(1, 200):
        print(f"GeekHaven: fetching page {page}...", flush=True)
        try:
            html = fetch_text(GEEK_HAVEN_PAGE_URL.format(page=page))
        except urllib.error.HTTPError as error:
            if error.code == 404:
                break
            raise
        page_products = _parse_geek_haven_page(html)
        print(f"GeekHaven: page {page} -> {len(page_products)} Bandai products", flush=True)
        if not page_products:
            print("GeekHaven: no Bandai products on this page — stopping (One Piece section ended).", flush=True)
            break
        products.extend(page_products)
    print(f"GeekHaven: {len(products)} products total", flush=True)
    return products


def _title_lookup_key(title: str) -> str:
    """Normalise a product title to a stable lookup key."""
    return re.sub(r"\s+", " ", title.strip()).lower()


def build_knightly_title_index(knightly_products: list[dict] | None = None) -> dict[str, str]:
    """Build a {normalised_title -> card_number} index from Knightly Gaming products.

    Knightly Gaming carries a near-complete One Piece card catalogue and uses
    the same title format as other stores (e.g. "Sengoku [Starter Deck: Black
    Smoker]"), so it can be used to look up card numbers for stores that omit
    them from their listings.

    If knightly_products is provided (already fetched), no extra network
    requests are made.
    """
    if knightly_products is None:
        print("Knightly index: fetching products...", flush=True)
        knightly_products = fetch_knightly_products()
    index: dict[str, str] = {}
    for product in knightly_products:
        body = product.get("body_html") or ""
        card_number = normalize_card_number(body_field(body, "Card Number"))
        if not card_number:
            continue
        title = clean_text(product.get("title") or "")
        if title:
            index[_title_lookup_key(title)] = card_number
    print(f"Knightly index: {len(index)} titled entries", flush=True)
    return index


def _knightly_search_card_number(title: str) -> str:
    """Query Knightly Gaming's predictive search API for a single title.

    Returns the card number if the top result matches the title exactly,
    otherwise returns "".
    """
    query = urllib.parse.quote(title)
    url = (
        f"https://www.knightlygaming.co.za/search/suggest.json"
        f"?q={query}&resources[type]=product&resources[limit]=1"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read())
    except Exception:
        return ""
    products = data.get("resources", {}).get("results", {}).get("products", [])
    if not products:
        return ""
    result = products[0]
    # Guard against fuzzy-matched wrong card
    if _title_lookup_key(str(result.get("title") or "")) != _title_lookup_key(title):
        return ""
    body = str(result.get("body") or "")
    return normalize_card_number(body_field(body, "Card Number")) or ""


def enrich_title_index_via_search(
    title_index: dict[str, str],
    titles: list[str],
    delay: float = 0.05,
) -> dict[str, str]:
    """Search Knightly Gaming for titles not already in title_index.

    Makes one API request per title, with a small delay to avoid rate-limiting.
    Returns a new dict merging the original index with newly resolved entries.
    """
    unresolved = [t for t in titles if _title_lookup_key(t) not in title_index]
    if not unresolved:
        return title_index
    print(f"Knightly search: resolving {len(unresolved)} unresolved titles...", flush=True)
    extra: dict[str, str] = {}
    for i, title in enumerate(unresolved):
        if i and i % 50 == 0:
            print(f"Knightly search: {i}/{len(unresolved)} done", flush=True)
        cn = _knightly_search_card_number(title)
        if cn:
            extra[_title_lookup_key(title)] = cn
        if delay and i < len(unresolved) - 1:
            time.sleep(delay)
    print(f"Knightly search: resolved {len(extra)} of {len(unresolved)} via search", flush=True)
    return {**title_index, **extra}


def match_geek_haven(
    missing: set[str],
    products: list[dict],
    ocr_cache: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    """Match GeekHaven products against missing card numbers.

    Card numbers are extracted from the product title when present (e.g.
    '(OP09-005)'). For titles without a card number, OCR is used on the card
    image's bottom-right area. OCR detections are cached and reused across runs.
    """
    matches: list[dict[str, object]] = []
    cache = ocr_cache or {}
    ocr_attempts = 0
    ocr_hits = 0
    cache_hits = 0
    total_products = len(products)
    unresolved_candidates = 0
    for product in products:
        if not normalize_card_number(str(product.get("name") or "")):
            unresolved_candidates += 1
    print(
        f"GeekHaven image match: starting detection for {unresolved_candidates} unresolved title(s) out of {total_products} product(s)",
        flush=True,
    )
    for product in products:
        name = str(product.get("name") or "")
        card_number = normalize_card_number(name)
        rarity = ""
        images = product.get("images") or []
        image_url = str(images[0].get("src") or "") if images else ""

        if not card_number:
            cache_key = _geek_cache_key(product)
            cached = cache.get(cache_key) or {}
            cached_image = str(cached.get("image_url") or "")
            cached_card = str(cached.get("card_number") or "")
            cached_rarity = str(cached.get("rarity") or "")
            if cached_card and (not image_url or not cached_image or cached_image == image_url):
                card_number = cached_card
                rarity = cached_rarity
                cache_hits += 1
                if cache_hits <= 10 or cache_hits % 50 == 0:
                    print(
                        f"GeekHaven image match: cache hit {cache_hits} -> {name[:80]} | {card_number}",
                        flush=True,
                    )
            else:
                ocr_attempts += 1
                detected_card, detected_rarity = resolve_card_info_from_image(product)
                if detected_card:
                    ocr_hits += 1
                    card_number = detected_card
                    rarity = detected_rarity
                    print(
                        f"GeekHaven image match: hit {ocr_hits}/{ocr_attempts} -> {name[:80]} | {card_number} | {rarity or 'rarity-unknown'}",
                        flush=True,
                    )
                elif ocr_attempts <= 10 or ocr_attempts % 25 == 0:
                    print(
                        f"GeekHaven image match: miss {ocr_attempts} -> {name[:80]}",
                        flush=True,
                    )
                cache[cache_key] = {
                    "card_number": card_number,
                    "rarity": rarity,
                    "image_url": image_url,
                    "updated_at": _now_iso(),
                }

        if not card_number or card_number not in missing:
            continue
        matches.append(
            {
                "store": "GeekHaven",
                "card_number": card_number,
                "title": name,
                "set_name": "",
                "rarity": rarity,
                "condition": "Second Hand",
                "stock": "In stock",
                "price": woo_price(product),
                "available_variants": "",
                "url": product.get("permalink") or GEEK_HAVEN_COLLECTION_URL,
                "image_url": str(images[0].get("src") or "") if images else "",
            }
        )
    if ocr_attempts:
        print(f"GeekHaven image match: {ocr_hits}/{ocr_attempts} titles resolved from image hashes", flush=True)
    print(f"GeekHaven image match: reused {cache_hits} cached detection(s)", flush=True)
    return matches


def run_geek_haven() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    ocr_cache = seed_geek_cache_from_previous_matches(load_geek_haven_ocr_cache())
    products = fetch_geek_haven_products()
    matches = sorted_matches(match_geek_haven(missing, products, ocr_cache=ocr_cache))
    save_geek_haven_ocr_cache(ocr_cache)
    save_image_match_cache()
    update_store_in_combined_json("GeekHaven", matches)
    print_store_summary("GeekHaven", missing, products, matches)
    print_found_listings("GeekHaven", matches)
    return matches


def run_all() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    failures: list[str] = []

    def scrape_store(
        store: str,
        fetcher,
        matcher,
    ) -> tuple[list[dict], list[dict[str, object]]]:
        try:
            products = fetcher()
            matches = sorted_matches(matcher(missing, products))
        except Exception as error:
            failures.append(f"{store}: {error}")
            print(f"{store} scrape failed: {error}", file=sys.stderr)
            return [], []
        return products, matches

    knightly_products, knightly_matches = scrape_store(
        "Knightly Gaming",
        fetch_knightly_products,
        match_knightly,
    )
    big_bang_products, big_bang_matches = scrape_store(
        "Big Bang Shop",
        fetch_big_bang_products,
        match_big_bang,
    )
    marvellous_products, marvellous_matches = scrape_store(
        "Marvellous Hobbies",
        fetch_marvellous_products,
        match_marvellous,
    )
    tanuki_products, tanuki_matches = scrape_store(
        "Tanuki Trader",
        fetch_tanuki_products,
        match_tanuki,
    )
    toad_products, toad_matches = scrape_store(
        "Toad Trader TCG",
        fetch_toad_products,
        match_toad,
    )
    geek_ocr_cache = seed_geek_cache_from_previous_matches(load_geek_haven_ocr_cache())
    geek_haven_products, geek_haven_matches = scrape_store(
        "GeekHaven",
        fetch_geek_haven_products,
        lambda missing_set, prods: match_geek_haven(missing_set, prods, ocr_cache=geek_ocr_cache),
    )
    save_geek_haven_ocr_cache(geek_ocr_cache)
    save_image_match_cache()

    combined = sorted_matches(
        knightly_matches + big_bang_matches + marvellous_matches + tanuki_matches + toad_matches + geek_haven_matches
    )
    write_combined_json(combined)

    print(f"Missing card numbers in spreadsheet: {len(missing)}")
    print(f"Knightly products fetched: {len(knightly_products)}")
    print(f"Knightly available missing listings: {len(knightly_matches)}")
    print(f"Big Bang products fetched: {len(big_bang_products)}")
    print(f"Big Bang available missing listings: {len(big_bang_matches)}")
    print(f"Marvellous products fetched: {len(marvellous_products)}")
    print(f"Marvellous available missing listings: {len(marvellous_matches)}")
    print(f"Tanuki products fetched: {len(tanuki_products)}")
    print(f"Tanuki available missing listings: {len(tanuki_matches)}")
    print(f"Toad Trader products fetched: {len(toad_products)}")
    print(f"Toad Trader available missing listings: {len(toad_matches)}")
    print(f"GeekHaven products fetched: {len(geek_haven_products)}")
    print(f"GeekHaven available missing listings: {len(geek_haven_matches)}")
    if failures:
        print("Store scrape failures:")
        for failure in failures:
            print(f"- {failure}")
    print_match_summary("Combined", combined)
    print_found_listings("Combined", combined)
    return combined


def print_store_summary(
    store: str,
    missing: set[str],
    products: list[dict],
    matches: list[dict[str, object]],
) -> None:
    print(f"Missing card numbers in spreadsheet: {len(missing)}")
    print(f"{store} products fetched: {len(products)}")
    print_match_summary(store, matches)


def print_match_summary(store: str, matches: list[dict[str, object]]) -> None:
    print(f"{store} available missing listings: {len(matches)}")
    print(f"{store} distinct missing card numbers available: {len({m['card_number'] for m in matches})}")
    print(f"{store} listing total: R {sum(float(m['price']) for m in matches):.2f}")
