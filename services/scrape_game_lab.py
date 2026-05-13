"""
Build the Picture Puzzle image manifest.

Scans docs/data/game_lab/puzzle/images/ and writes docs/data/game_lab/puzzle/images.json so the
static puzzle game can offer every image as a selectable puzzle.

Usage:
    python services/scrape_game_lab.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
PUZZLE_DIR = REPO_DIR / "docs" / "data" / "game_lab" / "puzzle"
IMAGES_DIR = PUZZLE_DIR / "images"
OUTPUT_PATH = PUZZLE_DIR / "images.json"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg"}


def title_from_filename(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    images = []
    for image_path in sorted(IMAGES_DIR.iterdir(), key=lambda item: item.name.lower()):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        images.append(
            {
                "title": title_from_filename(image_path),
                "path": f"images/{image_path.name}",
            }
        )

    OUTPUT_PATH.write_text(json.dumps({"images": images}, indent=2), encoding="utf-8")
    print(f"Puzzle images: {len(images)}", flush=True)
    print(f"Wrote: {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
