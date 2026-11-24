# -*- coding: utf-8 -*-
"""تست تشخیص مقیاس قیمت در `tools/backtest.py` (ایراد D1).

چرا این تست لازم است؟
    ابزار بک‌تست برای گرفتن اعتبار، به «قیمت واقعی» نیاز دارد: اسپرد و لغزش در
    واحد قیمت اعمال می‌شوند. خروجی متاتریدر قیمت را در *point* می‌دهد
    (`1.12066` → `112066`). در آن حالت R (که نسبی است) سالم به نظر می‌رسد ولی
    هزینه‌ها هزاران بار کوچک‌تر از واقعیت می‌شوند و بک‌تست بی‌سروصدا
    خوش‌بینانه می‌شود.

اندازه‌گیری واقعی روی ۸۱ معامله (۲۰۲۰-۰۱ → ۲۰۲۰-۰۳، EURUSD+XAUUSD):
    دادهٔ خام pointی: میانگین R = −۰٫۰۲۸  ·  دادهٔ درست: −۰٫۱۲۱
    یعنی سوگیری +۰٫۰۹۳R در هر معامله، بدون هیچ هشداری.

اجرا: python tests/test_data_scale.py    (آفلاین، بدون دادهٔ واقعی)
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import numpy as np
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


def frame(close: float, n: int = 600) -> pd.DataFrame:
    """فریم OHLC ساده با میانهٔ تقریبی `close`."""
    rng = np.random.default_rng(7)
    px = close * (1 + rng.normal(0, 0.001, n))
    return pd.DataFrame({"Open": px, "High": px * 1.001,
                         "Low": px * 0.999, "Close": px})


# ══════════════════════════════════════════════════════════════
#  ۱) تشخیص درست روی سه کلاس نماد
# ══════════════════════════════════════════════════════════════
def test_detect_classes() -> None:
    print("\n── ۱) تشخیص مقیاس در سه کلاس نماد ───────────────────────────")
    cases = [
        # (نام، قیمت خام، پیپ، k انتظاری، قیمت نهایی تقریبی)
        ("EURUSD points", 112066.0, 0.0001, 5, 1.12),
        ("USDJPY points", 114854.0, 0.01, 3, 114.8),
        ("XAUUSD points", 155450.0, 1.0, 2, 1554.5),
        ("EURUSD سالم", 1.12066, 0.0001, 0, 1.12),
        ("USDJPY سالم", 114.854, 0.01, 0, 114.8),
        ("XAUUSD سالم", 1554.5, 1.0, 0, 1554.5),
        ("EURUSD کم‌قیمت", 0.5123, 0.0001, 0, 0.51),
        ("XAUUSD ۱۰× بادکرده", 15545.0, 1.0, 1, 1554.5),
    ]
    for name, px, pip, want_k, want_px in cases:
        out, k = bt.scale_fix(frame(px), pip)
        got_px = float(out["Close"].median())
        A(k == want_k, f"{name}: k={k} (انتظار {want_k})")
        A(abs(got_px - want_px) / want_px < 0.01,
          f"{name}: قیمت نهایی {got_px:.4f} ≈ {want_px}")
        A(out["High"].median() > out["Low"].median(), f"{name}: OHLC معتبر ماند")


# ══════════════════════════════════════════════════════════════
#  ۲) حالت‌های مرزی — هیچ‌وقت دادهٔ سالم را خراب نکن
# ══════════════════════════════════════════════════════════════
def test_guards() -> None:
    print("\n── ۲) مرزها: دست‌نزدن به داده‌ای که سالم است ────────────────")
    A(bt.scale_fix(None, 0.0001) == (None, 0), "None → بدون تغییر")
    A(bt.scale_fix(pd.DataFrame(), 0.0001)[1] == 0, "فریم خالی → بدون تغییر")

    out, k = bt.scale_fix(frame(1.1), None)
    A(k == 0, "پیپ نامعلوم (None) → بدون تغییر")
    out, k = bt.scale_fix(frame(1.1), 0.0)
    A(k == 0, "پیپ صفر → بدون تغییر")

    out, k = bt.scale_fix(frame(5000.0), 0.00005)      # کلاس پیپ ناشناخته
    A(k == 0 and float(out["Close"].median()) > 4000, "کلاس پیپ ناشناخته → دست نزن")

    df = frame(1.1)
    out, k = bt.scale_fix(df, 0.0001)
    A(out is df and k == 0, "دادهٔ سالم → همان آبجکت، بدون کپی")

    # هرگز ضرب نمی‌کنیم: قیمت کوچک‌تر از حد معمول نباید بزرگ شود
    small = frame(0.004)
    out, k = bt.scale_fix(small, 0.0001)
    A(k == 0 and float(out["Close"].median()) < 0.01, "قیمت خیلی کوچک → ضرب نمی‌شود")

    # فایل pointی به‌غلطِ بازار دیگر: تقسیم با سقف ۶ صفر متوقف می‌شود
    out, k = bt.scale_fix(frame(1.1e12), 0.0001)
    A(k == 6, "حداکثر ۶ صفر حذف می‌شود (بی‌نهایت حلقه نمی‌زنیم)")


# ══════════════════════════════════════════════════════════════
#  ۳) مسیر واقعی خواندن فایل (read_data)
# ══════════════════════════════════════════════════════════════
def test_read_data_integration() -> None:
    print("\n── ۳) read_data: از فایل تا فریم آماده ──────────────────────")
    rows = ["time,open,high,low,close"]
    rng = np.random.default_rng(3)
    for i in range(600):
        px = 112066.0 * (1 + rng.normal(0, 1e-4))
        t = pd.Timestamp("2020-01-01") + pd.Timedelta(minutes=15 * i)
        rows.append(f"{t:%Y-%m-%d %H:%M:%S},{px:.1f},{px * 1.0002:.1f},"
                    f"{px * 0.9998:.1f},{px:.1f}")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "EURUSD_M15.csv").write_text("\n".join(rows), encoding="utf-8")

        on = bt.read_data(d, "0", pips={"EURUSD": 0.0001}, autoscale=True)
        A("EURUSD" in on, "نماد خوانده شد")
        med = float(on["EURUSD"]["Close"].median())
        A(0.5 < med < 2.5, f"مقیاس خودکار اصلاح شد (میانه={med:.4f})")
        A(on["EURUSD"].index[0] < on["EURUSD"].index[-1], "ایندکس صعودی است")

        off = bt.read_data(d, "0", pips={"EURUSD": 0.0001}, autoscale=False)
        A(float(off["EURUSD"]["Close"].median()) > 1000,
          "با --no-autoscale داده دست‌نخورده می‌ماند")

        none = bt.read_data(d, "0")           # بدون نقشهٔ پیپ
        A(float(none["EURUSD"]["Close"].median()) > 1000,
          "بدون پیپ‌ها (فراخوانی قدیمی) رفتاری عوض نمی‌شود")

    # پوشهٔ خالی → دیکشنری خالی، نه استثنا
    with tempfile.TemporaryDirectory() as tmp:
        A(bt.read_data(Path(tmp), "0") == {}, "پوشهٔ بدون CSV → دیکشنری خالی")


# ══════════════════════════════════════════════════════════════
#  ۴) قالب واقعی متاتریدر (ستون Date + tick_volume)
# ══════════════════════════════════════════════════════════════
def test_mt4_format() -> None:
    print("\n── ۴) قالب خروجی متاتریدر (Date,open,high,low,close,tick_volume) ──")
    rows = ["Date,open,high,low,close,tick_volume"]
    for i in range(600):
        px = 1.12e5 + i * 0.5
        t = pd.Timestamp("2020-01-01") + pd.Timedelta(minutes=15 * i)
        rows.append(f"{t:%Y-%m-%d %H:%M:%S},{px:.0f},{px + 3:.0f},{px - 3:.0f},{px:.0f},100")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "EURUSD_M15.csv").write_text("\n".join(rows), encoding="utf-8")
        df = bt.load_m15(d / "EURUSD_M15.csv")
        A(df is not None and len(df) == 600, "قالب MT4 پذیرفته شد (ستون Date)")
        A(list(df.columns) == ["Open", "High", "Low", "Close"], "نام ستون‌ها استاندارد شد")
        got = bt.read_data(d, "0", pips={"EURUSD": 0.0001})
        A(1.0 < float(got["EURUSD"]["Close"].median()) < 1.3,
          "و در مسیر کامل هم مقیاس اصلاح شد")


def main() -> int:
    print("=" * 62)
    print("🧪 DATA-SCALE TESTS — تشخیص دادهٔ pointی متاتریدر (D1)")
    print("=" * 62)
    test_detect_classes()
    test_guards()
    test_read_data_integration()
    test_mt4_format()
    print("\n" + "=" * 62)
    if FAILED:
        print(f"❌ {len(FAILED)} از {CHECKS} بررسی شکست خورد:")
        for f in FAILED:
            print("   •", f)
        return 1
    print(f"✅ DATA-SCALE TESTS OK — {CHECKS} بررسی پاس؛ دادهٔ pointی "
          f"دیگر بی‌سروصدا نتیجه را خراب نمی‌کند")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
