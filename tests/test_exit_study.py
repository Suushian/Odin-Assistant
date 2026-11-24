# -*- coding: utf-8 -*-
"""تست‌های سریع «مطالعهٔ خروج» (`tools/exit_study.py`).

چرا این تست لازم است؟
    این ابزار تصمیم «کدام قانون خروج سود بیشتری دارد» را می‌گیرد؛ اگر خودش
    اشتباه شبیه‌سازی کند، نتیجهٔ مطالعه بی‌اعتبار است. اینجا با کندل‌های
    دست‌ساز پین می‌شود: اولویت حد ضرر، سربه‌سر، ترییلینگ، خروج جزئی، انقضا،
    ورود لیمیت و سقف پوزیشن.

اجرا: python tests/test_exit_study.py    (آفلاین، بدون دادهٔ بازار)
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


es = _load("odin_exit_study", "tools/exit_study.py")

CHECKS = 0
FAILED: list[str] = []


def A(cond: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILED.append(label)


def section(title: str) -> None:
    print()
    print("-" * 74)
    print(title)
    print("-" * 74)


POL = es.POLICIES
T0 = pd.Timestamp("2024-06-03 09:00")
STEP = timedelta(minutes=15)


def bars(rows):
    """rows = [(open, high, low), ...] → آرایه‌های numpy + مهر زمانی."""
    o = np.array([r[0] for r in rows], dtype=float)
    h = np.array([r[1] for r in rows], dtype=float)
    l = np.array([r[2] for r in rows], dtype=float)
    t = np.array([np.datetime64(T0 + STEP * i) for i in range(len(rows))],
                 dtype="datetime64[ns]")
    return o, h, l, t


# ══════════════════════════════════════════════════════════════
section("۱) هدف و حد ضرر — و اولویت حد ضرر در یک کندل")

o, h, l, t = bars([(1.0000, 1.0012, 0.9991),      # کندل ورود (حد ضرر لمس نشود)
                   (1.0010, 1.0025, 1.0008),      # رسیدن به ۲R (۱٫۰۰۲۰)
                   (1.0020, 1.0025, 1.0015)])
r = es.simulate(o, h, l, t, 0, "BUY", 1.0000, 0.9990, 0.0010,
                T0 + timedelta(hours=24), POL["base"])
A(r is not None and r["result"] == "TP" and abs(r["r"] - 2.0) < 1e-9,
  f"هدف ۲R دقیقاً +۲R می‌دهد: {r}")

# همان کندل هم هدف و هم حد ضرر → حد ضرر (بدبینانه)
o, h, l, t = bars([(1.0000, 1.0050, 1.0000),
                   (1.0010, 1.0030, 0.9980)])
r = es.simulate(o, h, l, t, 1, "BUY", 1.0000, 0.9995, 0.0005,
                T0 + timedelta(hours=24), POL["base"])
A(r is not None and r["result"] == "SL" and abs(r["r"] + 1.0) < 1e-9,
  f"تعارض درون‌کندلی → حد ضرر: {r}")

# گپ بدتر از حد ضرر
o, h, l, t = bars([(1.0000, 1.0050, 1.0000), (0.9980, 0.9985, 0.9975)])
r = es.simulate(o, h, l, t, 1, "BUY", 1.0000, 0.9995, 0.0005,
                T0 + timedelta(hours=24), POL["base"])
A(r is not None and r["result"] == "GAP_SL" and r["r"] < -1.0,
  f"گپ → ضرر بزرگ‌تر از ۱R: {r}")


# ══════════════════════════════════════════════════════════════
section("۲) سربه‌سر، ترییلینگ و خروج جزئی")

# +۱R می‌زند، برمی‌گردد → سربه‌سر (۰R نه −۱R)
o, h, l, t = bars([(1.0000, 1.0002, 0.9998),
                   (1.0005, 1.0010, 1.0004),     # فقط +۱R (نه ۲R)
                   (1.0008, 1.0010, 0.9985)])    # شکست ورود (و حد ضرر)
r = es.simulate(o, h, l, t, 1, "BUY", 1.0000, 0.9990, 0.0010,
                T0 + timedelta(hours=48), POL["be1"])
A(r is not None and abs(r["r"]) < 1e-9, f"سربه‌سر: خروج روی نقطهٔ ورود: {r}")
r0 = es.simulate(o, h, l, t, 1, "BUY", 1.0000, 0.9990, 0.0010,
                 T0 + timedelta(hours=48), POL["base"])
A(r0 is not None and r0["r"] < -0.9, f"بدون سربه‌سر همان مسیر −۱R می‌شد: {r0}")

# +۲R می‌زند، بعد تا ۱٫۶R برمی‌گردد → ترییلینگ ۰٫۵R روی ~۱٫۵R می‌بندد
o, h, l, t = bars([(1.0000, 1.0002, 0.9998),
                   (1.0010, 1.0020, 1.0008),     # +۲R (سقف ۱٫۰۰۲۰)
                   (1.0025, 1.0026, 1.0010)])    # افت تا ۱٫۰۰۱۰
# سیاست بدون هدف، وگرنه هدف ۲R پیش از ترییلینگ شلیک می‌کند
TRAIL_ONLY = es.Policy("trail_only", "تریلینگ بدون هدف", tp_r=None, be_at=1.0,
                       trail_after=1.5, trail_dist=0.5, expiry_h=48.0)
r = es.simulate(o, h, l, t, 1, "BUY", 1.0000, 0.9990, 0.0010,
                T0 + timedelta(hours=48), TRAIL_ONLY)
A(r is not None and 1.4 <= r["r"] <= 1.6,
  f"تریلینگ ۰٫۵R بعد از سقف ۲R → حدود +۱٫۵R: {r}")

# خروج جزئی: نصف در ۱R، بعد سربه‌سر → +۰٫۵R
o, h, l, t = bars([(1.0000, 1.0002, 0.9998),
                   (1.0005, 1.0010, 1.0004),     # +۱R → نصف خارج
                   (1.0008, 1.0010, 0.9985)])    # بازگشت به ورود → بقیه سربه‌سر
r = es.simulate(o, h, l, t, 1, "BUY", 1.0000, 0.9990, 0.0010,
                T0 + timedelta(hours=48), POL["partial1"])
A(r is not None and abs(r["r"] - 0.5) < 1e-6,
  f"نصف در ۱R + بقیه سربه‌سر → +۰٫۵R: {r}")


# ══════════════════════════════════════════════════════════════
section("۳) انقضا و جهت فروش")

o, h, l, t = bars([(1.0000, 1.0001, 0.9999)] * 8)
r = es.simulate(o, h, l, t, 0, "BUY", 1.0000, 0.9990, 0.0010,
                T0 + timedelta(hours=1), POL["base"])
A(r is not None and r["result"] == "EXPIRED", f"انقضای یک‌ساعته شلیک شد: {r}")

o, h, l, t = bars([(1.0000, 1.0001, 0.9999), (0.9990, 0.9995, 0.9970)])
r = es.simulate(o, h, l, t, 1, "SELL", 1.0000, 1.0010, 0.0010,
                T0 + timedelta(hours=48), POL["base"])
A(r is not None and r["result"] == "TP" and abs(r["r"] - 2.0) < 1e-9,
  f"فروش: افت ۲R = سود +۲R: {r}")


# ══════════════════════════════════════════════════════════════
section("۴) موتور مطالعه: ورود لیمیت، سقف پوزیشن، فیلترها")

# بار ساختگی: ۱۰ کندل ۱۵ دقیقه‌ای، قیمت ثابت ۱٫۱۰۰۰ با نوسان کوچک
idx = pd.DatetimeIndex([T0 + STEP * i for i in range(12)])
fake = {
    "EURUSD": {
        "ts": idx.values.astype("datetime64[ns]"),
        "o": np.array([1.1000] * 12), "h": np.array([1.1005] * 12),
        "l": np.array([1.0995] * 12), "pip": 0.0001,
    }
}

sig = pd.DataFrame([
    # سه سیگنال هم‌زمان → با سقف ۲ پوزیشن، سومی نباید معامله شود
    dict(now=T0 + STEP, symbol="EURUSD", strategy="breakout", dir="BUY",
         score=9, tier="A", entry=1.1000, sl=1.0990, adx=30.0, sent=True),
    dict(now=T0 + STEP, symbol="EURUSD", strategy="trend_pullback", dir="BUY",
         score=6, tier="B", entry=1.1000, sl=1.0990, adx=22.0, sent=True),
    dict(now=T0 + STEP, symbol="EURUSD", strategy="range_reversion", dir="SELL",
         score=5, tier="B", entry=1.1000, sl=1.1010, adx=15.0, sent=True),
])
SHORT_POL = es.Policy("short", "انقضای ۳۰ دقیقه", tp_r=2.0, expiry_h=0.5)
s = es.run_policy(sig, fake, {"EURUSD": 0.8}, 0.2, SHORT_POL, 2, 0, set())
A(s["trades"] == 2 and s["blocked_capacity"] == 1,
  f"سقف ۲ پوزیشن: دو معامله و یکی مسدود: {s['trades']}/{s['blocked_capacity']}")

# ورود لیمیت شکست: با قیمت لیمیتِ بیرون از دامنه، پر نمی‌شود
sig2 = sig.iloc[[0]].copy()
sig2.loc[:, "entry"] = 1.0900      # لیمیت خرید زیر دامنه → پر نمی‌شود
s2 = es.run_policy(sig2, fake, {"EURUSD": 0.8}, 0.2, SHORT_POL, 2, 4, {"breakout"})
A(s2["trades"] == 0 and s2["unfilled_limit"] == 1,
  f"لیمیت پرنشده شمارش می‌شود: {s2['trades']}/{s2['unfilled_limit']}")

# ورود لیمیت شکست: قیمت لیمیت داخل دامنه → پرشدن روی همان قیمت
s3 = es.run_policy(sig.iloc[[0]], fake, {"EURUSD": 0.8}, 0.2, SHORT_POL, 2, 4,
                   {"breakout"})
A(s3["trades"] == 1 and s3["unfilled_limit"] == 0,
  f"لیمیت داخل دامنه پر می‌شود: {s3['trades']}")

# فیلترها: فقط شکست، حداقل ADX ۲۵، فقط ردهٔ A
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "sig.csv"
    sig.assign(sent="True").to_csv(p, index=False)

    class Args:
        only_strategies = exclude_strategies = exclude_symbols = tiers = ""
        min_score = None
        min_adx = None
        hours = ""

    A(len(es.load_signals([p], Args())) == 3, "بدون فیلتر: هر سه سیگنال")
    Args.only_strategies = "breakout"
    A(len(es.load_signals([p], Args())) == 1, "فیلتر استراتژی")
    Args.only_strategies = ""
    Args.min_adx = 25.0
    A(len(es.load_signals([p], Args())) == 1, "فیلتر ADX")
    Args.min_adx = None
    Args.tiers = "B"
    A(len(es.load_signals([p], Args())) == 2, "فیلتر رده")
    Args.tiers = ""
    Args.hours = "9-9"
    A(len(es.load_signals([p], Args())) == 3, "فیلتر ساعت (۰۹:۱۵ UTC)")

# سیاست‌های پیش‌ثبت‌شده کامل‌اند
A({"base", "tp15", "be1", "exp48", "partial1", "trail"} <= set(POL),
  "سیاست‌های کلیدی موجودند")
A(all(p.expiry_h > 0 for p in POL.values()), "انقضای همهٔ سیاست‌ها مثبت است")


# ══════════════════════════════════════════════════════════════
print()
print("=" * 74)
if FAILED:
    print(f"❌ EXIT STUDY TESTS FAILED — {len(FAILED)} از {CHECKS}")
    for f in FAILED:
        print("   •", f)
    raise SystemExit(1)
print(f"✅ EXIT STUDY TESTS OK — {CHECKS} بررسی پاس؛ سربه‌سر/تریلینگ/جزئی/انقضا/"
      f"اولویت حد ضرر/لیمیت/سقف پوزیشن سنجیده شد")
print("=" * 74)
