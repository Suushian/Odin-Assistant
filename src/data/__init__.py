# -*- coding: utf-8 -*-
"""کارخانهٔ تنها منبع دادهٔ قیمت بازار ODIN: Twelve Data."""
from __future__ import annotations

from .base import DataSource, MarketData  # noqa: F401 (برای import راحت‌تر)


def get_source(cfg: dict) -> DataSource:
    kind = str(cfg.get("data_source", "twelvedata")).strip().lower()
    if kind != "twelvedata":
        raise ValueError(
            f"منبع دادهٔ بازار «{kind}» حذف شده است؛ فقط twelvedata پشتیبانی می‌شود"
        )
    from .twelvedata_source import TwelveDataSource
    return TwelveDataSource(cfg)
