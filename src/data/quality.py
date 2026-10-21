# -*- coding: utf-8 -*-
"""اعتبارسنجی محافظه‌کارانهٔ کندل‌ها پیش از ورود به موتور تحلیل.

این ماژول جایگزین منبع داده نیست؛ دادهٔ خراب/کهنه را رد می‌کند تا منبع
جایگزین در حالت auto فرصت استفاده پیدا کند.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math

import pandas as pd

from .base import MarketData

_REQUIRED = ("Open", "High", "Low", "Close")
_MIN_BARS = {"m15": 50, "h1": 250, "h4": 210}
_INTERVAL = {"m15": timedelta(minutes=15), "h1": timedelta(hours=1)}
_MAX_INTRADAY_GAP = {"m15": timedelta(hours=1), "h1": timedelta(hours=3)}
_MAX_AGE = {"m15": timedelta(minutes=45), "h1": timedelta(minutes=90)}


def _fx_market_open(now: datetime) -> bool:
    """تقویم تقریبی FX بر مبنای UTC؛ تعطیلات رسمی را تشخیص نمی‌دهد."""
    utc = now.astimezone(timezone.utc)
    weekday = utc.weekday()  # Monday=0, Sunday=6
    minute = utc.hour * 60 + utc.minute
    if weekday == 5:
        return False
    if weekday == 4 and minute >= 21 * 60:
        return False
    if weekday == 6 and minute < 21 * 60:
        return False
    return True


def validate_market_data(md: MarketData, now: datetime | None = None) -> list[str]:
    """فهرست خطاهای داده را برمی‌گرداند؛ لیست خالی یعنی اعتبارسنجی موفق."""
    errors: list[str] = []
    if md is None:
        return ["داده‌ای دریافت نشد"]

    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    market_open = _fx_market_open(now_utc)

    for name, frame in (("M15", md.m15), ("H1", md.h1), ("H4", md.h4)):
        key = name.lower()
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            errors.append(f"{name}: قاب‌داده خالی است")
            continue
        missing = [col for col in _REQUIRED if col not in frame.columns]
        if missing:
            errors.append(f"{name}: ستون‌های OHLC ناقص است ({','.join(missing)})")
            continue
        if len(frame) < _MIN_BARS[key]:
            errors.append(f"{name}: تاریخچه ناکافی است ({len(frame)} < {_MIN_BARS[key]})")
        try:
            idx = pd.DatetimeIndex(pd.to_datetime(frame.index))
            if idx.has_duplicates:
                errors.append(f"{name}: زمان کندل تکراری است")
            if not idx.is_monotonic_increasing:
                errors.append(f"{name}: ترتیب زمانی کندل‌ها نامعتبر است")
            if name in ("M15", "H1") and idx.is_monotonic_increasing:
                gap_idx = idx.tz_convert("UTC").tz_localize(None) if idx.tz is not None else idx
                max_gap = _MAX_INTRADAY_GAP[key]
                for left, right in zip(gap_idx[:-1], gap_idx[1:]):
                    # Ignore date/session boundaries (weekends, holidays and FX rollover).
                    if left.date() == right.date() and right - left > max_gap:
                        errors.append(f"{name}: شکاف زمانی غیرعادی در دادهٔ کندل‌ها")
                        break
        except Exception:
            errors.append(f"{name}: شاخص زمانی نامعتبر است")
            continue

        try:
            values = frame.loc[:, list(_REQUIRED)].astype(float)
            rows = values.to_numpy()
            if not all(math.isfinite(float(v)) for row in rows for v in row):
                errors.append(f"{name}: مقدار OHLC نامتناهی یا خالی است")
                continue
            if (values <= 0).any().any():
                errors.append(f"{name}: قیمت صفر یا منفی است")
            bad = (
                (values["High"] < values[["Open", "Close", "Low"]].max(axis=1)) |
                (values["Low"] > values[["Open", "Close", "High"]].min(axis=1))
            )
            if bool(bad.any()):
                errors.append(f"{name}: رابطهٔ OHLC ناسازگار است")
        except Exception:
            errors.append(f"{name}: مقادیر OHLC قابل‌خواندن نیست")
            continue

        # زمان آینده حتی هنگام بسته‌بودن بازار نامعتبر است؛ فقط سن داده
        # در ساعات بازار کنترل می‌شود تا تعطیلی آخر هفته false positive نسازد.
        # H4 در این پروژه از H1 بازنمونه‌گیری می‌شود.
        if name in ("M15", "H1"):
            try:
                last = pd.Timestamp(idx[-1])
                if last.tzinfo is not None:
                    last = last.tz_convert("UTC").tz_localize(None)
                now_naive = now_utc.replace(tzinfo=None)
                if last.to_pydatetime() > now_naive + timedelta(minutes=5):
                    errors.append(f"{name}: زمان آخرین کندل در آینده است")
                elif market_open:
                    age = now_naive - (last.to_pydatetime() + _INTERVAL[key])
                    if age > _MAX_AGE[key]:
                        errors.append(
                            f"{name}: آخرین کندل بیش از "
                            f"{int(_MAX_AGE[key].total_seconds() // 60)} دقیقه کهنه است"
                        )
            except Exception:
                errors.append(f"{name}: زمان آخرین کندل قابل‌اعتبارسنجی نیست")

    return errors
