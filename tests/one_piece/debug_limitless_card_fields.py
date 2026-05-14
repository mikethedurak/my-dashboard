from __future__ import annotations

import argparse
import re
import urllib.request


def fetch_html(card_number: str) -> str:
    url = f"https://onepiece.limitlesstcg.com/cards/{card_number}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(text.split()).strip()


def tooltip_values(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r'data-tooltip="([^"]+)"\s*>\s*(.*?)\s*</span>', html, re.IGNORECASE | re.DOTALL):
        key = strip_html(m.group(1))
        val = strip_html(m.group(2))
        if key and key not in out:
            out[key] = val
    return out


def all_sections(html: str) -> list[str]:
    return [strip_html(m.group(1)) for m in re.finditer(r'<div class="card-text-section[^"]*">\s*(.*?)\s*</div>', html, re.IGNORECASE | re.DOTALL)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug all available fields on a Limitless One Piece card page.")
    parser.add_argument("--card-number", required=True, help="Card number, e.g. OP01-001")
    parser.add_argument("--show-html-snippets", action="store_true", help="Print nearby raw HTML around card-text blocks.")
    args = parser.parse_args()

    card_number = args.card_number.strip().upper()
    html = fetch_html(card_number)
    print(f"card_number={card_number}")
    print(f"html_length={len(html)}")

    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        print(f"title={strip_html(title_match.group(1))}")

    name_match = re.search(r'<span class="card-text-name">.*?<a[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    card_id_match = re.search(r'<span class="card-text-id">(.*?)</span>', html, re.IGNORECASE | re.DOTALL)
    print(f"name={strip_html(name_match.group(1)) if name_match else ''}")
    print(f"card_id_text={strip_html(card_id_match.group(1)) if card_id_match else ''}")

    tips = tooltip_values(html)
    print("\n[tooltip fields]")
    for key in sorted(tips):
        print(f"{key}: {tips[key]}")

    sections = all_sections(html)
    print("\n[card-text sections]")
    for i, section in enumerate(sections, start=1):
        print(f"{i}. {section}")

    # Show explicit class blocks that might hold description/family.
    effect_match = re.search(
        r'<div class="card-text-section">\s*(.*?)\s*</div>\s*<div class="card-text-section card-text-footer">',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    family_match = re.search(
        r'<div class="card-text-section card-text-footer">\s*(.*?)\s*</div>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    print("\n[explicit parser fields]")
    print(f"description_candidate={strip_html(effect_match.group(1)) if effect_match else ''}")
    print(f"family_candidate={strip_html(family_match.group(1)) if family_match else ''}")

    if args.show_html_snippets:
        anchor = html.find('class="card-text"')
        if anchor >= 0:
            start = max(0, anchor - 400)
            end = min(len(html), anchor + 4000)
            print("\n[html snippet around card-text]")
            print(html[start:end])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
