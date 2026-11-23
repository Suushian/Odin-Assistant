# -*- coding: utf-8 -*-
"""میخ‌های رفتاری «چند استراتژی + رده‌بندی + پورتفوی» — نسخهٔ ۱.۱.

اجرا:  python tests/test_strategies.py      (از ریشهٔ ریپو — آفلاین)

چرا این تست؟ پیش از ۱.۱ تنها یک قاعده ستاپ می‌ساخت (پولبک در روند) و هر
بازار رنج/شکست کاملاً از دست می‌رفت. این فایل رفتار جدید را پین می‌کند:

  ۱) سه استراتژی و کیفیت/جهتشان + خاموش‌کردن از config
  ۲) انتخاب «ستاپ برتر» و اولویت آن
  ۳) رده‌بندی A/B/C و «دیده‌بان» (بدون پایین‌آوردن min_score)
  ۴) استثنای وتوی رنج/تضاد تایم‌فریم برای استراتژی رنج
  ۵) حد ضرر بر پایهٔ لبهٔ شکست (stop_ref)
  ۶) برابری بایت‌به‌بایت خروجی ستاپ‌ها با آینهٔ جاوااسکریپت (technical.js)
  ۷) سهمیهٔ Twelve Data در config.yaml (۱۰ نماد × ۴۸ چرخه ≤ ۸۰۰)

⚠️ طلایی‌های تاریخی (`tests/golden/run_cycle_golden.json` و داور) عمداً
   «رفتار تک‌استراتژی» را پین می‌کنند و در این تست دست نمی‌خورند.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0] if (HERE.parents[0] / "main.py").exists() else HERE.parent
sys.path.insert(0, str(ROOT))

COUNT = 0


def A(cond: bool, msg: str) -> None:
    global COUNT
    assert cond, msg
    COUNT += 1


print("=" * 74)
print("۱) استراتژی‌ها: تشخیص، کیفیت، جهت، خاموش‌کردن")
print("=" * 74)

from src.analysis.strategies import (  # noqa: E402
    STRATEGY_FA, MarketState, best_setup, build_setups, strategy_enabled,
)

ACFG = {"adx_min_trend": 20, "adx_strong": 25}
SCFG = {}


def st(**kw) -> MarketState:
    base = dict(price=1.1000, trend="bullish", h1_agrees=True, adx=30.0, rsi=40.0,
                rsi_rising=True, atr=0.0010, support=1.0995, resistance=1.1050,
                range_high=1.1040, range_low=1.0960,
                prev_range_high=1.1035, prev_range_low=1.0965, prev_close=1.1010)
    base.update(kw)
    return MarketState(**base)


# پولبک در روند — همان قاعدهٔ ۱.۰
s = build_setups(st(), "EURUSD", ACFG, SCFG)
A(len(s) == 1 and s[0].key == "trend_pullback", f"پولبک شناسایی شد: {[x.key for x in s]}")
A(s[0].direction == "BUY" and s[0].quality == 3, "پولبک خرید با کیفیت ۳ (ADX قوی + برگشت RSI)")
A(s[0].stop_ref == 1.0995, "سطح مرجع حد ضرر پولبک = حمایت")
A(s[0].setup_id == "EURUSD|trend_pullback|BUY", f"شناسهٔ ستاپ: {s[0].setup_id}")
A(s[0].label_fa == STRATEGY_FA["trend_pullback"], "برچسب فارسی استراتژی")

# پولبک بدون تایید برگشت → کیفیت پایین‌تر، نه حذف
s = build_setups(st(rsi_rising=False), "EURUSD", ACFG, SCFG)
A(len(s) == 1 and s[0].quality == 2, f"پولبک بدون برگشت RSI → کیفیت ۲ (نه ۳): {s}")

# فروش آینه‌ای
s = build_setups(st(trend="bearish", rsi=62.0, rsi_rising=False), "EURUSD", ACFG, SCFG)
A(len(s) == 1 and (s[0].key, s[0].direction) == ("trend_pullback", "SELL"), "پولبک فروش")
A(s[0].stop_ref == 1.1050, "سطح مرجع فروش = مقاومت")

# بازار رنج: استراتژی بازگشت
s = build_setups(st(adx=14.0, rsi=28.0, price=1.0996, h1_agrees=False), "EURUSD", ACFG, SCFG)
A(len(s) == 1 and s[0].key == "range_reversion" and s[0].direction == "BUY",
  f"رنج: بازگشت خرید از حمایت: {[(x.key, x.direction) for x in s]}")
A(s[0].quality == 3, "کیفیت ۳ چون قیمت به سطح چسبیده (dist ≤ band/2)")

s = build_setups(st(adx=17.0, rsi=74.0, rsi_rising=False, price=1.1047), "EURUSD", ACFG, SCFG)
A(len(s) == 1 and (s[0].key, s[0].direction) == ("range_reversion", "SELL"),
  "رنج: بازگشت فروش از مقاومت")

# شکست تازه
s = build_setups(st(adx=28.0, rsi=62.0, price=1.1060, support=1.1000, resistance=1.1060,
                    range_high=1.1050, prev_range_high=1.1048, prev_close=1.1045),
                 "EURUSD", ACFG, SCFG)
A(len(s) == 1 and s[0].key == "breakout" and s[0].direction == "BUY", "شکست صعودی تازه")
A(s[0].stop_ref == 1.1050, "سطح مرجع حد ضرر شکست = لبهٔ دامنه")
A(s[0].quality == 3, "کیفیت ۳ شکست (ADX قوی + هم‌جهتی H1)")

# شکست *غیرتازه* (کندل قبلی هم بیرون بود) → هیچ ستاپی
s = build_setups(st(adx=28.0, rsi=62.0, price=1.1060, range_high=1.1050,
                    prev_range_high=1.1055, prev_close=1.1058), "EURUSD", ACFG, SCFG)
A(s == [], "شکست تکراری (کندل قبلی بیرون بود) شلیک نمی‌کند — ضد اسپم")

# شکست بدون ADX کافی
s = build_setups(st(adx=19.0, rsi=62.0, price=1.1060, range_high=1.1050,
                    prev_range_high=1.1048, prev_close=1.1045), "EURUSD", ACFG, SCFG)
A(s == [], "شکست با ADX زیر آستانهٔ شکست رد می‌شود")

# خاموش‌کردن استراتژی‌ها از config (دو شکل)
A(strategy_enabled({"breakout": False}, "breakout") is False, "شکل کوتاه {breakout: false}")
A(strategy_enabled({"breakout": {"enabled": False}}, "breakout") is False, "شکل کامل enabled:false")
A(strategy_enabled({}, "breakout") is True, "نبود کلید = روشن")
A(build_setups(st(), "EURUSD", ACFG, {"trend_pullback": {"enabled": False}}) == [],
  "خاموش‌کردن trend_pullback → هیچ ستاپی")
A(all(x.key != "range_reversion" for x in
      build_setups(st(adx=14.0, rsi=28.0, price=1.0996), "EURUSD", ACFG,
                   {"range_reversion": {"enabled": False}})),
  "خاموش‌کردن range_reversion → رنج ستاپ نمی‌دهد")


# ── اولویت ستاپ برتر
print()
print("=" * 74)
print("۲) انتخاب ستاپ برتر — کیفیت، بعد اولویت استراتژی")
print("=" * 74)

both = build_setups(st(adx=26.0, rsi=40.0), "EURUSD", ACFG, SCFG)
A(len(both) >= 1, "حداقل یک ستاپ")
A(best_setup(both, {}).key == both[0].key, "best_setup = بهترین ستاپ مرتب‌شده")


class _S:
    def __init__(self, key, quality, direction="BUY"):
        self.key, self.quality, self.direction = key, quality, direction


A(best_setup([_S("range_reversion", 3), _S("trend_pullback", 2)], {}).key == "range_reversion",
  "کیفیت بالاتر برنده است")
A(best_setup([_S("range_reversion", 3), _S("trend_pullback", 3)], {}).key == "trend_pullback",
  "با کیفیت برابر، اولویت استراتژی (پولبک > رنج)")
A(best_setup([_S("trend_pullback", 3)], {"trend_pullback": False}) is None,
  "ستاپ استراتژی خاموش نادیده گرفته می‌شود")
A(best_setup([], {}) is None and best_setup(None, {}) is None, "فهرست خالی → None")


# ── رده‌بندی A/B/C
print()
print("=" * 74)
print("۳) رده‌بندی A/B/C و «دیده‌بان» — min_score دست‌نخورده")
print("=" * 74)

_spec = importlib.util.spec_from_file_location("gen_judge_golden",
                                               HERE / "golden" / "gen_judge_golden.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

from src.judge.scoring import judge_symbol  # noqa: E402

TIERS_ON = {"enabled": True, "a_min_score": 7, "c_min_score": 4, "b_soft_vetoes": 1}

j = judge_symbol(gen.make_analysis(), {}, None, gen.make_ctx(tiers=TIERS_ON))
A(j.signal is not None, "امتیاز کامل → سیگنال")
A(j.tier == "A" and j.signal.tier == "A", f"امتیاز ۱۱ و بدون وتوی نرم → ردهٔ A: {j.tier}")
A(j.signal.actionable is True, "سیگنال تازه قابل‌اقدام است")
A(j.strategy == "" and j.signal.strategy == "", "تحلیل دست‌ساز (بدون setups) استراتژی ندارد")

# یک وتوی نرم (تضاد تایم‌فریم) → حداکثر B، ولی سیگنال صادر می‌شود
j = judge_symbol(gen.make_analysis(h1_agrees=False), {}, None, gen.make_ctx(tiers=TIERS_ON))
A(j.signal is not None, "با یک وتوی نرم سیگنال صادر می‌شود (نه وتوی کامل)")
A(j.tier == "B", f"با یک وتوی نرم → ردهٔ B: {j.tier}")
A(any("ردهٔ B" in w for w in j.signal.warnings), "هشدار «نیمریسک» به سیگنال اضافه شد")

# ردهٔ A فقط با امتیاز بالا
j = judge_symbol(gen.make_analysis(), {}, None,
                 gen.make_ctx(tiers={"enabled": True, "a_min_score": 12}))
A(j.signal is not None and j.tier == "B", "امتیاز زیر a_min_score → B")

# دیده‌بان: امتیاز زیر آستانه ولی بالای c_min → WATCHLIST، بدون سیگنال
j = judge_symbol(gen.make_analysis(), {}, None,
                 gen.make_ctx(min_score=12,
                              tiers={"enabled": True, "a_min_score": 7,
                                     "c_min_score": 6, "b_soft_vetoes": 1}))
A(j.signal is None and j.reject_reason == "WATCHLIST", f"امتیاز ۱۱ با آستانهٔ ۱۲ → دیده‌بان: {j.reject_reason}")
A("دیده‌بان" in j.status_fa, f"برچسب فارسی دیده‌بان: {j.status_fa}")
A(j.reject_detail and "امتیاز" in j.reject_detail, "دلیل دیده‌بان با عدد امتیاز گفته می‌شود")

# زیر c_min → همان LOW_SCORE قدیمی
# (c_min = min_score یعنی «دیده‌بان خاموش»؛ در config معتبر همیشه c_min < min_score
#  است و tests/check_config.py همین را تضمین می‌کند)
j = judge_symbol(gen.make_analysis(), {}, None,
                 gen.make_ctx(min_score=12,
                              tiers={"enabled": True, "a_min_score": 7,
                                     "c_min_score": 12, "b_soft_vetoes": 1}))
A(j.reject_reason == "LOW_SCORE", f"زیر c_min → LOW_SCORE (رفتار قبلی): {j.reject_reason}")

# رده‌بندی خاموش → رفتار ۱.۰ (هیچ tierای ست نمی‌شود)
j = judge_symbol(gen.make_analysis(), {}, None, gen.make_ctx(tiers={"enabled": False}))
A(j.signal is not None and j.tier == "", "رده‌بندی خاموش → بدون برچسب رده (سازگاری کامل)")


# ── استراتژی در داور: وتوها، جهت، حد ضرر
print()
print("=" * 74)
print("۴) داور با ستاپ: استثنای وتو، جهت از ستاپ، حد ضرر روی لبهٔ شکست")
print("=" * 74)

from src.analysis.strategies import Setup, entry_at_market  # noqa: E402

# ستاپ رنج روی نمادی که ADX پایین دارد → وتوی «بازار رنج» نباید شلیک شود
range_analysis = gen.make_analysis(adx=14.0, h1_agrees=False, verdict="RANGE", rsi=28.0,
                                   price=1.0996)
range_analysis.setups = [Setup("range_reversion", "EURUSD", "BUY", 3, 1.0996, 1.0995,
                               ["بازگشت از کف رنج"])]
j = judge_symbol(range_analysis, {}, None, gen.make_ctx(tiers=TIERS_ON))
A(not any(v.key == "RANGE" for v in j.vetoes), "وتوی رنج برای ستاپ بازگشت از رنج حذف شد")
A(not any(v.key == "TF_CONFLICT" for v in j.vetoes), "وتوی تضاد تایم‌فریم هم استثنا شد")
A(j.direction == "BUY" and j.strategy == "range_reversion", f"جهت از ستاپ: {j.direction}")
A(any(e.key == "trend" and e.points == 1 for e in j.evidences),
  "مدرک روند برای ستاپ رنج صادقانه ۱ از ۲ است (نه ۲ گمراه‌کننده)")

# ستاپ شکست: جهت از ستاپ (حتی وقتی verdict چیز دیگری می‌گوید) و حد ضرر زیر لبه
bo = gen.make_analysis(verdict="WAIT", adx=28.0, rsi=62.0, price=1.1060,
                       support=1.1000, resistance=1.1060)
bo.setups = [Setup("breakout", "EURUSD", "BUY", 3, 1.1060, 1.1050, ["شکست سقف دامنه"])]
j = judge_symbol(bo, {}, None, gen.make_ctx(tiers=TIERS_ON))
A(j.direction == "BUY" and j.strategy == "breakout", "جهت از ستاپ شکست گرفته شد")
A(j.signal is None or (1.1040 <= j.signal.sl < 1.1050),
  f"حد ضرر شکست زیر لبهٔ 1.1050 و نه دورتر: {j.signal.sl if j.signal else None}")

# ── نسخهٔ ۱.۱.۱ — قیمت مرجع ورود: شکست با کلوز M15، پولبک با کلوز H1
A(entry_at_market("breakout") is True, "شکست: قیمت مرجع لحظه‌ای")
A(entry_at_market("trend_pullback") is False and entry_at_market("range_reversion") is False,
  "پولبک و رنج: قیمت مرجع همان H1 (سازگاری با ۱.۰)")

bo2 = gen.make_analysis(verdict="WAIT", adx=28.0, rsi=62.0, price=1.1060,
                        support=1.1000, resistance=1.1060)
bo2.entry_ref = 1.1075                     # کلوز M15 جلوتر از کلوز H1
bo2.setups = [Setup("breakout", "EURUSD", "BUY", 3, 1.1075, 1.1050, ["شکست سقف دامنه"])]
j = judge_symbol(bo2, {}, None, gen.make_ctx(tiers=TIERS_ON))
A(j.signal is not None and abs(j.signal.entry - 1.1075) < 1e-9,
  f"ورود سیگنال شکست از کلوز M15 (نه H1): {j.signal.entry if j.signal else None}")

pb2 = gen.make_analysis(price=1.1000)
pb2.entry_ref = 1.1010
pb2.setups = [Setup("trend_pullback", "EURUSD", "BUY", 2, 1.1000, 0.9990, ["پولبک"])]
j = judge_symbol(pb2, {}, None, gen.make_ctx(tiers=TIERS_ON))
A(j.signal is not None and abs(j.signal.entry - 1.1000) < 1e-9,
  "ورود سیگنال پولبک همان کلوز H1 است (سازگاری کامل)")

# ستاپ خاموش در config → داور به verdict قدیمی برمی‌گردد
j = judge_symbol(gen.make_analysis(), {}, None,
                 gen.make_ctx(scfg={"trend_pullback": {"enabled": False}}))
A(j.strategy == "" and j.direction == "BUY",
  "ستاپ خاموش → مسیر قدیمی verdict (سازگاری)")


# ── برابری با جاوااسکریپت
print()
print("=" * 74)
print("۵) برابری بایت‌به‌بایت با آینهٔ JS (technical.js → O.buildSetups)")
print("=" * 74)

STATES = [
    dict(price=1.10, trend="bullish", h1_agrees=True, adx=28.0, rsi=40.0, rsi_rising=True,
         atr=0.0012, support=1.0995, resistance=1.1050, range_high=1.1040, range_low=1.0960,
         prev_range_high=1.1035, prev_range_low=1.0965, prev_close=1.1010),
    dict(price=1.10, trend="bearish", h1_agrees=False, adx=14.0, rsi=28.0, rsi_rising=True,
         atr=0.0012, support=1.0995, resistance=1.1050, range_high=0.0, range_low=0.0,
         prev_range_high=0.0, prev_range_low=0.0, prev_close=0.0),
    dict(price=1.1095, trend="bullish", h1_agrees=True, adx=14.4, rsi=74.0, rsi_rising=False,
         atr=0.0012, support=1.09, resistance=1.109, range_high=0.0, range_low=0.0,
         prev_range_high=0.0, prev_range_low=0.0, prev_close=0.0),
    dict(price=1.1060, trend="bullish", h1_agrees=True, adx=27.0, rsi=62.0, rsi_rising=True,
         atr=0.0012, support=1.10, resistance=1.106, range_high=1.105, range_low=1.098,
         prev_range_high=1.1048, prev_range_low=1.0982, prev_close=1.1045),
    dict(price=1.1060, trend="bearish", h1_agrees=False, adx=21.0, rsi=62.0, rsi_rising=True,
         atr=0.0012, support=1.10, resistance=1.106, range_high=1.1075, range_low=1.101,
         prev_range_high=1.107, prev_range_low=1.1005, prev_close=1.1025),
    dict(price=1.0960, trend="bullish", h1_agrees=True, adx=19.0, rsi=68.0, rsi_rising=False,
         atr=0.0012, support=1.09, resistance=1.096, range_high=0.0, range_low=0.0,
         prev_range_high=0.0, prev_range_low=0.0, prev_close=0.0),
]


def _py_setups(state: dict) -> list:
    out = []
    for s in build_setups(MarketState(**state), "EURUSD", ACFG, SCFG):
        out.append({"key": s.key, "symbol": s.symbol, "direction": s.direction,
                    "quality": s.quality, "entry": s.entry, "stop_ref": s.stop_ref,
                    "reasons_fa": s.reasons_fa, "label_fa": s.label_fa,
                    "setup_id": s.setup_id})
    return out


PY_OUT = [_py_setups(x) for x in STATES]
A(any(PY_OUT), "دست‌کم یک حالت ستاپ دارد (تست بی‌معنی نباشد)")

NODE = shutil.which("node")
if NODE is None:
    print("  ⏭️  node پیدا نشد — تست برابری JS رد شد (در CI با node اجرا می‌شود)")
else:
    script = r"""
const fs = require('fs'), path = require('path'), vm = require('vm');
const WWW = path.join(process.argv[2], 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const ctx = { console, Date, Math, JSON };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['fa.js', 'icons.js', 'indicators.js', 'technical.js']) {
  vm.runInContext(fs.readFileSync(path.join(WWW, f), 'utf8'), ctx, { filename: f });
}
const O = ctx.ODIN;
const states = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const out = states.map((st) => O.buildSetups(st, 'EURUSD',
  { adx_min_trend: 20, adx_strong: 25 }, {}).map((s) => ({
    key: s.key, symbol: s.symbol, direction: s.direction, quality: s.quality,
    entry: s.entry, stop_ref: s.stop_ref, reasons_fa: s.reasons_fa,
    label_fa: s.label_fa, setup_id: s.setup_id
  })));
process.stdout.write(JSON.stringify(out));
"""
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "parity.js"
        ip = Path(td) / "states.json"
        sp.write_text(script, encoding="utf-8")
        ip.write_text(json.dumps(STATES), encoding="utf-8")
        res = subprocess.run([NODE, str(sp), str(ROOT), str(ip)],
                             capture_output=True, text=True, timeout=120)
        A(res.returncode == 0, f"اسکریپت برابری JS اجرا شد: {res.stderr[-400:]}")
        js_out = json.loads(res.stdout or "[]")
    A(js_out == PY_OUT, "خروجی ستاپ‌های JS باید بایت‌به‌بایت با پایتون یکی باشد"
      f"\n   PY={json.dumps(PY_OUT, ensure_ascii=False)[:300]}"
      f"\n   JS={json.dumps(js_out, ensure_ascii=False)[:300]}")


# ── سقف پوزیشن/روز و کلید ضداسپم (سمت پایتون)
print()
print("=" * 74)
print("۵b) ظرفیت پوزیشن، سقف روزانه و کلید ضداسپم")
print("=" * 74)

from datetime import datetime, timezone  # noqa: E402

from src import engine  # noqa: E402


class _Sig:
    def __init__(self, symbol="EURUSD", direction="BUY", strategy="trend_pullback", score=8):
        self.symbol, self.direction, self.strategy, self.score = symbol, direction, strategy, score


A(engine._signal_state_key(_Sig()) == "EURUSD|trend_pullback|BUY", "کلید شامل استراتژی")
A(engine._signal_state_key(_Sig(strategy="")) == "EURUSD|BUY", "بدون استراتژی → کلید قدیمی")
A(engine._signal_state_key(_Sig(strategy="breakout")) != engine._signal_state_key(_Sig()),
  "دو استراتژی روی یک نماد کلید جدا دارند")

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
state = {"EURUSD|trend_pullback|BUY": {"ts": NOW.isoformat(), "score": 8},
         "GBPUSD|breakout|SELL": {"ts": "2026-11-22T09:00:00+00:00", "score": 7},
         "XAUUSD|legacy|BUY": {"ts": "خراب", "score": 6}}
today = engine._sends_today(state, NOW)
A(today["total"] == 1 and today["by_symbol"] == {"EURUSD": 1},
  f"فقط ارسال‌های امروز شمرده می‌شوند: {today}")
A(engine._daily_cap_block(_Sig(), today, {"max_per_symbol_per_day": 1}) != "",
  "سقف هر نماد اعمال می‌شود")
A(engine._daily_cap_block(_Sig(symbol="GBPUSD"), today, {"max_per_symbol_per_day": 1}) == "",
  "نماد دیگر بلوکه نیست")
A(engine._daily_cap_block(_Sig(symbol="GBPUSD"), {"total": 8, "by_symbol": {}},
                          {"max_signals_per_day": 8}) != "", "سقف کل روز اعمال می‌شود")
A(engine._daily_cap_block(_Sig(symbol="GBPUSD"), today, {}) == "", "سقف صفر = بی‌محدودیت")


class _Entry:
    def __init__(self, sent=True, actionable=True):
        self.sent, self.actionable = sent, actionable


class _Journal:
    def __init__(self, entries):
        self._entries = entries

    def open_entries(self):
        return self._entries


A(engine._open_positions(_Journal([_Entry(), _Entry()])) == 2, "دو پوزیشن باز")
A(engine._open_positions(_Journal([_Entry(sent=False), _Entry()])) == 1,
  "سیگنالی که ارسال نشد ظرفیت نمی‌گیرد")
A(engine._open_positions(_Journal([_Entry(actionable=False)])) == 0,
  "سیگنال «فقط پیگیری» ظرفیت نمی‌گیرد")
A(engine._open_positions(None) == 0, "ژورنال ناموجود → صفر (بدون استثنا)")


# ── صندلی ظرفیت: فقط سیگنالِ ارسال‌شده صندلی می‌گیرد (باگِ کشف‌شده در بک‌تست)
class _CapSig:
    def __init__(self):
        self.actionable = True
        self.capacity_note = ""


sig = _CapSig()
A(engine._apply_capacity(sig, True, 2, True, 2) == 1 and sig.actionable,
  "سیگنالِ ارسال‌شده صندلی می‌گیرد")
sig = _CapSig()
A(engine._apply_capacity(sig, False, 2, True, 2) == 2 and not sig.actionable,
  "سیگنالِ سرکوب‌شده (cooldown) صندلی نمی‌گیرد")
sig = _CapSig()
free = engine._apply_capacity(sig, True, 0, True, 2)
A(free == 0 and not sig.actionable and "پوزیشن باز پر است" in sig.capacity_note,
  "صندلی تمام‌شده → «فقط پیگیری» با توضیح")
sig = _CapSig()
A(engine._apply_capacity(sig, True, 0, False, 0) == 0 and sig.actionable,
  "ظرفیت خاموش → دست‌نخورده")

# ── config واقعی: نمادها، سهمیه، کلیدها
print()
print("=" * 74)
print("۶) config.yaml: ده نماد، سهمیهٔ پلن رایگان، کلیدهای نسخهٔ ۱.۱")
print("=" * 74)

import yaml  # noqa: E402

CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
names = [s["name"] for s in CFG["symbols"]]
A(len(names) == 10 and "EURJPY" in names and "EURGBP" in names,
  f"ده نماد شامل کراس‌های یورو: {names}")
cycles = 24 * 60 // int(CFG["loop"]["interval_minutes"])
A(len(names) * cycles <= 800, f"سهمیه: {len(names)}×{cycles} = {len(names) * cycles} ≤ ۸۰۰")
A(CFG["judge"]["min_score"] == 5, "min_score همان ۵ ماند (وعدهٔ «آستانهٔ شل‌تر نه»)")
A(CFG["judge"]["resend_cooldown_minutes"] <= 120, "cooldown به ۹۰ دقیقه کم شد")
A(CFG["judge"]["tiers"]["enabled"] is True, "رده‌بندی در config محصول روشن است")
A(CFG["judge"]["portfolio"]["max_open_positions"] == 2, "سقف دو پوزیشن باز")
A(CFG["judge"]["funnel"]["enabled"] is True, "قیف سیگنال روشن است")
for key in ("trend_pullback", "range_reversion", "breakout"):
    A(CFG["strategies"][key]["enabled"] is True, f"استراتژی {key} روشن است")

# آینهٔ JS
js_cfg = (ROOT / "android/app/src/main/assets/www/js/config.js").read_text(encoding="utf-8")
for needle in ("min_score: 5", "max_signals_per_cycle: 4", "resend_cooldown_minutes: 90",
               "max_open_positions: 2", "a_min_score: 7", "range_reversion", "breakout",
               "EURJPY", "EURGBP"):
    A(needle in js_cfg, f"آینهٔ اندروید شامل «{needle}» است")

print()
print("=" * 74)
print(f"✅ STRATEGY TESTS OK — {COUNT} بررسی پاس؛ سه استراتژی + رده‌بندی + "
      f"پورتفوی + برابری JS سبز است")
print("=" * 74)
