"""
Timeline sync service.

Scans timeline photo folders, adds missing manifest entries, preserves existing
metadata (including `type`), and syncs timeline data to docs.

File naming convention:
    DD-MM-YYYY-<index>.<ext>
Example:
    01-01-2026-1.jpg

Usage:
    python services/sync_timeline.py
"""

from __future__ import annotations

import hashlib
from datetime import date
import json
import re
import shutil
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_TIMELINE_DIR = REPO_DIR / "data" / "timeline"
DOCS_TIMELINE_DIR = REPO_DIR / "docs" / "data" / "timeline"
DATA_PHOTOS_DIR = DATA_TIMELINE_DIR / "photos"
DOCS_PHOTOS_DIR = DOCS_TIMELINE_DIR / "photos"
MANIFEST_NAME = "manifest.json"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}
TIMELINE_ID_PATTERN = re.compile(r"^(\d{2})-(\d{2})-(\d{4})-(\d+)$")
DATE_ONLY_PATTERN = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")


def _load_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _parse_timeline_id(value: str) -> tuple[int, int, int, int] | None:
    match = TIMELINE_ID_PATTERN.match(value.strip())
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    index = int(match.group(4))
    if day <= 0 or day > 31 or month <= 0 or month > 12 or index <= 0:
        return None
    return (year, month, day, index)


def _today_date_key() -> str:
    today = date.today()
    return f"{today.day:02d}-{today.month:02d}-{today.year:04d}"


def _date_key_from_timeline_id(timeline_id: str) -> str | None:
    parsed = _parse_timeline_id(timeline_id)
    if not parsed:
        return None
    year, month, day, _index = parsed
    return f"{day:02d}-{month:02d}-{year:04d}"


def _date_key_from_date_only(value: str) -> str | None:
    match = DATE_ONLY_PATTERN.match(value.strip())
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    if day <= 0 or day > 31 or month <= 0 or month > 12:
        return None
    return f"{day:02d}-{month:02d}-{year:04d}"


def _allocate_timeline_id(date_key: str, used_indices: dict[str, set[int]]) -> str:
    day, month, year = date_key.split("-")
    indices = used_indices.setdefault(date_key, set())
    next_index = 1
    while next_index in indices:
        next_index += 1
    indices.add(next_index)
    return f"{day}-{month}-{year}-{next_index}"


def _sorted_timeline_ids(timeline_ids: list[str]) -> list[str]:
    return sorted(
        timeline_ids,
        key=lambda item: _parse_timeline_id(item) or (0, 0, 0, 0),
    )


def _import_docs_photos_to_data() -> None:
    DATA_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    for source_file in DOCS_PHOTOS_DIR.iterdir():
        if not source_file.is_file():
            continue
        target_file = DATA_PHOTOS_DIR / source_file.name
        if not target_file.exists():
            shutil.copy2(source_file, target_file)


def _sync_photos_to_docs() -> None:
    DATA_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

    data_file_names = {file_path.name for file_path in DATA_PHOTOS_DIR.iterdir() if file_path.is_file()}
    for docs_file in DOCS_PHOTOS_DIR.iterdir():
        if docs_file.is_file() and docs_file.name not in data_file_names:
            docs_file.unlink()

    for source_file in DATA_PHOTOS_DIR.iterdir():
        if not source_file.is_file():
            continue
        target_file = DOCS_PHOTOS_DIR / source_file.name
        shutil.copy2(source_file, target_file)


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _dedupe_identical_photos() -> int:
    files = sorted(
        [
            file_path
            for file_path in DATA_PHOTOS_DIR.iterdir()
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=lambda file_path: file_path.name.lower(),
    )
    seen_hashes: dict[str, Path] = {}
    removed = 0
    for file_path in files:
        file_hash = _file_sha256(file_path)
        if file_hash in seen_hashes:
            file_path.unlink()
            removed += 1
            continue
        seen_hashes[file_hash] = file_path
    return removed


def _normalize_photo_filenames(used_indices: dict[str, set[int]]) -> dict[str, str]:
    discovered: dict[str, str] = {}
    claimed_ids: set[str] = set()
    files = sorted(
        [
            file_path
            for file_path in DATA_PHOTOS_DIR.iterdir()
            if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=lambda file_path: file_path.name.lower(),
    )

    for file_path in files:
        extension = file_path.suffix.lower().lstrip(".")
        stem = file_path.stem.strip()
        timeline_id = ""

        parsed_full = _parse_timeline_id(stem)
        if parsed_full:
            timeline_id = stem
            date_key = _date_key_from_timeline_id(timeline_id)
            if not date_key:
                continue
            if timeline_id in claimed_ids:
                timeline_id = _allocate_timeline_id(date_key, used_indices)
            else:
                claimed_ids.add(timeline_id)
                used_indices.setdefault(date_key, set()).add(parsed_full[3])
        else:
            date_key = _date_key_from_date_only(stem) or _today_date_key()
            timeline_id = _allocate_timeline_id(date_key, used_indices)

        desired_name = f"{timeline_id}.{extension}"
        desired_path = DATA_PHOTOS_DIR / desired_name
        if file_path.name != desired_name:
            while desired_path.exists() and desired_path.resolve() != file_path.resolve():
                date_key = _date_key_from_timeline_id(timeline_id) or _today_date_key()
                timeline_id = _allocate_timeline_id(date_key, used_indices)
                claimed_ids.add(timeline_id)
                desired_name = f"{timeline_id}.{extension}"
                desired_path = DATA_PHOTOS_DIR / desired_name
            file_path.rename(desired_path)
            file_path = desired_path

        claimed_ids.add(timeline_id)
        discovered[timeline_id] = extension
    return discovered


def _write_manifest(items: list[dict[str, str]]) -> None:
    payload = {"items": items}
    for target in (DATA_TIMELINE_DIR / MANIFEST_NAME, DOCS_TIMELINE_DIR / MANIFEST_NAME):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    _import_docs_photos_to_data()
    removed_duplicates = _dedupe_identical_photos()

    existing_payload = _load_json(DATA_TIMELINE_DIR / MANIFEST_NAME, {"items": []})
    existing_items_raw = existing_payload.get("items", []) if isinstance(existing_payload, dict) else []
    existing_items = existing_items_raw if isinstance(existing_items_raw, list) else []
    existing_by_id: dict[str, dict[str, str]] = {}

    for entry in existing_items:
        if not isinstance(entry, dict):
            continue
        timeline_id = str(entry.get("id", "")).strip()
        if not _parse_timeline_id(timeline_id):
            continue
        existing_by_id[timeline_id] = {
            "id": timeline_id,
            "extension": str(entry.get("extension", "jpg")).strip().lstrip(".") or "jpg",
            "type": str(entry.get("type", "")).strip(),
            "caption": str(entry.get("caption", "")).strip(),
        }

    used_indices: dict[str, set[int]] = {}
    scanned = _normalize_photo_filenames(used_indices)
    scanned_ids = set(scanned.keys())
    for timeline_id in list(existing_by_id.keys()):
        if timeline_id not in scanned_ids:
            del existing_by_id[timeline_id]

    for timeline_id, extension in scanned.items():
        if timeline_id in existing_by_id:
            existing_by_id[timeline_id]["extension"] = extension
            continue
        existing_by_id[timeline_id] = {
            "id": timeline_id,
            "extension": extension,
            "type": "",
            "caption": "",
        }

    sorted_ids = _sorted_timeline_ids(list(existing_by_id.keys()))
    final_items = [existing_by_id[timeline_id] for timeline_id in sorted_ids]
    _write_manifest(final_items)
    _sync_photos_to_docs()

    print(f"Timeline entries: {len(final_items)}", flush=True)
    if removed_duplicates:
        print(f"Removed duplicate photos: {removed_duplicates}", flush=True)
    print(f"Synced timeline data to: {DATA_TIMELINE_DIR} and {DOCS_TIMELINE_DIR}", flush=True)


if __name__ == "__main__":
    main()
