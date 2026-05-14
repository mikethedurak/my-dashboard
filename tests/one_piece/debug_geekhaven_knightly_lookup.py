from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2] / "services" / "one_piece"))
from one_piece_missing import (  # noqa: E402
    GEEK_HAVEN_PAGE_URL,
    _parse_geek_haven_page,
    _title_lookup_key,
    body_field,
    build_knightly_title_index,
    clean_text,
    fetch_text,
    missing_card_numbers,
    normalize_card_number,
)


def fetch_geekhaven_products(max_pages: int = 0) -> list[dict]:
    products: list[dict] = []
    page = 1
    while True:
        if max_pages > 0 and page > max_pages:
            break
        print(f"[geekhaven] fetching page {page}...", flush=True)
        html = fetch_text(GEEK_HAVEN_PAGE_URL.format(page=page))
        page_products = _parse_geek_haven_page(html)
        print(f"[geekhaven] page {page} -> {len(page_products)} Bandai products", flush=True)
        if not page_products:
            break
        products.extend(page_products)
        page += 1
    print(f"[geekhaven] total products: {len(products)}", flush=True)
    return products


def knightly_suggest(title: str, limit: int = 5) -> list[dict]:
    query = urllib.parse.quote(title)
    url = (
        "https://www.knightlygaming.co.za/search/suggest.json"
        f"?q={query}&resources[type]=product&resources[limit]={limit}"
    )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    return payload.get("resources", {}).get("results", {}).get("products", [])


def unresolved_geekhaven_titles(products: list[dict], title_index: dict[str, str]) -> list[str]:
    unresolved: list[str] = []
    for product in products:
        title = clean_text(product.get("name") or "")
        if not title:
            continue
        card_number = normalize_card_number(title)
        if card_number:
            continue
        if _title_lookup_key(title) in title_index:
            continue
        unresolved.append(title)
    return unresolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Debug Knightly search results for unresolved GeekHaven card titles."
    )
    parser.add_argument("--title", default="", help="Specific GeekHaven card title to test.")
    parser.add_argument("--index", type=int, default=0, help="Index within unresolved titles when --title is not provided.")
    parser.add_argument("--max-pages", type=int, default=0, help="Limit GeekHaven pages to scan (0 = all).")
    parser.add_argument("--limit", type=int, default=5, help="How many Knightly suggest results to print.")
    args = parser.parse_args()

    title = args.title.strip()
    title_index = build_knightly_title_index()
    unresolved: list[str] = []

    if not title:
        products = fetch_geekhaven_products(max_pages=args.max_pages)
        unresolved = unresolved_geekhaven_titles(products, title_index)
        if not unresolved:
            print("No unresolved GeekHaven titles found.")
            return 0
        if args.index < 0 or args.index >= len(unresolved):
            print(f"--index out of range. unresolved={len(unresolved)}")
            return 2
        title = unresolved[args.index]

    missing = missing_card_numbers()
    direct = normalize_card_number(title) or ""
    from_index = title_index.get(_title_lookup_key(title), "")
    print("")
    print("=== GeekHaven Lookup Debug ===")
    print(f"title: {title}")
    print(f"direct_card_number_from_title: {direct or '<none>'}")
    print(f"card_number_from_knightly_title_index: {from_index or '<none>'}")
    if unresolved:
        print(f"unresolved_count: {len(unresolved)}")
        print(f"selected_unresolved_index: {args.index}")

    print("")
    print(f"=== Knightly Suggest Results (limit={args.limit}) ===")
    try:
        results = knightly_suggest(title, limit=args.limit)
    except Exception as error:  # noqa: BLE001
        print(f"Knightly suggest failed: {error}")
        return 1

    if not results:
        print("No search results.")
        return 0

    for idx, result in enumerate(results, start=1):
        result_title = clean_text(result.get("title") or "")
        result_key_match = _title_lookup_key(result_title) == _title_lookup_key(title)
        body = str(result.get("body") or "")
        card_number = normalize_card_number(body_field(body, "Card Number")) or ""
        card_missing = bool(card_number and card_number in missing)
        print(f"{idx}. title={result_title}")
        print(f"   exact_key_match={result_key_match}")
        print(f"   card_number_from_body={card_number or '<none>'}")
        print(f"   in_missing_sheet={card_missing}")
        print(f"   url=https://www.knightlygaming.co.za/products/{result.get('handle', '')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
