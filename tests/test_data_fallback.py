# -*- coding: utf-8 -*-
"""تست‌های آفلاین سیاست تک‌منبعی بازار: فقط Twelve Data مجاز است."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import get_source  # noqa: E402
from src.data.twelvedata_source import TwelveDataSource  # noqa: E402


def main() -> None:
    cfg = {"data_source": "twelvedata", "twelvedata": {"api_key": "test"}}
    assert isinstance(get_source(cfg), TwelveDataSource)

    for legacy in ("auto", "yahoo", "mt5", "binance"):
        try:
            get_source({**cfg, "data_source": legacy})
        except ValueError:
            pass
        else:
            raise AssertionError(f"منبع حذف‌شدهٔ {legacy!r} نباید انتخاب شود")

    print("single market source tests passed (5 scenarios).")


if __name__ == "__main__":
    main()
