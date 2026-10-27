# -*- coding: utf-8 -*-
"""پلاگین‌های داده؛ Twelve Data تنها منبع قیمت/کندل بازار است."""
from __future__ import annotations

from typing import Any, List, Tuple

from ..core.manifest import PluginManifest


def _twelvedata(ctx: dict) -> Any:
    from ..data.twelvedata_source import TwelveDataSource
    return TwelveDataSource(ctx["cfg"])


class TvPlugin:
    """تأییدیهٔ تکنیکال TradingView؛ منبع جایگزین قیمت/کندل نیست."""

    def fetch_tv_snapshot(self, symbols_cfg: List[dict], timeframe: str = "4h",
                          timeout: int = 8) -> dict:
        from ..data.tradingview import fetch_tv_snapshot
        return fetch_tv_snapshot(symbols_cfg, timeframe=timeframe, timeout=timeout)


def _tv(_ctx: dict) -> TvPlugin:
    return TvPlugin()


def select_market_provider(registry: Any, cfg: dict) -> Any:
    """فقط پلاگین Twelve Data می‌تواند منبع قیمت و کندل بازار باشد."""
    kind = str(cfg.get("data_source", "twelvedata")).strip().lower()
    if kind != "twelvedata":
        raise ValueError(
            "منبع بازار نامعتبر است؛ تنها منبع مجاز Twelve Data است."
        )
    rec = registry.by_id("data-twelvedata")
    if rec is None or not rec.active:
        raise ValueError("پلاگین منبع داده «data-twelvedata» ثبت یا فعال نیست")
    return rec


def plugins() -> List[Tuple[PluginManifest, Any]]:
    return [
        (PluginManifest(
            id="data-twelvedata", version="1.0.0",
            provides=["odin.data.market@1"],
            platforms=["desktop"], stage="collect_market", priority=20,
            optional=True), _twelvedata),
        (PluginManifest(
            id="data-tradingview", version="1.0.0",
            provides=["odin.data.tv@1"],
            config={"section": "tradingview", "enabled_key": "enabled", "default": True},
            platforms=["desktop"], stage="collect_market", priority=40,
            optional=True), _tv),
    ]
