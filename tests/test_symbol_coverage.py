# -*- coding: utf-8 -*-
"""Guard the seven major FX pairs + gold and desktop/Android NZDUSD parity."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    symbols = cfg["symbols"]
    names = [s["name"] for s in symbols]
    expected = {
        "EURUSD", "GBPUSD", "USDJPY", "USDCAD",
        "AUDUSD", "USDCHF", "NZDUSD", "XAUUSD",
    }
    assert len(names) == len(set(names)), f"duplicate symbols: {names}"
    assert set(names) == expected, f"symbol universe mismatch: {names}"

    nzd = next(s for s in symbols if s["name"] == "NZDUSD")
    assert nzd["td"] == "NZD/USD"
    assert nzd["tv"]["symbol"] == "NZDUSD"
    assert nzd["base"] == "NZD" and nzd["quote"] == "USD"
    assert nzd["pip"] == 0.0001

    js = (ROOT / "android/app/src/main/assets/www/js/config.js").read_text(encoding="utf-8")
    match = re.search(r"\{ name: 'NZDUSD'[^\n]+", js)
    assert match, "NZDUSD missing from Android config"
    row = match.group(0)
    for field in (
        "symbol: 'NZDUSD'",
        "base: 'NZD'",
        "quote: 'USD'",
        "pip: 0.0001",
    ):
        assert field in row, f"Android NZDUSD metadata mismatch: missing {field}"

    assert "yahoo:" not in row and "fetchYahooSymbol" not in js
    print("symbol coverage passed: 7 major FX pairs + gold; Twelve Data-only config parity OK")


if __name__ == "__main__":
    main()
