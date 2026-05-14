from __future__ import annotations

import argparse
import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

try:
    import cv2  # type: ignore
    import numpy as np
except Exception:  # noqa: BLE001
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]


REPO_DIR = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_DIR / ".cache" / "one_piece_sample_removal"


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def card_image_url(card_number: str, variant: int = 0) -> str:
    set_code = card_number.split("-")[0].upper()
    if variant <= 0:
        return f"https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/one-piece/{set_code}/{card_number}_EN.webp"
    return f"https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/one-piece/{set_code}/{card_number}_p{variant}_EN.webp"


def remove_sample_with_cv2(image: Image.Image) -> Image.Image:
    arr = np.array(image.convert("RGB"))
    h, w = arr.shape[:2]
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)

    # SAMPLE watermark tends to be bright/white and centered.
    bright_white = (hsv[:, :, 2] >= 170) & (hsv[:, :, 1] <= 55)
    region = np.zeros((h, w), dtype=np.uint8)
    x0, x1 = int(w * 0.06), int(w * 0.94)
    y0, y1 = int(h * 0.28), int(h * 0.70)
    region[y0:y1, x0:x1] = 1

    mask = (bright_white & (region == 1)).astype(np.uint8) * 255
    if mask.sum() == 0:
        return image

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.dilate(mask, kernel, iterations=2)
    cleaned = cv2.inpaint(arr, mask, 5, cv2.INPAINT_TELEA)
    return Image.fromarray(cleaned)


def remove_sample_fallback(image: Image.Image) -> Image.Image:
    """
    Fallback when OpenCV isn't installed:
    Counteract the white SAMPLE overlay by approximating and inverting white alpha blend.
    """
    if np is None:
        # Last-resort fallback if numpy is unavailable.
        base = image.convert("RGB")
        return ImageEnhance.Contrast(base).enhance(1.08)

    base = image.convert("RGB")
    arr = np.asarray(base).astype(np.float32)
    h, w = arr.shape[:2]

    # Focus mask where SAMPLE watermark usually appears.
    xx, yy = np.meshgrid(np.arange(w), np.arange(h))
    cx, cy = w * 0.5, h * 0.5
    rx, ry = w * 0.45, h * 0.30
    center_ellipse = (((xx - cx) / max(rx, 1)) ** 2 + ((yy - cy) / max(ry, 1)) ** 2) <= 1.0

    # Whiteness detector for watermark glyphs.
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    value = arr.max(axis=2)
    saturation = value - arr.min(axis=2)
    bright = value >= 170
    low_sat = saturation <= 55
    watermark_mask = center_ellipse & bright & low_sat

    # Build alpha strength from brightness (higher => stronger presumed white overlay).
    alpha = np.zeros((h, w), dtype=np.float32)
    alpha[watermark_mask] = np.clip((value[watermark_mask] - 165.0) / 115.0, 0.18, 0.72)

    # Smooth alpha so edges don't look harsh.
    alpha_img = Image.fromarray((alpha * 255).astype("uint8"), mode="L").filter(ImageFilter.GaussianBlur(radius=2.0))
    alpha = np.asarray(alpha_img).astype(np.float32) / 255.0

    # Invert white overlay model: observed = (1-a)*orig + a*255  => orig ~= (obs - a*255)/(1-a)
    eps = 1e-4
    den = np.clip(1.0 - alpha, eps, 1.0)
    restored = (arr - (alpha[:, :, None] * 255.0)) / den[:, :, None]
    restored = np.clip(restored, 0.0, 255.0)

    # Blend restored only in mask area, keep original elsewhere.
    blend = np.clip(alpha * 1.15, 0.0, 1.0)[:, :, None]
    out = arr * (1.0 - blend) + restored * blend
    out = np.clip(out, 0.0, 255.0).astype("uint8")

    out_img = Image.fromarray(out, mode="RGB")
    out_img = ImageEnhance.Contrast(out_img).enhance(1.05)
    out_img = ImageEnhance.Sharpness(out_img).enhance(1.08)
    return out_img


def main() -> int:
    parser = argparse.ArgumentParser(description="Test SAMPLE watermark removal on a single One Piece card image.")
    parser.add_argument("--card", default="OP15-113", help="Card number like OP15-113")
    parser.add_argument("--variant", type=int, default=0, help="0=original art, 1+=alternate art")
    parser.add_argument("--url", default="", help="Optional explicit image URL (overrides --card/--variant)")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output folder for before/after images")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    image_url = args.url.strip() or card_image_url(args.card.strip().upper(), args.variant)
    original_bytes = fetch_bytes(image_url)
    original = Image.open(io.BytesIO(original_bytes)).convert("RGB")

    if cv2 is not None and np is not None:
        cleaned = remove_sample_with_cv2(original)
        method = "opencv-inpaint"
    else:
        cleaned = remove_sample_fallback(original)
        method = "pillow-fallback"

    stem = f"{args.card.strip().upper()}_v{args.variant}"
    before_path = out_dir / f"{stem}_before.webp"
    after_path = out_dir / f"{stem}_after_{method}.webp"
    original.save(before_path, format="WEBP", quality=96)
    cleaned.save(after_path, format="WEBP", quality=96)

    print(f"Source: {image_url}", flush=True)
    print(f"Method: {method}", flush=True)
    print(f"Before: {before_path}", flush=True)
    print(f"After : {after_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
