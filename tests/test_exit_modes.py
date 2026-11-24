# -*- coding: utf-8 -*-
"""تست مدیریت خروج (D8) — نسخهٔ ۱٫۶٫۶.

چرا این تست لازم است؟
    در بک‌تست واقعی ۹۸۴ معامله از ۱٬۶۸۸ با حد ضرر بسته شد و TP=2R فقط ۴۸۸
    بار خورد؛ با نرخ برد ۳۳٫۷٪ و RR=۲ انتظار دقیقاً صفر بود. تنها اهرمِ باقی
    «ساختار خروج» است. اما هر تغییری در حد ضرر، اگر درست پیاده نشود، یا
    نگاه به آینده می‌آورد (حد ضرر وسط همان کندل جابه‌جا شود) یا رفتار قبلی را
    می‌شکند.

اندازه‌گیری واقعی (EURUSD، ۲۰۲۰-۰۱ → ۲۰۲۰-۰۴، ۹۱–۹۳ معامله):
    fixed: میانگین +۰٫۱۴۷R · PF ۱٫۲۹ · افت −۵٫۸R
    be   : میانگین +۰٫۰۵۲R · PF ۱٫۱۱ · افت −۵٫۴R
    trail: میانگین +۰٫۰۴۸R · PF ۱٫۱۱ · افت −۴٫۱R
    ⇒ سربه‌سر/دنباله‌رو، افت را کم می‌کند ولی انتظار را هم می‌خورد.

اجرا: python tests/test_exit_modes.py    (آفلاین)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("odin_backtest", ROOT / "tools" / "backtest.py")
bt = importlib.util.module_from_spec(_spec)
sys.modules["odin_backtest"] = bt
_spec.loader.exec_module(bt)

from src.config import load_config      # noqa: E402

CHECKS = 0
FAILED: list[str] = []

T0 = pd.Timestamp("2024-01-02 10:00")


def A(cond: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILED.append(label)


def mk(mode: str = "fixed"):
    cfg = load_config()
    cfg["symbols"] = [s for s in cfg["symbols"] if s["name"] == "EURUSD"]
    idx = pd.date_range("2024-01-01", periods=600, freq="15min")
    base = 1.1000
    rows = pd.DataFrame({"Open": base, "High": base + 0.0010,
                         "Low": base - 0.0010, "Close": base}, index=idx)
    return bt.Backtest(cfg, {"EURUSD": rows}, label="t", exit_mode=mode)


def make_trade(direction: str = "BUY") -> object:
    """ورود ۱٫۱۰۰۰ · حد ضرر ۱٫۰۹۰۰ (۱R = ۱۰۰ پیپ) · هدف ۱٫۱۲۰۰ (۲R)."""
    if direction == "BUY":
        sl, tp = 1.0900, 1.1200
    else:
        sl, tp = 1.1100, 1.0800
    return bt.Trade(symbol="EURUSD", direction=direction, strategy="breakout",
                    tier="B", score=6, decision_ts=T0, entry_ts=T0,
                    entry=1.1000, sl=sl, tp=tp, risk_units=0.0100,
                    expiry_ts=T0 + pd.Timedelta(hours=72))


def bar(o: float, h: float, l: float, c: float) -> dict:
    return {"Open": o, "High": h, "Low": l, "Close": c}


# ══════════════════════════════════════════════════════════════
#  ۱) پیش‌فرض و انتخاب حالت
# ══════════════════════════════════════════════════════════════
def test_default() -> None:
    print("\n── ۱) پیش‌فرض fixed و حالت نامعتبر ─────────────────────────")
    A(mk().exit_mode == "fixed", "پیش‌فرض fixed است")
    A(mk("be").exit_mode == "be", "be پذیرفته می‌شود")
    A(mk("trail").exit_mode == "trail", "trail پذیرفته می‌شود")
    A(mk("bogus").exit_mode == "fixed", "حالت ناشناخته → fixed (نه استثنا)")
    A(mk("fixed").exit_mode == "fixed", "نمونه‌سازی بدون res هم کار می‌کند")


# ══════════════════════════════════════════════════════════════
#  ۲) fixed = رفتار قبلی
# ══════════════════════════════════════════════════════════════
def test_fixed_untouched() -> None:
    print("\n── ۲) fixed: هیچ حد ضرری جابه‌جا نمی‌شود ────────────────────")
    b = mk("fixed")
    tr = make_trade()
    b._resolve(tr, T0, bar(1.1000, 1.1150, 1.0995, 1.1100))   # +۱٫۵R دیده شد
    A(tr.sl == 1.0900, "حد ضرر دست‌نخورده ماند")
    A(tr.sl_moved is False, "پرچم جابه‌جایی روشن نشد")
    A(tr.best == 0.0, "بهترین قیمت هم ثبت نمی‌شود (هزینهٔ اضافی صفر)")


# ══════════════════════════════════════════════════════════════
#  ۳) be: سربه‌سر در +۱R
# ══════════════════════════════════════════════════════════════
def test_be() -> None:
    print("\n── ۳) be: بعد از +۱R، حد ضرر به نقطهٔ ورود می‌آید ──────────")
    b = mk("be")
    tr = make_trade()
    b._resolve(tr, T0, bar(1.1000, 1.1050, 1.0995, 1.1040))   # فقط +۰٫۵R
    A(tr.sl == 1.0900 and not tr.sl_moved, "زیر +۱R، تغییری نیست")
    b._resolve(tr, T0, bar(1.1040, 1.1105, 1.1030, 1.1090))   # +۱R (۱٫۱۱۰)
    A(tr.sl == 1.1000 and tr.sl_moved, "در +۱R حد ضرر به ورود آمد")
    closed = b._resolve(tr, T0, bar(1.1000, 1.1005, 1.0980, 1.0990))  # برگشت
    A(closed and tr.result in ("SL", "GAP_SL") and abs(tr.exit - 1.1000) < 1e-9,
      f"برگشت → بسته‌شدن روی سربه‌سر (نتیجه: {tr.result})")

    # جهت SELL آینه است
    s = mk("be")
    tr2 = make_trade("SELL")
    s._resolve(tr2, T0, bar(1.1000, 1.1005, 1.0895, 1.0905))
    A(tr2.sl == 1.1000 and tr2.sl_moved, "SELL: در +۱R حد ضرر به ورود آمد")

    # هرگز عقب‌تر نمی‌رود
    tr3 = make_trade()
    b._resolve(tr3, T0, bar(1.1000, 1.1110, 1.0990, 1.1100))
    A(tr3.sl == 1.1000, "حد ضرر جابه‌جا شد")
    b._resolve(tr3, T0, bar(1.1100, 1.1105, 1.1090, 1.1100))
    A(tr3.sl == 1.1000, "حد ضرر هرگز عقب نمی‌رود")


# ══════════════════════════════════════════════════════════════
#  ۴) trail: ۱R پشت بهترین قیمت
# ══════════════════════════════════════════════════════════════
def test_trail() -> None:
    print("\n── ۴) trail: حد ضرر ۱R پشت بهترین قیمت ────────────────────")
    b = mk("trail")
    tr = make_trade()
    b._resolve(tr, T0, bar(1.1000, 1.1100, 1.0995, 1.1090))   # +۱R
    A(abs(tr.sl - 1.1000) < 1e-9, "در +۱R: حد ضرر روی سربه‌سر")
    b._resolve(tr, T0, bar(1.1090, 1.1160, 1.1085, 1.1150))   # +۱٫۶R
    A(abs(tr.sl - 1.1060) < 1e-9, f"حد ضرر ۱R پشت سقف (۱٫۱۰۶۰) — دریافت {tr.sl:.4f}")
    closed = b._resolve(tr, T0, bar(1.1150, 1.1155, 1.1055, 1.1060))
    A(closed and tr.result == "SL" and tr.r > 0.5,
      f"خروج با سود قفل‌شده (R={tr.r:+.2f})")

    s = mk("trail")
    tr2 = make_trade("SELL")
    s._resolve(tr2, T0, bar(1.1000, 1.1005, 1.0900, 1.0910))
    A(abs(tr2.sl - 1.1000) < 1e-9, "SELL: حد ضرر روی سربه‌سر")
    s._resolve(tr2, T0, bar(1.0910, 1.0915, 1.0840, 1.0850))
    A(abs(tr2.sl - 1.0940) < 1e-9, f"SELL: ۱R پشت کف (۱٫۰۹۴۰) — دریافت {tr2.sl:.4f}")


# ══════════════════════════════════════════════════════════════
#  ۵) بدون نگاه به آینده
# ══════════════════════════════════════════════════════════════
def test_no_lookahead() -> None:
    print("\n── ۵) کندلی که هم هدف و هم حد ضرر را دارد ──────────────────")
    b = mk("be")
    tr = make_trade()
    # کندلِ بزرگ: سقف +۱٫۵R و کف زیر حد ضرر اولیه
    closed = b._resolve(tr, T0, bar(1.1000, 1.1150, 1.0890, 1.1100))
    A(closed and tr.result == "SL" and abs(tr.exit - 1.0900) < 1e-9,
      "حد ضرر اولیه اول اعمال می‌شود (بدبینانه، نه سربه‌سر)")
    A(not tr.sl_moved, "چون همان کندل بسته شد، جابه‌جایی ثبت نمی‌شود")

    b2 = mk("be")
    tr2 = make_trade()
    closed2 = b2._resolve(tr2, T0, bar(1.1000, 1.1210, 1.0995, 1.1200))
    A(closed2 and tr2.result == "TP", "لمس هدف همان کندل → TP، نه سربه‌سر")


# ══════════════════════════════════════════════════════════════
#  ۶) شمارنده در گزارش
# ══════════════════════════════════════════════════════════════
def test_counter() -> None:
    print("\n── ۶) شمارندهٔ «مدیریت خروج» در stats ──────────────────────")
    b = mk("be")
    b.res = bt.Result(label="t")
    tr = make_trade()
    b._resolve(tr, T0, bar(1.1000, 1.1105, 1.0990, 1.1095))   # +۱R → سربه‌سر
    b._resolve(tr, T0, bar(1.1095, 1.1100, 1.0985, 1.0990))   # خروج
    A(b.res.managed == 1, f"یک معاملهٔ مدیریت‌شده شمرده شد ({b.res.managed})")
    st = b.res.stats()
    A("managed" in st and st["managed"] == 1, "کلید managed در stats هست")

    b2 = mk("fixed")
    b2.res = bt.Result(label="t")
    tr2 = make_trade()
    b2._resolve(tr2, T0, bar(1.1000, 1.1105, 1.0990, 1.1095))
    A(b2.res.managed == 0, "در حالت fixed شمارنده صفر می‌ماند")


def main() -> int:
    print("=" * 62)
    print("🧪 EXIT-MODE TESTS — fixed · be · trail (D8)")
    print("=" * 62)
    test_default()
    test_fixed_untouched()
    test_be()
    test_trail()
    test_no_lookahead()
    test_counter()
    print("\n" + "=" * 62)
    if FAILED:
        print(f"❌ {len(FAILED)} از {CHECKS} بررسی شکست خورد:")
        for f in FAILED:
            print("   •", f)
        return 1
    print(f"✅ EXIT-MODE TESTS OK — {CHECKS} بررسی پاس؛ fixed دست‌نخورده، "
          f"be/trail بدون نگاه به آینده")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
