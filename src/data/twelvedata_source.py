# -*- coding: utf-8 -*-
"""تنها منبع دادهٔ قیمت بازار ODIN: Twelve Data.

برای هر نماد فقط یک درخواست M15 ارسال می‌شود؛ H1 و H4 از کندل‌های M15
بازنمونه‌گیری می‌شوند تا مصرف اعتبار API کنترل شود.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from .base import DataSource, MarketData


class TwelveDataSource(DataSource):
    name = "twelvedata"
    BASE_URL = "https://api.twelvedata.com/time_series"
    OUTPUTSIZE = 5000

    def __init__(self, cfg: dict):
        td = cfg.get("twelvedata") or {}
        h = cfg.get("history") or {}
        self.key = str(td.get("api_key") or "").strip()
        self.min_gap = max(7.5, float(td.get("min_request_gap_sec", 8)))
        self.drop_forming = bool(h.get("drop_forming_candle", True))
        self._last_call = 0.0

    def connect(self) -> None:
        if not self.key:
            raise RuntimeError(
                "کلید Twelve Data خالی است — در Twelve Data حساب بسازید و کلید شخصی را "
                "در twelvedata.api_key در config.local.yaml یا config.yaml قرار دهید"
            )

    def disconnect(self) -> None:
        pass

    def fetch(self, sym_cfg: dict) -> MarketData | None:
        td_sym = str(sym_cfg.get("td") or "").strip()
        if not td_sym:
            print(f"[!] نماد Twelve Data برای {sym_cfg.get('name', '?')} تعریف نشده است")
            return None

        try:
            # فقط یک درخواست برای هر نماد؛ تایم‌فریم‌های بالاتر از M15 ساخته می‌شوند.
            m15 = self._series(td_sym)
        except Exception as e:
            print(f"[!] خطای Twelve Data برای {sym_cfg['name']}: {str(e)[:140]}")
            return None
        if m15 is None or m15.empty:
            return None

        h1 = self._resample_m15(m15, 60)
        h4 = self._resample_m15(m15, 240)
        if len(m15) < 50 or len(h1) < 250 or len(h4) < 210:
            print(
                f"[!] تاریخچه Twelve Data برای {sym_cfg['name']} کافی نیست "
                f"(M15={len(m15)}, H1={len(h1)}, H4={len(h4)})"
            )
            return None

        md = MarketData(symbol=sym_cfg["name"], m15=m15, h1=h1, h4=h4)
        from .quality import validate_market_data
        problems = validate_market_data(md)
        if problems:
            print(
                f"[!] داده Twelve Data برای {sym_cfg['name']} از اعتبارسنجی کیفیت رد شد: "
                f"{'؛ '.join(problems[:3])}"
            )
            return None
        return md

    @staticmethod
    def _resample_m15(m15: pd.DataFrame, minutes: int) -> pd.DataFrame:
        """بازنمونه‌گیری UTC-aligned و حذف سطل‌های ناقص یا دارای کندل مفقود."""
        columns = ["Open", "High", "Low", "Close"]
        if m15 is None or m15.empty:
            return pd.DataFrame(columns=columns)
        expected = minutes // 15
        rule = f"{minutes}min"
        grouped = m15.resample(rule, origin="start_day", label="left", closed="left")
        frame = grouped.agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
        }).dropna()
        counts = grouped["Close"].count()
        complete = counts[counts == expected].index
        return frame.loc[frame.index.isin(complete), columns].dropna()

    def _series(self, td_sym: str) -> pd.DataFrame | None:
        # Basic: حداکثر ۸ اعتبار در دقیقه؛ فاصلهٔ حداقل ۷٫۵ ثانیه رعایت می‌شود.
        wait = self.min_gap - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

        response = requests.get(
            self.BASE_URL,
            params={
                "symbol": td_sym,
                "interval": "15min",
                "outputsize": self.OUTPUTSIZE,
                "timezone": "UTC",
                "apikey": self.key,
            },
            timeout=20,
        )
        payload = response.json()
        if "values" not in payload:
            message = payload.get("message") or payload.get("status")
            raise RuntimeError(message or f"پاسخ نامعتبر (HTTP {response.status_code})")

        frame = pd.DataFrame(list(reversed(payload["values"])))
        if frame.empty:
            return None
        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
        frame = frame.set_index("datetime")[["open", "high", "low", "close"]].astype(float)
        frame.index = frame.index.tz_convert("UTC").tz_localize(None)
        frame.columns = ["Open", "High", "Low", "Close"]
        frame = frame.dropna().sort_index()
        if self.drop_forming and len(frame) > 1:
            frame = frame.iloc[:-1]
        return frame
