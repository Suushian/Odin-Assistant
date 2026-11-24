# -*- coding: utf-8 -*-
"""تست‌های گزارش بک‌تست — ایرادهای D5، D6، D7.

D5 — هدر گزارش بازهٔ *داده* را به‌جای بازهٔ *شبیه‌سازی* می‌نوشت
     (می‌گفت ۲۰۱۲→۲۰۲۲ در حالی که اجرا ۲۰۱۹–۲۰۲۰ بود).
D6 — متن دلایل رد در قیف، وسط کلمه بریده می‌شد
     («... — تا ۶۰ دقیق»، «... فردا دوباره بررسی م»).
D7 — نمادی که در config بود ولی فایل داده نداشت، بی‌صدا حذف می‌شد.

اجرا: python tests/test_backtest_report.py    (آفلاین)
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("odin_backtest", ROOT / "tools" / "backtest.py")
bt = importlib.util.module_from_spec(_spec)
sys.modules["odin_backtest"] = bt
_spec.loader.exec_module(bt)

CHECKS = 0
FAILED: list[str] = []


def A(cond: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILED.append(label)


# ══════════════════════════════════════════════════════════════
#  D6 — کلید دلیل
# ══════════════════════════════════════════════════════════════
def test_reason_key() -> None:
    print("\n── D6) متن دلیل وسط کلمه بریده نمی‌شود ─────────────────────")
    full = "همین سیگنال ۳۰ دقیقه پیش فرستاده شد — تا ۶۰ دقیقه دیگر دوباره بررسی می‌شود"
    key = bt._reason_key(full)
    A(key == "همین سیگنال ۳۰ دقیقه پیش فرستاده شد", f"بخش متغیر حذف شد: {key}")
    A("—" not in key, "جداکننده در کلید نیست")
    A(all(w in full for w in key.split()), "هیچ کلمهٔ نصفه‌ای در کلید نیست")

    short = "برای EURUSD امروز ۲ سیگنال فرستاده شد (سقف ۲)"
    A(bt._reason_key(short) == short, "متن کوتاه دست‌نخورده می‌ماند")

    long_one = "ک" * 90
    out = bt._reason_key(long_one + " " + "ب" * 10)
    A(out.endswith("…"), "متن بلند با … کوتاه می‌شود")
    A(len(out) <= 61, f"طول کلید محدود است ({len(out)})")

    A(bt._reason_key(None) == "", "None → رشتهٔ خالی (بدون استثنا)")
    A(bt._reason_key("") == "", "رشتهٔ خالی → خالی")

    # همان دلیل با توضیح متغیرِ متفاوت باید یک کلید بدهد (گروه‌بندی درست)
    a = bt._reason_key("سقف ۸ سیگنال در روز پر شده — فردا دوباره بررسی می‌شود")
    b = bt._reason_key("سقف ۸ سیگنال در روز پر شده — امروز دیگر نه")
    A(a == b, "دو روایت از یک قاعده، یک کلید می‌دهند")


# ══════════════════════════════════════════════════════════════
#  D5 — بازهٔ شبیه‌سازی
# ══════════════════════════════════════════════════════════════
def _data() -> dict:
    idx = pd.date_range("2019-01-01", "2021-12-31", freq="15min")
    df = pd.DataFrame({"Open": 1.0, "High": 1.0, "Low": 1.0, "Close": 1.0}, index=idx)
    return {"EURUSD": df}


def test_window_note() -> None:
    print("\n── D5) بازهٔ شبیه‌سازی از بازهٔ داده جدا می‌شود ─────────────")
    data = _data()
    A(bt._window_note(None, None, data) == "2019-01-01 → 2021-12-31",
      "بدون محدوده: کل داده")
    A(bt._window_note(datetime(2020, 1, 1), datetime(2020, 12, 31), data)
      == "2020-01-01 → 2020-12-31", "محدودهٔ داده‌شده")
    A(bt._window_note(datetime(2010, 1, 1), None, data).startswith("2019-01-01"),
      "شروع زودتر از داده → به شروع داده بریده می‌شود")
    A(bt._window_note(None, datetime(2030, 1, 1), data).endswith("2021-12-31"),
      "پایان دیرتر از داده → به پایان داده بریده می‌شود")

    # خروجی نهایی در مارک‌داون
    meta = {"date": "2026-11-24", "data_note": "۲ فایل", "period": "2012-05-15 → 2022-03-04",
            "window": "2019-01-01 → 2021-01-01", "cycle": 30, "slippage": 0.2,
            "missing": []}
    md = bt.render_markdown([], meta)
    A("**بازهٔ شبیه‌سازی:** 2019-01-01 → 2021-01-01" in md, "خط بازهٔ شبیه‌سازی در گزارش")
    A("**بازهٔ کامل داده:** 2012-05-15 → 2022-03-04" in md, "خط بازهٔ داده هم می‌ماند")
    A("نمادهای غایب" not in md, "بدون نماد غایب، هشدار چاپ نمی‌شود")

    meta_old = dict(meta)
    meta_old.pop("window")
    A("**بازهٔ شبیه‌سازی:** 2012-05-15" in bt.render_markdown([], meta_old),
      "گزارش قدیمی (بدون window) هم می‌شکند — به period برمی‌گردد")


# ══════════════════════════════════════════════════════════════
#  D7 — نمادهای غایب
# ══════════════════════════════════════════════════════════════
def test_missing_symbols() -> None:
    print("\n── D7) نماد غایب بی‌صدا حذف نمی‌شود ────────────────────────")
    cfg = {"symbols": [{"name": "EURUSD"}, {"name": "GBPUSD"}, {"name": "NZDUSD"}]}
    data = {"EURUSD": None, "GBPUSD": None}
    got = bt.missing_symbols(cfg, data)
    A(got == ["NZDUSD"], f"فقط NZDUSD غایب است (دریافتی: {got})")
    A(bt.missing_symbols(cfg, {"EURUSD": None, "GBPUSD": None, "NZDUSD": None}) == [],
      "همه حاضر → فهرست خالی")
    A(bt.missing_symbols({}, data) == [], "config بدون symbols → خطا نمی‌دهد")

    meta = {"date": "2026-11-24", "data_note": "۲ فایل", "period": "2019 → 2021",
            "window": "2019 → 2021", "cycle": 30, "slippage": 0.2,
            "missing": got}
    md = bt.render_markdown([], meta)
    A("⚠️ **نمادهای غایب:** NZDUSD" in md, "هشدار در گزارش مارک‌داون هست")


def main() -> int:
    print("=" * 62)
    print("🧪 BACKTEST-REPORT TESTS — D5 (بازه) · D6 (بریدگی متن) · D7 (نماد غایب)")
    print("=" * 62)
    test_reason_key()
    test_window_note()
    test_missing_symbols()
    print("\n" + "=" * 62)
    if FAILED:
        print(f"❌ {len(FAILED)} از {CHECKS} بررسی شکست خورد:")
        for f in FAILED:
            print("   •", f)
        return 1
    print(f"✅ BACKTEST-REPORT TESTS OK — {CHECKS} بررسی پاس")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
