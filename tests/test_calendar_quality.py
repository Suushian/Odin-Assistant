# -*- coding: utf-8 -*-
"""Offline regression tests for empty/invalid economic calendar responses."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fundamental import calendar
from src.fundamental.calendar import CalendarSnapshot
from src.judge.scoring import veto_event


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

    # When event veto is enabled, an unavailable calendar must not be treated
    # as proof that no high-impact event exists. Explicitly disabled remains opt-out.
    analysis = SimpleNamespace(base="EUR", quote="USD")
    ctx = SimpleNamespace(
        jcfg={"veto": {"high_impact_event": True}},
        cal_snap=CalendarSnapshot(events=[], error="network unavailable"),
        now=datetime(2026, 10, 14, 14, 30, tzinfo=timezone.utc),
        event_veto_minutes=30,
    )
    veto = veto_event(analysis, {}, None, ctx)
    assert veto is not None and veto.key == "CALENDAR_UNAVAILABLE", veto
    ctx.cal_snap = None  # feature explicitly disabled by configuration
    assert veto_event(analysis, {}, None, ctx) is None

    print("calendar quality tests passed (empty/invalid payloads + fail-closed veto).")


if __name__ == "__main__":
    main()
