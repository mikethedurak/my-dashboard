from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.request
from pathlib import Path

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except Exception:  # noqa: BLE001
    Image = None  # type: ignore[assignment]
    ImageEnhance = None  # type: ignore[assignment]
    ImageFilter = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]

try:
    import pytesseract
except Exception:  # noqa: BLE001
    pytesseract = None  # type: ignore[assignment]

sys.path.append(str(Path(__file__).resolve().parents[2] / "services" / "one_piece"))
from one_piece_missing import (  # noqa: E402
    GEEK_HAVEN_PAGE_URL,
    _parse_geek_haven_page,
    _title_lookup_key,
    build_knightly_title_index,
    clean_text,
    fetch_text,
    normalize_card_number,
)


CARD_RE = re.compile(r"\b(?:OP|ST|EB|PRB)\d{1,2}-\d{1,3}\b", re.IGNORECASE)


def fetch_geekhaven_products(max_pages: int = 0) -> list[dict]:
    products: list[dict] = []
    page = 1
    while True:
        if max_pages > 0 and page > max_pages:
            break
        print(f"[geekhaven] fetching page {page}...", flush=True)
        html = fetch_text(GEEK_HAVEN_PAGE_URL.format(page=page))
        page_products = _parse_geek_haven_page(html)
        print(f"[geekhaven] page {page} -> {len(page_products)} Bandai products", flush=True)
        if not page_products:
            break
        products.extend(page_products)
        page += 1
    print(f"[geekhaven] total products: {len(products)}", flush=True)
    return products


def unresolved_geekhaven_products(products: list[dict], title_index: dict[str, str]) -> list[dict]:
    unresolved: list[dict] = []
    for product in products:
        title = clean_text(product.get("name") or "")
        if not title:
            continue
        if normalize_card_number(title):
            continue
        if _title_lookup_key(title) in title_index:
            continue
        unresolved.append(product)
    return unresolved


def fetch_image(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def crop_bottom_right(img: Image.Image, width_ratio: float = 0.32, height_ratio: float = 0.22) -> Image.Image:
    w, h = img.size
    x0 = int(w * (1.0 - width_ratio))
    y0 = int(h * (1.0 - height_ratio))
    return img.crop((x0, y0, w, h))


def preprocess_variants(crop: Image.Image) -> list[Image.Image]:
    out: list[Image.Image] = []
    gray = ImageOps.grayscale(crop)
    up2 = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
    up3 = gray.resize((gray.width * 3, gray.height * 3), Image.Resampling.LANCZOS)
    out.append(up2)
    out.append(up3)

    sharpened = up3.filter(ImageFilter.SHARPEN)
    out.append(sharpened)

    high_contrast = ImageEnhance.Contrast(sharpened).enhance(2.4)
    out.append(high_contrast)

    binary = high_contrast.point(lambda p: 255 if p > 145 else 0)
    out.append(binary)

    inv = ImageOps.invert(high_contrast)
    out.append(inv)
    return out


def extract_card_number_from_text(text: str) -> str:
    match = CARD_RE.search(text or "")
    if not match:
        return ""
    return normalize_card_number(match.group(0)) or ""


def ocr_try(image: Image.Image, psm: int) -> str:
    config = f"--oem 3 --psm {psm} -c tessedit_char_whitelist=OPSTEBPRB0123456789-"
    return pytesseract.image_to_string(image, config=config)  # type: ignore[union-attr]


def detect_from_image_bytes(image_bytes: bytes, dump_dir: Path | None = None) -> tuple[str, list[str]]:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    crop = crop_bottom_right(img)
    variants = preprocess_variants(crop)

    if dump_dir:
        dump_dir.mkdir(parents=True, exist_ok=True)
        crop.save(dump_dir / "crop_base.png")
        for i, v in enumerate(variants, start=1):
            v.save(dump_dir / f"variant_{i}.png")

    seen_texts: list[str] = []
    for idx, variant in enumerate(variants, start=1):
        for psm in (6, 7, 11, 13):
            text = ocr_try(variant, psm=psm)
            text_clean = " ".join(text.split())
            if text_clean:
                seen_texts.append(f"variant={idx} psm={psm} text={text_clean}")
            card = extract_card_number_from_text(text)
            if card:
                return card, seen_texts
    return "", seen_texts


def require_ocr_deps() -> bool:
    if Image is None or pytesseract is None:
        print("Missing Python OCR dependencies.")
        print("Install: pip install pillow pytesseract")
        return False
    try:
        _ = pytesseract.get_tesseract_version()  # type: ignore[union-attr]
    except Exception as error:  # noqa: BLE001
        print("Tesseract binary not detected.")
        print("Install Tesseract OCR and ensure it's on PATH.")
        print(f"Details: {error}")
        return False
    return True


def configure_tesseract_cmd(tesseract_cmd: str) -> None:
    if pytesseract is None:
        return
    candidate = tesseract_cmd.strip()
    if candidate:
        pytesseract.pytesseract.tesseract_cmd = candidate  # type: ignore[union-attr]
        return
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in common_paths:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path  # type: ignore[union-attr]
            return


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR test for unresolved GeekHaven card images (bottom-right card number).")
    parser.add_argument("--index", type=int, default=0, help="Index in unresolved GeekHaven list.")
    parser.add_argument("--title", default="", help="Specific GeekHaven title to test.")
    parser.add_argument("--max-pages", type=int, default=0, help="Limit GeekHaven pages scanned (0=all).")
    parser.add_argument("--dump-dir", default="", help="Optional folder to save crop/preprocessed images.")
    parser.add_argument(
        "--tesseract-cmd",
        default="",
        help="Full path to tesseract.exe (use if Tesseract is not on PATH).",
    )
    args = parser.parse_args()

    configure_tesseract_cmd(args.tesseract_cmd)
    if not require_ocr_deps():
        return 2

    title_index = build_knightly_title_index()
    products = fetch_geekhaven_products(max_pages=args.max_pages)
    unresolved = unresolved_geekhaven_products(products, title_index)

    if not unresolved:
        print("No unresolved GeekHaven products found.")
        return 0

    product: dict | None = None
    if args.title.strip():
        wanted = _title_lookup_key(args.title)
        for item in unresolved:
            if _title_lookup_key(clean_text(item.get("name") or "")) == wanted:
                product = item
                break
        if product is None:
            print("Title not found in unresolved list.")
            return 1
    else:
        if args.index < 0 or args.index >= len(unresolved):
            print(f"--index out of range. unresolved={len(unresolved)}")
            return 2
        product = unresolved[args.index]

    title = clean_text(product.get("name") or "")
    images = product.get("images") or []
    image_url = str(images[0].get("src") or "") if images else ""
    if not image_url:
        print("No image URL on selected GeekHaven product.")
        print(f"title: {title}")
        return 1

    print("")
    print("=== GeekHaven OCR Debug ===")
    print(f"unresolved_count: {len(unresolved)}")
    print(f"title: {title}")
    print(f"url: {product.get('permalink') or ''}")
    print(f"image_url: {image_url}")

    image_bytes = fetch_image(image_url)
    dump_dir = Path(args.dump_dir).resolve() if args.dump_dir else None
    card, traces = detect_from_image_bytes(image_bytes, dump_dir=dump_dir)

    print("")
    print("=== OCR Result ===")
    print(f"detected_card_number: {card or '<none>'}")
    print("")
    print("=== OCR Trace (first 20 lines) ===")
    for line in traces[:20]:
        print(line)
    if len(traces) > 20:
        print(f"... {len(traces) - 20} more lines")
    if dump_dir:
        print(f"Saved crops/variants to: {dump_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
