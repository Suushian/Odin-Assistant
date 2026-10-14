# -*- coding: utf-8 -*-
"""موتور فاندامنتال و اخبار (مرحله ۲).

ماژول‌ها:
  calendar : تقویم اقتصادی (ForexFactory JSON) + تشخیص رویداد پراثر + دروازه وتو
  news     : رصد اخبار فارکس از فیدهای RSS رایگان با امتیازدهی جهت‌دار

دریافت اخبار در صورت قطع منبع تحمل‌پذیر است و در گزارش ثبت می‌شود. اما وقتی
تقویم فعال است، نبود پلاگین/دادهٔ قابل تأیید به‌معنای نبود رویداد نیست و داور
برای جلوگیری از سیگنال بدون بررسی ریسک خبری، fail-closed عمل می‌کند.
"""
from __future__ import annotations

from .calendar import (  # noqa: F401
    CalendarEvent,
    CalendarSnapshot,
    fetch_calendar,
    parse_events,
    upcoming_events,
    veto_for_symbol,
)
from .news import (  # noqa: F401
    NewsItem,
    NewsSnapshot,
    NewsVote,
    detect_currencies,
    fetch_news,
    market_movers,
    news_supports,
    parse_entries,
    score_text,
    subject_spans,
)
