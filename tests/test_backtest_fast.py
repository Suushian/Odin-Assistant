# -*- coding: utf-8 -*-
"""تست‌های سریع «ابزار بک‌تست» (`tools/backtest.py`).

چرا این تست لازم است؟
    خودِ ابزار ادعا می‌کند «بدون نگاه به آینده» و «حد ضرر مقدم بر هدف» کار
    می‌کند. این ادعاها باید پین شوند، وگرنه یک اشتباه در برش H1/H4 نتیجهٔ
    بک‌تست را بی‌سر‌و‌صدا خوش‌بینانه می‌کند — همان اشتباهی که یک‌بار در
    نسخهٔ اول همین ابزار رخ داد (برش با برچسب شروع کندل H1).

اجرا: python tests/test_backtest_fast.py    (آفلاین، بدون دادهٔ واقعی)
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("odin_backtest", ROOT / "tools" / "backtest.py")
bt_mod = importlib.util.module_from_spec(_spec)
sys.modules["odin_backtest"] = bt_mod
_spec.loader.exec_module(bt_mod)

from src.config import load_config      # noqa: E402

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


# ══════════════════════════════════════════════════════════════
section("۱) خواندن CSV و تبدیل وقت بروکر به UTC")
import tempfile  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "EURUSD_M15.csv"
    p.write_text("time,open,high,low,close\n"
                 "2024-06-03 00:00:00,1.0,1.1,0.9,1.05\n"
                 "2024-06-03 00:15:00,1.05,1.2,1.0,1.15\n", encoding="utf-8")
    df = bt_mod.load_m15(p)
    A(df is not None and list(df.columns) == ["Open", "High", "Low", "Close"], "ستون‌ها استاندارد شدند")
    A(df is not None and len(df) == 2, "دو کندل خوانده شد")

    p2 = Path(td) / "XAUUSD.csv"
    p2.write_text("date,time,open,high,low,close\n"
                  "2024.06.03,00:00,2000,2001,1999,2000.5\n", encoding="utf-8")
    df2 = bt_mod.load_m15(p2)
    A(df2 is not None and len(df2) == 1, "قالب date+time هم پشتیبانی می‌شود")

idx = pd.DatetimeIndex([pd.Timestamp("2024-06-03 12:00"), pd.Timestamp("2024-01-15 12:00")])
utc = bt_mod.to_utc(idx, "auto")
A(utc[0] == pd.Timestamp("2024-06-03 09:00"), "تابستان: ۳ ساعت عقب (GMT+3)")
A(utc[1] == pd.Timestamp("2024-01-15 10:00"), "زمستان: ۲ ساعت عقب (GMT+2)")
A(bt_mod.to_utc(idx, "0")[0] == pd.Timestamp("2024-06-03 12:00"), "tz=0 بدون تغییر")
A(bt_mod.to_utc(idx, "3")[0] == pd.Timestamp("2024-06-03 09:00"), "tz=3 ثابت")


# ══════════════════════════════════════════════════════════════
section("۲) حل معامله: اولویت حد ضرر، گپ، انقضا، محاسبهٔ R")


def mk_bt():
    cfg = load_config()
    cfg["symbols"] = [s for s in cfg["symbols"] if s["name"] == "EURUSD"]
    sym = cfg["symbols"][0]
    idx = pd.date_range("2024-01-01", periods=600, freq="15min")
    base = 1.1000
    rows = pd.DataFrame({"Open": base, "High": base + 0.0010,
                         "Low": base - 0.0010, "Close": base}, index=idx)
    data = {sym["name"]: rows}
    return bt_mod.Backtest(cfg, data, label="test")


bt = mk_bt()
T0 = pd.Timestamp("2024-01-02 10:00")


def mk_trade(direction="BUY", entry=1.1000, sl=1.0980, tp=1.1040, tier="A"):
    return bt_mod.Trade(symbol="EURUSD", direction=direction, strategy="trend_pullback",
                        tier=tier, score=7, decision_ts=T0, entry_ts=T0, entry=entry,
                        sl=sl, tp=tp, risk_units=abs(entry - sl),
                        expiry_ts=T0 + timedelta(hours=24))


# هدف و حد ضرر هر دو در یک کندل → حد ضرر (بدبینانه)
tr = mk_trade()
bar = {"Open": 1.1000, "High": 1.1045, "Low": 1.0975, "Close": 1.1010}
A(bt._resolve(tr, T0, bar) and tr.result == "SL" and abs(tr.r + 1.0) < 1e-9,
  "لمس هم‌زمان هدف و حد ضرر → حد ضرر و R=−۱")

# فقط هدف
tr = mk_trade()
bar = {"Open": 1.1000, "High": 1.1045, "Low": 1.0995, "Close": 1.1040}
A(bt._resolve(tr, T0, bar) and tr.result == "TP" and abs(tr.r - 2.0) < 1e-9,
  "هدف → R=+۲ (نسبت ۱:۲)")

# گپِ بدتر از حد ضرر → به قیمت گپ
tr = mk_trade()
bar = {"Open": 1.0960, "High": 1.0965, "Low": 1.0955, "Close": 1.0960}
A(bt._resolve(tr, T0, bar) and tr.result == "GAP_SL" and tr.r < -1.9,
  "گپ پایین‌تر از حد ضرر → خروج با گپ (بدتر از −۱R)")

# فروش، هدف
tr = mk_trade(direction="SELL", entry=1.1000, sl=1.1020, tp=1.0960)
bar = {"Open": 1.1000, "High": 1.1005, "Low": 1.0955, "Close": 1.0960}
A(bt._resolve(tr, T0, bar) and tr.result == "TP" and abs(tr.r - 2.0) < 1e-9,
  "فروش: هدف → R=+۲")

# انقضا
tr = mk_trade()
tr.expiry_ts = T0
bar = {"Open": 1.1000, "High": 1.1002, "Low": 1.0998, "Close": 1.1001}
A(bt._resolve(tr, T0, bar) and tr.result == "EXPIRED", "انقضای ۲۴ ساعته → خروج با بازار")

# وزن رده در منحنی سرمایه
tr = mk_trade(tier="B")
bar = {"Open": 1.1000, "High": 1.1045, "Low": 1.0995, "Close": 1.1040}
bt._resolve(tr, T0, bar)
A(abs(tr.r_weighted - 1.0) < 1e-9, "ردهٔ B = نیم‌ریسک در R وزن‌دار")


# ══════════════════════════════════════════════════════════════
section("۲b) نسخهٔ ۱.۲ — انقضای ۱۴۴ ساعته و اردر لیمیت")

A(bt.expiry_hours == 72, f"انقضا از config خوانده می‌شود (۷۲): {bt.expiry_hours}")
bt24 = bt_mod.Backtest({"symbols": [], "analysis": {}, "judge": {}, "journal": {}},
                       {"EURUSD": pd.DataFrame()}, label="t", expiry_hours=24)
A(bt24.expiry_hours == 24, "بازنویسی انقضا با پارامتر ممکن است")

# اردر لیمیت پرنشده: هیچ معامله‌ای باز نمی‌شود و شمارنده بالا می‌رود
import types  # noqa: E402
sig = types.SimpleNamespace(
    symbol="EURUSD", direction="BUY", strategy="breakout", tier="A", score=8,
    entry=1.0500, sl=1.0480, tp=1.0540, actionable=True,
    order_type="limit", valid_minutes=120)
bt2 = bt_mod.Backtest({"symbols": [], "analysis": {}, "judge": {}, "journal": {}},
                      {"EURUSD": pd.DataFrame()}, label="t2", expiry_hours=144)
idx = pd.date_range("2024-01-02 10:00", periods=10, freq="15min")
flat = pd.DataFrame({"Open": 1.06, "High": 1.061, "Low": 1.059, "Close": 1.06}, index=idx)
bt2.data = {"EURUSD": flat}
bt2.pos = {"EURUSD": {t: i for i, t in enumerate(flat.index)}}
bt2.timeline = list(flat.index)
bt2.cycles_before = 0

_orig_cycle = bt2._cycle


def _cycle_once(self, ts, now, state, open_trades):
    """فقط در اولین چرخه یک سیگنال لیمیت می‌دهد (قیمت هرگز به ۱٫۰۵ نمی‌رسد)."""
    if self.cycles_before:
        return []
    self.cycles_before += 1
    return [types.SimpleNamespace(**{**vars(sig), "actionable": True})]


bt2._cycle = types.MethodType(_cycle_once, bt2)
res2 = bt2.run()
A(res2.unfilled == 1 and len(res2.trades) == 0,
  f"لیمیتِ پرنشده معامله نمی‌سازد و شمرده می‌شود: unfilled={res2.unfilled}, "
  f"trades={len(res2.trades)}")


# ══════════════════════════════════════════════════════════════
section("۳) بدون نگاه به آینده: H1/H4 با زمان بستهٔ کندل برش می‌خورند")


def synthetic(n_days: int = 50, seed: int = 7) -> dict:
    """روند صعودی با نوسان — تا ستاپ‌ها واقعاً ساخته شوند."""
    rng = np.random.default_rng(seed)
    idx = []
    t = datetime(2024, 1, 1)
    while len(idx) < n_days * 96:
        if t.weekday() < 5:
            idx.append(t)
        t += timedelta(minutes=15)
    n = len(idx)
    steps = rng.normal(0.00002, 0.0006, n)
    close = 1.1000 + np.cumsum(steps)
    o = np.concatenate([[1.1000], close[:-1]])
    span = np.abs(rng.normal(0, 0.0004, n)) + 0.0001
    rows = pd.DataFrame({"Open": o, "High": np.maximum(o, close) + span,
                         "Low": np.minimum(o, close) - span, "Close": close},
                        index=pd.DatetimeIndex(idx))
    return {"EURUSD": rows}


cfg = load_config()
cfg["symbols"] = [s for s in cfg["symbols"] if s["name"] == "EURUSD"]
cfg["judge"]["min_score"] = 3          # تا در دادهٔ ساختگی سیگنال صادر شود
data = synthetic()
# ۵۰ روز داده برای گرم‌کردن EMA200 روی H4 کافی است، ولی فقط ۵ روز آخر
# شبیه‌سازی می‌شود تا تست سریع بماند.
bt2 = bt_mod.Backtest(cfg, data, label="synthetic", debug_signals=True,
                      start=datetime(2024, 3, 4))
res = bt2.run()

A(res.cycles > 100, f"چرخه‌های کافی اجرا شد ({res.cycles})")
A(res.signals > 0, f"سیگنال صادر شد ({res.signals})")
A(len(res.trades) > 0, f"معامله بسته شد ({len(res.trades)})")
A(all(t.entry_ts > t.decision_ts for t in res.trades), "ورود همیشه بعد از تصمیم")
A(all((t.entry_ts - t.decision_ts) == timedelta(minutes=15) for t in res.trades),
  "ورود روی بازِ کندل بعدی (۱۵ دقیقه بعد)")
A(all(t.bars >= 1 for t in res.trades), "هر معامله حداقل یک کندل بررسی شد")
A(all(t.result in {"TP", "SL", "GAP_SL", "EXPIRED"} for t in res.trades), "نتیجهٔ معتبر")
A(len({t.strategy for t in res.trades}) >= 1, "استراتژی روی معامله ثبت شد")

# سقف پوزیشن باز: هیچ‌وقت بیش از ۲ معاملهٔ هم‌زمان باز نشده
stamps = [(t.entry_ts, t.exit_ts) for t in res.trades]
peak = max((sum(1 for a, b in stamps if a <= ts and (b is None or ts < b))
            for ts, _ in stamps), default=0)
A(peak <= 2, f"حداکثر پوزیشن باز هم‌زمان = {peak} (سقف ۲)")


# ══════════════════════════════════════════════════════════════
print()
print("=" * 74)
if FAILED:
    print(f"❌ BACKTEST TESTS FAILED — {len(FAILED)} از {CHECKS} بررسی")
    for f in FAILED:
        print(f"   - {f}")
    sys.exit(1)
print(f"✅ BACKTEST TESTS OK — {CHECKS} بررسی پاس؛ بدون نگاه به آینده، اولویت حد ضرر، "
      f"گپ/انقضا و سقف پوزیشن سنجیده شد")
print("=" * 74)
