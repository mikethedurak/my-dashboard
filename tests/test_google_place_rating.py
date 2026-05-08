from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parents[1]
LOCAL_SECRETS_FILE = REPO_DIR / "secrets.env"


def local_secret(name: str) -> str:
    if not LOCAL_SECRETS_FILE.exists():
        return ""
    for line in LOCAL_SECRETS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def secret(name: str) -> str:
    return os.environ.get(name, "").strip() or local_secret(name)


def fetch_json_post(url: str, headers: dict[str, str], body: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            **headers,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def text_query_from_maps_url(url: str, fallback_name: str, lat: float, lng: float) -> str:
    if url:
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query).get("query", [""])[0].strip()
        if query:
            return urllib.parse.unquote_plus(query)
    return f"{fallback_name} {lat},{lng}"


def google_places_search_text_new(api_key: str, text_query: str, lat: float, lng: float) -> dict:
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.rating,places.userRatingCount,"
            "places.formattedAddress,places.googleMapsUri,places.websiteUri"
        ),
    }
    body = {
        "textQuery": text_query,
        "pageSize": 3,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 600.0,
            }
        },
    }
    return fetch_json_post("https://places.googleapis.com/v1/places:searchText", headers, body)


def main() -> int:
    if len(sys.argv) < 5:
        print(
            "Usage:\n"
            "  python events/test_google_place_rating.py \"Place Name\" <lat> <lng> \"<google_maps_url_or_dash>\"\n"
            "Example:\n"
            "  python events/test_google_place_rating.py \"Jooma\" -33.91746 18.38637 "
            "\"https://www.google.com/maps/search/?api=1&query=Jooma%20-33.91746%2C18.38637\""
        )
        return 1

    place_name = sys.argv[1].strip()
    lat = float(sys.argv[2])
    lng = float(sys.argv[3])
    maps_url = sys.argv[4].strip()
    if maps_url == "-":
        maps_url = ""

    api_key = secret("GOOGLE_PLACES_API_KEY") or secret("GOOGLE_MAPS_API_KEY") or secret("GOOGLE_API_KEY")
    if not api_key:
        print("Missing GOOGLE_PLACES_API_KEY (or GOOGLE_MAPS_API_KEY / GOOGLE_API_KEY) in env/secrets.env")
        return 1

    text_query = text_query_from_maps_url(maps_url, place_name, lat, lng)
    payload = google_places_search_text_new(api_key, text_query, lat, lng)
    places = payload.get("places", []) if isinstance(payload, dict) else []

    if not places:
        print(json.dumps({"query": text_query, "places_found": 0, "raw": payload}, indent=2))
        return 0

    best = places[0]
    output = {
        "query_used": text_query,
        "places_found": len(places),
        "best_place": {
            "id": best.get("id"),
            "name": (best.get("displayName") or {}).get("text", ""),
            "rating": best.get("rating"),
            "user_ratings_total": best.get("userRatingCount"),
            "formatted_address": best.get("formattedAddress", ""),
            "google_maps_url": best.get("googleMapsUri", ""),
            "website": best.get("websiteUri", ""),
        },
        "top_3": [
            {
                "id": place.get("id"),
                "name": (place.get("displayName") or {}).get("text", ""),
                "rating": place.get("rating"),
                "user_ratings_total": place.get("userRatingCount"),
                "formatted_address": place.get("formattedAddress", ""),
            }
            for place in places[:3]
        ],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
