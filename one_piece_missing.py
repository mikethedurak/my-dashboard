from __future__ import annotations

import csv
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


WORKBOOK = Path("One Piece Cards.xlsx")

KNIGHTLY_COLLECTION_URL = "https://www.knightlygaming.co.za/collections/one-piece-singles"
KNIGHTLY_PRODUCTS_URL = KNIGHTLY_COLLECTION_URL + "/products.json?limit=250&page={page}"

MARVELLOUS_COLLECTION_URL = "https://marvelloushobbies.com/one-piece-singles/"
MARVELLOUS_PRODUCTS_URL = (
    "https://marvelloushobbies.com/wp-json/wc/store/v1/products"
    "?per_page=100&page={page}&category=36"
)

TANUKI_COLLECTION_URL = "https://tanukitrader.co.za/"
TANUKI_PRODUCTS_URL = (
    "https://tanukitrader.co.za/wp-json/wc/store/v1/products"
    "?per_page=100&page={page}"
)

BIG_BANG_COLLECTION_URL = "https://bigbangshop.co.za/collections/one-piece-single-cards"
BIG_BANG_PRODUCTS_URL = BIG_BANG_COLLECTION_URL + "/products.json?limit=250&page={page}"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

TAG_RE = re.compile(r"<[^>]+>")

RARITY_NAMES = [
    "Super Rare",
    "Secret Rare",
    "Uncommon",
    "Common",
    "Leader",
    "Rare",
    "DON!!",
]


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
    missing: set[str] = set()
    for row in load_sheet_rows(workbook, "Missing"):
        for value in row.values():
            card_number = normalize_card_number(value)
            if card_number:
                missing.add(card_number)
    return missing


def fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


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


def write_reports(prefix: str, heading: str, matches: list[dict[str, object]]) -> None:
    matches = sorted_matches(matches)
    fieldnames = [
        "card_number",
        "price",
        "title",
        "rarity",
        "store",
        "set_name",
        "condition",
        "stock",
        "available_variants",
        "url",
    ]

    with Path(f"{prefix}.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matches)

    with Path(f"{prefix}.md").open("w", encoding="utf-8") as file:
        file.write(f"# {heading}\n\n")
        file.write(
            f"Found {len(matches)} purchasable listings across "
            f"{len({match['card_number'] for match in matches})} missing card numbers.\n\n"
        )
        file.write("| Card | Price | Name | Rarity | Store | Stock | Link |\n")
        file.write("|---|---:|---|---|---|---|---|\n")
        for match in matches:
            title = str(match["title"]).replace("|", "/")
            rarity = str(match["rarity"]).replace("|", "/")
            file.write(
                f"| {match['card_number']} | R {float(match['price']):.2f} | "
                f"{title} | {rarity} | {match['store']} | {match['stock']} | "
                f"[open]({match['url']}) |\n"
            )


def fetch_knightly_products() -> list[dict]:
    products: list[dict] = []
    for page in range(1, 50):
        data = fetch_json(KNIGHTLY_PRODUCTS_URL.format(page=page))
        page_products = data.get("products", [])
        if not page_products:
            break
        products.extend(page_products)
    return products


def match_knightly(missing: set[str], products: list[dict]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for product in products:
        body = product.get("body_html") or ""
        card_number = normalize_card_number(body_field(body, "Card Number"))
        if not card_number or card_number not in missing:
            continue

        available_variants = [
            variant for variant in product.get("variants", []) if variant.get("available")
        ]
        if not available_variants:
            continue

        cheapest = min(available_variants, key=lambda item: float(item.get("price") or 0))
        matches.append(
            {
                "store": "Knightly Gaming",
                "card_number": card_number,
                "title": product.get("title") or "",
                "set_name": body_field(body, "Set Name"),
                "rarity": body_field(body, "Rarity"),
                "condition": cheapest.get("title") or "",
                "stock": "In stock",
                "price": float(cheapest.get("price") or 0),
                "available_variants": "; ".join(
                    f"{variant.get('title')} R{float(variant.get('price') or 0):.2f}"
                    for variant in available_variants
                ),
                "url": f"{KNIGHTLY_COLLECTION_URL}/products/{product.get('handle', '')}",
            }
        )
    return matches


def run_knightly() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_knightly_products()
    matches = sorted_matches(match_knightly(missing, products))
    write_reports("knightly_missing_available", "Knightly Gaming Missing Cards Available", matches)
    print_store_summary("Knightly Gaming", missing, products, matches)
    return matches


def fetch_big_bang_products() -> list[dict]:
    products: list[dict] = []
    for page in range(1, 50):
        data = fetch_json(BIG_BANG_PRODUCTS_URL.format(page=page))
        page_products = data.get("products", [])
        if not page_products:
            break
        products.extend(page_products)
    return products


def match_big_bang(missing: set[str], products: list[dict]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for product in products:
        body = product.get("body_html") or ""
        card_number = normalize_card_number(body_field(body, "Card Number"))
        if not card_number or card_number not in missing:
            continue

        available_variants = [
            variant for variant in product.get("variants", []) if variant.get("available")
        ]
        if not available_variants:
            continue

        cheapest = min(available_variants, key=lambda item: float(item.get("price") or 0))
        matches.append(
            {
                "store": "Big Bang Shop",
                "card_number": card_number,
                "title": product.get("title") or "",
                "set_name": body_field(body, "Set Name"),
                "rarity": body_field(body, "Rarity"),
                "condition": cheapest.get("title") or "",
                "stock": "In stock",
                "price": float(cheapest.get("price") or 0),
                "available_variants": "; ".join(
                    f"{variant.get('title')} R{float(variant.get('price') or 0):.2f}"
                    for variant in available_variants
                ),
                "url": f"{BIG_BANG_COLLECTION_URL}/products/{product.get('handle', '')}",
            }
        )
    return matches


def run_big_bang() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_big_bang_products()
    matches = sorted_matches(match_big_bang(missing, products))
    write_reports(
        "big_bang_missing_available",
        "Big Bang Shop Missing Cards Available",
        matches,
    )
    print_store_summary("Big Bang Shop", missing, products, matches)
    return matches


def fetch_marvellous_products() -> list[dict]:
    products: list[dict] = []
    for page in range(1, 100):
        page_products = fetch_json(MARVELLOUS_PRODUCTS_URL.format(page=page))
        if not page_products:
            break
        products.extend(page_products)
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
        search_text = " ".join(
            str(product.get(key) or "")
            for key in ["name", "sku", "description", "short_description", "permalink"]
        )
        card_number = normalize_card_number(search_text)
        if not card_number or card_number not in missing:
            continue
        if not product.get("is_in_stock") or not product.get("is_purchasable"):
            continue

        stock = clean_text((product.get("stock_availability") or {}).get("text"))
        matches.append(
            {
                "store": "Marvellous Hobbies",
                "card_number": card_number,
                "title": clean_text(product.get("name")),
                "set_name": "",
                "rarity": "",
                "condition": "",
                "stock": stock,
                "price": woo_price(product),
                "available_variants": stock,
                "url": product.get("permalink") or MARVELLOUS_COLLECTION_URL,
            }
        )
    return matches


def run_marvellous() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_marvellous_products()
    matches = sorted_matches(match_marvellous(missing, products))
    write_reports(
        "marvellous_missing_available",
        "Marvellous Hobbies Missing Cards Available",
        matches,
    )
    print_store_summary("Marvellous Hobbies", missing, products, matches)
    return matches


def fetch_tanuki_products() -> list[dict]:
    products: list[dict] = []
    for page in range(1, 100):
        page_products = fetch_json(TANUKI_PRODUCTS_URL.format(page=page))
        if not page_products:
            break
        products.extend(page_products)
    return products


def match_tanuki(missing: set[str], products: list[dict]) -> list[dict[str, object]]:
    matches: list[dict[str, object]] = []
    for product in products:
        search_text = " ".join(
            str(product.get(key) or "")
            for key in ["sku", "name", "description", "short_description", "permalink"]
        )
        card_number = normalize_card_number(search_text)
        if not card_number or card_number not in missing:
            continue
        if not product.get("is_in_stock") or not product.get("is_purchasable"):
            continue

        stock = clean_text((product.get("stock_availability") or {}).get("text"))
        matches.append(
            {
                "store": "Tanuki Trader",
                "card_number": card_number,
                "title": clean_text(product.get("name")),
                "set_name": category_set_name(product),
                "rarity": category_rarity(product),
                "condition": "",
                "stock": stock,
                "price": woo_price(product),
                "available_variants": stock,
                "url": product.get("permalink") or TANUKI_COLLECTION_URL,
            }
        )
    return matches


def run_tanuki() -> list[dict[str, object]]:
    missing = missing_card_numbers()
    products = fetch_tanuki_products()
    matches = sorted_matches(match_tanuki(missing, products))
    write_reports(
        "tanuki_missing_available",
        "Tanuki Trader Missing Cards Available",
        matches,
    )
    print_store_summary("Tanuki Trader", missing, products, matches)
    return matches


def run_all() -> list[dict[str, object]]:
    missing = missing_card_numbers()

    knightly_products = fetch_knightly_products()
    knightly_matches = sorted_matches(match_knightly(missing, knightly_products))
    write_reports(
        "knightly_missing_available",
        "Knightly Gaming Missing Cards Available",
        knightly_matches,
    )

    big_bang_products = fetch_big_bang_products()
    big_bang_matches = sorted_matches(match_big_bang(missing, big_bang_products))
    write_reports(
        "big_bang_missing_available",
        "Big Bang Shop Missing Cards Available",
        big_bang_matches,
    )

    marvellous_products = fetch_marvellous_products()
    marvellous_matches = sorted_matches(match_marvellous(missing, marvellous_products))
    write_reports(
        "marvellous_missing_available",
        "Marvellous Hobbies Missing Cards Available",
        marvellous_matches,
    )

    tanuki_products = fetch_tanuki_products()
    tanuki_matches = sorted_matches(match_tanuki(missing, tanuki_products))
    write_reports(
        "tanuki_missing_available",
        "Tanuki Trader Missing Cards Available",
        tanuki_matches,
    )

    combined = sorted_matches(
        knightly_matches + big_bang_matches + marvellous_matches + tanuki_matches
    )
    write_reports("all_stores_missing_available", "All Stores Missing Cards Available", combined)

    print(f"Missing card numbers in spreadsheet: {len(missing)}")
    print(f"Knightly products fetched: {len(knightly_products)}")
    print(f"Knightly available missing listings: {len(knightly_matches)}")
    print(f"Big Bang products fetched: {len(big_bang_products)}")
    print(f"Big Bang available missing listings: {len(big_bang_matches)}")
    print(f"Marvellous products fetched: {len(marvellous_products)}")
    print(f"Marvellous available missing listings: {len(marvellous_matches)}")
    print(f"Tanuki products fetched: {len(tanuki_products)}")
    print(f"Tanuki available missing listings: {len(tanuki_matches)}")
    print_match_summary("Combined", combined)
    print("Wrote knightly, big_bang, marvellous, tanuki, and all_stores reports as CSV and Markdown")
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
