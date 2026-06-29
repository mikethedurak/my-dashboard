from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from services.common.secrets import env_get


NOTION_VERSION = "2022-06-28"
NOTION_API_BASE_URL = env_get("SCRAPE_NOTION_API_BASE_URL", "https://api.notion.com/v1")
NOTION_TIMEOUT_SECONDS = int(env_get("SCRAPE_NOTION_TIMEOUT_SECONDS", "60") or "60")
NOTION_MAX_RETRIES = int(env_get("SCRAPE_NOTION_MAX_RETRIES", "4") or "4")
NOTION_RETRY_BACKOFF_SECONDS = float(env_get("SCRAPE_NOTION_RETRY_BACKOFF_SECONDS", "2") or "2")


def rich_text_plain(rich_text: list[dict[str, Any]], include_strikethrough: bool = False) -> str:
    parts: list[str] = []
    for part in rich_text:
        annotations = part.get("annotations") or {}
        if annotations.get("strikethrough") and not include_strikethrough:
            continue
        parts.append(str(part.get("plain_text", "")))
    return "".join(parts).strip()


def retry_delay(error: BaseException, attempt: int) -> float:
    if isinstance(error, urllib.error.HTTPError):
        retry_after = error.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    return NOTION_RETRY_BACKOFF_SECONDS * attempt


def is_retryable_error(error: BaseException) -> bool:
    if isinstance(error, TimeoutError):
        return True
    if isinstance(error, urllib.error.HTTPError):
        return error.code == 429 or 500 <= error.code < 600
    if isinstance(error, urllib.error.URLError):
        return True
    return False


def request(path: str, token: str, user_agent: str = "Mozilla/5.0") -> dict[str, Any]:
    req = urllib.request.Request(
        f"{NOTION_API_BASE_URL}/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )
    for attempt in range(1, NOTION_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=NOTION_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if attempt >= NOTION_MAX_RETRIES or not is_retryable_error(error):
                raise
            delay = retry_delay(error, attempt)
            print(f"[notion] Request failed ({error}); retrying in {delay:g}s ({attempt}/{NOTION_MAX_RETRIES})")
            time.sleep(delay)
    raise TimeoutError(f"Notion request timed out after {NOTION_MAX_RETRIES} attempts: {path}")


def post(path: str, token: str, body: dict[str, Any], user_agent: str = "Mozilla/5.0") -> dict[str, Any]:
    req = urllib.request.Request(
        f"{NOTION_API_BASE_URL}/{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_block_children(block_id: str, token: str, log_label: str = "") -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    cursor = ""
    page = 0
    while True:
        page += 1
        query = f"?page_size=100&start_cursor={cursor}" if cursor else "?page_size=100"
        payload = request(f"blocks/{block_id}/children{query}", token)
        results = payload.get("results", [])
        if isinstance(results, list):
            blocks.extend(item for item in results if isinstance(item, dict))
        if log_label:
            print(f"[notion] {log_label}: page {page}, +{len(results)} blocks (total {len(blocks)})")
        if not payload.get("has_more"):
            return blocks
        cursor = str(payload.get("next_cursor") or "")
