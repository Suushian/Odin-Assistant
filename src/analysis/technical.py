# -*- coding: utf-8 -*-
"""موتور تحلیل تکنیکال چندتایم‌فریمی.

برای هر نماد یک SymbolAnalysis تولید می‌کند:
  - جهت روند در H4 (EMA سریع vs کند) و هم‌راستایی H1
  - قدرت روند (ADX)، مومنتوم (RSI در M15)، نوسان (ATR در H1)
  - نزدیک‌ترین حمایت/مقاومت (swing های H4)
  - verdict: کد جمع‌بندی که لایه گزارش آن را به فارسی ترجمه می‌کند
  - setups:  فهرست ستاپ‌های نامزد از چند استراتژی (نسخهٔ ۱.۱) — بهترین
             ستاپ در `strategy` می‌آید؛ `verdict` برای سازگاری با نسخهٔ ۱.۰
             همان قاعدهٔ پولبک را گزارش می‌کند و دست‌نخورده مانده است.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..data.base import MarketData
from . import indicators as ind
from .strategies import MarketState, Setup, build_setups


@dataclass
class SymbolAnalysis:
    symbol: str
    fa_name: str
    base: str
    quote: str
    price: float
    pip: float
    trend: str               # bullish | bearish | none
    h1_agrees: bool
    adx: float
    rsi: float
    rsi_rising: bool
    atr: float               # واحد قیمت (H1)
    support: Optional[float]
    resistance: Optional[float]
    last_candle: Optional[datetime]
    verdict: str             # RANGE | BUY_SETUP | SELL_SETUP | WAIT | DATA
    # ── نسخهٔ ۱.۱: چند استراتژی ────────────────────────────────
    # فیلدهای زیر مقدار پیش‌فرض دارند تا تحلیل‌های دست‌سازِ تست‌ها و
    # مصرف‌کننده‌های قدیمی بدون تغییر معتبر بمانند (سازگاری کامل).
    setups: list = field(default_factory=list)   # list[Setup] — بهترین اول
    strategy: str = ""                           # کلید ستاپ برتر ("" = ستاپ قدیمی)
    # نسخهٔ ۱.۱.۱ — «قیمت همین حالا»: کلوز آخرین کندل بستهٔ M15. `price` عمداً
    # همان کلوز H1 مانده است (سازگاری بایت‌به‌بایت با ۱.۰ و گلدن‌ها)؛ فقط
    # ستاپ‌هایی که در بک‌تست آسیب دیدند (شکست) از این مرجع استفاده می‌کنند.
    entry_ref: float = 0.0


def analyze_symbol(sym_cfg: dict, md: MarketData, acfg: dict,
                   scfg: Optional[dict] = None) -> SymbolAnalysis:
    """تحلیل کامل یک نماد بر اساس داده سه تایم‌فریم.

    scfg: بخش `strategies` پیکربندی (نسخهٔ ۱.۱). None = همهٔ استراتژی‌های
    فعال با مقادیر پیش‌فرض — همان رفتاری که فراخوانی سه‌آرگومانی امروز
    انتظار دارد (سازگاری با قرارداد odin.analysis.technical@1).
    """
    ema_fast_n = int(acfg.get("ema_fast", 50))
    ema_slow_n = int(acfg.get("ema_slow", 200))
    adx_n = int(acfg.get("adx_period", 14))
    adx_min = float(acfg.get("adx_min_trend", 20))
    rsi_n = int(acfg.get("rsi_period", 14))
    atr_n = int(acfg.get("atr_period", 14))
    swing_win = int(acfg.get("swing_window", 5))

    h4, h1, m15 = md.h4, md.h1, md.m15
    common = dict(
        symbol=sym_cfg["name"],
        fa_name=sym_cfg.get("fa", sym_cfg["name"]),
        base=sym_cfg["base"],
        quote=sym_cfg["quote"],
        pip=float(sym_cfg["pip"]),
    )

    # ── بررسی کفایت داده ──────────────────────────────────────
    if len(h4) < ema_slow_n + 10 or len(h1) < ema_slow_n + 10 or len(m15) < rsi_n + 10:
        return SymbolAnalysis(
            **common, price=float(h1["Close"].iloc[-1]) if len(h1) else 0.0,
            entry_ref=float(m15["Close"].iloc[-1]) if len(m15) else 0.0,
            trend="none", h1_agrees=False, adx=0.0, rsi=50.0, rsi_rising=False,
            atr=0.0, support=None, resistance=None,
            last_candle=_last_ts(m15), verdict="DATA",
        )

    price = float(h1["Close"].iloc[-1])

    # ── روند H4 و هم‌راستایی H1 ───────────────────────────────
    e_fast_h4 = float(ind.ema(h4["Close"], ema_fast_n).iloc[-1])
    e_slow_h4 = float(ind.ema(h4["Close"], ema_slow_n).iloc[-1])
    trend = "bullish" if e_fast_h4 > e_slow_h4 else "bearish"

    e_fast_h1 = float(ind.ema(h1["Close"], ema_fast_n).iloc[-1])
    e_slow_h1 = float(ind.ema(h1["Close"], ema_slow_n).iloc[-1])
    h1_bullish = e_fast_h1 > e_slow_h1
    h1_agrees = h1_bullish if trend == "bullish" else (not h1_bullish)

    # ── سایر اندیکاتورها ──────────────────────────────────────
    adx_v = float(ind.adx(h4, adx_n).iloc[-1])
    rsi_s = ind.rsi(m15["Close"], rsi_n)
    rsi_v = float(rsi_s.iloc[-1])
    rsi_rising = bool(rsi_s.iloc[-1] > rsi_s.iloc[-2])
    atr_v = float(ind.atr(h1, atr_n).iloc[-1])
    support, resistance = ind.nearest_levels(price, h4, swing_win)

    # ── جمع‌بندی (verdict) ────────────────────────────────────
    if adx_v < adx_min:
        verdict = "RANGE"                       # وتو: بازار بی‌روند
    elif trend == "bullish" and h1_agrees and rsi_v < 45:
        verdict = "BUY_SETUP"                   # پولبک در روند صعودی
    elif trend == "bearish" and h1_agrees and rsi_v > 55:
        verdict = "SELL_SETUP"                  # اصلاح رو به بالا در روند نزولی
    else:
        verdict = "WAIT"

    # ── ستاپ‌های چند-استراتژی (نسخهٔ ۱.۱) ────────────────────
    st = MarketState(
        price=price, trend=trend, h1_agrees=h1_agrees, adx=adx_v, rsi=rsi_v,
        rsi_rising=rsi_rising, atr=atr_v, support=support, resistance=resistance,
        **_range_bounds(h1, scfg),
    )
    setups = build_setups(st, sym_cfg["name"], acfg, scfg)

    return SymbolAnalysis(
        **common, price=price, trend=trend, h1_agrees=h1_agrees,
        adx=adx_v, rsi=rsi_v, rsi_rising=rsi_rising, atr=atr_v,
        support=support, resistance=resistance,
        entry_ref=float(m15["Close"].iloc[-1]),
        last_candle=_last_ts(m15), verdict=verdict,
        setups=setups, strategy=(setups[0].key if setups else ""),
    )


def _range_bounds(h1, scfg: Optional[dict]) -> dict:
    """دامنهٔ N کندلیِ H1 برای استراتژی شکست (نسخهٔ ۱.۱).

    «دامنه» = سقف/کفِ N کندلِ *قبل از کندل جاری*؛ «دامنهٔ قبلی» همان پنجره
    یک کندل عقب‌تر است. مقایسهٔ این دو، شکست را «تازه» می‌کند (شکست‌های
    تکراری روی هر کندل بعدی، اسپم می‌سازند).
    خروجی خالی (۰) یعنی داده کافی نیست → استراتژی شکست شلیک نمی‌کند.
    """
    empty = {"range_high": 0.0, "range_low": 0.0,
             "prev_range_high": 0.0, "prev_range_low": 0.0, "prev_close": 0.0}
    block = ((scfg or {}).get("breakout") or {}) if isinstance(scfg, dict) else {}
    if not isinstance(block, dict):
        block = {}
    try:
        n = int(block.get("lookback_h1", 24))
    except (TypeError, ValueError):
        n = 24
    n = max(5, min(240, n))
    if h1 is None or len(h1) < n + 3:
        return empty
    try:
        win = h1.iloc[-(n + 1):-1]
        prev = h1.iloc[-(n + 2):-2]
        return {
            "range_high": float(win["High"].max()), "range_low": float(win["Low"].min()),
            "prev_range_high": float(prev["High"].max()),
            "prev_range_low": float(prev["Low"].min()),
            "prev_close": float(h1["Close"].iloc[-2]),
        }
    except Exception:
        return empty


def _last_ts(df) -> Optional[datetime]:
    try:
        ts = df.index[-1]
        return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.fromisoformat(str(ts))
    except Exception:
        return None
