# -*- coding: utf-8 -*-
"""نگهبان سیاست: منبع بازار جایگزین و fallback نباید فعال باشند."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from src.config import load_config
    from src.data import get_source
    from src.data.twelvedata_source import TwelveDataSource
    from src.plugins import build_default_registry
    from src.plugins.data import select_market_provider

    cfg = load_config()
    assert cfg["data_source"] == "twelvedata"
    source = get_source(cfg)
    assert isinstance(source, TwelveDataSource)

    registry, _ = build_default_registry(cfg)
    selected = select_market_provider(registry, cfg)
    assert selected.id == "data-twelvedata"
    market_providers = registry.providers("odin.data.market@1")
    assert [provider.id for provider in market_providers] == ["data-twelvedata"]

    for legacy in ("auto", "yahoo"):
        old_cfg = {**cfg, "data_source": legacy}
        for factory in (get_source, lambda value: select_market_provider(registry, value)):
            try:
                factory(old_cfg)
            except ValueError:
                pass
            else:
                raise AssertionError(f"legacy market source {legacy!r} must be rejected")

    print("market source policy passed: Twelve Data only; no fallback provider.")
    

if __name__ == "__main__":
    main()
