# -*- coding: utf-8 -*-
"""Offline regression checks for the M15 scalping strategy."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.base import MarketData
from src.judge.scoring import JudgeContext
from src.strategies import scalping

NOW = datetime(2026, 9, 23, 8, 30)


def analysis_stub():
    class A:
        symbol = "EURUSD"
        price = 1.1
        pip = 0.0001
    return A()


def market(direction="BUY", h1_direction=None, bars=80, setup=True):
    sign = 1 if direction == "BUY" else -1
    hsign = sign if h1_direction is None else (1 if h1_direction == "BUY" else -1)
    h1c = [1.1000 + hsign * i * 0.00030 for i in range(bars)]
    h1o = [x - hsign * 0.00005 for x in h1c]
    h1 = pd.DataFrame({
        "Open": h1o, "High": [x + 0.00020 for x in h1c],
        "Low": [x - 0.00020 for x in h1c], "Close": h1c,
    }, index=pd.date_range(end=NOW, periods=bars, freq="h"))
    mclose = [1.1000 + sign * i * 0.00003 for i in range(bars)]
    if setup:
        mclose[-1] = mclose[-2] + sign * 0.00023
    else:
        mclose = [1.1000] * bars
    mopen = [x - sign * 0.00003 for x in mclose]
    if setup:
        mopen[-1] = mclose[-2]
    m15 = pd.DataFrame({
        "Open": mopen, "High": [x + 0.00015 for x in mclose],
        "Low": [x - 0.00015 for x in mclose], "Close": mclose,
    }, index=pd.date_range(end=NOW, periods=bars, freq="15min"))
    return MarketData(symbol="EURUSD", m15=m15, h1=h1, h4=h1)


CFG = {"h1_fast_ema": 20, "h1_slow_ema": 50, "m15_fast_ema": 9,
       "m15_slow_ema": 21, "atr_period": 14, "breakout_lookback": 3,
       "min_body_atr": 0.15, "max_extension_atr": 1.5}


def context():
    return JudgeContext(jcfg={}, acfg={}, symbols_cfg=[],
                        now=NOW, ranking=[], news_snap=None)


def check(condition, message):
    assert condition, message


def main():
    a, ctx = analysis_stub(), context()
    v = scalping.evaluate(a, market("BUY"), CFG, ctx)
    check(v.direction == "BUY" and v.proposes, "bullish M15 setup should BUY")
    check(v.key == "scalping" and len(v.reasons_fa) == 3, "stable verdict shape")
    v = scalping.evaluate(a, market("SELL"), CFG, ctx)
    check(v.direction == "SELL", "bearish M15 setup should SELL")
    v = scalping.evaluate(a, market("BUY", h1_direction="SELL"), CFG, ctx)
    check(v.direction == "NONE" and "H1" in v.reasons_fa[0], "H1 conflict must veto")
    v = scalping.evaluate(a, market("BUY", setup=False), CFG, ctx)
    check(v.direction == "NONE", "flat M15 must not create an entry")
    v = scalping.evaluate(a, market("BUY", bars=30), CFG, ctx)
    check(v.direction == "NONE" and "دادهٔ کافی نیست" in v.reasons_fa[0],
          "insufficient H1 candles must be rejected")
    v = scalping.evaluate(a, None, CFG, ctx)
    check(v.direction == "NONE", "missing market data must be rejected")
    v = scalping.evaluate(a, market("BUY"), dict(CFG, max_extension_atr=0.01), ctx)
    check(v.direction == "NONE" and "کشیده شده" in v.reasons_fa[0],
          "overextended entry must be rejected")
    first = scalping.evaluate(a, market("BUY"), CFG, ctx).to_dict()
    second = scalping.evaluate(a, market("BUY"), CFG, ctx).to_dict()
    check(first == second, "strategy evaluation must be deterministic")
    print("OK: 8 scalping regression checks passed")


if __name__ == "__main__":
    main()
