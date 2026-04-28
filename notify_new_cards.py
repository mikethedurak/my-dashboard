from __future__ import annotations

import argparse
import csv
import os
import shutil
import smtplib
import subprocess
import sys
from email.message import EmailMessage
from pathlib import Path


REPORT_PREFIXES = {
    "all": "all_stores_missing_available",
    "bigbang": "big_bang_missing_available",
    "bigbangshop": "big_bang_missing_available",
    "knightly": "knightly_missing_available",
    "knightlygaming": "knightly_missing_available",
    "marvellous": "marvellous_missing_available",
    "marvelloushobbies": "marvellous_missing_available",
    "tanuki": "tanuki_missing_available",
    "tanukitrader": "tanuki_missing_available",
}

LATEST_NEW_CARDS = Path(".scrape/latest_new_cards.txt")
MATCH_KEY = ("card_number", "store", "url")


def normalized_store(value: str) -> str:
    return value.lower().replace("-", "").replace("_", "")


def report_prefix(store: str) -> str:
    store_key = normalized_store(store)
    try:
        return REPORT_PREFIXES[store_key]
    except KeyError as error:
        choices = ", ".join(sorted(REPORT_PREFIXES))
        raise RuntimeError(f"Unknown store {store!r}. Use one of: {choices}") from error


def current_report(store: str) -> Path:
    return Path(f"{report_prefix(store)}.csv")


def previous_report(store: str) -> Path:
    return Path(f".scrape/previous_{report_prefix(store)}.csv")


def run_scraper(store: str) -> None:
    subprocess.run(
        [sys.executable, "find_missing_cards.py", store],
        check=True,
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def row_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple((row.get(field) or "").strip() for field in MATCH_KEY)


def new_rows(today: list[dict[str, str]], previous: list[dict[str, str]]) -> list[dict[str, str]]:
    previous_keys = {row_key(row) for row in previous}
    return [row for row in today if row_key(row) not in previous_keys]


def money(value: str) -> str:
    try:
        return f"R {float(value):.2f}"
    except (TypeError, ValueError):
        return value or ""


def card_line(row: dict[str, str]) -> str:
    pieces = [
        row.get("card_number", ""),
        money(row.get("price", "")),
        row.get("title", ""),
        row.get("rarity", ""),
        row.get("store", ""),
        row.get("stock", ""),
    ]
    summary = " | ".join(piece for piece in pieces if piece)
    url = row.get("url", "")
    return f"{summary}\n{url}" if url else summary


def email_body(rows: list[dict[str, str]], store: str, mode: str) -> str:
    label = "All missing cards available" if mode == "all" else "New missing cards available"
    lines = [
        f"{label} for {store}: {len(rows)}",
        "",
    ]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {card_line(row)}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def write_latest_text(body: str) -> None:
    LATEST_NEW_CARDS.parent.mkdir(parents=True, exist_ok=True)
    LATEST_NEW_CARDS.write_text(body, encoding="utf-8")


def send_email(rows: list[dict[str, str]], store: str, mode: str) -> None:
    smtp_host = env_required("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = env_required("SMTP_USER")
    smtp_password = env_required("SMTP_PASSWORD")
    email_to = env_required("EMAIL_TO")
    email_from = os.environ.get("EMAIL_FROM", "").strip() or smtp_user

    message = EmailMessage()
    subject_label = "available" if mode == "all" else "new available"
    message["Subject"] = f"One Piece cards: {len(rows)} {subject_label} ({store})"
    message["From"] = email_from
    message["To"] = email_to
    message.set_content(email_body(rows, store, mode))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def update_snapshot(current: Path, previous: Path) -> None:
    previous.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(current, previous)


def main() -> int:
    parser = argparse.ArgumentParser(description="Email new missing-card listings once per day.")
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Compare existing CSV files without running the scraper first.",
    )
    parser.add_argument(
        "--store",
        default=os.environ.get("CARD_STORE", "all"),
        help="Store to check: all, knightly, bigbang, marvellous, or tanuki.",
    )
    parser.add_argument(
        "--mode",
        choices=["new", "all"],
        default=os.environ.get("CARD_NOTIFY_MODE", "new"),
        help="Use 'new' to email only new listings, or 'all' to email every current listing.",
    )
    args = parser.parse_args()
    store = normalized_store(args.store)
    mode = args.mode
    current = current_report(store)
    previous = previous_report(store)

    if not args.no_scrape:
        run_scraper(store)

    if not current.exists():
        print(f"Could not find current report: {current}", file=sys.stderr)
        return 2

    today = read_rows(current)
    previous_rows = read_rows(previous)

    if mode == "all":
        body = email_body(today, store, mode)
        write_latest_text(body)
        send_email(today, store, mode)
        update_snapshot(current, previous)
        print(f"Sent email for all {len(today)} current card listing(s). Snapshot updated.")
        return 0

    if not previous_rows:
        write_latest_text(f"No previous snapshot found for {store}. Saved today's report as the baseline.\n")
        update_snapshot(current, previous)
        print(f"No previous snapshot found for {store}. Saved today's report as the baseline.")
        return 0

    additions = new_rows(today, previous_rows)
    if not additions:
        write_latest_text(f"No new cards found for {store}.\n")
        update_snapshot(current, previous)
        print(f"No new cards found for {store}. Snapshot updated.")
        return 0

    body = email_body(additions, store, mode)
    write_latest_text(body)
    send_email(additions, store, mode)
    update_snapshot(current, previous)
    print(f"Sent email for {len(additions)} new card listing(s). Snapshot updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
