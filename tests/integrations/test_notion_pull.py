#!/usr/bin/env python3
"""
Quick connectivity test for a public Notion page.

Usage:
  python scripts/test_notion_pull.py "https://www.notion.so/Your-Page-<32hex>"
"""

from __future__ import annotations

import json
import re
import sys
from typing import Optional
from urllib import error, request
from urllib.parse import urlparse


def extract_page_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return None

    # Look for a 32-char hex id in the last path segment.
    match = re.search(r"([0-9a-fA-F]{32})", path.split("/")[-1])
    if not match:
        return None

    raw = match.group(1).lower()
    # Convert to UUID format 8-4-4-4-12.
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def test_public_html(url: str) -> None:
    print("== Test 1: Public HTML fetch ==")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=20) as response:
            body_bytes = response.read()
            body_text = body_bytes.decode("utf-8", errors="replace")
            print(f"Status: {response.status}")
            print(f"Content-Type: {response.headers.get('content-type', '-')}")
            print(f"Body size: {len(body_text)} chars")
            print(f"URL after redirects: {response.geturl()}")

        title_match = re.search(r"<title>(.*?)</title>", body_text, flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r"\s+", " ", title_match.group(1)).strip()
            print(f"HTML title: {title}")
        else:
            print("HTML title: <not found>")
    except error.URLError as exc:
        print(f"HTML fetch failed: {exc}")


def test_cached_page_chunk(url: str, page_id: str) -> None:
    print("\n== Test 2: Notion loadCachedPageChunk API ==")
    endpoint = "https://www.notion.so/api/v3/loadCachedPageChunk"
    payload = {
        "page": {"id": page_id},
        "limit": 30,
        "cursor": {"stack": []},
        "chunkNumber": 0,
        "verticalColumns": False,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Origin": "https://www.notion.so",
        "Referer": url,
    }

    req = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            body_bytes = response.read()
            body_text = body_bytes.decode("utf-8", errors="replace")
            print(f"Status: {response.status}")
            print(f"Content-Type: {response.headers.get('content-type', '-')}")

        snippet = body_text[:300].replace("\n", " ")
        print(f"Response preview: {snippet}")

        try:
            body = json.loads(body_text)
        except ValueError:
            print("JSON parse: failed")
            return

        record_map = body.get("recordMap", {})
        block_map = record_map.get("block", {}) if isinstance(record_map, dict) else {}
        print(f"JSON parse: ok")
        print(f"Blocks returned: {len(block_map)}")
    except error.HTTPError as exc:
        print(f"Status: {exc.code}")
        print(f"API request failed: {exc.reason}")
    except error.URLError as exc:
        print(f"API request failed: {exc}")


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: python scripts/test_notion_pull.py "https://www.notion.so/Your-Page-<32hex>"')
        return 2

    url = sys.argv[1].strip()
    page_id = extract_page_id(url)
    if not page_id:
        print("Could not extract a Notion page ID from this URL.")
        return 2

    print(f"Notion page ID: {page_id}")
    test_public_html(url)
    test_cached_page_chunk(url, page_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
