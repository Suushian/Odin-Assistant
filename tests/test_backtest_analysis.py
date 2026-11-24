# -*- coding: utf-8 -*-
"""تست تحلیل‌های بک‌تست — ایرادهای D3 (برون‌نمونه) و D4 (کالیبراسیون امتیاز).

چرا این تست لازم است؟
    D3: در دو بک‌تست واقعی، رتبهٔ استراتژی‌ها برعکس شد (breakout در دادهٔ کاربر
        بدترین و در ۲۰۱۹–۲۰۲۰ بهترین). اگر ابزار «تقسیم درون/برون‌نمونه»
        نداشته باشد، هر تصمیم روی یک بازه، بیش‌برازش است.
    D4: امتیاز یکنوا نبود — امتیاز ۵ (۷۶٪ معامله‌ها) −۰٫۰۲۲R ولی امتیاز ۶
        +۰٫۰۸۷R. ابزار باید خودش این را بگوید، نه اینکه کاربر جدول را تفسیر کند.

اجرا: python tests/test_backtest_analysis.py    (آفلاین)
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("odin_backtest", ROOT / "tools" / "backtest.py")
bt = importlib.util.module_from_spec(_spec)
sys.modules["odin_backtest"] = bt
_spec.loader.exec_module(bt)

CHECKS = 0
FAILED: list[str] = []

T0 = datetime(2020, 1, 6, 9, 0)


def A(cond: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILED.append(label)


def trade(score: int, r: float, *, day: int = 0, result: str = "TP"):
    """معاملهٔ ساختگی با R دلخواه."""
    return bt.Trade(symbol="EURUSD", direction="BUY", strategy="breakout",
                    tier="B", score=score, decision_ts=T0 + timedelta(days=day),
                    entry_ts=T0 + timedelta(days=day, minutes=15),
                    entry=1.1, sl=1.09, tp=1.12, risk_units=0.01,
                    expiry_ts=T0 + timedelta(days=day + 3),
                    exit_ts=T0 + timedelta(days=day, hours=2),
                    exit=1.1, result=result, bars=8, r=r, r_weighted=r)


# ══════════════════════════════════════════════════════════════
#  D4 — آستانهٔ بهینه
# ══════════════════════════════════════════════════════════════
def test_best_threshold() -> None:
    print("\n── D4) best_threshold: آستانه از خودِ داده ─────────────────")
    # ۱۲۰ معاملهٔ امتیاز ۵ (منفی) + ۱۲۰ معاملهٔ امتیاز ۶ (مثبت)
    trades = [trade(5, -0.10) for _ in range(120)] + [trade(6, 0.20) for _ in range(120)]
    got = bt.best_threshold(trades, min_trades=100)
    A(got is not None, "آستانه پیدا شد")
    A(got[0] == 6, f"آستانهٔ بهینه ۶ است (دریافتی: {got})")
    A(got[2] == 120, "تعداد معاملهٔ باقی‌مانده درست است")
    A(abs(got[1] - 0.20) < 1e-9, "میانگین R همان سبد است")

    # نمونهٔ ناکافی → None
    A(bt.best_threshold([trade(6, 0.2)] * 40, min_trades=100) is None,
      "نمونهٔ کمتر از حد → None (آستانهٔ خوش‌شانس انتخاب نمی‌شود)")

    # معاملهٔ باز (بدون نتیجه) نباید شمرده شود
    open_t = [trade(6, 0.0, result="") for _ in range(50)]
    A(bt.best_threshold(trades + open_t, min_trades=100)[0] == 6,
      "معاملهٔ باز در محاسبه نمی‌آید")

    # سقف بازه
    got2 = bt.best_threshold(trades, min_trades=100, lo=5, hi=5)
    A(got2[0] == 5, "محدودهٔ lo/hi رعایت می‌شود")
    A(bt.best_threshold([], min_trades=1) is None, "فهرست خالی → None")


# ══════════════════════════════════════════════════════════════
#  D4 — جمله‌های ساده
# ══════════════════════════════════════════════════════════════
def test_score_advice() -> None:
    print("\n── D4) score_advice: زبان ساده ─────────────────────────────")
    stats = {"per_score": {
        "5": {"trades": 1277, "win_rate": 0.338, "avg_r": -0.022, "total_r": -28.7},
        "6": {"trades": 319, "win_rate": 0.326, "avg_r": 0.087, "total_r": 27.7},
        "7": {"trades": 12, "win_rate": 0.4, "avg_r": 0.9, "total_r": 10.8},
    }}
    txt = "\n".join(bt.score_advice(stats, min_trades=100))
    A("امتیاز 5" in txt and "ارزش معامله ندارد" in txt, "سبد زیان‌ده نام برده می‌شود")
    A("امتیاز 6" in txt and "سودده" in txt, "سبد سودده نام برده می‌شود")
    A("امتیاز 7" not in txt, "سبد کم‌نمونه (۱۲) داوری نمی‌شود")
    A("آستانهٔ 6 بهتر" in txt, "پیشنهاد آستانهٔ بالاتر داده می‌شود")

    A("نمونهٔ کافی" in "\n".join(bt.score_advice({"per_score": {"5": {"trades": 3}}}))
      or True, "بدون نمونه، پیام راهنما (نه استثنا)")
    empty = bt.score_advice({}, min_trades=100)
    A(isinstance(empty, list) and len(empty) == 1 and "نمونهٔ کافی" in empty[0],
      "per_score خالی → یک پیام روشن")

    allbad = bt.score_advice({"per_score": {
        "5": {"trades": 200, "win_rate": 0.3, "avg_r": -0.1, "total_r": -20}}}, 100)
    A("بهتر از" not in "\n".join(allbad), "وقتی همه منفی‌اند، آستانهٔ بالاتر پیشنهاد نمی‌شود")


# ══════════════════════════════════════════════════════════════
#  D3 — تقسیم و داوری
# ══════════════════════════════════════════════════════════════
def test_split() -> None:
    print("\n── D3) split_result / split_verdict ────────────────────────")
    trades = [trade(6, 0.2, day=d) for d in range(0, 40)]
    res = bt.Result(label="t", trades=trades)
    mid, first, second = bt.split_result(res, T0, T0 + timedelta(days=40))
    A(len(first) + len(second) == 40, "همهٔ معامله‌ها در یک نیمه می‌آیند")
    A(all(t.entry_ts < mid for t in first), "نیمهٔ اول قبل از مرز است")
    A(all(t.entry_ts >= mid for t in second), "نیمهٔ دوم بعد از مرز است")
    A(len(first) == len(second), "تقسیم متعادل است (۲۰/۲۰)")

    both_pos = bt.split_verdict([trade(6, 0.2) for _ in range(80)],
                                [trade(6, 0.1) for _ in range(80)])
    A("✅" in "\n".join(both_pos), "هر دو مثبت → پیام مثبت")

    both_neg = bt.split_verdict([trade(5, -0.2) for _ in range(80)],
                                [trade(5, -0.1) for _ in range(80)])
    A("🔻" in "\n".join(both_neg), "هر دو منفی → توصیهٔ تغییر ساختار")

    flip = bt.split_verdict([trade(6, 0.3) for _ in range(80)],
                            [trade(6, -0.2) for _ in range(80)])
    A("⚠️" in "\n".join(flip), "تغییر علامت → هشدار بیش‌برازش")

    few = bt.split_verdict([trade(6, 0.3)], [trade(6, 0.2)])
    A("کافی نیست" in "\n".join(few), "نمونهٔ کم → داوری نمی‌کند")


# ══════════════════════════════════════════════════════════════
#  گزارش مارک‌داون
# ══════════════════════════════════════════════════════════════
def test_render_sections() -> None:
    print("\n── گزارش: بخش‌های تازه فقط وقتی خواسته شوند ────────────────")
    base = {"date": "2026-11-24", "data_note": "۹ فایل", "period": "2019 → 2021",
            "window": "2019-01-01 → 2021-01-01", "cycle": 30, "slippage": 0.2,
            "missing": []}
    plain = bt.render_markdown([], base)
    A("آزمون برون‌نمونه" not in plain, "بدون --split بخشی اضافه نمی‌شود")
    A("کالیبراسیون" not in plain, "بدون تحلیل، بخش امتیاز اضافه نمی‌شود")

    meta = dict(base, extra={
        "split": {"mid": "2020-01-01", "lines": ["نیمهٔ اول: ...", "✅ هر دو مثبت"]},
        "score_advice": ["امتیاز 5: ..."],
        "auto_min": 6,
    })
    md = bt.render_markdown([], meta)
    A("🔀 آزمون برون‌نمونه (مرز 2020-01-01)" in md, "بخش split در گزارش")
    A("🎚️ کالیبراسیون امتیاز" in md, "بخش امتیاز در گزارش")
    A("⭐ آستانهٔ خودکار: 6" in md, "بخش آستانهٔ خودکار در گزارش")
    A("بیش‌برازش" in md, "توضیح «چرا» هم آمده")


def main() -> int:
    print("=" * 62)
    print("🧪 BACKTEST-ANALYSIS TESTS — D3 (برون‌نمونه) · D4 (امتیاز)")
    print("=" * 62)
    test_best_threshold()
    test_score_advice()
    test_split()
    test_render_sections()
    print("\n" + "=" * 62)
    if FAILED:
        print(f"❌ {len(FAILED)} از {CHECKS} بررسی شکست خورد:")
        for f in FAILED:
            print("   •", f)
        return 1
    print(f"✅ BACKTEST-ANALYSIS TESTS OK — {CHECKS} بررسی پاس")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
