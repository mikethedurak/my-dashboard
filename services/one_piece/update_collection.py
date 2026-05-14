from __future__ import annotations

import argparse
import io
import json
import re
import urllib.request
from pathlib import Path

from PIL import Image

from scrape_collection import scrape_collection


REPO_DIR = Path(__file__).resolve().parents[2]
COLLECTION_PATH = REPO_DIR / "docs" / "data" / "one_piece" / "collection.json"
LIMITLESS_CARD_URL = "https://onepiece.limitlesstcg.com/cards/{card_number}"
LIMITLESS_CARD_API_URL = "https://onepiece.limitlesstcg.com/api/cards/{card_number}"

DESIRED_FIELDS = [
    "rarity",
    "card_type",
    "name",
    "color",
    "attribute",
    "description",
    "family",
    "life",
    "power",
    "image_url",
    "image_hash",
]

RARITY_CODE_TO_NAME = {
    "C": "Common",
    "UC": "Uncommon",
    "R": "Rare",
    "SR": "Super Rare",
    "SEC": "Secret Rare",
    "L": "Leader",
    "P": "Promo",
}


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(text.split()).strip()


def tooltip_value(html: str, label: str) -> str:
    pattern = re.compile(rf'data-tooltip="{re.escape(label)}"\s*>\s*(.*?)\s*</span>', re.I | re.S)
    match = pattern.search(html)
    return strip_html(match.group(1)) if match else ""


def card_text_sections(html: str) -> list[str]:
    return [strip_html(m.group(1)) for m in re.finditer(r'<div class="card-text-section[^"]*">\s*(.*?)\s*</div>', html, re.I | re.S)]


def collection_card_image_url(card_number: str) -> str:
    set_code = str(card_number or "").split("-")[0]
    return f"https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/one-piece/{set_code}/{card_number}_EN.webp"


def avg_hash(image_bytes: bytes, hash_size: int = 16) -> str:
    img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    mean = sum(pixels) / len(pixels)
    bits = ["1" if p >= mean else "0" for p in pixels]
    hex_len = (hash_size * hash_size) // 4
    return f"{int(''.join(bits), 2):0{hex_len}x}"


def fetch_card_metadata(card_number: str) -> dict[str, str]:
    # Prefer structured API fields.
    api_url = LIMITLESS_CARD_API_URL.format(card_number=card_number)
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    rarity_code = str(data.get("rarity") or "").strip().upper()
    rarity = RARITY_CODE_TO_NAME.get(rarity_code, rarity_code)
    return {
        "name": str(data.get("name") or "").strip(),
        "rarity": rarity,
        "card_type": str(data.get("category") or "").strip().title(),
        "color": str(data.get("color") or "").strip().title(),
        "attribute": str(data.get("attribute") or "").strip().title(),
        "description": str(data.get("effect") or "").strip(),
        "family": str(data.get("type") or "").strip(),
        "life": "" if data.get("life") is None else str(data.get("life")),
        "power": "" if data.get("power") is None else str(data.get("power")),
    }


def load_existing() -> dict:
    if not COLLECTION_PATH.exists():
        return {}
    try:
        return json.loads(COLLECTION_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save(payload: dict) -> None:
    COLLECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    COLLECTION_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def iter_cards(payload: dict) -> list[dict]:
    out: list[dict] = []
    for set_payload in payload.get("sets", {}).values():
        if not isinstance(set_payload, dict):
            continue
        cards = set_payload.get("cards", [])
        if isinstance(cards, list):
            out.extend([row for row in cards if isinstance(row, dict)])
    return out


def has_missing_fields(card: dict) -> bool:
    return any(not str(card.get(field) or "").strip() for field in DESIRED_FIELDS)


def merge_preserving_existing(new_payload: dict, old_payload: dict) -> dict:
    old_sets = old_payload.get("sets", {}) if isinstance(old_payload, dict) else {}
    for set_code, set_payload in new_payload.get("sets", {}).items():
        if not isinstance(set_payload, dict):
            continue
        old_set = old_sets.get(set_code, {}) if isinstance(old_sets, dict) else {}
        old_cards = old_set.get("cards", []) if isinstance(old_set, dict) else []
        old_by_number = {
            str(row.get("card_number") or "").strip().upper(): row
            for row in old_cards
            if isinstance(row, dict)
        }
        for card in set_payload.get("cards", []):
            if not isinstance(card, dict):
                continue
            card_number = str(card.get("card_number") or "").strip().upper()
            prev = old_by_number.get(card_number) or {}
            for field in ["name", "color", "attribute", "description", "family", "life", "power", "image_url", "image_hash"]:
                if not str(card.get(field) or "").strip() and str(prev.get(field) or "").strip():
                    card[field] = prev[field]
            if not str(card.get("rarity") or "").strip() and str(prev.get("rarity") or "").strip():
                card["rarity"] = prev["rarity"]
    new_payload["_listing_match_cache"] = old_payload.get("_listing_match_cache", {}) if isinstance(old_payload, dict) else {}
    return new_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Update collection.json from workbook + card database metadata.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max cards to enrich for quick tests.")
    parser.add_argument("--checkpoint-every", type=int, default=100, help="Save every N enriched cards.")
    parser.add_argument("--hard", action="store_true", help="Re-enrich all cards even if fields exist.")
    args = parser.parse_args()

    print("Updating ownership from workbook (Overview)...", flush=True)
    old_payload = load_existing()
    base_payload = scrape_collection()
    payload = merge_preserving_existing(base_payload, old_payload)
    save(payload)

    cards = iter_cards(payload)
    targets = cards if args.hard else [c for c in cards if has_missing_fields(c)]
    if args.limit > 0:
        targets = targets[: args.limit]
    print(f"Cards to enrich: {len(targets)}", flush=True)

    updated = 0
    failed = 0
    for idx, card in enumerate(targets, start=1):
        card_number = str(card.get("card_number") or "").strip().upper()
        if not card_number:
            continue
        try:
            meta = fetch_card_metadata(card_number)
            image_url = str(card.get("image_url") or "").strip() or collection_card_image_url(card_number)
            image_hash = str(card.get("image_hash") or "").strip()
            if not image_hash:
                image_hash = avg_hash(fetch_bytes(image_url))
            card["image_url"] = image_url
            card["image_hash"] = image_hash
            for field in ["rarity", "card_type", "name", "color", "attribute", "description", "family", "life", "power"]:
                value = str(meta.get(field) or "").strip()
                if value:
                    card[field] = value
            updated += 1
            if updated <= 10 or updated % 50 == 0:
                print(f"[{idx}/{len(targets)}] updated {card_number}", flush=True)
            if args.checkpoint_every > 0 and updated % args.checkpoint_every == 0:
                save(payload)
                print(f"[checkpoint] saved after {updated} cards", flush=True)
        except Exception as error:  # noqa: BLE001
            failed += 1
            if failed <= 10 or failed % 50 == 0:
                print(f"[{idx}/{len(targets)}] failed {card_number}: {error}", flush=True)

    save(payload)
    remaining = sum(1 for c in iter_cards(payload) if has_missing_fields(c))
    print(f"Done. Updated: {updated}, failed: {failed}, remaining incomplete: {remaining}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
