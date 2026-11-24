# -*- coding: utf-8 -*-
"""تولید آیکون‌های ODIN Assistant از نشانِ «پالسِ منفی».

اجرا: python assets/make_icon.py
خروجی: assets/icon.ico (۹ اندازه)، assets/icon.png (۵۱۲) و پنج mipmap لانچر اندروید.
هندسهٔ مشترک در assets/brand_mark.py است.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402

from brand_mark import raster  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MIPMAPS = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def main() -> None:
    master = raster(1024)
    sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40),
             (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(HERE / "icon.ico", format="ICO", sizes=sizes)
    master.resize((512, 512), Image.Resampling.LANCZOS).save(
        HERE / "icon.png", optimize=True)
    res = ROOT / "android" / "app" / "src" / "main" / "res"
    for name, px in MIPMAPS.items():
        master.resize((px, px), Image.Resampling.LANCZOS).save(
            res / ("mipmap-" + name) / "ic_launcher.png", optimize=True)
    print("[make_icon] icon.ico (%d sizes) + icon.png (512) + %d mipmaps"
          % (len(sizes), len(MIPMAPS)))


if __name__ == "__main__":
    main()
