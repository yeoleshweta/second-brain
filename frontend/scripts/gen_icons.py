"""Home-screen icon: storm-red sky and the outlined THE VOID wordmark."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SKY = (90, 15, 18)
BG = (11, 11, 16)
RED = (255, 69, 69, 255)
FONT_PATH = Path(__file__).resolve().parent / "fonts" / "Cinzel-Variable.ttf"
OUT = Path(__file__).resolve().parent.parent / "public" / "icons"


def _font(size: int) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(FONT_PATH), size)
    face.set_variation_by_axes([700])
    return face


def _gradient(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    pixels = img.load()
    for y in range(size):
        t = min(1.0, y / (size * 0.62))
        color = tuple(int(a + (b - a) * t) for a, b in zip(SKY, BG)) + (255,)
        for x in range(size):
            pixels[x, y] = color
    return img


def _draw_line(
    base: Image.Image,
    text: str,
    y: int,
    face: ImageFont.FreeTypeFont,
    stroke: int,
    gap: float,
) -> None:
    widths = [face.getlength(ch) for ch in text]
    total = sum(widths) + gap * (len(text) - 1)
    x = (base.width - total) / 2

    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cursor = x
    for ch, width in zip(text, widths):
        glow_draw.text((cursor, y), ch, font=face, fill=(*RED[:3], 170))
        cursor += width + gap
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(2, base.width // 40)))
    base.alpha_composite(glow)

    draw = ImageDraw.Draw(base)
    cursor = x
    for ch, width in zip(text, widths):
        draw.text(
            (cursor, y),
            ch,
            font=face,
            fill=(0, 0, 0, 0),
            stroke_width=stroke,
            stroke_fill=RED,
        )
        cursor += width + gap


def render(size: int, *, inset: float = 1.0) -> Image.Image:
    img = _gradient(size)
    scale = inset
    small = _font(max(12, int(size * 0.13 * scale)))
    big = _font(max(18, int(size * 0.20 * scale)))
    _draw_line(img, "THE", int(size * (0.5 - 0.20 * scale)), small, max(1, size // 170), size * 0.018 * scale)
    _draw_line(img, "VOID", int(size * (0.5 - 0.02 * scale)), big, max(2, size // 120), size * 0.008 * scale)
    return img.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "icon-192": (192, 1.0),
        "icon-512": (512, 1.0),
        "apple-touch-icon": (180, 1.0),
        "void-touch-icon": (180, 1.0),
        "icon-maskable": (512, 0.72),
    }
    for name, (px, inset) in files.items():
        path = OUT / f"{name}.png"
        render(px, inset=inset).save(path, optimize=True)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
