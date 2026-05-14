from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from one_piece_missing import load_sheet_rows, resolve_workbook_path

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "docs" / "data" / "one_piece"
SHEET_NAME = "Overview"
SUMMARY_ROWS = 5  # Total, Common, Rare, Super Rare, Leader

RARITY_MAP = {"1": "Common", "2": "Rare", "3": "Super Rare", "4": "Leader"}


def normalize_set_code(header: str) -> str | None:
    cleaned = header.strip().upper()
    if cleaned == "P":
        return "P"
    match = re.match(r"^(OP|ST|EB|PRB)-?(\d+)$", header.strip(), re.IGNORECASE)
    if not match:
        return None
    return f"{match.group(1).upper()}{int(match.group(2)):02d}"


def scrape_collection() -> dict:
    print("Loading workbook...", flush=True)
    workbook = resolve_workbook_path()
    print(f"Reading sheet '{SHEET_NAME}'...", flush=True)
    rows = load_sheet_rows(workbook, SHEET_NAME)
    if not rows:
        return {"sets": {}}

    header_row = rows[0]
    col_to_set: dict[int, str] = {}
    for col_num, value in header_row.items():
        set_code = normalize_set_code(value)
        if set_code:
            col_to_set[col_num] = set_code

    print(f"Found {len(col_to_set)} set columns: {', '.join(sorted(col_to_set.values()))}", flush=True)

    def to_int(value: str) -> int | None:
        try:
            return int(float(value.strip()))
        except (ValueError, TypeError):
            return None

    def parse_fraction(value: str) -> tuple[int, int]:
        """Parse 'x/y' → (x, y). Returns (0, 0) if not parseable."""
        m = re.match(r"^(\d+)/(\d+)$", value.strip())
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    # Parse per-rarity totals from summary rows (rows 1-5)
    # rows[1]=Total, rows[2]=Common, rows[3]=Rare, rows[4]=Super Rare, rows[5]=Leader
    SUMMARY_RARITY_ROWS = [
        (1, None),           # Total
        (2, "Common"),
        (3, "Rare"),
        (4, "Super Rare"),
        (5, "Leader"),
    ]
    set_totals: dict[str, int] = {}
    set_rarity_totals: dict[str, dict[str, int]] = {code: {} for code in col_to_set.values()}

    for row_idx, rarity_name in SUMMARY_RARITY_ROWS:
        if row_idx >= len(rows):
            continue
        summary_row = rows[row_idx]
        for col_num, set_code in col_to_set.items():
            owned, total = parse_fraction(summary_row.get(col_num, ""))
            if rarity_name is None:
                # Total row — use as fallback for set_totals
                if total > 0 and set_code not in set_totals:
                    set_totals[set_code] = total
            elif rarity_name and total > 0:
                set_rarity_totals[set_code][rarity_name] = total

    # skip header row + 5 summary rows
    card_rows = rows[1 + SUMMARY_ROWS:]
    sets: dict[str, list[dict]] = {code: [] for code in col_to_set.values()}

    for row in card_rows:
        card_num = to_int(row.get(1, ""))
        if card_num is None or card_num < 1:
            continue

        for col_num, set_code in col_to_set.items():
            raw = row.get(col_num, "").strip()

            # "-" marks the row after the last card — overrides summary total with exact count
            if raw == "-":
                set_totals[set_code] = card_num - 1
                continue

            rarity_int = to_int(raw)
            rarity = RARITY_MAP.get(str(rarity_int)) if rarity_int is not None else None
            if rarity:
                sets[set_code].append({
                    "card_number": f"{set_code}-{card_num:03d}",
                    "rarity": rarity,
                })

    result: dict[str, dict] = {}
    for set_code, cards in sets.items():
        total_cards = set_totals.get(set_code, 0)
        if not cards and not total_cards:
            continue
        owned_set = {card["card_number"] for card in cards}
        owned_by_number = {card["card_number"]: card for card in cards}
        all_cards: list[dict] = []
        if total_cards > 0:
            for i in range(1, total_cards + 1):
                card_number = f"{set_code}-{i:03d}"
                owned_card = owned_by_number.get(card_number)
                all_cards.append(
                    {
                        "card_number": card_number,
                        "owned": card_number in owned_set,
                        "rarity": owned_card.get("rarity", "") if owned_card else "",
                        "image_url": "",
                        "image_hash": "",
                        "alternate_arts": [],
                        "alternate_art_checked": False,
                    }
                )
        by_rarity: dict[str, int] = {}
        for card in cards:
            by_rarity[card["rarity"]] = by_rarity.get(card["rarity"], 0) + 1
        result[set_code] = {
            "owned": sorted(cards, key=lambda c: c["card_number"]),
            "cards": all_cards,
            "total_owned": len(cards),
            "total_cards": total_cards,
            "by_rarity": by_rarity,
            "total_by_rarity": set_rarity_totals.get(set_code, {}),
        }
        print(f"  {set_code}: {len(cards)}/{total_cards} cards owned", flush=True)

    print(f"Total: {sum(v['total_owned'] for v in result.values())} cards across {len(result)} sets", flush=True)
    return {"sets": result, "_listing_match_cache": {}}


def main() -> int:
    output_file = OUTPUT_DIR / "collection.json"
    existing: dict = {}
    if output_file.exists():
        try:
            existing = json.loads(output_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    data = scrape_collection()
    existing_sets = existing.get("sets", {}) if isinstance(existing, dict) else {}
    for set_code, set_payload in data.get("sets", {}).items():
        existing_set = existing_sets.get(set_code, {}) if isinstance(existing_sets, dict) else {}
        existing_cards = existing_set.get("cards", []) if isinstance(existing_set, dict) else []
        hash_by_number = {
            str(card.get("card_number") or ""): {
                "image_url": str(card.get("image_url") or ""),
                "image_hash": str(card.get("image_hash") or ""),
                "rarity": str(card.get("rarity") or ""),
                "alternate_arts": card.get("alternate_arts") if isinstance(card.get("alternate_arts"), list) else [],
                "alternate_art_checked": bool(card.get("alternate_art_checked")),
            }
            for card in existing_cards
            if isinstance(card, dict)
        }
        for card in set_payload.get("cards", []):
            card_number = str(card.get("card_number") or "")
            existing_row = hash_by_number.get(card_number) or {}
            if existing_row.get("image_url"):
                card["image_url"] = existing_row["image_url"]
            if existing_row.get("image_hash"):
                card["image_hash"] = existing_row["image_hash"]
            existing_alt_rows = existing_row.get("alternate_arts")
            if isinstance(existing_alt_rows, list):
                cleaned_alt_rows = []
                for alt in existing_alt_rows:
                    if not isinstance(alt, dict):
                        continue
                    image_url = str(alt.get("image_url") or "").strip()
                    if not image_url:
                        continue
                    cleaned_alt_rows.append(
                        {
                            "image_url": image_url,
                            "label": str(alt.get("label") or "").strip(),
                            "name": str(alt.get("name") or "").strip(),
                        }
                    )
                card["alternate_arts"] = cleaned_alt_rows
            card["alternate_art_checked"] = bool(existing_row.get("alternate_art_checked"))
            if not card.get("rarity") and existing_row.get("rarity"):
                card["rarity"] = existing_row["rarity"]

    data["_listing_match_cache"] = existing.get("_listing_match_cache", {}) if isinstance(existing, dict) else {}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output_file}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
