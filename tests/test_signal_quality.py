# -*- coding: utf-8 -*-
"""تست‌های «کیفیت سیگنال» — نسخهٔ ۱٫۶٫۰.

سه چیزِ تازه را پین می‌کند:

۱) **دروازهٔ استراتژی** (`strategy_gate` در `src/judge/scoring.py`)
   • پیش‌فرض خاموش = رفتار ۱٫۵٫۰ دست‌نخورده (هیچ سیگنالی گم نمی‌شود)
   • ستاپ خاموش → رد با دلیل `STRATEGY_OFF`
   • آستانهٔ بالاتر برای یک ستاپ → `LOW_SCORE` با همان آستانهٔ مؤثر در متن

۲) **برش‌های تشخیصی بک‌تست** (`per_score`, `per_hour`, `per_weekday`) — همان
   چیزهایی که تصمیم «کدام امتیاز سود می‌دهد» را ممکن می‌کند.

۳) **جاروی آستانه** (`sweep_pick` / `render_sweep`) — انتخاب باید نمونهٔ کافی
   را شرط بگذارد، وگرنه یک آستانهٔ خوش‌شانس با ۸ معامله برندهٔ گزارش می‌شود.

اجرا: python tests/test_signal_quality.py     (آفلاین)
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

COUNT = 0
FAILS: list[str] = []


def A(cond: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not cond:
        FAILS.append(label)
        print(f"  ✗ {label}")


# ── بارگذاری ماژول بک‌تست و هارنس طلایی داور ─────────────────────────
_spec = importlib.util.spec_from_file_location("odin_backtest_sq", ROOT / "tools" / "backtest.py")
bt = importlib.util.module_from_spec(_spec)
sys.modules["odin_backtest_sq"] = bt
_spec.loader.exec_module(bt)

_g = importlib.util.spec_from_file_location(
    "gen_judge_golden_sq", ROOT / "tests" / "golden" / "gen_judge_golden.py")
gen = importlib.util.module_from_spec(_g)
sys.modules["gen_judge_golden_sq"] = gen
_g.loader.exec_module(gen)

from src.analysis.strategies import Setup                     # noqa: E402
from src.judge.scoring import judge_symbol, strategy_gate, symbol_gate   # noqa: E402


def _analysis(key: str = "range_reversion"):
    """تحلیل ساختگی با یک ستاپ مشخص — برای آزمودن دروازه."""
    a = gen.make_analysis()
    a.setups = [Setup(key, "EURUSD", "BUY", 3, 1.1490, 1.1486, ["تست"])]
    return a


def _judge(key: str, **over):
    ctx = gen.make_ctx(cal=gen.clean_cal(), news=gen.good_news(), **over)
    return judge_symbol(_analysis(key), {}, gen.make_md(), ctx)


# ── ۱) تابع خالص ─────────────────────────────────────────────────────
def test_gate_helper() -> None:
    print("\n── ۱) strategy_gate: پیش‌فرض خاموش و سه حالت روشن ──────────")
    off = strategy_gate({"strategy_gate": {"enabled": False}}, "breakout")
    A(off["on"] is False and off["allowed"] is True and off["min_score"] == 0,
      "پیش‌فرض: دروازه خاموش، ستاپ مجاز، آستانهٔ اضافه صفر")
    A(strategy_gate({}, "breakout")["on"] is False, "نبودِ کلید config = خاموش")

    g = {"strategy_gate": {"enabled": True,
                           "breakout": {"enabled": False},
                           "range_reversion": {"min_score": 8},
                           "trend_pullback": {"min_score": "6"}}}
    A(strategy_gate(g, "breakout")["allowed"] is False, "ستاپ خاموش → allowed=False")
    A(strategy_gate(g, "range_reversion")["min_score"] == 8, "min_score عددی خوانده شد")
    A(strategy_gate(g, "trend_pullback")["min_score"] == 6, "min_score رشته‌ای هم خوانده شد")
    A(strategy_gate(g, "unknown_key")["allowed"] is True, "ستاپ ناشناخته = بدون تغییر")
    A(strategy_gate({"strategy_gate": {"enabled": True,
                                       "breakout": {"min_score": "x"}}}, "breakout")["min_score"] == 0,
      "min_score نامعتبر → بی‌اثر (نه استثنا)")


# ── ۲) رفتار داوری ───────────────────────────────────────────────────
def test_gate_in_judge() -> None:
    print("\n── ۲) دروازه در مسیر داوری ─────────────────────────────────")
    base = _judge("range_reversion")
    A(base.signal is not None and base.reject_reason == "",
      "پیش‌فرض (دروازهٔ خاموش): سیگنال مثل قبل صادر می‌شود")
    score = base.score

    off = _judge("range_reversion",
                 strategy_gate={"enabled": True, "range_reversion": {"enabled": False}})
    A(off.signal is None and off.reject_reason == "STRATEGY_OFF",
      "ستاپ خاموش → STRATEGY_OFF و بدون سیگنال")
    A("«بازگشت از کف/سقف رنج»" in off.reject_detail,
      "متن رد، نام فارسی همان ستاپ را دارد")
    A(str(score) in off.reject_detail.replace("۰", "0").replace("۱", "1")
      .replace("۲", "2").replace("۳", "3").replace("۴", "4").replace("۵", "5")
      .replace("۶", "6").replace("۷", "7").replace("۸", "8").replace("۹", "9"),
      "متن رد، امتیاز همان ستاپ را نشان می‌دهد")

    high = _judge("range_reversion",
                  strategy_gate={"enabled": True, "range_reversion": {"min_score": 11}})
    A(high.signal is None and high.reject_reason == "LOW_SCORE",
      "آستانهٔ ۱۱ برای ستاپ با امتیاز کمتر → LOW_SCORE")
    A("۱۱" in high.reject_detail, "متن LOW_SCORE آستانهٔ مؤثر (۱۱) را نشان می‌دهد")

    same = _judge("range_reversion",
                  strategy_gate={"enabled": True, "range_reversion": {"min_score": 5}})
    A(same.signal is not None, "آستانهٔ ۵ = آستانهٔ عمومی → سیگنال صادر می‌شود")

    other = _judge("trend_pullback",
                   strategy_gate={"enabled": True, "range_reversion": {"enabled": False}})
    A(other.signal is not None,
      "خاموش‌کردن یک ستاپ، ستاپ‌های دیگر را نمی‌بندد")


# ── ۳) برش‌های تشخیصی ────────────────────────────────────────────────
def _trade(score: int, hour: int, weekday: int, r: float):
    t0 = datetime(2026, 3, 2) + timedelta(days=weekday)      # ۲ مارس ۲۰۲۶ = دوشنبه
    ts = t0.replace(hour=hour)
    return bt.Trade(symbol="EURUSD", direction="BUY", strategy="trend_pullback",
                    tier="B", score=score, decision_ts=ts, entry_ts=ts,
                    entry=1.1, sl=1.09, tp=1.12, risk_units=0.01,
                    expiry_ts=ts + timedelta(hours=8), result="TP" if r > 0 else "SL",
                    r=r, r_gross=r, r_weighted=r)


def test_stats_breakdowns() -> None:
    print("\n── ۳) برش‌های تازهٔ stats ───────────────────────────────────")
    trades = [
        _trade(7, 9, 0, +2.0), _trade(7, 9, 0, -1.0),
        _trade(9, 15, 2, +2.0), _trade(5, 15, 2, -1.0),
    ]
    res = bt.Result(label="test", trades=trades, signals=4, days=4)
    s = res.stats()
    for key in ("per_score", "per_hour", "per_weekday"):
        A(key in s, f"کلید {key} در stats هست")
    A(set(s["per_score"]) == {"5", "7", "9"}, "per_score بر اساس امتیاز گروه شد")
    A(s["per_score"]["7"]["trades"] == 2 and abs(s["per_score"]["7"]["avg_r"] - 0.5) < 1e-9,
      "per_score[7]: دو معامله، میانگین R = +۰٫۵")
    A(set(s["per_hour"]) == {"09", "15"}, "per_hour با دو رقم (UTC) گروه شد")
    A(s["per_hour"]["09"]["trades"] == 2, "per_hour[09]: دو معامله")
    A(set(s["per_weekday"]) == {"0", "2"}, "per_weekday بر اساس روز هفته گروه شد")


# ── ۴) جاروی آستانه ──────────────────────────────────────────────────
def test_sweep_helpers() -> None:
    print("\n── ۴) جاروی آستانه: انتخاب با شرط نمونه ────────────────────")
    meta = {"date": "2026-11-24", "period": "2024-01-01 → 2025-12-31", "slippage": 0.3}

    def mk(min_score: int, n: int, avg: float):
        trades = [_trade(min_score, 10, 1, avg)] * n
        return min_score, bt.Result(label=f"min_score={min_score}", trades=trades,
                                    signals=n, days=100)

    pairs = [mk(5, 400, -0.03), mk(6, 250, 0.02), mk(7, 120, 0.11), mk(8, 12, 0.60)]
    A(bt.sweep_pick(pairs) == 7,
      "جارو آستانهٔ ۸ را با ۱۲ معامله رد می‌کند و ۷ را (۱۲۰ معامله) برمی‌گزیند")
    A(bt.sweep_pick([mk(8, 5, 0.9)]) is None, "اگر هیچ آستانه‌ای نمونهٔ کافی نداشت → None")

    md = bt.render_sweep(pairs, meta)
    A("min_score = 7" in md, "گزارش جارو، آستانهٔ پیشنهادی را صریح می‌نویسد")
    A("واک‌فوروارد" in md, "گزارش هشدار فیت‌شدن روی گذشته را می‌دهد")
    A(md.count("|") > 20, "جدول مارک‌داون ساخته شد")



# ── ۵) ابزار «چه کاری الان انجام بدهم» (tools/quality_check.py) ───────
def test_quality_check_tool() -> None:
    print("\n── ۵) ابزار check: خلاصه و پیشنهاد ─────────────────────────")
    qs = importlib.util.spec_from_file_location("odin_qc", ROOT / "tools" / "quality_check.py")
    qc = importlib.util.module_from_spec(qs)
    sys.modules["odin_qc"] = qc
    qs.loader.exec_module(qc)

    stats = {
        "trades": 120, "hit_rate": 0.35, "avg_r": -0.02,
        "profit_factor": 0.94, "max_dd_r": -18.0,
        "per_strategy": {
            "trend_pullback": {"trades": 60, "win_rate": 0.42, "avg_r": 0.08, "total_r": 4.8},
            "range_reversion": {"trades": 55, "win_rate": 0.27, "avg_r": -0.12, "total_r": -6.6},
            "breakout": {"trades": 5, "win_rate": 0.0, "avg_r": -0.9, "total_r": -4.5},
        },
        "per_symbol": {
            "EURUSD": {"trades": 60, "win_rate": 0.42, "avg_r": 0.115, "total_r": 6.9},
            "GBPUSD": {"trades": 58, "win_rate": 0.24, "avg_r": -0.218, "total_r": -12.6},
            "XAUUSD": {"trades": 40, "win_rate": 0.30, "avg_r": -0.066, "total_r": -2.6},
        },
        "per_score": {"5": {"trades": 70, "win_rate": 0.31, "avg_r": -0.09, "total_r": -6.3},
                      "7": {"trades": 50, "win_rate": 0.41, "avg_r": 0.09, "total_r": 4.5}},
    }

    lines = qc.summarize(stats, min_trades=30)
    joined = "\n".join(lines)
    A("range_reversion" in joined and "trend_pullback" in joined,
      "خلاصه، استراتژی‌های با نمونهٔ کافی را می‌آورد")
    A("breakout" not in joined, "گروه با ۵ معامله (کمتر از آستانهٔ ۳۰) حذف می‌شود")
    A("امتیاز 5" in joined and "امتیاز 7" in joined, "جدول امتیاز در خلاصه هست")

    tips = "\n".join(qc.advice(stats, min_trades=30))
    A("range_reversion" in tips and "منفی" in tips, "پیشنهاد، استراتژی منفی را نام می‌برد")
    A("trend_pullback" in tips, "پیشنهاد، تنها گروهِ سودده را هم نام می‌برد")
    A("breakout" not in tips, "پیشنهاد روی نمونهٔ ناکافی تصمیم نمی‌گیرد")

    tips2 = "\n".join(qc.advice(stats, min_trades=30))
    A("GBPUSD" in tips2 and "symbol_gate" in tips2, "پیشنهاد، نماد زیان‌ده را با symbol_gate نام می‌برد")
    A("پراکندگی نمادها" in tips2, "پراکندگی نمادها گزارش می‌شود")

    A("همهٔ گروه‌ها منفی" in "\n".join(qc.advice(
        {"per_strategy": {"a": {"trades": 40, "win_rate": 0.2, "avg_r": -0.1, "total_r": -4},
                          "b": {"trades": 40, "win_rate": 0.3, "avg_r": -0.05, "total_r": -2}}})),
      "حالت «همه منفی» پیام درست می‌دهد")
    A("نمونهٔ کافی" in "\n".join(qc.advice({"per_strategy": {}})),
      "نبودِ نمونه → پیام صریح، نه استثنا")

    # نام‌گذاری فایل‌ها همان قاعدهٔ read_data است
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        for n in ("EURUSD_M15.csv", "XAUUSD.csv", "EURUSD_H1.csv", "notes.txt"):
            (pathlib.Path(tmp) / n).write_text("time,open,high,low,close\n", encoding="utf-8")
        got = set(qc.data_files(pathlib.Path(tmp)))
        A(got == {"EURUSD", "XAUUSD"}, f"فقط CSVهای M15 شمرده می‌شوند (دریافتی: {got})")


# ── ۶) دروازهٔ نماد (D2) ─────────────────────────────────────────────
def test_symbol_gate() -> None:
    print("\n── ۶) symbol_gate: خاموش‌کردن یک نماد یا آستانهٔ آن ─────────")

    off = symbol_gate({"symbol_gate": {"enabled": False}}, "GBPUSD")
    A(off["on"] is False and off["allowed"] is True and off["min_score"] == 0,
      "پیش‌فرض: دروازهٔ نماد خاموش")
    A(symbol_gate({}, "GBPUSD")["on"] is False, "نبودِ کلید config = خاموش")

    g = {"symbol_gate": {"enabled": True, "GBPUSD": {"enabled": False},
                         "XAUUSD": {"min_score": 9}, "EURJPY": {"min_score": "7"}}}
    A(symbol_gate(g, "GBPUSD")["allowed"] is False, "نماد خاموش → allowed=False")
    A(symbol_gate(g, "XAUUSD")["min_score"] == 9, "min_score عددی")
    A(symbol_gate(g, "EURJPY")["min_score"] == 7, "min_score رشته‌ای")
    A(symbol_gate(g, "EURUSD")["allowed"] is True, "نماد دیگر دست‌نخورده")
    A(symbol_gate({"symbol_gate": {"enabled": True, "EURUSD": {"min_score": "x"}}},
                  "EURUSD")["min_score"] == 0, "min_score نامعتبر → بی‌اثر")
    A(symbol_gate(g, "")["on"] is True and symbol_gate(g, "")["allowed"] is True,
      "نماد خالی → بدون رد (نه استثنا)")

    # مسیر داوری
    base = _judge("range_reversion")
    A(base.signal is not None, "دروازهٔ خاموش: سیگنال صادر می‌شود")
    sym = base.symbol

    j = _judge("range_reversion", symbol_gate={"enabled": True, sym: {"enabled": False}})
    A(j.signal is None and j.reject_reason == "SYMBOL_OFF", "نماد خاموش → SYMBOL_OFF")
    A(f"«{j.fa_name}»" in j.reject_detail, "متن رد، نام فارسی نماد را دارد")
    A("خاموش" in j.reject_detail and len(j.reject_detail) > 25, "متن رد کامل است")

    j = _judge("range_reversion", symbol_gate={"enabled": True, sym: {"min_score": 11}})
    A(j.signal is None and j.reject_reason == "LOW_SCORE",
      "آستانهٔ ۱۱ برای نماد → LOW_SCORE (نه SYMBOL_OFF)")
    A("۱۱" in j.reject_detail, "متن LOW_SCORE آستانهٔ مؤثر نماد را دارد")

    j = _judge("range_reversion", symbol_gate={"enabled": True, sym: {"min_score": 5}})
    A(j.signal is not None, "آستانهٔ ۵ = عمومی → سیگنال صادر می‌شود")

    # هر دو دروازه: دلیل ستاپ اولویت دارد (چون اول بررسی می‌شود)
    j = _judge("range_reversion",
               strategy_gate={"enabled": True, "range_reversion": {"enabled": False}},
               symbol_gate={"enabled": True, sym: {"enabled": False}})
    A(j.reject_reason == "STRATEGY_OFF", "وقتی هر دو خاموش‌اند، ستاپ اولویت دارد")

    # بالاترین آستانهٔ دو دروازه اعمال می‌شود
    j = _judge("range_reversion",
               strategy_gate={"enabled": True, "range_reversion": {"min_score": 6}},
               symbol_gate={"enabled": True, sym: {"min_score": 11}})
    A(j.reject_reason == "LOW_SCORE" and "۱۱" in j.reject_detail,
      "آستانهٔ نماد (۱۱) بر آستانهٔ ستاپ (۶) غالب می‌شود")

    # config واقعی: کلیدها با نمادهای پیکربندی هم‌خوان‌اند
    from src.config import load_config
    cfg = load_config()
    sg = (cfg.get("judge") or {}).get("symbol_gate") or {}
    A(sg.get("enabled") is False, "config.yaml: دروازهٔ نماد پیش‌فرض خاموش است")
    names = [s["name"] for s in cfg["symbols"]]
    A(all(n in sg for n in names), "config.yaml: هر ۱۰ نماد در symbol_gate آمده")

def main() -> int:
    print("🔎 تست کیفیت سیگنال (v1.6.0)")
    test_gate_helper()
    test_gate_in_judge()
    test_stats_breakdowns()
    test_sweep_helpers()
    test_quality_check_tool()
    test_symbol_gate()
    print("\n" + "=" * 60)
    if FAILS:
        print(f"❌ SIGNAL-QUALITY TESTS FAILED — {len(FAILS)} از {COUNT} بررسی")
        for f in FAILS:
            print("  •", f)
        return 1
    print(f"✅ SIGNAL-QUALITY TESTS OK — {COUNT} بررسی پاس؛ دروازهٔ استراتژی، "
          f"برش‌های تشخیصی، انتخاب آستانه و ابزار check قفل شدند")
    return 0


if __name__ == "__main__":
    sys.exit(main())
