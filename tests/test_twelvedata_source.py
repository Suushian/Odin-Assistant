# -*- coding: utf-8 -*-
"""تست‌های آفلاین منبع یگانهٔ بازار Twelve Data."""
from __future__ import annotations

from unittest import mock

import pandas as pd

from src.data.twelvedata_source import TwelveDataSource


def _frame(periods: int = 18) -> pd.DataFrame:
    idx = pd.date_range("2026-10-01T00:00:00", periods=periods, freq="15min")
    close = [100.0 + i for i in range(periods)]
    return pd.DataFrame({
        "Open": [x - 0.5 for x in close],
        "High": [x + 2.0 for x in close],
        "Low": [x - 2.0 for x in close],
        "Close": close,
    }, index=idx)


def test_resample_keeps_only_complete_buckets() -> None:
    source = TwelveDataSource({"twelvedata": {"api_key": "test"}})
    frame = _frame(18)  # چهار ساعت کامل + دو کندل ناقص در سطل بعدی

    h1 = source._resample_m15(frame, 60)
    h4 = source._resample_m15(frame, 240)

    assert len(h1) == 4
    assert len(h4) == 1
    assert h1.iloc[0]["Open"] == frame.iloc[0]["Open"]
    assert h1.iloc[0]["High"] == frame.iloc[:4]["High"].max()
    assert h1.iloc[0]["Low"] == frame.iloc[:4]["Low"].min()
    assert h1.iloc[0]["Close"] == frame.iloc[3]["Close"]
    assert h4.iloc[0]["Open"] == frame.iloc[0]["Open"]
    assert h4.iloc[0]["High"] == frame.iloc[:16]["High"].max()
    assert h4.iloc[0]["Low"] == frame.iloc[:16]["Low"].min()
    assert h4.iloc[0]["Close"] == frame.iloc[15]["Close"]


def test_fetch_requests_one_m15_series_per_symbol() -> None:
    source = TwelveDataSource({"twelvedata": {"api_key": "test"}})
    end = pd.Timestamp.now(tz="UTC").floor("15min") - pd.Timedelta(minutes=15)
    idx = pd.date_range(end=end, periods=5000, freq="15min")
    close = [1.0 + i * 0.00001 for i in range(len(idx))]
    frame = pd.DataFrame({
        "Open": close,
        "High": [x + 0.0001 for x in close],
        "Low": [x - 0.0001 for x in close],
        "Close": close,
    }, index=idx)
    source._series = mock.Mock(return_value=frame)

    with mock.patch("src.data.quality.validate_market_data", return_value=[]):
        md = source.fetch({"name": "EURUSD", "td": "EUR/USD"})

    assert md is not None
    assert source._series.call_count == 1
    source._series.assert_called_once_with("EUR/USD")
    assert len(md.h1) >= 250
    assert len(md.h4) >= 210
