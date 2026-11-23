# -*- coding: utf-8 -*-
"""قیف سیگنال — پاسخِ داده‌محور به «چرا سیگنال کم است؟» (نسخهٔ ۱.۱).

پیش از این، تنها چیزی که در لاگ می‌ماند «N سیگنال صادر شد» بود؛ معلوم نبود
بقیهٔ نمادها کجا مردند: ستاپی شکل نگرفت؟ وتو شدند؟ امتیاز کم آوردند؟ سقف
چرخه خورد؟ این ماژول همان توزیع را برای هر چرخه و برای هر روز جمع می‌زند.

⚠️ قاعدهٔ صداقت: این ماژول هیچ‌وقت آستانه/وتو را شل نمی‌کند. فقط می‌شمارد.
اگر روزی «۵ سیگنال» درنیامد، عددها می‌گویند کدام دروازه بسته بوده است.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from ..fa import fa_num

# ترتیب نمایش = مسیر طبیعی عبور یک نماد از قیف
REASON_ORDER = ("SIGNAL", "WATCHLIST", "NO_SETUP", "LOW_SCORE", "VETO", "CAPPED", "DISABLED")

REASON_FA = {
    "SIGNAL": "سیگنال",
    "WATCHLIST": "دیده‌بان",
    "NO_SETUP": "بدون ستاپ",
    "LOW_SCORE": "امتیاز ناکافی",
    "VETO": "وتو",
    "CAPPED": "سقف چرخه",
    "DISABLED": "داور خاموش",
}


def summarize(judgments: Iterable) -> dict:
    """توزیع سرنوشت نمادها در یک چرخه.

    Returns: {"total", "signals", "counts", "vetoes", "line_fa"}
    """
    items = list(judgments or [])
    counts: dict[str, int] = {k: 0 for k in REASON_ORDER}
    veto_keys: dict[str, int] = {}
    for j in items:
        if getattr(j, "signal", None) is not None:
            counts["SIGNAL"] += 1
        else:
            reason = getattr(j, "reject_reason", "") or "?"
            counts[reason] = counts.get(reason, 0) + 1
        for v in (getattr(j, "vetoes", None) or []):
            veto_keys[v.key] = veto_keys.get(v.key, 0) + 1

    total = len(items)
    signals = counts.get("SIGNAL", 0)
    parts = [f"{fa_num(counts[k])} {REASON_FA[k]}" for k in REASON_ORDER
             if counts.get(k)]
    line = (f"🧭 قیف سیگنال (از {fa_num(total)} نماد): " + " | ".join(parts)
            if parts else "🧭 قیف سیگنال: هیچ نمادی داوری نشد")
    return {"total": total, "signals": signals, "counts": counts,
            "vetoes": veto_keys, "line_fa": line}


def merge_daily(prev: Optional[dict], snap: dict, now: datetime) -> dict:
    """جمع‌زدن قیفِ یک چرخه در سبدِ روز (UTC).

    شکل خروجی: {"days": {"YYYY-MM-DD": {"cycles", "total", "signals", "counts", "vetoes"}}}
    """
    out = dict(prev or {})
    days = dict(out.get("days") or {})
    key = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%d")
    day = dict(days.get(key) or {})
    day["cycles"] = int(day.get("cycles", 0)) + 1
    day["total"] = int(day.get("total", 0)) + int(snap.get("total", 0))
    day["signals"] = int(day.get("signals", 0)) + int(snap.get("signals", 0))
    counts = dict(day.get("counts") or {})
    for k, v in (snap.get("counts") or {}).items():
        counts[k] = int(counts.get(k, 0)) + int(v)
    day["counts"] = counts
    vetoes = dict(day.get("vetoes") or {})
    for k, v in (snap.get("vetoes") or {}).items():
        vetoes[k] = int(vetoes.get(k, 0)) + int(v)
    day["vetoes"] = vetoes
    days[key] = day
    out["days"] = days
    return out


def day_line(day: Optional[dict]) -> str:
    """یک خط فارسی از سبد امروز — برای گزارش/لاگ."""
    if not day:
        return ""
    counts = day.get("counts") or {}
    parts = [f"{fa_num(counts[k])} {REASON_FA[k]}" for k in REASON_ORDER if counts.get(k)]
    return (f"📅 امروز (تا این لحظه): {fa_num(day.get('signals', 0))} سیگنال در "
            f"{fa_num(day.get('cycles', 0))} چرخه — " + " | ".join(parts))
