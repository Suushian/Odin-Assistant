# -*- coding: utf-8 -*-
"""Generate the ODIN Assistant desktop icon from the canonical Ø brand mark.

Run: python assets/make_icon.py
The same proportions are used by docs/odin-launcher-icon.svg and Android
vector resources: dark rounded-square field, white ring, diagonal spear stroke.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
S = 1024
RADIUS = 228
TOP, BOT = (28, 35, 45), (10, 13, 18)
INK = (242, 245, 249, 255)


def _gradient() -> Image.Image:
    col = Image.new("RGB", (1, S))
    for y in range(S):
        k = y / (S - 1)
        col.putpixel((0, y), tuple(round(a + (b - a) * k)
                                   for a, b in zip(TOP, BOT)))
    return col.resize((S, S))


def build_master() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, S - 1, S - 1], radius=RADIUS, fill=255)
    img.paste(_gradient(), (0, 0), mask)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, S - 5, S - 5], radius=RADIUS - 4,
                        outline=(255, 255, 255, 34), width=4)

    cx = cy = S // 2
    ring_r, width = 226, 78
    d.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
              outline=INK, width=width)
    extent = ring_r + 84
    start = (cx - extent * 0.7071, cy + extent * 0.7071)
    end = (cx + extent * 0.7071, cy - extent * 0.7071)
    d.line([start, end], fill=INK, width=width)
    for x, y in (start, end):
        d.ellipse([x - width / 2, y - width / 2,
                   x + width / 2, y + width / 2], fill=INK)
    return img


def main() -> None:
    master = build_master()
    sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
             (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(HERE / "icon.ico", format="ICO", sizes=sizes)
    master.resize((512, 512), Image.Resampling.LANCZOS).save(
        HERE / "icon.png", optimize=True)
    print(f"[make_icon] icon.ico ({len(sizes)} sizes) + icon.png (512)")


if __name__ == "__main__":
    main()
