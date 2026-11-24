# -*- coding: utf-8 -*-
"""بک‌تست آفلاین موتور سیگنال روی کندل‌های M15 تاریخی.

چرا این ابزار؟
    «سیگنال بیشتر» یک ادعا بود؛ بدون اجرای موتور روی دادهٔ تاریخی هیچ عددی
    پشتش نیست. این اسکریپت *همان کد تولید* را اجرا می‌کند (نه بازنویسی):
        analyze_symbol → currency_strength → judge_all
        → should_send_signal / _daily_cap_block (قواعد ضداسپم واقعی)
    و بعد هر سیگنالِ ارسال‌شده را با کندل‌های بعدی تا حد ضرر/هدف/انقضا
    تعقیب می‌کند تا نرخ برد و R واقعی به دست آید.

اصول صحتی که رعایت می‌شود:
    ۱) بدون نگاه به آینده: تصمیم روی کندلِ بستهٔ `ts` گرفته می‌شود؛ H1/H4 با
       «زمان بستهٔ» کندل برش می‌خورند (H1 برچسب ۰۹:۰۰ تا ۱۰:۰۰ کامل نیست)،
       و ورود روی *باز* کندل بعدی انجام می‌شود.
    ۲) H1/H4 با همان تابع تولید (`TwelveDataSource._resample_m15`) ساخته
       می‌شوند؛ فقط گروه‌های کامل، دقیقاً مثل اپ.
    ۳) اگر در یک کندل هم حد ضرر و هم هدف لمس شود، **حد ضرر** فرض می‌شود
       (بدبینانه). گپِ بازشدن بدتر از حد ضرر، به قیمت همان گپ بسته می‌شود.
    ۴) ۱R = فاصلهٔ «ورودِ برنامه − حد ضرر» (ریسک سیگنال)، نه فاصلهٔ پرشدن.
    ۵) اسپرد و لغزش به‌صورت هزینهٔ ورود (پیپ) کم می‌شوند.

آنچه شبیه‌سازی *نمی‌شود* (باید در تفسیر حساب شود):
    • تقویم/اخبار: دادهٔ تاریخی تقویم در دسترس نیست → وتوی رویداد شلیک
      نمی‌شود و مدرک «پنجرهٔ فاندامنتال پاک (+۲)» همیشه داده می‌شود →
      **خوش‌بینانه**.
    • تاییدیهٔ تریدینگ‌ویو: در دسترس نیست → مدرک TV صفر می‌شود (سقف امتیاز
      همچنان ۱۱ می‌ماند) → **بدبینانه**.
    • ارسال تلگرام: اگر قواعد ضداسپم اجازه بدهند، «ارسال‌شده» فرض می‌شود.

ورودی: پوشه‌ای از CSV با ستون‌های time/open/high/low/close
        (نام فایل `EURUSD_M15.csv` یا `EURUSD.csv`).
اجرا:
    python tools/backtest.py --data-dir ~/odin-m15 --out reports/backtest
    python tools/backtest.py --data-dir ~/odin-m15 --legacy       # فقط ۱.۰
    python tools/backtest.py --data-dir ~/odin-m15 --jobs 2 --debug-signals
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analysis.strength import currency_strength                      # noqa: E402
from src.analysis.technical import analyze_symbol                         # noqa: E402
from src.config import load_config                                        # noqa: E402
from src.data.base import MarketData                                      # noqa: E402
from src.data.twelvedata_source import TwelveDataSource                   # noqa: E402
from src.engine import (_apply_capacity, _daily_cap_block, _sends_today,   # noqa: E402
                        _signal_state_key, should_send_signal)
from src.judge.scoring import JudgeContext, judge_all                     # noqa: E402
from src.judge.session import market_status                                # noqa: E402

OHLC = ["Open", "High", "Low", "Close"]
EMPTY = pd.DataFrame(columns=OHLC)

# اسپرد پیش‌فرض (پیپ) — تقریب خرد؛ با --spread قابل بازنویسی است.
DEFAULT_SPREAD = {
    "EURUSD": 0.8, "GBPUSD": 1.0, "AUDUSD": 1.0, "NZDUSD": 1.3,
    "USDCAD": 1.2, "USDCHF": 1.2, "USDJPY": 0.9, "EURJPY": 1.4,
    "EURGBP": 1.2, "XAUUSD": 2.5,
}
DEFAULT_SLIPPAGE = 0.2          # پیپ، یک‌طرفه

# وزن ریسک هر رده در منحنی سرمایه (۰ = فقط پیگیری، فارغ از نتیجه)
TIER_RISK = {"A": 1.0, "B": 0.5, "C": 0.0, "": 1.0}


# ══════════════════════════════════════════════════════════════
#  خواندن داده + تبدیل وقت بروکر به UTC
# ══════════════════════════════════════════════════════════════
def _last_sunday(year: int, month: int) -> datetime:
    d = datetime(year, month, 31)
    while d.weekday() != 6:
        d -= timedelta(days=1)
    return d


def _eu_offsets(year: int) -> tuple[datetime, datetime]:
    """(شروع تابستان، پایان تابستان) ساعت ۰۱:۰۰ UTC."""
    return (_last_sunday(year, 3).replace(hour=1), _last_sunday(year, 10).replace(hour=1))


def to_utc(idx: pd.DatetimeIndex, mode: str) -> pd.DatetimeIndex:
    """تبدیل «وقت بروکر» به UTC.

    mode: ``auto`` = GMT+2 زمستان و +3 تابستان (رایج‌ترین تنظیم MT4/MT5)،
    یا عدد ثابت (``0``، ``2``، ``3``).
    """
    idx = pd.DatetimeIndex(idx)
    if idx.tz is not None:
        return idx.tz_convert("UTC").tz_localize(None)
    if mode in ("auto", "broker"):
        out = []
        for t in idx:
            start, end = _eu_offsets(t.year)
            out.append(t - timedelta(hours=3 if start <= t < end else 2))
        return pd.DatetimeIndex(out)
    return idx - timedelta(hours=float(mode))


def load_m15(path: Path) -> Optional[pd.DataFrame]:
    """CSV کندل → DataFrame با ایندکس زمانی و ستون‌های Open/High/Low/Close."""
    try:
        raw = pd.read_csv(path)
    except Exception as e:                                   # pragma: no cover
        print(f"   [!] {path.name}: خوانده نشد ({e})")
        return None
    cols = {str(c).strip().lower(): c for c in raw.columns}
    if "time" in cols and "date" not in cols:
        stamps = pd.to_datetime(raw[cols["time"]], errors="coerce", utc=True)
    elif "datetime" in cols:
        stamps = pd.to_datetime(raw[cols["datetime"]], errors="coerce", utc=True)
    elif "date" in cols and "time" in cols:
        stamps = pd.to_datetime(raw[cols["date"]].astype(str).str.replace(".", "-", regex=False)
                                + " " + raw[cols["time"]].astype(str),
                                errors="coerce", utc=True)
    elif "date" in cols:
        stamps = pd.to_datetime(raw[cols["date"]].astype(str), errors="coerce", utc=True)
    else:
        print(f"   [!] {path.name}: ستون زمان پیدا نشد")
        return None
    if getattr(stamps.dt, "tz", None) is not None:
        stamps = stamps.dt.tz_convert("UTC").dt.tz_localize(None)
    need = {k: cols.get(k) for k in ("open", "high", "low", "close")}
    if any(v is None for v in need.values()):
        print(f"   [!] {path.name}: ستون‌های OHLC ناقص است")
        return None
    df = pd.DataFrame({c: pd.to_numeric(raw[need[c.lower()]], errors="coerce")
                       for c in ("open", "high", "low", "close")})
    df["__ts"] = stamps
    df = df.dropna().set_index("__ts")
    df = df.loc[~df.index.duplicated(keep="last")].sort_index()
    df.columns = OHLC
    return df[df["High"] >= df["Low"]]


def read_data(data_dir: Path, tz_mode: str) -> dict[str, pd.DataFrame]:
    """همهٔ فایل‌های M15 پوشه را می‌خواند: {نماد: DataFrame(UTC)}."""
    out: dict[str, pd.DataFrame] = {}
    for path in sorted(data_dir.glob("*.csv")):
        stem = path.stem.upper()
        if stem.endswith("_M5") or stem.endswith("_H1") or stem.endswith("_H4"):
            continue
        symbol = stem[:-4] if stem.endswith("_M15") else stem
        df = load_m15(path)
        if df is None or len(df) < 500:
            continue
        df.index = to_utc(df.index, tz_mode)
        df = df.sort_index()
        out[symbol] = df
        print(f"   ✓ {symbol:<8} {len(df):>6} کندل  {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d}")
    return out


# ══════════════════════════════════════════════════════════════
#  معامله‌ها
# ══════════════════════════════════════════════════════════════
@dataclass
class Trade:
    symbol: str
    direction: str
    strategy: str
    tier: str
    score: int
    decision_ts: datetime
    entry_ts: datetime
    entry: float
    sl: float
    tp: float
    risk_units: float                       # ۱R = |ورود برنامه − حد ضرر|
    expiry_ts: datetime
    plan_entry: float = 0.0                 # قیمت مرجع سیگنال (قبل از پرشدن)
    exit_ts: Optional[datetime] = None
    exit: float = 0.0
    result: str = ""                        # TP | SL | GAP_SL | EXPIRED
    bars: int = 0
    r: float = 0.0                          # خالص (با اسپرد/لغزش)
    r_gross: float = 0.0                    # ناخالص: از قیمت مرجع سیگنال، بدون هزینه
    r_weighted: float = 0.0

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol, "direction": self.direction,
            "strategy": self.strategy, "tier": self.tier, "score": self.score,
            "decision": self.decision_ts.strftime("%Y-%m-%d %H:%M"),
            "entry_ts": self.entry_ts.strftime("%Y-%m-%d %H:%M"),
            "exit_ts": self.exit_ts.strftime("%Y-%m-%d %H:%M") if self.exit_ts else "",
            "plan_entry": round(self.plan_entry, 5),
            "entry": round(self.entry, 5), "sl": round(self.sl, 5), "tp": round(self.tp, 5),
            "exit": round(self.exit, 5), "result": self.result, "bars": self.bars,
            "r": round(self.r, 3), "r_gross": round(self.r_gross, 3),
            "r_weighted": round(self.r_weighted, 3),
        }


# ══════════════════════════════════════════════════════════════
#  نتیجه
# ══════════════════════════════════════════════════════════════
@dataclass
class Result:
    label: str
    trades: list[Trade] = field(default_factory=list)
    signals: int = 0
    signals_actionable: int = 0
    cycles: int = 0
    judgments: int = 0
    days: int = 1
    seat_stolen: int = 0
    unfilled: int = 0                      # نسخهٔ ۱.۲ — اردر لیمیت پرنشده
    funnel: Counter = field(default_factory=Counter)
    vetoes: Counter = field(default_factory=Counter)
    strategy_pick: Counter = field(default_factory=Counter)
    tiers: Counter = field(default_factory=Counter)
    suppress: Counter = field(default_factory=Counter)
    per_day: list = field(default_factory=list)
    config_note: dict = field(default_factory=dict)

    def stats(self) -> dict:
        t = [x for x in self.trades if x.result]
        wins = [x for x in t if x.r > 0]
        losses = [x for x in t if x.r <= 0]
        gross_win = sum(x.r for x in wins)
        gross_loss = -sum(x.r for x in losses)
        total_r = sum(x.r for x in t)
        weighted = sum(x.r_weighted for x in t)
        peak = eq = mdd = 0.0
        for x in sorted(t, key=lambda y: y.exit_ts or y.entry_ts):
            eq += x.r_weighted
            peak = max(peak, eq)
            mdd = min(mdd, eq - peak)

        def group(key):
            d = defaultdict(list)
            for x in t:
                d[key(x)].append(x)
            return {k: {"trades": len(v),
                        "win_rate": sum(1 for r in v if r.r > 0) / len(v),
                        "avg_r": sum(r.r for r in v) / len(v),
                        "total_r": sum(r.r for r in v)}
                    for k, v in sorted(d.items())}

        res = Counter(x.result for x in t)
        # فاصلهٔ قیمتِ پرشدن از قیمت مرجع سیگنال — اگر بزرگ باشد یعنی قیمت
        # مرجع سیگنال (کلوز H1) کهنه است و SL/TP حول قیمت واقعی نبسته‌اند.
        slips = sorted(abs(x.entry - x.plan_entry) for x in t if x.plan_entry)
        med_slip = slips[len(slips) // 2] if slips else 0.0
        return {
            "trades": len(t), "open_at_end": len(self.trades) - len(t),
            "wins": len(wins), "losses": len(losses),
            "hit_rate": (len(wins) / len(t)) if t else 0.0,
            "tp": res.get("TP", 0), "sl": res.get("SL", 0), "gap_sl": res.get("GAP_SL", 0),
            "expired": res.get("EXPIRED", 0),
            "avg_r": (total_r / len(t)) if t else 0.0,
            "avg_r_gross": (sum(x.r_gross for x in t) / len(t)) if t else 0.0,
            "avg_cost_r": ((total_r - sum(x.r_gross for x in t)) / len(t)) if t else 0.0,
            "total_r": total_r, "total_r_weighted": weighted,
            "profit_factor": (gross_win / gross_loss) if gross_loss else float("inf"),
            "max_dd_r": mdd,
            "avg_bars": (sum(x.bars for x in t) / len(t)) if t else 0,
            "signals": self.signals, "signals_actionable": self.signals_actionable,
            "unfilled": self.unfilled,
            "signals_per_day": self.signals / max(1, self.days),
            "trades_per_day": len(t) / max(1, self.days),
            "per_strategy": group(lambda x: x.strategy or "-"),
            "per_tier": group(lambda x: x.tier or "-"),
            # v1.6.0 — سه برش تشخیصی که برای «قدرت سیگنال» تصمیم‌سازند:
            #   per_score  → کدام امتیاز واقعاً سود می‌دهد (کالیبراسیون آستانه)
            #   per_hour   → کدام ساعت‌ها انتظار منفی دارند (گیت سشن)
            #   per_weekday→ کدام روزهای هفته (دوشنبه/جمعه معمولاً متفاوت‌اند)
            "per_score": group(lambda x: str(int(x.score))),
            "per_hour": group(lambda x: f"{x.entry_ts.hour:02d}"),
            "per_weekday": group(lambda x: str(x.entry_ts.weekday())),
            "per_symbol": group(lambda x: x.symbol),
            "per_direction": group(lambda x: x.direction),
            "funnel": dict(self.funnel), "vetoes": dict(self.vetoes),
            "strategy_pick": dict(self.strategy_pick), "tiers": dict(self.tiers),
            "suppress": dict(self.suppress),
            "median_slip_abs": med_slip,
            "mean_slip_abs": (sum(slips) / len(slips)) if slips else 0.0,
            "cycles": self.cycles, "judgments": self.judgments, "days": self.days,
            "seat_stolen": self.seat_stolen, "config_note": self.config_note,
        }


# ══════════════════════════════════════════════════════════════
#  اجرای بک‌تست
# ══════════════════════════════════════════════════════════════
_W_BT = None            # ارجاع سراسریِ کپی‌شده در فرزندهای fork (بدون pickle داده)


def _worker_analyze(args):
    """تحلیل یک نماد در پروسهٔ کارگر (داده با fork به ارث رسیده)."""
    name, ts, now = args
    return _W_BT.analyze_one(name, ts, now)


class Backtest:
    """شبیه‌ساز چرخه‌های تولید روی دادهٔ تاریخی."""

    WINDOW_M15 = 3800           # ≈ ۴۰ روز: کافی برای EMA200 روی H4
    WINDOW_H1 = 300
    WINDOW_H4 = 300
    CYCLE_MINUTES = 30
    BAR_MINUTES = 15

    def __init__(self, cfg: dict, data: dict[str, pd.DataFrame], *,
                 start: Optional[datetime] = None, end: Optional[datetime] = None,
                 spread: Optional[dict] = None, slippage: float = DEFAULT_SLIPPAGE,
                 label: str = "baseline", verbose_every: int = 0,
                 debug_signals: bool = False,
                 expiry_hours: float | None = None):
        self.cfg = cfg
        self.label = label
        self.verbose_every = verbose_every
        self.debug_rows = [] if debug_signals else None
        self.spread = spread or DEFAULT_SPREAD
        # نسخهٔ ۱.۲ — انقضا از config می‌آید (پیش‌فرض تولید: ۱۴۴ ساعت).
        jcfg = (cfg.get("journal") or {})
        self.expiry_hours = float(expiry_hours if expiry_hours is not None
                                  else jcfg.get("expiry_hours", 24))
        self.slippage = slippage
        self.pool = None
        sym_cfg = {s["name"]: s for s in cfg["symbols"]}
        self.symbols = [n for n in sym_cfg if n in data]
        self.sym_cfg = {n: sym_cfg[n] for n in self.symbols}
        self.data = data
        # H1/H4 یک‌بار با همان تابع تولید ساخته می‌شوند، بعد فقط برش می‌خورند.
        self.h1 = {n: TwelveDataSource._resample_m15(data[n], 1) for n in self.symbols}
        self.h4 = {n: TwelveDataSource._resample_m15(data[n], 4) for n in self.symbols}
        self.pos = {n: {t: i for i, t in enumerate(data[n].index)} for n in self.symbols}
        stamps = sorted({t for n in self.symbols for t in data[n].index
                         if (start is None or t >= start) and (end is None or t <= end)})
        self.timeline = stamps

    # ── تحلیل یک نماد (در همین پروسه یا کارگر) ───────────────
    def analyze_one(self, name: str, ts, now):
        """(SymbolAnalysis, MarketData) در لحظهٔ ts — فقط داده‌های بسته‌شده."""
        i = self.pos[name].get(ts)
        if i is None or i + 1 < self.WINDOW_M15:
            return (None, None)
        naive = now.replace(tzinfo=None)          # ایندکس داده‌ها UTC بدون tz است
        m15 = self.data[name].iloc[i + 1 - self.WINDOW_M15:i + 1]
        # ⚠️ برش H1/H4 با «زمان بستهٔ» کندل، نه برچسب شروع: کندل H1 با برچسب
        #    ۰۹:۰۰ تا ۱۰:۰۰ کامل نیست. برش با `ts` یعنی ۴۵ دقیقه نگاه به آینده.
        h1i = self.h1[name].index.searchsorted(naive - timedelta(hours=1), side="right")
        h4i = self.h4[name].index.searchsorted(naive - timedelta(hours=4), side="right")
        if h1i < 220 or h4i < 220:                # گرم‌کردن EMA200
            return (None, None)
        h1 = self.h1[name].iloc[max(0, h1i - self.WINDOW_H1):h1i]
        h4 = self.h4[name].iloc[max(0, h4i - self.WINDOW_H4):h4i]
        if self.debug_rows is not None:
            assert m15.index[-1] == ts, "نگاه به آینده در M15"
            assert h1.index[-1] + timedelta(hours=1) <= naive, "نگاه به آینده در H1"
            assert h4.index[-1] + timedelta(hours=4) <= naive, "نگاه به آینده در H4"
        md = MarketData(name, m15, h1, h4)
        try:
            a = analyze_symbol(self.sym_cfg[name], md, self.cfg["analysis"],
                               self.cfg.get("strategies") or {})
        except Exception:                          # pragma: no cover
            return (None, None)
        # فقط H1 برای وتوی «جهش نوسان» لازم است؛ فرستادن سه DataFrame به
        # پروسهٔ والد گران است، پس نسخهٔ سبک برمی‌گردانیم.
        return (a, MarketData(name, EMPTY, h1, EMPTY))

    # ── یک چرخه: تحلیل → داوری → قواعد ارسال ────────────────
    def _cycle(self, ts, now, state: dict, open_trades: list[Trade]) -> list:
        tasks = [(n, ts, now) for n in self.symbols if ts in self.pos[n]]
        if not tasks:
            return []
        if self.pool is not None and len(tasks) > 1:
            results = self.pool.map(_worker_analyze, tasks)
        else:
            results = [self.analyze_one(*t) for t in tasks]
        datasets, analyses = {}, []
        for (name, _ts, _now), (a, md) in zip(tasks, results):
            if a is None:
                continue
            datasets[name] = md
            analyses.append(a)
        if not analyses:
            return []

        cfg = self.cfg
        try:
            ranking = currency_strength(datasets, lookback_h1=int(
                cfg["analysis"].get("strength_lookback_h1", 24)))
        except Exception:                          # pragma: no cover
            ranking = []
        ctx = JudgeContext(
            jcfg=cfg["judge"], acfg=cfg["analysis"], symbols_cfg=cfg["symbols"],
            scfg=cfg.get("strategies") or {}, ranking=ranking,
            tv_map={}, cal_snap=None, news_snap=None,
            now=now, status=market_status(now),
            event_veto_minutes=float((cfg.get("fundamental") or {}).get("veto_minutes_before", 30)),
            calendar_enabled=False,                # تقویم تاریخی در دسترس نیست
        )
        judgments = judge_all(analyses, datasets, ctx)
        self.res.judgments += len(judgments)
        for j in judgments:
            self.res.funnel[j.reject_reason or "SIGNAL"] += 1
            for v in j.vetoes:
                self.res.vetoes[v.key] += 1
            if j.signal is not None:
                self.res.tiers[j.tier or "-"] += 1
                self.res.strategy_pick[j.signal.strategy or "-"] += 1

        signals = [j.signal for j in judgments if j.signal]
        dbg_by_sig = {}
        if self.debug_rows is not None:
            by_sym = {a.symbol: a for a in analyses}
            for j in judgments:
                if j.signal is None:
                    continue
                a = by_sym[j.symbol]
                su = getattr(a, "active_setup", None)
                sg = j.signal
                row = {
                    "now": now.strftime("%Y-%m-%d %H:%M"), "symbol": j.symbol,
                    "strategy": sg.strategy, "dir": sg.direction, "score": sg.score,
                    "atr": round(float(a.atr or 0.0), 7), "price": a.price,
                    "entry": sg.entry, "sl": sg.sl, "tp": sg.tp,
                    "risk_pips": round(sg.risk_pips, 2), "rr": sg.rr,
                    "stop_ref": getattr(su, "stop_ref", None),
                    "support": a.support, "resistance": a.resistance,
                    "adx": round(float(getattr(a, "adx", 0.0) or 0.0), 2),
                    "rsi": round(float(getattr(a, "rsi", 50.0) or 50.0), 2),
                    "tier": sg.tier, "actionable": sg.actionable,
                    # این دو ستون بعد از تصمیم ارسال پر می‌شوند (مطالعات فیلتر)
                    "sent": False, "suppress": "",
                }
                dbg_by_sig[id(sg)] = row
                self.debug_rows.append(row)
        if not signals:
            return []

        jcfg = cfg["judge"]
        pcfg = jcfg.get("portfolio") or {}
        limit = int(pcfg.get("max_open_positions", 0) or 0)
        enforce = bool(pcfg.get("enforce_capacity", True)) and limit > 0
        free = max(0, limit - len(open_trades))
        today = _sends_today(state, now)
        ordered = sorted(signals, key=lambda s: (0 if getattr(s, "tier", "") == "A" else 1,
                                                 -s.score))
        sent = []
        for sig in ordered:
            block = _daily_cap_block(sig, today, pcfg)
            go, why = should_send_signal(state, sig, jcfg, now=now)
            if go and block:
                go, why = False, block
            # نسخهٔ ۱.۱.۱: همان تابع موتور، تا شبیه‌ساز و موتور یک قاعده داشته
            # باشند (صندلی فقط با ارسال واقعی مصرف می‌شود).
            free = _apply_capacity(sig, go, free, enforce, limit)
            row = dbg_by_sig.get(id(sig))
            if row is not None:
                row["sent"] = bool(go)
                row["suppress"] = "" if go else str(why)[:64]
            if go:
                state[_signal_state_key(sig)] = {"ts": now.isoformat(), "score": sig.score}
                sent.append(sig)
                self.res.signals += 1
                if sig.actionable:
                    self.res.signals_actionable += 1
            else:
                self.res.suppress[str(why)[:48]] += 1
                if sig.actionable:
                    self.res.seat_stolen += 1     # نباید رخ دهد (۱.۱.۱ به بعد)
        return sent

    # ── بستن معامله با کندل‌های بعدی ─────────────────────────
    def _close(self, tr: Trade, ts, price: float, result: str) -> bool:
        tr.exit_ts, tr.exit, tr.result = ts, price, result
        move = (price - tr.entry) if tr.direction == "BUY" else (tr.entry - price)
        tr.r = move / tr.risk_units if tr.risk_units else 0.0
        if tr.plan_entry:
            gross = (price - tr.plan_entry) if tr.direction == "BUY" else (tr.plan_entry - price)
            tr.r_gross = gross / tr.risk_units if tr.risk_units else 0.0
        else:
            tr.r_gross = tr.r
        tr.r_weighted = tr.r * TIER_RISK.get(tr.tier, 1.0)
        return True

    def _resolve(self, tr: Trade, ts, bar) -> bool:
        o, h, l = float(bar["Open"]), float(bar["High"]), float(bar["Low"])
        tr.bars += 1
        if tr.direction == "BUY":
            if o <= tr.sl:                         # گپ بدتر از حد ضرر
                return self._close(tr, ts, o, "GAP_SL")
            if l <= tr.sl:
                return self._close(tr, ts, tr.sl, "SL")
            if h >= tr.tp:
                return self._close(tr, ts, tr.tp, "TP")
        else:
            if o >= tr.sl:
                return self._close(tr, ts, o, "GAP_SL")
            if h >= tr.sl:
                return self._close(tr, ts, tr.sl, "SL")
            if l <= tr.tp:
                return self._close(tr, ts, tr.tp, "TP")
        if ts >= tr.expiry_ts:                     # انقضای ۲۴ ساعته (مثل ژورنال)
            return self._close(tr, ts, o, "EXPIRED")
        return False

    # ── حلقهٔ اصلی ───────────────────────────────────────────
    def run(self) -> Result:
        self.res = Result(label=self.label, config_note={
            "min_score": self.cfg["judge"].get("min_score"),
            "tiers": bool((self.cfg["judge"].get("tiers") or {}).get("enabled")),
            "portfolio": self.cfg["judge"].get("portfolio"),
            "cooldown_min": self.cfg["judge"].get("resend_cooldown_minutes"),
            "max_per_cycle": self.cfg["judge"].get("max_signals_per_cycle"),
            "strategies": self.cfg.get("strategies"),
            "symbols": self.symbols,
            "spread": {k: self.spread.get(k) for k in self.symbols},
            "slippage": self.slippage,
            "expiry_hours": self.expiry_hours,
        })
        state: dict = {}
        open_trades: list[Trade] = []
        pending: dict = {}                     # ts → [(نماد, سیگنال)]
        # نسخهٔ ۱.۲ — اردرهای لیمیت منتظر پرشدن (per symbol)
        pending_limits: list[dict] = []
        day_counts: Counter = Counter()
        step = timedelta(minutes=self.BAR_MINUTES)

        for ts in self.timeline:
            # ۱) ورودهای معلق (بازِ همین کندل) — یعنی سیگنالِ کندل قبل
            for name, sig in pending.pop(ts, []):
                bar = self.data[name].loc[ts]
                pip = float(self.sym_cfg[name]["pip"])
                cost = (self.spread.get(name, 1.0) / 2 + self.slippage) * pip
                entry = float(bar["Open"]) + (cost if sig.direction == "BUY" else -cost)
                risk = abs(float(sig.entry) - float(sig.sl))
                if risk <= 0:
                    continue
                open_trades.append(Trade(
                    symbol=name, direction=sig.direction, strategy=sig.strategy,
                    tier=getattr(sig, "tier", "") or "", score=sig.score,
                    decision_ts=ts - step, entry_ts=ts, entry=entry,
                    sl=sig.sl, tp=sig.tp, risk_units=risk,
                    plan_entry=float(sig.entry),
                    expiry_ts=ts + timedelta(hours=self.expiry_hours)))

            # ۱b) اردرهای لیمیت: پرشدن روی همین کندل یا انقضای سفارش
            if pending_limits:
                keep_limits = []
                for o in pending_limits:
                    sym, sig = o["symbol"], o["sig"]
                    if ts <= o["decision"] or ts not in self.pos.get(sym, {}):
                        keep_limits.append(o)
                        continue
                    bar = self.data[sym].loc[ts]
                    buy = sig.direction == "BUY"
                    filled = (float(bar["Low"]) <= float(sig.entry) if buy
                              else float(bar["High"]) >= float(sig.entry))
                    if filled:
                        risk = abs(float(sig.entry) - float(sig.sl))
                        if risk > 0:
                            open_trades.append(Trade(
                                symbol=sym, direction=sig.direction,
                                strategy=sig.strategy, tier=getattr(sig, "tier", "") or "",
                                score=sig.score, decision_ts=o["decision"],
                                entry_ts=ts, entry=float(sig.entry),
                                sl=sig.sl, tp=sig.tp, risk_units=risk,
                                plan_entry=float(sig.entry),
                                expiry_ts=ts + timedelta(hours=self.expiry_hours)))
                        continue                    # سفارش مصرف شد
                    if ts >= o["deadline"]:
                        self.res.unfilled += 1      # لیمیت تا مهلت پر نشد
                        continue
                    keep_limits.append(o)
                pending_limits = keep_limits

            # ۲) تعقیب معامله‌های باز روی همین کندل
            still = []
            for tr in open_trades:
                if tr.entry_ts > ts:
                    still.append(tr)
                    continue
                idx = self.pos[tr.symbol]
                if ts not in idx:
                    still.append(tr)
                    continue
                if not self._resolve(tr, ts, self.data[tr.symbol].loc[ts]):
                    still.append(tr)
                else:
                    self.res.trades.append(tr)
            open_trades = still

            # ۳) چرخهٔ تصمیم هر ۳۰ دقیقه — روی کندلِ تازه‌بسته‌شده
            if ts.minute % self.CYCLE_MINUTES == 0:
                now = ts.to_pydatetime().replace(tzinfo=timezone.utc) + step
                self.res.cycles += 1
                sent = self._cycle(ts, now, state, open_trades)
                for sig in sent:
                    if not sig.actionable:
                        continue
                    # نسخهٔ ۱.۲ — ستاپ‌های لیمیت تا پرشدن صبر می‌کنند
                    if (getattr(sig, "order_type", "market") == "limit"
                            and int(getattr(sig, "valid_minutes", 0) or 0) > 0):
                        pending_limits.append({
                            "symbol": sig.symbol, "sig": sig, "decision": ts,
                            "deadline": ts + step + timedelta(
                                minutes=int(sig.valid_minutes))})
                        continue
                    nxt = ts + step
                    if nxt in self.pos.get(sig.symbol, {}):
                        pending.setdefault(nxt, []).append((sig.symbol, sig))
                    day_counts[now.strftime("%Y-%m-%d")] += 1
                if self.verbose_every and self.res.cycles % self.verbose_every == 0:
                    print(f"   … {now:%Y-%m-%d %H:%M} | چرخه {self.res.cycles} | "
                          f"سیگنال {self.res.signals} | بسته‌شده {len(self.res.trades)}")

        # معامله‌های باز در پایان دوره: با آخرین قیمت بسته می‌شوند
        for tr in open_trades:
            last = self.data[tr.symbol].index[-1]
            self._close(tr, last, float(self.data[tr.symbol]["Close"].iloc[-1]), "EXPIRED")
            self.res.trades.append(tr)

        self.res.days = max(1, len(pd.date_range(self.timeline[0], self.timeline[-1], freq="B")))
        self.res.per_day = sorted(day_counts.values(), reverse=True)
        return self.res


# ══════════════════════════════════════════════════════════════
#  گزارش
# ══════════════════════════════════════════════════════════════
def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _table(rows: list[tuple], head: list[str]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def render_markdown(results: list[Result], meta: dict) -> str:
    L = [f"# بک‌تست موتور سیگنال — {meta['date']}", ""]
    L += [f"- **داده:** {meta['data_note']}",
          f"- **بازه:** {meta['period']}",
          f"- **چرخه:** هر {meta['cycle']} دقیقه، ورود روی بازِ کندل ۱۵ دقیقه‌ای بعد",
          f"- **هزینه:** اسپرد/۲ + {meta['slippage']} پیپ لغزش در هر طرف",
          "- **شبیه‌سازی‌نشده:** تقویم/خبر (مدرک +۲ همیشه داده می‌شود → خوش‌بینانه) و "
          "تریدینگ‌ویو (مدرک صفر → بدبینانه)", ""]
    L += ["## خلاصه", ""]
    head = ["سناریو", "سیگنال", "سیگنال/روز", "معامله", "نرخ برد", "میانگین R",
            "مجموع R", "R وزن‌دار", "PF", "حداکثر افت"]
    rows = []
    for r in results:
        s = r.stats()
        rows.append([r.label, s["signals"], f"{s['signals_per_day']:.2f}", s["trades"],
                     _pct(s["hit_rate"]), f"{s['avg_r']:+.3f}", f"{s['total_r']:+.1f}",
                     f"{s['total_r_weighted']:+.1f}",
                     ("∞" if s["profit_factor"] == float("inf") else f"{s['profit_factor']:.2f}"),
                     f"{s['max_dd_r']:+.1f}"])
    L += _table(rows, head) + [""]
    for r in results:
        s = r.stats()
        L += [f"## جزئیات — {r.label}", "",
              f"{s['cycles']} چرخه · {s['judgments']} قضاوت · {s['days']} روز معاملاتی · "
              f"سیگنال {s['signals']} (قابل اقدام {s['signals_actionable']})", ""]
        for title, key, head2 in (
            ("به تفکیک استراتژی", "per_strategy",
             ["استراتژی", "معامله", "نرخ برد", "میانگین R", "مجموع R"]),
            ("به تفکیک رده", "per_tier",
             ["رده", "معامله", "نرخ برد", "میانگین R", "مجموع R"]),
            ("به تفکیک جهت", "per_direction",
             ["جهت", "معامله", "نرخ برد", "میانگین R", "مجموع R"]),
            ("به تفکیک نماد", "per_symbol",
             ["نماد", "معامله", "نرخ برد", "میانگین R", "مجموع R"]),
        ):
            L += [f"### {title}", ""]
            L += _table([[k, v["trades"], _pct(v["win_rate"]), f"{v['avg_r']:+.3f}",
                          f"{v['total_r']:+.1f}"] for k, v in s[key].items()], head2) + [""]
        for title, key, head3 in (
            ("به تفکیک امتیاز", "per_score",
             ["امتیاز", "معامله", "نرخ برد", "میانگین R", "مجموع R"]),
            ("به تفکیک ساعت ورود (UTC)", "per_hour",
             ["ساعت", "معامله", "نرخ برد", "میانگین R", "مجموع R"]),
            ("به تفکیک روز هفته", "per_weekday",
             ["روز (۰=دوشنبه)", "معامله", "نرخ برد", "میانگین R", "مجموع R"]),
        ):
            L += [f"### {title}", ""]
            L += _table([[k, v["trades"], _pct(v["win_rate"]), f"{v['avg_r']:+.3f}",
                          f"{v['total_r']:+.1f}"] for k, v in s[key].items()], head3) + [""]
        L += ["### قیف و ردها", "",
              "- نتیجهٔ داوری: " + "، ".join(f"{k}={v}" for k, v in s["funnel"].items()),
              "- وتوها: " + ("، ".join(f"{k}={v}" for k, v in s["vetoes"].items()) or "—"),
              "- انتخاب استراتژی: " + "، ".join(f"{k}={v}" for k, v in s["strategy_pick"].items()),
              "- دلایل سرکوب ارسال: " + ("، ".join(f"{k} ({v})" for k, v in s["suppress"].items()) or "—"),
              f"- خروجی: TP={s['tp']} · SL={s['sl']} · گپ‌استاپ={s['gap_sl']} · "
              f"منقضی={s['expired']} · میانگین نگهداری {s['avg_bars']:.0f} کندل", ""]
        if s["seat_stolen"]:
            L += [f"⚠️ {s['seat_stolen']} بار صندلی ظرفیت را سیگنالی گرفت که ارسال نشد.", ""]
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════
#  v1.6.0 — جاروی آستانهٔ امتیاز (min_score sweep)
# ══════════════════════════════════════════════════════════════
#  چرا: آستانهٔ ۵ از یازده، یک عددِ دستی است. با یک اجرا می‌توان دید
#  کدام آستانه در همان دادهٔ واقعی انتظار مثبت می‌دهد — بدون تغییر config.
def sweep_min_scores(cfg: dict, data: dict, values, *, start=None, end=None,
                     spread: Optional[dict] = None, slippage: float = DEFAULT_SLIPPAGE):
    """اجرای پیاپی بک‌تست با آستانه‌های مختلف روی *همان* داده."""
    import copy
    out = []
    for v in values:
        c = copy.deepcopy(cfg)
        c.setdefault("judge", {})["min_score"] = int(v)
        bt = Backtest(c, data, start=start, end=end,
                      spread=spread or DEFAULT_SPREAD, slippage=slippage,
                      label=f"min_score={int(v)}")
        out.append((int(v), bt.run()))
    return out


def sweep_pick(pairs, min_trades: int = 100):
    """بهترین آستانه: بیشترین میانگین R میان گزینه‌هایی که نمونهٔ کافی دارند."""
    ok = [(v, r.stats()) for v, r in pairs if r.stats()["trades"] >= min_trades]
    if not ok:
        return None
    return max(ok, key=lambda p: p[1]["avg_r"])[0]


def render_sweep(pairs, meta: dict, min_trades: int = 100) -> str:
    """گزارش مارک‌داون جاروی آستانه."""
    head = ["آستانه", "سیگنال", "سیگنال/روز", "معامله", "نرخ برد", "میانگین R",
            "مجموع R", "PF", "حداکثر افت"]
    rows = []
    for v, r in pairs:
        s = r.stats()
        rows.append([v, s["signals"], f"{s['signals_per_day']:.2f}", s["trades"],
                     _pct(s["hit_rate"]), f"{s['avg_r']:+.3f}", f"{s['total_r']:+.1f}",
                     ("∞" if s["profit_factor"] == float("inf") else f"{s['profit_factor']:.2f}"),
                     f"{s['max_dd_r']:+.1f}"])
    pick = sweep_pick(pairs, min_trades)
    L = [f"# جاروی آستانهٔ امتیاز — {meta['date']}", "",
         f"- **بازه:** {meta['period']}",
         f"- **هزینه:** اسپرد/۲ + {meta['slippage']} پیپ لغزش در هر طرف",
         f"- **معیار انتخاب:** بیشترین میانگین R میان آستانه‌هایی با ≥ {min_trades} معامله", ""]
    L += _table(rows, head) + [""]
    if pick is not None:
        L += [f"**پیشنهاد بر پایهٔ همین داده: `min_score = {pick}`.** "
              "این پیشنهاد را باید در یک بازهٔ دوم (واک‌فوروارد) هم دید، "
              "وگرنه فیت‌شدن روی گذشته است.", ""]
    L += ["**چطور بخوانیم:** ستون «معامله» را هم ببین؛ آستانه‌ای که ۱۲ معامله دارد "
          "با وجود میانگین R بالا قابل اعتماد نیست.", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="بک‌تست آفلاین موتور سیگنال ODIN")
    ap.add_argument("--data-dir", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "backtest")
    ap.add_argument("--tz", default="auto", help="auto | 0 | 2 | 3")
    ap.add_argument("--from", dest="start", default="")
    ap.add_argument("--to", dest="end", default="")
    ap.add_argument("--label", default="نسخهٔ ۱.۱ (پیکربندی تولید)")
    ap.add_argument("--legacy", action="store_true", help="فقط استراتژی ۱.۰ (پولبک)")
    ap.add_argument("--no-breakout", action="store_true")
    ap.add_argument("--no-tiers", action="store_true")
    ap.add_argument("--min-score", type=int, default=None)
    ap.add_argument("--sweep-min-score", default="",
                    help="جاروی آستانهٔ امتیاز؛ مثال: 5,6,7,8")
    ap.add_argument("--max-open", type=int, default=None)
    ap.add_argument("--max-per-day", type=int, default=None)
    ap.add_argument("--cooldown", type=int, default=None)
    ap.add_argument("--slippage", type=float, default=DEFAULT_SLIPPAGE)
    ap.add_argument("--spread", default="", help="بازنویسی: EURUSD=1.2,XAUUSD=3")
    ap.add_argument("--jobs", type=int, default=1, help="تعداد پروسه (fork)")
    ap.add_argument("--save-trades", action="store_true")
    ap.add_argument("--debug-signals", action="store_true")
    ap.add_argument("--verbose-every", type=int, default=0)
    ap.add_argument("--expiry-hours", type=float, default=None,
                    help="بازنویسی journal.expiry_hours برای آزمون‌ها")
    args = ap.parse_args(argv)

    if not args.data_dir.exists():
        print(f"❌ پوشهٔ داده پیدا نشد: {args.data_dir}")
        return 2

    print("📥 خواندن داده…")
    data = read_data(args.data_dir, args.tz)
    if not data:
        print("❌ هیچ فایل معتبری خوانده نشد")
        return 2

    cfg = load_config()
    if args.legacy:
        cfg["strategies"] = {"trend_pullback": True,
                             "range_reversion": False, "breakout": False}
    if args.no_breakout:
        cfg["strategies"] = dict(cfg.get("strategies") or {})
        cfg["strategies"]["breakout"] = False
    if args.no_tiers:
        cfg["judge"]["tiers"]["enabled"] = False
    if args.min_score is not None:
        cfg["judge"]["min_score"] = args.min_score
    if args.max_open is not None:
        cfg["judge"]["portfolio"]["max_open_positions"] = args.max_open
    if args.max_per_day is not None:
        cfg["judge"]["portfolio"]["max_signals_per_day"] = args.max_per_day
    if args.cooldown is not None:
        cfg["judge"]["resend_cooldown_minutes"] = args.cooldown

    spread = dict(DEFAULT_SPREAD)
    for part in filter(None, args.spread.split(",")):
        k, _, v = part.partition("=")
        spread[k.strip().upper()] = float(v)

    start = datetime.fromisoformat(args.start) if args.start else None
    end = (datetime.fromisoformat(args.end) + timedelta(days=1)) if args.end else None

    if args.sweep_min_score.strip():
        values = sorted({int(x) for x in args.sweep_min_score.split(",") if x.strip()})
        print(f"🚀 جاروی آستانهٔ امتیاز: {values}")
        pairs = sweep_min_scores(cfg, data, values, start=start, end=end,
                                 spread=spread, slippage=args.slippage)
        s_meta = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "period": f"{min(d.index[0] for d in data.values()):%Y-%m-%d} → "
                      f"{max(d.index[-1] for d in data.values()):%Y-%m-%d}",
            "slippage": args.slippage,
        }
        for v, r in pairs:
            st = r.stats()
            print(f"  • min_score={v:<2} سیگنال {st['signals']:>4} | معامله {st['trades']:>4} | "
                  f"برد {_pct(st['hit_rate'])} | میانگین R {st['avg_r']:+.3f} | "
                  f"PF {st['profit_factor']:.2f} | افت {st['max_dd_r']:+.1f}R")
        pick = sweep_pick(pairs)
        if pick is not None:
            print(f"  ⭐ پیشنهاد (بیشترین میانگین R با ≥۱۰۰ معامله): min_score={pick}")
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "sweep-min-score.md").write_text(render_sweep(pairs, s_meta), encoding="utf-8")
        print(f"\n💾 {args.out / 'sweep-min-score.md'}")
        return 0

    print(f"🚀 اجرا: {args.label}")
    bt = Backtest(cfg, data, start=start, end=end, spread=spread,
                  slippage=args.slippage, label=args.label,
                  verbose_every=args.verbose_every,
                  debug_signals=args.debug_signals,
                  expiry_hours=args.expiry_hours)
    print(f"   نمادهای شبیه‌سازی: {', '.join(bt.symbols)}")
    _GLOBAL_BT = bt
    if args.jobs > 1 and "fork" in __import__("multiprocessing").get_all_start_methods():
        import multiprocessing as mp
        globals()["_W_BT"] = bt                # کوپی به فرزند fork
        bt.pool = mp.get_context("fork").Pool(args.jobs)
        print(f"   پروسه‌های موازی: {args.jobs}")
    try:
        res = bt.run()
    finally:
        if bt.pool is not None:
            bt.pool.close()
            bt.pool.join()
    s = res.stats()

    print()
    print(f"══ {args.label} ══")
    print(f"  چرخه: {s['cycles']} | قضاوت: {s['judgments']} | روز: {s['days']}")
    print(f"  سیگنال: {s['signals']} ({s['signals_per_day']:.2f} در روز) | "
          f"قابل اقدام: {s['signals_actionable']}")
    print(f"  معاملهٔ بسته: {s['trades']} | برد {s['wins']} / باخت {s['losses']} | "
          f"نرخ برد {_pct(s['hit_rate'])}")
    print(f"  میانگین R: {s['avg_r']:+.3f} | مجموع R: {s['total_r']:+.1f} | "
          f"وزن‌دار: {s['total_r_weighted']:+.1f} | PF: {s['profit_factor']:.2f} | "
          f"حداکثر افت: {s['max_dd_r']:+.1f}R")
    print(f"  خروجی: TP={s['tp']} SL={s['sl']} گپ‌استاپ={s['gap_sl']} منقضی={s['expired']}")
    for name, v in s["per_strategy"].items():
        print(f"    • {name:<16} {v['trades']:>4} معامله | برد {_pct(v['win_rate'])} | "
              f"میانگین R {v['avg_r']:+.3f} | مجموع {v['total_r']:+.1f}")
    for name, v in s["per_tier"].items():
        print(f"    ◆ رده {name:<3} {v['trades']:>4} معامله | برد {_pct(v['win_rate'])} | "
              f"میانگین R {v['avg_r']:+.3f}")

    args.out.mkdir(parents=True, exist_ok=True)
    meta = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "data_note": f"{len(data)} فایل، {sum(len(d) for d in data.values()):,} کندل M15",
        "period": f"{min(d.index[0] for d in data.values()):%Y-%m-%d} → "
                  f"{max(d.index[-1] for d in data.values()):%Y-%m-%d}",
        "cycle": Backtest.CYCLE_MINUTES, "slippage": args.slippage,
    }
    stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in args.label)[:48]
    (args.out / f"{stem}.json").write_text(
        json.dumps({"meta": meta, "stats": s,
                    "trades": [t.as_dict() for t in res.trades]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / f"{stem}.md").write_text(render_markdown([res], meta), encoding="utf-8")
    if bt.debug_rows:
        pd.DataFrame(bt.debug_rows).to_csv(args.out / f"{stem}-signals.csv", index=False)
    if args.save_trades and res.trades:
        pd.DataFrame([t.as_dict() for t in res.trades]).to_csv(
            args.out / f"{stem}-trades.csv", index=False)
    print(f"\n💾 {args.out / (stem + '.md')}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
