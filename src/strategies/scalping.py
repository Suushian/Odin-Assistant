# -*- coding: utf-8 -*-
"""استراتژی اسکالپ M15 با فیلتر جهت H1.

این ماژول فقط ستاپ ورود را ارزیابی می‌کند؛ مدیریت اختصاصی SL/TP و
تغییر قواعد داور عمداً خارج از محدوده است. نبود/خرابی داده همیشه NONE است.
قرارداد: evaluate(a, md, scfg, ctx) -> StrategyVerdict (odin.strategy@1)
"""
from __future__ import annotations

from typing import Any, Optional

from ..fa import fa_num
from .base import StrategyVerdict, ctx_now, none

KEY = "scalping"
NAME_FA = "اسکالپ M15 با فیلتر H1"


def evaluate(a: Any, md: Optional[Any], scfg: Optional[dict] = None,
             ctx: Any = None) -> StrategyVerdict:
    scfg = dict(scfg or {})
    h1_fast_n = _period(scfg, "h1_fast_ema", 20, minimum=2)
    h1_slow_n = _period(scfg, "h1_slow_ema", 50, minimum=3)
    m15_fast_n = _period(scfg, "m15_fast_ema", 9, minimum=2)
    m15_slow_n = _period(scfg, "m15_slow_ema", 21, minimum=3)
    atr_n = _period(scfg, "atr_period", 14, minimum=2)
    lookback = _period(scfg, "breakout_lookback", 3, minimum=1)
    min_body_atr = _positive(scfg, "min_body_atr", 0.15)
    max_extension_atr = _positive(scfg, "max_extension_atr", 1.5)
    max_m15_age = _period(scfg, "max_m15_age_minutes", 45, minimum=1)
    max_h1_age = _period(scfg, "max_h1_age_minutes", 90, minimum=1)

    if h1_fast_n >= h1_slow_n or m15_fast_n >= m15_slow_n:
        return none(KEY, NAME_FA, "تنظیم EMA نامعتبر است — دورهٔ سریع باید از دورهٔ کند کوتاه‌تر باشد")

    if md is None:
        return none(KEY, NAME_FA, "دادهٔ بازار برای اسکالپ در دسترس نیست")
    h1 = getattr(md, "h1", None)
    m15 = getattr(md, "m15", None)
    if h1 is None or m15 is None:
        return none(KEY, NAME_FA, "دادهٔ H1 یا M15 در دسترس نیست")

    required_h1 = h1_slow_n + 2
    required_m15 = max(m15_slow_n + 2, atr_n + 2, lookback + 3)
    if len(h1) < required_h1 or len(m15) < required_m15:
        return none(KEY, NAME_FA,
                    f"دادهٔ کافی نیست — H1 حداقل {required_h1} و M15 حداقل {required_m15} کندل لازم دارد")

    now = ctx_now(ctx)
    h1_time = _utc_timestamp(h1.index[-1])
    m15_time = _utc_timestamp(m15.index[-1])
    if h1_time is None or m15_time is None:
        return none(KEY, NAME_FA, "زمان آخرین کندل H1 یا M15 قابل تشخیص نیست")
    h1_age = (now - h1_time).total_seconds() / 60.0
    m15_age = (now - m15_time).total_seconds() / 60.0
    if h1_age < -5 or m15_age < -5:
        return none(KEY, NAME_FA, "زمان آخرین کندل در آینده است — دادهٔ بازار معتبر نیست")
    if h1_age > max_h1_age or m15_age > max_m15_age:
        return none(KEY, NAME_FA, "دادهٔ بازار کهنه است — برای اسکالپ به کندل تازهٔ H1 و M15 نیاز داریم")

    try:
        for frame in (h1, m15):
            for col in ("Open", "High", "Low", "Close"):
                if col not in frame.columns:
                    return none(KEY, NAME_FA, f"ستون {col} در دادهٔ کندل وجود ندارد")
        h1_close = h1["Close"].astype(float)
        mclose = m15["Close"].astype(float)
        mopen = m15["Open"].astype(float)
        mhigh = m15["High"].astype(float)
        mlow = m15["Low"].astype(float)

        h1_fast = float(h1_close.ewm(span=h1_fast_n, adjust=False).mean().iloc[-1])
        h1_slow = float(h1_close.ewm(span=h1_slow_n, adjust=False).mean().iloc[-1])
        h1_last = float(h1_close.iloc[-1])
        fast = mclose.ewm(span=m15_fast_n, adjust=False).mean()
        slow = mclose.ewm(span=m15_slow_n, adjust=False).mean()

        previous_close = mclose.shift(1)
        true_range = (mhigh - mlow).combine(
            (mhigh - previous_close).abs(), max).combine(
            (mlow - previous_close).abs(), max)
        atr = float(true_range.rolling(atr_n).mean().iloc[-1])
        close = float(mclose.iloc[-1])
        open_ = float(mopen.iloc[-1])
        body = abs(close - open_)
        ema_fast = float(fast.iloc[-1])
        ema_slow = float(slow.iloc[-1])
        prior_fast = float(fast.iloc[-2])
        prior_low = float(mlow.iloc[-2])
        prior_high = float(mhigh.iloc[-2])
        prior_close = float(mclose.iloc[-2])
        recent_high = float(mhigh.iloc[-lookback-1:-1].max())
        recent_low = float(mlow.iloc[-lookback-1:-1].min())
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        return none(KEY, NAME_FA, "دادهٔ کندل‌ها خوانا یا عددی نیست")

    values = (h1_fast, h1_slow, h1_last, ema_fast, ema_slow, prior_fast,
              prior_low, prior_high, prior_close, close, open_, atr, body, recent_high, recent_low)
    if any(not _finite(x) for x in values) or atr <= 0:
        return none(KEY, NAME_FA, "ATR یا مقادیر اندیکاتورها معتبر نیست")

    # فیلتر جهت H1: روند و قیمت آخر هر دو باید در یک سمت EMA باشند.
    if h1_fast > h1_slow and h1_last > h1_fast:
        h1_direction = "BUY"
    elif h1_fast < h1_slow and h1_last < h1_fast:
        h1_direction = "SELL"
    else:
        return none(KEY, NAME_FA, "فیلتر H1 جهت معتبر و هم‌سو نشان نمی‌دهد")

    if body < min_body_atr * atr:
        return none(KEY, NAME_FA,
                    f"بدنهٔ کندل M15 ضعیف است — کمتر از {fa_num(f'{min_body_atr:.2f}')} ATR")

    if h1_direction == "BUY":
        if not (ema_fast > ema_slow and close > ema_fast and close > open_):
            return none(KEY, NAME_FA, "مومنتوم M15 با جهت صعودی H1 هم‌سو نیست")
        breakout = close > recent_high
        reclaim = prior_low <= prior_fast and prior_close <= prior_fast and close > ema_fast
        if not (breakout or reclaim):
            return none(KEY, NAME_FA, "ورود تأیید نشد — نه شکست سقف کوتاه‌مدت داریم و نه بازپس‌گیری EMA")
        extension = (close - ema_fast) / atr
        direction_fa = "صعودی"
        entry_fa = "شکست سقف کوتاه‌مدت" if breakout else "بازپس‌گیری EMA پس از پولبک"
    else:
        if not (ema_fast < ema_slow and close < ema_fast and close < open_):
            return none(KEY, NAME_FA, "مومنتوم M15 با جهت نزولی H1 هم‌سو نیست")
        breakdown = close < recent_low
        reclaim = prior_high >= prior_fast and prior_close >= prior_fast and close < ema_fast
        if not (breakdown or reclaim):
            return none(KEY, NAME_FA, "ورود تأیید نشد — نه شکست کف کوتاه‌مدت داریم و نه ازدست‌رفتن EMA")
        extension = (ema_fast - close) / atr
        direction_fa = "نزولی"
        entry_fa = "شکست کف کوتاه‌مدت" if breakdown else "ازدست‌رفتن EMA پس از پولبک"

    if extension > max_extension_atr:
        return none(KEY, NAME_FA,
                    f"قیمت بیش از حد کشیده شده است — فاصله از EMA سریع {fa_num(f'{extension:.2f}')} ATR")

    separation = abs(ema_fast - ema_slow) / atr
    strength = min(1.0, max(0.55, 0.55 + 0.25 * separation + 0.10 * (body / atr)))
    reasons = [
        f"فیلتر H1 صعودی/نزولی: جهت {direction_fa} تأیید شد",
        f"ورود M15: {entry_fa}؛ EMA سریع/کند هم‌جهت‌اند",
        f"بدنهٔ کندل {fa_num(f'{body / atr:.2f}')} ATR و فاصله از EMA سریع {fa_num(f'{extension:.2f}')} ATR است",
    ]
    return StrategyVerdict(
        key=KEY, name_fa=NAME_FA, direction=h1_direction,
        strength=strength, proposes=True, reasons_fa=reasons,
        detail_fa=f"{NAME_FA}: پیشنهاد {h1_direction} — فیلتر H1 + تأیید M15",
    )


def _period(cfg: dict, key: str, default: int, minimum: int) -> int:
    try:
        value = int(cfg.get(key, default))
        return value if value >= minimum else default
    except (TypeError, ValueError):
        return default


def _positive(cfg: dict, key: str, default: float) -> float:
    try:
        value = float(cfg.get(key, default))
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _finite(value: float) -> bool:
    try:
        return value == value and abs(value) != float("inf")
    except Exception:
        return False


def _utc_timestamp(value: Any):
    """Convert an index value to UTC; naive timestamps follow the data contract."""
    try:
        stamp = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
        if not hasattr(stamp, "tzinfo"):
            return None
        from datetime import timezone
        if stamp.tzinfo is None:
            return stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc)
    except Exception:
        return None
