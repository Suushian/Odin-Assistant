# -*- coding: utf-8 -*-
"""تست‌های آفلاین اعتبارسنجی کیفیت دادهٔ بازار."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.base import MarketData  # noqa: E402
from src.data.quality import validate_market_data  # noqa: E402


def frame(n: int, freq: str, end: datetime, base: float = 1.2) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=n, freq=freq)
    close = [base + i * 0.00001 for i in range(n)]
    return pd.DataFrame({
        "Open": [x - 0.00002 for x in close],
        "High": [x + 0.00005 for x in close],
        "Low": [x - 0.00005 for x in close],
        "Close": close,
    }, index=idx)


def sample(now: datetime) -> MarketData:
    naive = now.astimezone(timezone.utc).replace(tzinfo=None)
    h1_end = naive.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    m15_end = naive.replace(minute=(naive.minute // 15) * 15, second=0, microsecond=0) - timedelta(minutes=15)
    h4_end = naive.replace(minute=0, second=0, microsecond=0) - timedelta(hours=4)
    return MarketData("EURUSD", frame(100, "15min", m15_end), frame(300, "1h", h1_end),
                      frame(240, "4h", h4_end))


def main() -> None:
    now = datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc)  # چهارشنبه، بازار باز
    md = sample(now)
    assert validate_market_data(md, now) == [], validate_market_data(md, now)

    stale = sample(now)
    stale.h1.index = stale.h1.index - pd.Timedelta(hours=5)
    stale.m15.index = stale.m15.index - pd.Timedelta(hours=2)
    errors = validate_market_data(stale, now)
    assert any("H1" in e and "کهنه" in e for e in errors), errors
    assert any("M15" in e and "کهنه" in e for e in errors), errors

    broken = sample(now)
    broken.m15.iloc[-1, broken.m15.columns.get_loc("High")] = 0.1
    errors = validate_market_data(broken, now)
    assert any("OHLC ناسازگار" in e for e in errors), errors

    duplicate = sample(now)
    duplicate.h1.index = list(duplicate.h1.index[:-1]) + [duplicate.h1.index[-2]]
    errors = validate_market_data(duplicate, now)
    assert any("تکراری" in e for e in errors), errors

    gap = sample(now)
    gap.h1 = gap.h1.drop(gap.h1.index[100:103])
    errors = validate_market_data(gap, now)
    assert any("H1" in e and "شکاف زمانی" in e for e in errors), errors

    weekend = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)  # Saturday
    weekend_data = sample(weekend)
    weekend_data.h1.index = weekend_data.h1.index - pd.Timedelta(days=1)
    weekend_data.m15.index = weekend_data.m15.index - pd.Timedelta(days=1)
    errors = validate_market_data(weekend_data, weekend)
    assert not any("کهنه است" in e for e in errors), errors

    # Future timestamps remain invalid even when the FX market is closed.
    future_weekend = sample(weekend)
    future_weekend.h1.index = future_weekend.h1.index + pd.Timedelta(days=2)
    errors = validate_market_data(future_weekend, weekend)
    assert any("H1" in e and "آینده" in e for e in errors), errors

    # H4 future timestamps must also be rejected, even though H4 age is not gated.
    future_h4 = sample(now)
    future_h4.h4.index = future_h4.h4.index + pd.Timedelta(days=2)
    errors = validate_market_data(future_h4, now)
    assert any("H4" in e and "آینده" in e for e in errors), errors

    print("data quality tests passed (8 scenarios).")


if __name__ == "__main__":
    main()
