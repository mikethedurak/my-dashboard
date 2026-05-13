from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request


IMAX_URL = "https://www.imax.com/en/za/theatre/ster-kinekor-va-waterfront-imax"
FALLBACK_URL = "https://r.jina.ai/http://www.imax.com/en/za/theatre/ster-kinekor-va-waterfront-imax"
COMING_SOON_LIMIT = 4


def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_listings(text: str) -> list[dict[str, object]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    listings: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line in lines:
        title_match = re.match(r"^##\s+\[(.+?)>\]\((http://www\.imax\.com/en/za/movie/[^)]+)\)", line)
        if title_match:
            if current:
                listings.append(current)
            current = {
                "title": title_match.group(1).strip(),
                "url": title_match.group(2).strip(),
                "format": "",
                "showtimes": [],
            }
            continue

        if not current:
            continue

        if line.upper().startswith("IMAX "):
            current["format"] = line
            continue

        time_match = re.match(r"^\[([0-2]\d:[0-5]\d)\]\(http://www\.imax\.com/en/za/ticket-partner\)$", line)
        if time_match:
            showtimes = current.get("showtimes")
            if isinstance(showtimes, list):
                showtimes.append(time_match.group(1))

    if current:
        listings.append(current)

    return listings


def fallback_url(url: str) -> str:
    return "https://r.jina.ai/" + url.replace("https://", "http://", 1)


def parse_related_movies(text: str, excluded_urls: set[str]) -> list[dict[str, str]]:
    seen_urls: set[str] = set()
    movies: list[dict[str, str]] = []
    for match in re.finditer(r"\[([^\]]+?)>\]\((http://www\.imax\.com/en/za/movie/[^)]+)\)", text):
        title = match.group(1).strip()
        url = match.group(2).strip()
        if url in seen_urls or url in excluded_urls:
            continue
        seen_urls.add(url)
        movies.append({"title": title, "url": url})
    return movies


def parse_coming_soon_from_current_movies(listings: list[dict[str, object]]) -> list[dict[str, str]]:
    excluded_urls = {str(movie.get("url", "")).strip() for movie in listings if str(movie.get("url", "")).strip()}
    coming_soon: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for movie in listings:
        movie_url = str(movie.get("url", "")).strip()
        if not movie_url:
            continue
        movie_text = fetch_text(fallback_url(movie_url))
        for related in parse_related_movies(movie_text, excluded_urls):
            if related["url"] in seen_urls:
                continue
            seen_urls.add(related["url"])
            coming_soon.append(related)
            if len(coming_soon) >= COMING_SOON_LIMIT:
                return coming_soon
    return coming_soon


def main() -> int:
    source = IMAX_URL
    try:
        text = fetch_text(IMAX_URL)
        print(f"Fetched IMAX page directly: {IMAX_URL}")
    except urllib.error.HTTPError as error:
        if error.code != 403:
            raise
        source = FALLBACK_URL
        text = fetch_text(FALLBACK_URL)
        print(f"Direct IMAX fetch returned 403, used fallback: {FALLBACK_URL}")

    listings = parse_listings(text)
    print(f"Source: {source}")
    print(f"Now playing here: {len(listings)}")
    print("")

    if not listings:
        print("No movie listings found.")
        return 1

    for index, movie in enumerate(listings, start=1):
        title = str(movie.get("title", "")).strip()
        showtimes = movie.get("showtimes")
        showtime_text = ", ".join(showtimes) if isinstance(showtimes, list) else ""
        format_text = str(movie.get("format", "")).strip()
        print(f"{index}. {title}")
        if format_text:
            print(f"   Format: {format_text}")
        print(f"   Showtimes: {showtime_text if showtime_text else 'None'}")
        print("")

    coming_soon = parse_coming_soon_from_current_movies(listings)
    if not coming_soon:
        return 0

    print("Coming soon on ZA IMAX ticket carousel:")
    print("")
    for index, movie in enumerate(coming_soon, start=1):
        print(f"{index}. {movie['title']}")
        print("   Status: coming_soon")
        print(f"   URL: {movie['url']}")
        print("")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"IMAX test failed: {error}", file=sys.stderr)
        raise
