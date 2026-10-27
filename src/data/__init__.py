# -*- coding: utf-8 -*-
"""کارخانهٔ تنها منبع قیمت و کندل بازار: Twelve Data."""
from __future__ import annotations

from .base import DataSource, MarketData  # noqa: F401


def get_source(cfg: dict) -> DataSource:
    """همیشه Twelve Data؛ منابع جایگزین عمداً قابل انتخاب نیستند."""
    kind = str(cfg.get("data_source", "twelvedata")).strip().lower()
    if kind != "twelvedata":
        raise ValueError(
            "منبع بازار نامعتبر است؛ تنها منبع مجاز Twelve Data است."
        )
    from .twelvedata_source import TwelveDataSource
    return TwelveDataSource(cfg)
