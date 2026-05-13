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

    # skip header row + 5 summary rows
    card_rows = rows[1 + SUMMARY_ROWS:]

    set_totals: dict[str, int] = {}
    sets: dict[str, list[dict]] = {code: [] for code in col_to_set.values()}

    for row in card_rows:
        card_num = to_int(row.get(1, ""))
        if card_num is None or card_num < 1:
            continue

        for col_num, set_code in col_to_set.items():
            raw = row.get(col_num, "").strip()

            # "-" marks the row after the last card in this set
            if raw == "-" and set_code not in set_totals:
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
        by_rarity: dict[str, int] = {}
        for card in cards:
            by_rarity[card["rarity"]] = by_rarity.get(card["rarity"], 0) + 1
        result[set_code] = {
            "owned": sorted(cards, key=lambda c: c["card_number"]),
            "total_owned": len(cards),
            "total_cards": total_cards,
            "by_rarity": by_rarity,
        }
        print(f"  {set_code}: {len(cards)} cards owned (of {total_cards})", flush=True)

    print(f"Total: {sum(v['total_owned'] for v in result.values())} cards across {len(result)} sets", flush=True)
    return {"sets": result}


def main() -> int:
    data = scrape_collection()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "collection.json"
    output_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output_file}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
