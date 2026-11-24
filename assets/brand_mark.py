# -*- coding: utf-8 -*-
"""نشانِ برند ODIN Assistant — «پالسِ منفی».

یک اسکوئرکلِ روشن که یک خطِ ضربان (پالسِ سیگنال) از دلش بریده شده است.
هندسه در فضای viewBox ۱۰۸×۱۰۸ تعریف شده و همهٔ داشته‌ها (آیکون دسکتاپ،
لانچر اندروید، اسپلش، صفحهٔ درباره) از همین یک منبع ساخته می‌شوند.

قاعدهٔ تغییر: اگر مسیرها عوض شد، `assets/make_icon.py` را دوباره اجرا کن؛
`tests/js/smoke_brand_identity.js` همهٔ سطوح را پین می‌کند.
"""
from __future__ import annotations

# ── توکن‌های رنگ (مونوکروم + یک گرادیان یخی) ─────────────────────
FIELD_TOP = "#1C2430"
FIELD_BOT = "#0A0E15"
INK_TOP = "#FFFFFF"
INK_BOT = "#DCE8F8"
HAIRLINE = "#FFFFFF"

# ── هندسه در viewBox ۱۰۸ ────────────────────────────────────────
SIZE = 108
#: اسکوئرکلِ نشان (۷۶×۷۶ در مرکز، گوشهٔ ۲۳)
SQUIRCLE = "M39.0 16.0H69.0A23 23 0 0 1 92.0 39.0V69.0A23 23 0 0 1 69.0 92.0H39.0A23 23 0 0 1 16.0 69.0V39.0A23 23 0 0 1 39.0 16.0Z"
#: حفرهٔ پالس (خط ضربان با ضخامت ۱۱ و سرهای گرد) — با evenodd بریده می‌شود
PULSE_HOLE = "M39.0 65.5 L40.0 65.4 L41.0 65.1 L41.9 64.7 L42.7 64.1 L43.4 63.3 L43.9 62.5 L44.3 61.5 L44.6 60.3 L48.7 76.3 L49.0 77.4 L49.6 78.3 L50.4 79.1 L51.3 79.8 L52.3 80.2 L53.4 80.5 L54.5 80.5 L55.6 80.3 L56.6 79.8 L57.5 79.2 L58.3 78.4 L58.9 77.5 L59.3 76.5 L63.0 63.1 L63.1 63.3 L63.8 64.1 L64.6 64.7 L65.5 65.1 L66.5 65.4 L67.5 65.5 L84.0 65.5 L85.1 65.4 L86.1 65.1 L87.1 64.6 L87.9 63.9 L88.6 63.1 L89.1 62.1 L89.4 61.1 L89.5 60.0 L89.4 58.9 L89.1 57.9 L88.6 56.9 L87.9 56.1 L87.1 55.4 L86.1 54.9 L85.1 54.6 L84.0 54.5 L70.9 54.5 L66.4 45.5 L65.8 44.6 L65.1 43.8 L64.2 43.2 L63.2 42.8 L62.1 42.5 L61.0 42.5 L59.9 42.7 L58.9 43.2 L58.0 43.8 L57.2 44.6 L56.6 45.5 L56.2 46.5 L54.3 53.4 L50.3 37.7 L50.0 36.6 L49.4 35.7 L48.6 34.9 L47.7 34.2 L46.7 33.8 L45.6 33.5 L44.5 33.5 L43.5 33.7 L42.4 34.1 L41.5 34.8 L40.7 35.5 L40.1 36.5 L39.7 37.5 L34.9 54.5 L24.0 54.5 L22.9 54.6 L21.9 54.9 L20.9 55.4 L20.1 56.1 L19.4 56.9 L18.9 57.9 L18.6 58.9 L18.5 60.0 L18.6 61.1 L18.9 62.1 L19.4 63.1 L20.1 63.9 L20.9 64.6 L21.9 65.1 L22.9 65.4 L24.0 65.5 L39.0 65.5 Z"
#: همان خط به‌صورت مسیرِ خطی (برای آیکون تک‌رنگ نوار وضعیت)
PULSE_LINE = "M24.0 60.0 L39.0 60.0 L45.0 39.0 L54.0 75.0 L61.5 48.0 L67.5 60.0 L84.0 60.0"
#: مسیر کاملِ نشان: اسکوئرکل + حفره
MARK_PATH = SQUIRCLE + " " + PULSE_HOLE
#: نقطه‌های خط پالس و ضخامتش (برای نسخهٔ رستری)
PULSE_POINTS = [(24.0, 60.0), (39.0, 60.0), (45.0, 39.0), (54.0, 75.0),
                (61.5, 48.0), (67.5, 60.0), (84.0, 60.0)]
PULSE_WIDTH = 11.0


def mark_svg(size: int = 108, field: bool = True) -> str:
    """SVG کاملِ آیکون (مربعِ گرد + نشان) در اندازهٔ دلخواه."""
    r = round(size * 24 / SIZE, 2)
    head = ('<svg xmlns="http://www.w3.org/2000/svg" width="' + str(size)
            + '" height="' + str(size) + '" viewBox="0 0 108 108">')
    defs = ('<defs>'
            '<linearGradient id="f" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="' + FIELD_TOP + '"/>'
            '<stop offset="1" stop-color="' + FIELD_BOT + '"/></linearGradient>'
            '<linearGradient id="i" x1=".1" y1="0" x2=".9" y2="1">'
            '<stop offset="0" stop-color="' + INK_TOP + '"/>'
            '<stop offset="1" stop-color="' + INK_BOT + '"/></linearGradient>'
            '</defs>')
    bg = ''
    if field:
        bg = ('<rect width="108" height="108" rx="' + str(r) + '" fill="url(#f)"/>'
              '<rect x="1" y="1" width="106" height="106" rx="' + str(r - 1)
              + '" fill="none" stroke="' + HAIRLINE + '" stroke-opacity=".13"/>')
    return head + defs + bg + '<path d="' + MARK_PATH + '" fill="url(#i)" fill-rule="evenodd"/></svg>'


def raster(px: int = 1024, field: bool = True):
    """نسخهٔ رستری (PIL) — برای icon.png/ico و mipmapهای اندروید."""
    from PIL import Image, ImageDraw

    k = px / SIZE
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))

    def grad(top: str, bot: str) -> Image.Image:
        col = Image.new("RGB", (1, px))
        t = tuple(int(top[i:i + 2], 16) for i in (1, 3, 5))
        b = tuple(int(bot[i:i + 2], 16) for i in (1, 3, 5))
        for y in range(px):
            f = y / max(1, px - 1)
            col.putpixel((0, y), tuple(round(a + (c - a) * f) for a, c in zip(t, b)))
        return col.resize((px, px))

    if field:
        mask = Image.new("L", (px, px), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, px - 1, px - 1],
                                               radius=round(24 * k), fill=255)
        img.paste(grad(FIELD_TOP, FIELD_BOT), (0, 0), mask)

    ink = Image.new("L", (px, px), 0)
    d = ImageDraw.Draw(ink)
    d.rounded_rectangle([16 * k, 16 * k, 92 * k - 1, 92 * k - 1],
                        radius=round(23 * k), fill=255)
    pts = [(x * k, y * k) for x, y in PULSE_POINTS]
    w = max(1, round(PULSE_WIDTH * k))
    d.line(pts, fill=0, width=w, joint="curve")
    r = w / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=0)
    img.paste(grad(INK_TOP, INK_BOT), (0, 0), ink)
    return img
