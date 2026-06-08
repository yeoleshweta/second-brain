"""Generate simple Central Perk PWA icons — purple background + orange couch only."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PURPLE = (107, 63, 160)
OUT = Path(__file__).resolve().parent.parent / "public" / "icons"


def _draw_couch(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx = (x0 + x1) // 2

    frame = (int(x0 + w * 0.04), int(y0 + h * 0.06), int(x1 - w * 0.04), int(y1 - h * 0.04))
    draw.rounded_rectangle(frame, radius=max(4, w // 16), outline=(244, 208, 63), width=max(2, w // 64))

    back_top = int(y0 + h * 0.22)
    back_bot = int(y0 + h * 0.58)
    draw.polygon(
        [
            (int(x0 + w * 0.12), back_bot),
            (int(x0 + w * 0.12), back_top + h * 0.08),
            (int(cx - w * 0.02), int(y0 + h * 0.14)),
            (int(cx + w * 0.02), int(y0 + h * 0.14)),
            (int(x1 - w * 0.12), back_top + h * 0.08),
            (int(x1 - w * 0.12), back_bot),
        ],
        fill=(200, 80, 24),
    )
    draw.polygon(
        [
            (int(x0 + w * 0.16), back_bot - h * 0.04),
            (int(x0 + w * 0.16), back_top + h * 0.14),
            (int(cx), int(y0 + h * 0.18)),
            (int(x1 - w * 0.16), back_top + h * 0.14),
            (int(x1 - w * 0.16), back_bot - h * 0.04),
        ],
        fill=(232, 117, 26),
    )

    arm_w = int(w * 0.11)
    arm_h = int(h * 0.28)
    arm_y = int(y0 + h * 0.48)
    draw.rounded_rectangle(
        (int(x0 + w * 0.06), arm_y, int(x0 + w * 0.06) + arm_w, arm_y + arm_h),
        radius=arm_w // 2,
        fill=(184, 69, 16),
    )
    draw.rounded_rectangle(
        (int(x1 - w * 0.06) - arm_w, arm_y, int(x1 - w * 0.06), arm_y + arm_h),
        radius=arm_w // 2,
        fill=(184, 69, 16),
    )

    seat_y = int(y0 + h * 0.62)
    seat_h = int(h * 0.18)
    left = (int(x0 + w * 0.22), seat_y, int(cx - w * 0.04), seat_y + seat_h)
    right = (int(cx + w * 0.04), seat_y, int(x1 - w * 0.22), seat_y + seat_h)
    draw.rounded_rectangle(left, radius=max(3, w // 32), fill=(217, 96, 20))
    draw.rounded_rectangle(right, radius=max(3, w // 32), fill=(217, 96, 20))


def render(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), PURPLE)
    draw = ImageDraw.Draw(img)
    pad = int(size * 0.14)
    _draw_couch(draw, (pad, pad, size - pad, size - pad))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, px in (("icon-192", 192), ("icon-512", 512), ("apple-touch-icon", 180)):
        path = OUT / f"{name}.png"
        render(px).save(path, optimize=True)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
