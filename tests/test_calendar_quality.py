# -*- coding: utf-8 -*-
"""Offline regression tests for empty/invalid economic calendar responses."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fundamental import calendar


class Response:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def main() -> None:
    cfg = {"fundamental": {"source_url": "https://calendar.invalid", "cache_ttl_minutes": 30}}
    for payload in ([], [{"date": "not-a-date", "title": "invalid"}]):
        logs: list[str] = []
        with mock.patch.object(calendar.requests, "get", return_value=Response(payload)), \
             mock.patch.object(calendar, "_write_cache"):
            snap = calendar.fetch_calendar(cfg, on_log=logs.append, use_cache=False)
        assert not snap.ok, snap
        assert "فاقد رویداد معتبر" in snap.error, snap.error
        assert any("نبود رویداد تأییدشده نیست" in line for line in logs), logs

    print("calendar quality tests passed (empty and invalid payloads).")


if __name__ == "__main__":
    main()
