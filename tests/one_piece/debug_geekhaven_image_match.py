from __future__ import annotations

import argparse
import io
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.append(str(Path(__file__).resolve().parents[2] / "services" / "one_piece"))
from one_piece_missing import (  # noqa: E402
    _parse_geek_haven_page,
    clean_text,
    fetch_text,
    GEEK_HAVEN_PAGE_URL,
)


REPO_DIR = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_DIR / ".cache" / "one_piece_ref_images"
COLLECTION_FILE = REPO_DIR / "docs" / "data" / "one_piece" / "collection.json"


def collection_card_image_url(card_number: str) -> str:
    set_code = str(card_number or "").split("-")[0]
    return f"https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/one-piece/{set_code}/{card_number}_EN.webp"


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def avg_hash(image_bytes: bytes, hash_size: int = 16) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    mean = sum(pixels) / len(pixels)
    bits = ["1" if p >= mean else "0" for p in pixels]
    hex_len = (hash_size * hash_size) // 4
    return f"{int(''.join(bits), 2):0{hex_len}x}"


def hamming_hex(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def load_collection_hashes() -> dict[str, dict]:
    if not COLLECTION_FILE.exists():
        return {}
    try:
        payload = json.loads(COLLECTION_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    sets = payload.get("sets", {})
    if not isinstance(sets, dict):
        return {}
    out: dict[str, dict] = {}
    for set_payload in sets.values():
        if not isinstance(set_payload, dict):
            continue
        for card in set_payload.get("cards", []):
            if not isinstance(card, dict):
                continue
            card_number = str(card.get("card_number") or "").strip().upper()
            image_hash = str(card.get("image_hash") or "").strip()
            if card_number and image_hash:
                out[card_number] = {
                    "hash": image_hash,
                    "rarity": str(card.get("rarity") or "").strip(),
                }
    return out


def fetch_geekhaven_page(page: int) -> list[dict]:
    print(f"[geekhaven] fetching page {page}...", flush=True)
    html = fetch_text(GEEK_HAVEN_PAGE_URL.format(page=page))
    products = _parse_geek_haven_page(html)
    print(f"[geekhaven] page {page} -> {len(products)} Bandai products", flush=True)
    return products


def ensure_ref_hash(card_number: str, cache: dict[str, str]) -> str:
    if card_number in cache and cache[card_number]:
        return cache[card_number]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    local_file = CACHE_DIR / f"{card_number}.img"
    if not local_file.exists():
        try:
            local_file.write_bytes(fetch_bytes(collection_card_image_url(card_number)))
        except Exception:
            return ""
    try:
        digest = avg_hash(local_file.read_bytes())
    except Exception:
        return ""
    cache[card_number] = digest
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description="Image-similarity debug for GeekHaven cards using collection image hashes.")
    parser.add_argument("--page", type=int, default=1, help="GeekHaven page number to scrape.")
    parser.add_argument("--card-index", type=int, default=0, help="Card index on the selected GeekHaven page.")
    parser.add_argument("--top", type=int, default=10, help="How many closest matches to print.")
    parser.add_argument("--max-candidates", type=int, default=0, help="Limit candidate hashes from collection file (0=all).")
    args = parser.parse_args()

    products = fetch_geekhaven_page(args.page)
    if not products:
        print("No GeekHaven cards found on this page.")
        return 0

    if args.card_index < 0 or args.card_index >= len(products):
        print(f"--card-index out of range. page_cards={len(products)}")
        return 2
    product = products[args.card_index]

    title = clean_text(product.get("name") or "")
    images = product.get("images") or []
    image_url = str(images[0].get("src") or "") if images else ""
    if not image_url:
        print("Selected product has no image URL.")
        return 1

    print("")
    print("=== GeekHaven Image Match Debug ===")
    print(f"page: {args.page}")
    print(f"card_index: {args.card_index}")
    print(f"title: {title}")
    print(f"url: {product.get('permalink') or ''}")
    print(f"image_url: {image_url}")

    target_hash = avg_hash(fetch_bytes(image_url))
    print(f"target_hash: {target_hash}")

    collection_hashes = load_collection_hashes()
    if not collection_hashes:
        print("No collection hashes found.")
        print("Run: python services/one_piece/update_collection.py")
        return 1

    candidates: list[tuple[str, str]] = []
    for card_number, row in collection_hashes.items():
        if not isinstance(row, dict):
            continue
        digest = str(row.get("hash") or "").strip()
        if digest:
            candidates.append((str(card_number), digest))
    candidates.sort(key=lambda item: item[0])
    if args.max_candidates > 0:
        candidates = candidates[: args.max_candidates]
    print(f"candidate_count: {len(candidates)}")

    cache: dict[str, str] = {}
    distances: list[tuple[int, str]] = []
    processed = 0
    for card_number, ref_hash in candidates:
        dist = hamming_hex(target_hash, ref_hash)
        distances.append((dist, card_number))
        processed += 1
        if processed % 100 == 0:
            print(f"[progress] compared {processed} candidates...", flush=True)
    if not distances:
        print("No reference hashes available to compare.")
        return 1

    distances.sort(key=lambda x: x[0])
    print("")
    print(f"=== Top {args.top} Closest Matches (lower distance = closer) ===")
    for rank, (dist, card_number) in enumerate(distances[: args.top], start=1):
        print(f"{rank}. {card_number}  distance={dist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
