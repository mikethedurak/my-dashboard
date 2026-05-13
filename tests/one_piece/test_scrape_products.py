from __future__ import annotations

import sys
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_DIR))

from services.one_piece.scrape_products import fetch_text, parse_products, sort_products


def main() -> int:
    html_text = fetch_text("https://en.onepiece-cardgame.com/products/")
    items = sort_products(parse_products(html_text))
    for item in items:
        name = str(item.get("title") or "").strip()
        release_date = str(item.get("release_date") or "").strip()
        date_text = str(item.get("release_date_text") or "").strip()
        product_type = str(item.get("category_label") or "").strip() or str(item.get("category") or "").strip()
        date_value = release_date or date_text or "Date TBA"
        print(f"{name} | {date_value} | {product_type}")
    print(f"Total products found: {len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
