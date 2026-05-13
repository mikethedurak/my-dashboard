from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from env import get as env_get


URL = env_get("SCRAPE_GOOGLE_PLACES_SEARCH_URL", "https://places.googleapis.com/v1/places:searchText")
PHOTO_URL = env_get("SCRAPE_GOOGLE_PLACES_PHOTO_URL", "https://places.googleapis.com/v1/{name}/media")


def local_secret(name: str) -> str:
    secrets_path = Path(__file__).resolve().parents[1] / "secrets.env"
    if not secrets_path.exists():
        return ""
    for line in secrets_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def secret(name: str) -> str:
    return env_get(name, "") or local_secret(name)


def photo_media_url(photo_name: str, api_key: str, max_height: int = 600) -> str:
    encoded_name = urllib.parse.quote(str(photo_name or "").strip(), safe="/")
    params = urllib.parse.urlencode(
        {
            "maxHeightPx": str(max(1, int(max_height))),
            "key": api_key,
            "skipHttpRedirect": "true",
        }
    )
    return f"{PHOTO_URL.format(name=encoded_name)}?{params}"


def simplify_place(place: dict, api_key: str, max_photos: int = 3) -> dict:
    photos = place.get("photos") if isinstance(place.get("photos"), list) else []
    reviews = place.get("reviews") if isinstance(place.get("reviews"), list) else []
    return {
        "name": ((place.get("displayName") or {}).get("text") if isinstance(place.get("displayName"), dict) else "") or "",
        "place_id": place.get("id", ""),
        "types": place.get("types", []),
        "primary_type": place.get("primaryType", ""),
        "primary_type_label": ((place.get("primaryTypeDisplayName") or {}).get("text") if isinstance(place.get("primaryTypeDisplayName"), dict) else "") or "",
        "address": place.get("formattedAddress", ""),
        "short_address": place.get("shortFormattedAddress", ""),
        "location": {
            "lat": ((place.get("location") or {}).get("latitude") if isinstance(place.get("location"), dict) else None),
            "lng": ((place.get("location") or {}).get("longitude") if isinstance(place.get("location"), dict) else None),
        },
        "rating": place.get("rating"),
        "rating_count": place.get("userRatingCount"),
        "business_status": place.get("businessStatus", ""),
        "phone_national": place.get("nationalPhoneNumber", ""),
        "phone_international": place.get("internationalPhoneNumber", ""),
        "website": place.get("websiteUri", ""),
        "maps_url": place.get("googleMapsUri", ""),
        "timezone": ((place.get("timeZone") or {}).get("id") if isinstance(place.get("timeZone"), dict) else "") or "",
        "service_flags": {
            "takeout": place.get("takeout"),
            "delivery": place.get("delivery"),
            "serves_dinner": place.get("servesDinner"),
            "serves_beer": place.get("servesBeer"),
            "serves_wine": place.get("servesWine"),
            "serves_cocktails": place.get("servesCocktails"),
            "serves_dessert": place.get("servesDessert"),
            "outdoor_seating": place.get("outdoorSeating"),
            "good_for_children": place.get("goodForChildren"),
            "restroom": place.get("restroom"),
        },
        "payment_options": place.get("paymentOptions", {}),
        "accessibility_options": place.get("accessibilityOptions", {}),
        "reviews_preview": [
            {
                "rating": review.get("rating"),
                "relative_time": review.get("relativePublishTimeDescription", ""),
                "author": ((review.get("authorAttribution") or {}).get("displayName") if isinstance(review.get("authorAttribution"), dict) else "") or "",
                "text": ((review.get("text") or {}).get("text") if isinstance(review.get("text"), dict) else "") or "",
            }
            for review in reviews[:3]
        ],
        "photos_preview": [
            {
                "name": photo.get("name", ""),
                "width": photo.get("widthPx"),
                "height": photo.get("heightPx"),
                "author": (((photo.get("authorAttributions") or [{}])[0]).get("displayName") if isinstance(photo.get("authorAttributions"), list) and photo.get("authorAttributions") else ""),
                "media_url": photo_media_url(photo.get("name", ""), api_key),
            }
            for photo in photos[:max_photos]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Google Places (New) searchText endpoint.")
    parser.add_argument("--query", default="Botanik Social House Cape Town", help="Text query to search for.")
    parser.add_argument("--page-size", type=int, default=3, help="Number of places to request.")
    parser.add_argument(
        "--field-mask",
        default=(
            "places.id,places.displayName,places.formattedAddress,"
            "places.rating,places.userRatingCount,places.googleMapsUri"
        ),
        help="Places API field mask. Use '*' to request all fields.",
    )
    parser.add_argument("--max-photos", type=int, default=3, help="How many photo entries to print per place.")
    args = parser.parse_args()

    api_key = secret("GOOGLE_PLACES_API_KEY") or secret("GOOGLE_MAPS_API_KEY") or secret("GOOGLE_API_KEY")
    if not api_key:
        print("Missing GOOGLE_PLACES_API_KEY (or GOOGLE_MAPS_API_KEY / GOOGLE_API_KEY)")
        return 1

    body = {
        "textQuery": args.query,
        "pageSize": max(1, args.page_size),
    }

    request = urllib.request.Request(
        URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": args.field_mask.strip() or "*",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    places = payload.get("places", []) if isinstance(payload, dict) else []
    simplified = [simplify_place(place, api_key, max_photos=max(0, args.max_photos)) for place in places if isinstance(place, dict)]
    print(json.dumps({"query": args.query, "count": len(simplified), "places": simplified}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
