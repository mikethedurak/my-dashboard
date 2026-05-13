from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


MOVIES_URL = "https://thegalileo.co.za/movies/"
DEFAULT_TIMEOUT = 30


def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; my-dashboard/1.0)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-ZA,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def absolute_url(url: str, base_url: str = MOVIES_URL) -> str:
    return urllib.parse.urljoin(base_url, html.unescape(url.strip()))


def clean_text(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<svg\b[^>]*>.*?</svg>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def first_match(pattern: str, text: str, flags: int = re.IGNORECASE | re.DOTALL) -> str:
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ""


def parse_label_value_spans(block: str) -> dict[str, str]:
    values: dict[str, str] = {}
    spans = re.findall(r"<span\b[^>]*>(.*?)</span>", block, flags=re.IGNORECASE | re.DOTALL)
    pending_label = ""
    for raw_span in spans:
        text = clean_text(raw_span)
        if not text:
            continue
        if text.endswith(":"):
            pending_label = text[:-1].strip().lower().replace(" ", "_")
            continue
        if text.startswith("Day:"):
            values["day"] = text.split(":", 1)[1].strip()
            continue
        if pending_label:
            values[pending_label] = text
            pending_label = ""
    return values


def parse_listing_movies(page_html: str) -> list[dict[str, str]]:
    movies: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for block_match in re.finditer(
        r'<li class="wcs-class">(.*?)</li>',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        block = block_match.group(1)
        url = first_match(r'<a\b[^>]*class="[^"]*\bwcs-btn\b[^"]*"[^>]*href="([^"]+)"', block)
        title = first_match(
            r'<h3\b[^>]*class="[^"]*\btitledesktop\b[^"]*"[^>]*>(.*?)</h3>',
            block,
        ) or first_match(r'<h3\b[^>]*class="[^"]*\btitlembile\b[^"]*"[^>]*>(.*?)</h3>', block)
        date_text = first_match(r'<time\b[^>]*datetime="([^"]+)"', block)

        if not title or not url:
            continue

        url = absolute_url(url)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        info = parse_label_value_spans(block)
        movies.append(
            {
                "title": clean_text(title),
                "date_text": clean_text(date_text),
                "day": info.get("day", ""),
                "venue": info.get("venue", ""),
                "doors_open": info.get("doors_open", ""),
                "movie_starts": info.get("movie_starts", ""),
                "genre": info.get("genre", ""),
                "age_restriction": info.get("age_restriction", ""),
                "url": url,
            }
        )

    return movies


def parse_detail_table(detail_html: str) -> dict[str, str]:
    details: dict[str, str] = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", detail_html, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 2:
            continue
        label = clean_text(cells[0]).rstrip(":").lower().replace(" ", "_")
        value = clean_text(cells[1])
        if label and value:
            details[label] = value
    return details


def button_link_by_text(page_html: str, text_pattern: str) -> str:
    for match in re.finditer(
        r'(<a\b[^>]*class="[^"]*\belementor-button-link\b[^"]*"[^>]*href="([^"]+)"[^>]*>.*?</a>)',
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        button_html, href = match.groups()
        if re.search(text_pattern, clean_text(button_html), flags=re.IGNORECASE):
            return href.strip()
    return ""


def parse_detail_page(detail_html: str, url: str) -> dict[str, str]:
    title = clean_text(first_match(r"<h1\b[^>]*>(.*?)</h1>", detail_html))
    image = first_match(
        r'<img\b[^>]*src="([^"]+)"[^>]*class="[^"]*attachment-large[^"]*"',
        detail_html,
    )
    synopsis = clean_text(first_match(r"(<p><strong>[^<]+</strong>.*?</p>)", detail_html))
    trailer_url = button_link_by_text(detail_html, r"\bmovie trailer\b")
    book_url = button_link_by_text(detail_html, r"\bbook\b")

    details = parse_detail_table(detail_html)
    parsed = {
        "detail_title": title,
        "image": absolute_url(image, url) if image else "",
        "synopsis": synopsis,
        "trailer_url": absolute_url(trailer_url, url) if trailer_url else "",
        "book_url": absolute_url(book_url, url) if book_url else "",
    }
    parsed.update(details)
    return parsed


def enrich_with_details(movies: list[dict[str, str]]) -> list[dict[str, str]]:
    enriched: list[dict[str, str]] = []
    for movie in movies:
        item = dict(movie)
        detail_html = fetch_html(movie["url"])
        item.update(parse_detail_page(detail_html, movie["url"]))
        enriched.append(item)
    return enriched


def load_source_html(args: argparse.Namespace) -> str:
    if args.html:
        return Path(args.html).read_text(encoding="utf-8")
    return fetch_html(args.url)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test-scrape Galileo open-air cinema movies and print the available fields as JSON.",
    )
    parser.add_argument("--url", default=MOVIES_URL, help="Galileo movies listing URL.")
    parser.add_argument("--html", default="", help="Optional local HTML snapshot to parse instead of fetching.")
    parser.add_argument("--details", action="store_true", help="Fetch each detail page for runtime, synopsis, image, etc.")
    parser.add_argument("--expect-current", action="store_true", help="Fail if Grease and About Time are not present.")
    args = parser.parse_args()

    page_html = load_source_html(args)
    movies = parse_listing_movies(page_html)
    if args.details:
        movies = enrich_with_details(movies)

    print(json.dumps(movies, indent=2, ensure_ascii=False))

    if not movies:
        print("No Galileo movie listings found.", file=sys.stderr)
        return 1

    if args.expect_current:
        titles = {movie.get("title", "").lower() for movie in movies}
        if not any("grease" in title for title in titles):
            print("Expected current movie not found: Grease", file=sys.stderr)
            return 1
        if not any("about time" in title for title in titles):
            print("Expected current movie not found: About Time", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
