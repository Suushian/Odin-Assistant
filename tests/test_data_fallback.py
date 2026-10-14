# -*- coding: utf-8 -*-
"""تست‌های آفلاین برای ادامهٔ تلاش AutoSource پس از شکست یک منبع."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.auto_source import AutoSource  # noqa: E402


class Source:
    def __init__(self, name, result=None, error=None):
        self.name = name
        self.result = result
        self.error = error

    def fetch(self, _symbol):
        if self.error:
            raise self.error
        return self.result


def main() -> None:
    expected = object()
    auto = AutoSource.__new__(AutoSource)
    auto._connected = [
        Source("primary", error=RuntimeError("simulated provider outage")),
        Source("fallback", result=expected),
    ]
    assert auto.fetch({"name": "EURUSD"}) is expected

    auto._connected = [
        Source("primary", result=None),
        Source("fallback", result=expected),
    ]
    assert auto.fetch({"name": "XAUUSD"}) is expected
    print("auto-source fallback tests passed (2 scenarios).")


if __name__ == "__main__":
    main()
