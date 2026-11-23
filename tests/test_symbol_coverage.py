# -*- coding: utf-8 -*-
"""Guard the seven major FX pairs + gold and desktop/Android NZDUSD parity."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["data_source"] == "twelvedata"
    symbols = cfg["symbols"]
    names = [s["name"] for s in symbols]
    expected = {
        "EURUSD", "GBPUSD", "USDJPY", "USDCAD",
        "AUDUSD", "USDCHF", "NZDUSD", "XAUUSD",
        # نسخهٔ ۱.۱ — کراس‌های یورو برای تنوع فرصت (سبد قبلی تماماً ...USD بود)
        "EURJPY", "EURGBP",
    }
    assert len(names) == len(set(names)), f"duplicate symbols: {names}"
    assert set(names) == expected, f"symbol universe mismatch: {names}"

    nzd = next(s for s in symbols if s["name"] == "NZDUSD")
    assert "yahoo" not in nzd
    assert nzd["td"] == "NZD/USD"
    assert nzd["tv"]["symbol"] == "NZDUSD"
    assert nzd["base"] == "NZD" and nzd["quote"] == "USD"
    assert nzd["pip"] == 0.0001

    js = (ROOT / "android/app/src/main/assets/www/js/config.js").read_text(encoding="utf-8")
    match = re.search(r"\{ name: 'NZDUSD'[^\n]+", js)
    assert match, "NZDUSD missing from Android config"
    row = match.group(0)
    assert "yahoo:" not in row, "Yahoo must not remain in Android symbol config"
    for field in (
        "symbol: 'NZDUSD'",
        "base: 'NZD'",
        "quote: 'USD'",
        "pip: 0.0001",
    ):
        assert field in row, f"Android NZDUSD metadata mismatch: missing {field}"

    # ── کراس‌های یورو: متادیتای درست در هر دو موتور (دسکتاپ/اندروید) ──
    for name, td, base, quote, pip in (("EURJPY", "EUR/JPY", "EUR", "JPY", 0.01),
                                       ("EURGBP", "EUR/GBP", "EUR", "GBP", 0.0001)):
        sym = next(x for x in symbols if x["name"] == name)
        assert sym["td"] == td, f"{name} td mismatch: {sym['td']}"
        assert sym["tv"]["symbol"] == name
        assert sym["base"] == base and sym["quote"] == quote
        assert sym["pip"] == pip, f"{name} pip mismatch: {sym['pip']}"
        m = re.search(r"\{ name: '" + name + r"'[^\n]+", js)
        assert m, f"{name} missing from Android config"
        row = m.group(0)
        for field in (f"td: '{td}'", f"base: '{base}'", f"quote: '{quote}'", f"pip: {pip}"):
            assert field in row, f"Android {name} metadata mismatch: missing {field}"

    # ── سهمیهٔ پلن رایگان Twelve Data (≈۸۰۰ درخواست/روز) ──
    interval = int(cfg["loop"]["interval_minutes"])
    per_day = len(symbols) * max(1, 24 * 60 // interval)
    assert per_day <= 800, f"quota blown: {len(symbols)} symbols × {interval}min = {per_day}/day"

    print(f"symbol coverage passed: {len(symbols)} symbols (7 majors + 2 EUR crosses + gold); "
          f"NZDUSD/EURJPY/EURGBP config parity OK; quota {per_day}/day ≤ 800")


if __name__ == "__main__":
    main()
