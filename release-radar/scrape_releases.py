from __future__ import annotations

import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


SOURCE_URL = "https://pahe.ink/"
DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_FILE = DATA_DIR / "pahe_latest.json"


class PosterGridParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_grid = False
        self.grid_depth = 0
        self.current_link: dict[str, str] | None = None
        self.items: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}

        if tag == "section" and self._is_poster_grid(attributes):
            self.in_grid = True
            self.grid_depth = 1
            return

        if not self.in_grid:
            return

        self.grid_depth += 1
        if tag == "a" and attributes.get("href") and attributes.get("title"):
            self.current_link = {
                "title": clean_title(attributes["title"]),
                "url": attributes["href"],
            }
        elif tag == "img" and self.current_link and attributes.get("src"):
            self.items.append(
                {
                    **self.current_link,
                    "image": attributes["src"],
                }
            )
            self.current_link = None

    def handle_endtag(self, tag: str) -> None:
        if not self.in_grid:
            return

        self.grid_depth -= 1
        if self.grid_depth <= 0:
            self.in_grid = False

    @staticmethod
    def _is_poster_grid(attributes: dict[str, str]) -> bool:
        classes = attributes.get("class", "")
        return "pic-grid" in classes and "cat-box" in classes


def clean_title(value: str) -> str:
    title = html.unescape(value).strip()
    return re.sub(r"\s+", " ", title)


def fetch_html(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def scrape_latest(limit: int = 12) -> list[dict[str, str]]:
    parser = PosterGridParser()
    parser.feed(fetch_html(SOURCE_URL))
    return parser.items[:limit]


def write_latest(items: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": SOURCE_URL,
        "items": items,
    }
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    items = scrape_latest()
    write_latest(items)
    print(f"Wrote {len(items)} release radar item(s) to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
