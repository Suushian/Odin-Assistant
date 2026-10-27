# -*- coding: utf-8 -*-
"""Offline regression tests for one-call Twelve Data market ingestion."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.twelvedata_source import TwelveDataSource


def main() -> None:
    now = pd.Timestamp.now(tz="UTC").tz_localize(None).floor("15min")
    index = pd.date_range(end=now - pd.Timedelta(minutes=15), periods=5000, freq="15min")
    values = []
    for i, ts in enumerate(index):
        close = 1.1 + i * 0.000001
        values.append({
            "datetime": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "open": str(close - 0.0001),
            "high": str(close + 0.0002),
            "low": str(close - 0.0002),
            "close": str(close),
        })

    response = mock.Mock(status_code=200)
    response.json.return_value = {"values": list(reversed(values))}
    cfg = {
        "data_source": "twelvedata",
        "twelvedata": {"api_key": "test-key", "min_request_gap_sec": 0},
        "history": {"td_m15_bars": 5000, "drop_forming_candle": True},
    }
    source = TwelveDataSource(cfg)
    with mock.patch("src.data.twelvedata_source.requests.get", return_value=response) as get:
        md = source.fetch({"name": "EURUSD", "td": "EUR/USD"})

    assert get.call_count == 1, f"expected one API request per symbol, got {get.call_count}"
    args, kwargs = get.call_args
    assert args[0] == source.BASE_URL
    assert kwargs["params"]["symbol"] == "EUR/USD"
    assert kwargs["params"]["interval"] == "15min"
    assert kwargs["params"]["outputsize"] == 5000
    assert kwargs["params"]["timezone"] == "UTC"
    assert kwargs["params"]["apikey"] == "test-key"
    assert md is not None, "valid M15 history should produce market data"
    assert len(md.m15) >= 4000 and len(md.h1) >= 250 and len(md.h4) >= 210
    assert all(ts.minute % 15 == 0 for ts in md.m15.index)
    assert all(ts.minute == 0 for ts in md.h1.index)
    assert all(ts.hour % 4 == 0 and ts.minute == 0 for ts in md.h4.index)
    assert md.m15.index[-1] + pd.Timedelta(minutes=15) <= now
    assert md.h1.index[-1] + pd.Timedelta(hours=1) <= now
    assert md.h4.index[-1] + pd.Timedelta(hours=4) <= now
    print("Twelve Data source tests passed: one request, complete resampling, closed candles.")


if __name__ == "__main__":
    main()
