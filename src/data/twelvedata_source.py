# -*- coding: utf-8 -*-
"""منبع واحد دادهٔ بازار: Twelve Data؛ هر نماد فقط یک درخواست M15 دارد."""
from __future__ import annotations

import time

import pandas as pd
import requests

from .base import DataSource, MarketData


class TwelveDataSource(DataSource):
    name = "twelvedata"
    BASE_URL = "https://api.twelvedata.com/time_series"

    def __init__(self, cfg: dict):
        td = cfg.get("twelvedata") or {}
        h = cfg.get("history") or {}
        self.key = str(td.get("api_key") or "").strip()
        self.min_gap = max(0.0, float(td.get("min_request_gap_sec", 8)))
        self.drop_forming = bool(h.get("drop_forming_candle", True))
        self.outputsize = max(4000, min(5000, int(h.get("td_m15_bars", 5000))))
        self._last_call = 0.0

    def connect(self) -> None:
        if not self.key:
            raise RuntimeError(
                "کلید Twelve Data خالی است — کلید API اختصاصی خود را در تنظیمات محلی وارد کنید"
            )

    def disconnect(self) -> None:
        pass

    def fetch(self, sym_cfg: dict) -> MarketData | None:
        td_sym = str(sym_cfg.get("td") or "").strip()
        if not td_sym:
            print(f"[!] نماد Twelve Data برای {sym_cfg.get('name', '?')} تعریف نشده است")
            return None
        try:
            m15 = self._series(td_sym)
            if m15 is None or m15.empty:
                return None
            h1 = self._resample_m15(m15, 1)
            h4 = self._resample_m15(m15, 4)
        except Exception as e:
            print(f"[!] خطای Twelve Data برای {sym_cfg['name']}: {str(e)[:140]}")
            return None
        if len(m15) < 50 or len(h1) < 250 or len(h4) < 210:
            print(f"[!] تاریخچه Twelve Data برای {sym_cfg['name']} کافی نیست "
                  f"(m15={len(m15)}, h1={len(h1)}, h4={len(h4)})")
            return None
        md = MarketData(symbol=sym_cfg["name"], m15=m15, h1=h1, h4=h4)
        from .quality import validate_market_data
        problems = validate_market_data(md)
        if problems:
            print(f"[!] داده Twelve Data برای {sym_cfg['name']} از اعتبارسنجی کیفیت رد شد: {'؛ '.join(problems[:3])}")
            return None
        return md

    def _series(self, td_sym: str) -> pd.DataFrame | None:
        wait = self.min_gap - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

        response = requests.get(self.BASE_URL, params={
            "symbol": td_sym,
            "interval": "15min",
            "outputsize": self.outputsize,
            "timezone": "UTC",
            "apikey": self.key,
        }, timeout=20)
        payload = response.json()
        if response.status_code != 200 or "values" not in payload:
            raise RuntimeError(payload.get("message") or payload.get("status") or
                               f"پاسخ نامعتبر (HTTP {response.status_code})")

        df = pd.DataFrame(list(reversed(payload["values"])))
        if df.empty or not {"datetime", "open", "high", "low", "close"} <= set(df.columns):
            return None
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_localize(None)
        df = df.set_index("datetime")[["open", "high", "low", "close"]].astype(float)
        df.columns = ["Open", "High", "Low", "Close"]
        df = df.sort_index().loc[~df.index.duplicated(keep="last")].dropna()
        if self.drop_forming and len(df) > 1:
            df = df.iloc[:-1]
        return df

    @staticmethod
    def _resample_m15(m15: pd.DataFrame, hours: int) -> pd.DataFrame:
        """ساخت فقط کندل‌های H1/H4 کامل و هم‌تراز با مرزهای UTC."""
        if m15 is None or m15.empty or hours not in (1, 4):
            return pd.DataFrame(columns=["Open", "High", "Low", "Close"])
        width = pd.Timedelta(hours=hours)
        step = pd.Timedelta(minutes=15)
        expected = hours * 4
        out = []
        for start, group in m15.groupby(pd.Grouper(freq=f"{hours}h", origin="epoch")):
            if group.empty or len(group) != expected:
                continue
            if group.index[0] != start or group.index[-1] != start + width - step:
                continue
            out.append((start, {
                "Open": float(group["Open"].iloc[0]),
                "High": float(group["High"].max()),
                "Low": float(group["Low"].min()),
                "Close": float(group["Close"].iloc[-1]),
            }))
        if not out:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close"])
        return pd.DataFrame([row for _, row in out],
                            index=pd.DatetimeIndex([start for start, _ in out], name=m15.index.name),
                            columns=["Open", "High", "Low", "Close"])
