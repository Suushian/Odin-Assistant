"""رندرِ پیش‌نمایشِ صفحهٔ خانهٔ اپ اندروید — برای مستندات UI/UX.

چرا این فایل وجود دارد
──────────────────────
این مخزن یک اپ اندروید (WebView) + یک اپ دسکتاپ (PySide6) است. برای نوشتنِ
گزارشِ UI/UX به تصویری از «قبل» و «بعد» نیاز بود، ولی:

  • PySide6 در محیطِ ساختِ مستندات اجرا نمی‌شود (libEGL/libGL/libdbus نیست)،
  • WebView/Chromium هم در دسترس نیست.

پس این اسکریپت با Pillow یک رندرِ *طراحی* از همان توکن‌های واقعی می‌سازد:
اعداد و رنگ‌ها از `www/style.css` و `src/ui/theme.py` کپی می‌شوند و دو حالت
رندر می‌گیرد (`before` = v1.3.1، `after` = v1.4.0). خروجی «اسکرین‌شاتِ
دستگاه» نیست؛ پیش‌نمایشِ طراحی است و در گزارش هم همین‌طور عنوان شده.

اجرا:
    .venv/bin/python assets/render_ui_preview.py
خروجی:
    docs/images/ui-1.3.1-home.png
    docs/images/ui-1.4.0-home.png
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover
    print("نیازمند: pip install arabic-reshaper python-bidi")
    raise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "android", "app", "src", "main", "assets", "www", "fonts")
OUT_DIR = os.path.join(ROOT, "docs", "images")

S = 2                  # ضریب بزرگ‌نمایی برای لبه‌های نرم
W, H = 390, 844        # اندازهٔ منطقیِ دستگاه (px)

# ── توکن‌های مشترک (بدون تغییر بین دو نسخه) ──────────────────────────
BG_TOP, BG_MID, BG_BOT = "#EFEFF3", "#E7E7EC", "#E1E1E8"
INK_CARD = "#101013"
INK_TILE = "#26262B"
WHITE = "#FFFFFF"
GREEN, GREEN_TINT, GREEN_TEXT = "#1F9D66", "#E4F5EC", "#177B50"
RED_TINT, RED_TEXT = "#FBEAEA", "#B23A3A"
RAISED, BORDER = "#EDEDF0", "#E3E3E8"
TEXT, TEXT2 = "#0B0B0C", "#55555E"


def font(size: float, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, f"Vazirmatn-{weight}.ttf"),
                              int(round(size * S)))


def fa(s: str) -> str:
    """شکل‌دهی + ترتیبِ راست‌به‌چپ برای Pillow (که shaping ندارد)."""
    return get_display(arabic_reshaper.reshape(s))


def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def X(v: float) -> int:
    return int(round(v * S))


def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle([X(box[0]), X(box[1]), X(box[2]), X(box[3])],
                        radius=X(r), fill=fill, outline=outline, width=X(width))


def shadows(size, shapes, alpha, blur):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for box, r, dy in shapes:
        d.rounded_rectangle([X(box[0]), X(box[1] + dy), X(box[2]), X(box[3] + dy)],
                            radius=X(r), fill=(16, 16, 19, alpha))
    return layer.filter(ImageFilter.GaussianBlur(X(blur)))


def txt(d, xy, s, f, fill, anchor="ra"):
    d.text((X(xy[0]), X(xy[1])), s, font=f, fill=fill, anchor=anchor)


def width(d, s, f) -> float:
    return d.textlength(s, font=f) / S


def background() -> Image.Image:
    img = Image.new("RGBA", (X(W), X(H)), rgb(BG_MID) + (255,))
    top, bot = rgb(BG_TOP), rgb(BG_BOT)
    d = ImageDraw.Draw(img)
    for row in range(img.height):
        t = row / (img.height - 1)
        d.line([(0, row), (img.width, row)],
               fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([X(W * 0.46), X(-H * 0.20), X(W * 1.40), X(H * 0.26)],
               fill=(255, 255, 255, 200))
    return Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(X(60))))


def card_shadows(img, boxes, style, r_card):
    if style == "before":
        img.alpha_composite(shadows(img.size, [(b, r_card, 8) for b in boxes], 18, 12))
    else:
        for b in boxes:
            img.alpha_composite(shadows(img.size, [(b, r_card, 1)], 10, 2))
            img.alpha_composite(shadows(img.size, [(b, r_card, 10)], 16, 26))


def icon(d, name, cx, cy, color, active=False):
    """آیکون‌های خطیِ نازک برای نوار تب (بدون فونت آیکون)."""
    c = color
    if name == "home":
        d.line([X(cx - 8), X(cy - 5), X(cx), X(cy - 12)], fill=c, width=X(1.6))
        d.line([X(cx), X(cy - 12), X(cx + 8), X(cy - 5)], fill=c, width=X(1.6))
        d.rounded_rectangle([X(cx - 6), X(cy - 5), X(cx + 6), X(cy + 5)],
                            radius=X(2), outline=c, width=X(1.6))
    elif name == "signal":
        for i, h in enumerate((6, 11, 16)):
            d.line([X(cx - 6 + i * 6), X(cy + 6), X(cx - 6 + i * 6), X(cy + 6 - h)],
                   fill=c, width=X(2))
    elif name == "calendar":
        d.rounded_rectangle([X(cx - 8), X(cy - 7), X(cx + 8), X(cy + 7)],
                            radius=X(3), outline=c, width=X(1.6))
        d.line([X(cx - 8), X(cy - 2), X(cx + 8), X(cy - 2)], fill=c, width=X(1.4))
        d.line([X(cx - 4), X(cy - 10), X(cx - 4), X(cy - 6)], fill=c, width=X(1.6))
        d.line([X(cx + 4), X(cy - 10), X(cx + 4), X(cy - 6)], fill=c, width=X(1.6))
    else:  # journal
        d.rounded_rectangle([X(cx - 7), X(cy - 8), X(cx + 7), X(cy + 8)],
                            radius=X(2), outline=c, width=X(1.6))
        d.line([X(cx - 3), X(cy - 3), X(cx + 3), X(cy - 3)], fill=c, width=X(1.2))
        d.line([X(cx - 3), X(cy + 1), X(cx + 3), X(cy + 1)], fill=c, width=X(1.2))


def render(v: dict, path: str):
    img = background()
    pad = 16

    ink_box = (pad, 118, W - pad, 118 + 180)
    sig_box = (pad, 368, W - pad, 368 + 172)
    cal_box = (pad, 560, W - pad, 560 + 150)
    tab_box = (14, H - 84, W - 14, H - 10)

    card_shadows(img, [ink_box, sig_box, cal_box], v["shadow_style"], v["r_card"])
    d = ImageDraw.Draw(img)
    caption_c = rgb(v["text3"])
    on_ink = (255, 255, 255, int(v["on_ink_cap"] * 255))

    # ── هدر: دکمهٔ تنظیمات + قرص ساعت در سمتِ چپ (چون RTL است) ────────
    btn = v["circle"]
    bx1, bx2 = 18, 18 + btn
    rrect(d, (bx1, 20, bx2, 20 + btn), btn / 2, fill=WHITE, outline=rgb("#D2D2D9"))
    cx, cy = (bx1 + bx2) / 2, 20 + btn / 2
    d.ellipse([X(cx - 6.5), X(cy - 6.5), X(cx + 6.5), X(cy + 6.5)],
              outline=rgb(TEXT2), width=X(1.6))
    d.ellipse([X(cx - 2), X(cy - 2), X(cx + 2), X(cy + 2)], fill=rgb(TEXT2))

    clock = fa("14:32")
    f_clock = font(11)
    cw = width(d, clock, f_clock)
    cl1 = bx2 + 16
    rrect(d, (cl1, 20 + (btn - 30) / 2, cl1 + cw + 22, 20 + (btn + 30) / 2), 15,
          fill=(255, 255, 255, 235), outline=rgb("#D2D2D9"))
    txt(d, (cl1 + 11, 20 + (btn - 30) / 2 + 7), clock, f_clock, rgb(TEXT2))

    txt(d, (W - 18, 24), fa("سلام سوشیان!"), font(21, "Bold"), rgb(TEXT))
    txt(d, (W - 18, 56), fa("دوشنبه ۲ آذر ۱۴۰۴ · ۱۴:۳۲ تهران"),
        font(v["cap"]), caption_c)

    # قرص وضعیت
    st = fa("داور فعال · ۵ سیگنال امروز")
    f_st = font(12, "Bold")
    sw = width(d, st, f_st)
    rrect(d, (W - 18 - sw - 34, 80, W - 18, 107), 13.5, fill=rgb(GREEN_TINT))
    d.ellipse([X(W - 18 - sw - 25), X(91.5), X(W - 18 - sw - 18), X(98.5)],
              fill=rgb(GREEN))
    txt(d, (W - 18 - 12, 85), st, f_st, rgb(GREEN_TEXT))

    # ── کارت جوهری ──────────────────────────────────────────────────
    r_ink = v.get("r_ink", v["r_card"])
    rrect(d, ink_box, r_ink, fill=rgb(INK_CARD), outline=(255, 255, 255, 18))
    if v.get("hero_glow"):
        # همان شفقِ CSS: دو گرادیان شعاعیِ ایندایگو/سیان با آلفای <۱۰٪
        gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gdd = ImageDraw.Draw(gl)
        gdd.ellipse([X(W - 210), X(ink_box[1] - 70), X(W + 10), X(ink_box[1] + 120)],
                    fill=rgb("#7A6CF0") + (84,))
        gdd.ellipse([X(W - 260), X(ink_box[1] + 60), X(W - 40), X(ink_box[3] + 40)],
                    fill=rgb("#46C8E8") + (58,))
        gl = gl.filter(ImageFilter.GaussianBlur(X(34)))
        m = Image.new("L", img.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([X(ink_box[0]), X(ink_box[1]), X(ink_box[2]), X(ink_box[3])],
                                            radius=X(r_ink), fill=255)
        img.paste(Image.alpha_composite(img, Image.composite(gl, Image.new("RGBA", img.size, (0,0,0,0)), m)),
                  (0, 0))
        d = ImageDraw.Draw(img)
    top = ink_box[1]
    txt(d, (W - pad - 16, top + 16), fa("خلاصهٔ امروز"), font(14, "Bold"), WHITE)
    txt(d, (W - pad - 16, top + 38), fa("۵ سیگنال صادر شد · ۲ پوزیشن باز"),
        font(v["cap"] - 0.5), on_ink)
    txt(d, (W - pad - 22, top + 58), "5", font(v.get("ink_num", 30), "Bold"), WHITE)
    txt(d, (W - pad - 60, top + 92), fa("سیگنال"), font(v["cap"]), on_ink)

    tiles_y = ink_box[3] - 16 - 54
    tw = (W - 2 * pad - 32 - 16) / 3
    for i, (num, cap) in enumerate([("+1.84", "بازده (R)"), ("67%", "وین‌ریت"), ("2", "باز")]):
        tx1 = W - pad - 16 - (i + 1) * tw - i * 8
        rrect(d, (tx1, tiles_y, tx1 + tw, tiles_y + 54), 14, fill=rgb(INK_TILE))
        txt(d, (tx1 + tw / 2, tiles_y + 10), num, font(20, "Bold"), WHITE, anchor="ma")
        txt(d, (tx1 + tw / 2, tiles_y + 36), fa(cap), font(10), on_ink, anchor="ma")

    # ── سربرگ بخش + چیپ شمارش ───────────────────────────────────────
    sec_y = 312
    title = fa("سیگنال‌های فعال")
    f_sec = font(v.get("sec_size", 15), "Bold")
    txt(d, (W - pad, sec_y), title, f_sec, rgb(TEXT))
    right = W - pad - width(d, title, f_sec) - 18
    f_cnt = font(11, "Bold")
    cnt = fa("۲")
    cw2 = width(d, cnt, f_cnt)
    rrect(d, (right - cw2 - 18, sec_y + 2, right, sec_y + 24), 11, fill=rgb(RAISED))
    txt(d, (right - 9, sec_y + 6), cnt, f_cnt, rgb(TEXT2))
    txt(d, (right - cw2 - 26, sec_y + 6), fa("امروز"), font(v["cap"]), caption_c)
    # خط موییِ امتداد‌یابنده (v1.4.0) — در نسخهٔ قبل خطی نبود
    if v.get("section_rule"):
        line_end = right - cw2 - 26 - width(d, fa("امروز"), font(v["cap"])) - 10
        d.line([X(pad), X(sec_y + 12), X(line_end), X(sec_y + 12)],
               fill=rgb("#ECECF0"), width=X(1))

    # ── کارت سیگنال ─────────────────────────────────────────────────
    rrect(d, sig_box, v["r_sig"], fill=v["card_fill"], outline=v["card_edge"])
    top = sig_box[1] + 14
    txt(d, (W - pad - 14, top), "XAUUSD", font(15, "Bold"), rgb(TEXT))
    txt(d, (W - pad - 14, top + 22), fa("طلا / دلار آمریکا"), font(v["cap"]), caption_c)
    rrect(d, (pad + 14, top - 1, pad + 14 + 58, top + 23), 12, fill=rgb(GREEN_TINT))
    txt(d, (pad + 14 + 29, top + 3), fa("خرید"), font(12, "Bold"), rgb(GREEN_TEXT), anchor="ma")
    txt(d, (W - pad - 14, top + 42), "2418.60", font(24, "Bold"), rgb(TEXT))

    ty = top + 84
    tw2 = (W - 2 * pad - 28 - 16) / 3
    for i, (cap, val, danger) in enumerate([("ورود", "2412.4", False),
                                            ("حد ضرر", "2398.0", True),
                                            ("هدف", "2447.9", False)]):
        tx1 = W - pad - 14 - (i + 1) * tw2 - i * 8
        rrect(d, (tx1, ty, tx1 + tw2, ty + 56), 12,
              fill=rgb(RED_TINT) if danger else rgb(RAISED))
        txt(d, (tx1 + tw2 / 2, ty + 8), fa(cap), font(v["cap"] - 0.5),
            rgb(RED_TEXT) if danger else caption_c, anchor="ma")
        txt(d, (tx1 + tw2 / 2, ty + 26), val, font(13, "Bold"),
            rgb(RED_TEXT) if danger else rgb(TEXT), anchor="ma")

    # ── کارت تقویم ──────────────────────────────────────────────────
    rrect(d, cal_box, v["r_card"], fill=v["card_fill"], outline=v["card_edge"])
    top = cal_box[1] + 14
    txt(d, (W - pad - 14, top), fa("تقویم امروز"), font(14, "Bold"), rgb(TEXT))
    txt(d, (pad + 14, top + 2), fa("۳ رویداد"), font(v["cap"]), caption_c, anchor="la")
    rows = [("۱۵:۳۰", "سخنرانی فدرال‌رزرو", True),
            ("۱۷:۰۰", "تورم منطقهٔ یورو", False),
            ("۱۹:۴۵", "موجودی نفت آمریکا", False)]
    ry = top + 30
    for i, (t, label, hot) in enumerate(rows):
        if i:
            d.line([X(pad + 14), X(ry - 8), X(W - pad - 14), X(ry - 8)], fill=rgb("#ECECF0"))
        d.ellipse([X(W - pad - 22), X(ry + 4), X(W - pad - 15), X(ry + 11)],
                  fill=rgb("#D64545") if hot else rgb("#94949C") if v["text3"] == "#94949C"
                  else rgb("#6A6A74"))
        txt(d, (W - pad - 30, ry), fa(label), font(12.5), rgb(TEXT))
        txt(d, (pad + 14, ry + 1), t, font(11, "Bold"), rgb(TEXT2), anchor="la")
        ry += 30

    # ── نوار تب ─────────────────────────────────────────────────────
    rrect(d, tab_box, v["r_tab"], fill=v["tab_fill"], outline=(255, 255, 255, 255))
    # RTL: خانه سمت راست است، ژورنال سمت چپ — پس ترتیب رسم برعکس می‌شود
    labels = [("ژورنال", "journal"), ("تقویم", "calendar"), ("سیگنال", "signal"), ("خانه", "home")]
    ix1, ix2 = tab_box[0] + 6, tab_box[2] - 6
    tw3 = (ix2 - ix1) / 4
    for i, (lab, ico) in enumerate(labels):
        tx1 = ix1 + i * tw3
        active = i == len(labels) - 1
        dy = -1 if (active and v["tab_lift"]) else 0
        if active and v.get("tab_horizontal"):
            wide = 104
            px1 = tx1 + tw3 - wide - 2      # چسبیده به لبهٔ راست (RTL)
            rrect(d, (px1, tab_box[1] + 7 + dy, tx1 + tw3 - 2, tab_box[3] - 7 + dy),
                  22, fill=rgb(INK_CARD))
            mid = (tab_box[1] + tab_box[3]) / 2 + dy
            icon(d, ico, px1 + wide - 26, mid, WHITE, True)
            txt(d, (px1 + 14, mid - 8), fa(lab), font(11, "Bold"), WHITE, anchor="la")
            continue
        if active:
            rrect(d, (tx1 + 2, tab_box[1] + 6 + dy, tx1 + tw3 - 2, tab_box[3] - 6 + dy),
                  20, fill=rgb(INK_CARD))
        cxx = tx1 + tw3 / 2
        cyy = (tab_box[1] + tab_box[3]) / 2 + dy
        fg = WHITE if active else rgb(v["text3"])
        icon(d, ico, cxx, cyy - 11, fg, active)
        txt(d, (cxx, cyy + 2), fa(lab), font(9.5, "Bold"), fg, anchor="ma")

    img.convert("RGB").save(path, optimize=True)
    print("→", os.path.relpath(path, ROOT))


BEFORE = dict(cap=10.5, text3="#94949C", circle=40, r_card=22, r_sig=20, r_tab=26,
              on_ink_cap=0.55, tab_lift=False, shadow_style="before",
              card_fill=(255, 255, 255, 235), card_edge=(255, 255, 255, 230),
              tab_fill=(255, 255, 255, 229), section_rule=False)
AFTER15 = dict(cap=11, text3="#6A6A74", circle=44, r_card=22, r_ink=26, r_sig=24, r_tab=28,
               on_ink_cap=0.62, tab_lift=True, shadow_style="after", hero_glow=True,
               ink_num=34, sec_size=16, tab_horizontal=True,
               card_fill=(255, 255, 255, 255), card_edge=(16, 16, 19, 11),
               tab_fill=(255, 255, 255, 240), section_rule=True)

AFTER = dict(cap=11, text3="#6A6A74", circle=44, r_card=22, r_sig=20, r_tab=26,
             on_ink_cap=0.62, tab_lift=True, shadow_style="after",
             card_fill=(255, 255, 255, 255), card_edge=(16, 16, 19, 11),
             tab_fill=(255, 255, 255, 240), section_rule=True)





if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    render(BEFORE, os.path.join(OUT_DIR, "ui-1.3.1-home.png"))
    render(AFTER, os.path.join(OUT_DIR, "ui-1.4.0-home.png"))
    render(AFTER15, os.path.join(OUT_DIR, "ui-1.5.0-home.png"))
