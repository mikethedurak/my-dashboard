from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from services.common.scrape_metadata import run_and_record


REPO_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_DIR / "docs" / "data" / "one_piece"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run One Piece missing-card scrapes.")
    parser.add_argument("--source", choices=["all", "bigbang", "collectiverse", "geekhaven", "knightly", "marvellous", "toad", "tanuki"], default="all", help="Which store source to scrape.")
    parser.add_argument("--hard", action="store_true", help="Remove selected report outputs before scraping.")
    parser.add_argument("--limit", type=int, default=0, help="Accepted for wrapper consistency; store scraping is not item-limited.")
    parser.add_argument("--max-pages", type=int, default=0, help="Accepted for wrapper consistency; store pagination is source-defined.")
    args = parser.parse_args()

    if args.hard:
        patterns = ["*_missing_available.csv", "new_missing_cards.json"] if args.source == "all" else [f"*{args.source}*_missing_available.csv"]
        for pattern in patterns:
            for path in DATA_DIR.glob(pattern):
                print(f"Removing stale One Piece output: {path}", flush=True)
                path.unlink()

    update_command = [sys.executable, "services/one_piece/update_collection.py"]
    if args.hard:
        update_command.append("--hard")
    print(f"Updating One Piece collection: {' '.join(update_command)}", flush=True)
    run_and_record(
        update_command,
        cwd=REPO_DIR,
        outputs=[DATA_DIR / "collection.json"],
        module="one-piece",
        source="collection",
    )

    command = [sys.executable, "services/one_piece/find_missing_cards.py", args.source]
    print(f"Running One Piece scrape: {' '.join(command)}", flush=True)
    run_and_record(
        command,
        cwd=REPO_DIR,
        outputs=[DATA_DIR / "missing_cards.json"],
        module="one-piece",
        source=args.source,
    )
    product_command = [sys.executable, "services/one_piece/scrape_products.py", "--pages", "1"]
    if args.hard:
        product_command.append("--hard")
    print(f"Running One Piece products scrape: {' '.join(product_command)}", flush=True)
    run_and_record(
        product_command,
        cwd=REPO_DIR,
        outputs=[DATA_DIR / "products.json"],
        module="one-piece",
        source="products",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
