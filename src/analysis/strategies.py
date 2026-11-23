# -*- coding: utf-8 -*-
"""تولیدکننده‌های ستاپ — چند استراتژی روی یک موتور تحلیل.

فلسفه (نسخهٔ ۱.۱): موتور تحلیل (`technical.py`) فقط «وضعیت بازار» را می‌سنجد؛
این ماژول از همان وضعیت «ستاپ‌های نامزد» می‌سازد. پیش از این، تنها یک قاعده
(پولبک در روند) اجازهٔ ستاپ داشت و هر بازار رنج یا شکست‌دار کاملاً از دست
می‌رفت — نتیجه: در بسیاری از روزها صفر سیگنال.

سه استراتژی (هر کدام قابل خاموش‌کردن در `config.yaml` → `strategies.<key>`):

  ۱) **trend_pullback** — پولبک در روند (همان قاعدهٔ نسخهٔ ۱.۰، بدون تغییر)
  ۲) **range_reversion** — بازگشت از کف/سقف رنج (ADX پایین، RSI اشباع + برگشت)
  ۳) **breakout** — شکست *تازهٔ* دامنهٔ N کندلی H1 (نه هر کندلی که بالای دامنه است)

⚠️ دو قاعدهٔ صداقت:

  • هیچ ستاپی «امتیاز» نمی‌سازد. امتیاز فقط از جدول مدارک داور می‌آید
    (`src/judge/scoring.py`). این لایه فقط می‌گوید «کجا و در چه جهتی» می‌شود
    معامله کرد؛ اینکه چقدر پشتوانه دارد کار داور است. پس `min_score: 5`
    دست‌نخورده می‌ماند و کیفیت ستاپ جای مدارک را نمی‌گیرد.

  • هر ستاپ `setup_id` پایدار دارد (`symbol|strategy|direction`). لایهٔ ضداسپم
    موتور (نه این ماژول) با همین شناسه فاصلهٔ ارسال را می‌سنجد، پس یک ستاپ
    رنجِ چندساعته با یک ستاپ شکستِ تازه قاطی نمی‌شود.

آینهٔ جاوااسکریپت: `android/app/src/main/assets/www/js/technical.js`
(`O.buildSetups`) — هر تغییر اینجا باید آنجا هم اعمال شود؛
`tests/test_strategies.py` و `tests/js/test_strategies.js` دو باتری آینه‌اند.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..fa import fa_num

# برچسب فارسی استراتژی‌ها — در پیام سیگنال و گزارش داور نمایش داده می‌شود
STRATEGY_FA = {
    "trend_pullback": "پولبک در روند",
    "range_reversion": "بازگشت از کف/سقف رنج",
    "breakout": "شکست تازهٔ دامنه",
}

# اولویت وقتی دو ستاپ کیفیت برابر دارند (بزرگ‌تر = مهم‌تر).
# پولبک در روند محافظه‌کارانه‌ترین است، پس اول؛ رنج آخر (بیشترین نیاز به تایید).
STRATEGY_PRIORITY = {"trend_pullback": 3, "breakout": 2, "range_reversion": 1}

# فقط این کلیدها به لایهٔ داور می‌رسند (جلوگیری از تایپو در config)
STRATEGY_KEYS = tuple(STRATEGY_FA)


@dataclass
class Setup:
    """یک ستاپ نامزد — مستقل از امتیاز و از داوری.

    quality: ۰ تا ۳ (۳ = تمیزترین حالت ممکن برای آن استراتژی).
             کیفیت فقط برای *اولویت‌بندی* و انتخاب «ستاپ برتر» است، نه امتیاز.
    stop_ref: سطح مرجعی که حد ضرر باید آن‌سویش بنشیند (حمایت، مقاومت، یا
              لبهٔ شکسته‌شدهٔ دامنه). None = داور از ATR استفاده می‌کند.
    """

    key: str
    symbol: str
    direction: str                     # BUY | SELL
    quality: int
    entry: float
    stop_ref: Optional[float] = None
    reasons_fa: list[str] = field(default_factory=list)

    @property
    def label_fa(self) -> str:
        return STRATEGY_FA.get(self.key, self.key)

    @property
    def setup_id(self) -> str:
        """شناسهٔ پایدار ستاپ برای لایهٔ ضداسپم (نه برای ژورنال)."""
        return f"{self.symbol}|{self.key}|{self.direction}"

    def to_dict(self) -> dict:
        return {
            "key": self.key, "symbol": self.symbol, "direction": self.direction,
            "quality": self.quality, "entry": round(self.entry, 6),
            "stop_ref": (round(self.stop_ref, 6) if self.stop_ref is not None else None),
            "reasons_fa": list(self.reasons_fa),
        }


@dataclass(frozen=True)
class MarketState:
    """وضعیت خام بازار که استراتژی‌ها روی آن تصمیم می‌گیرند.

    همهٔ میدان‌ها از `SymbolAnalysis`/دادهٔ کندل پر می‌شوند تا استراتژی‌ها
    خالص و قابل‌تست باشند (بدون pandas، بدون شبکه).
    """

    price: float
    trend: str                 # bullish | bearish
    h1_agrees: bool
    adx: float
    rsi: float
    rsi_rising: bool
    atr: float
    support: Optional[float]
    resistance: Optional[float]
    # دامنهٔ N کندلی H1 (شکست) — از کندل‌های *بستهٔ* قبلی
    range_high: float = 0.0
    range_low: float = 0.0
    prev_range_high: float = 0.0
    prev_range_low: float = 0.0
    prev_close: float = 0.0


def _num(cfg: dict, key: str, default: float) -> float:
    try:
        v = (cfg or {}).get(key, default)
        return float(default if v is None else v)
    except (TypeError, ValueError):
        return float(default)


def strategy_enabled(scfg: dict, key: str) -> bool:
    """آیا این استراتژی روشن است؟ (پیش‌فرض: روشن)

    سه شکل پذیرفته می‌شود، به همان ترتیب اولویت:
      • `strategies: {breakout: false}`         → خاموش (شکل کوتاه)
      • `strategies: {breakout: {enabled: false}}`
      • نبودِ کلید                              → روشن
    """
    block = (scfg or {}).get(key)
    if isinstance(block, dict):
        return bool(block.get("enabled", True))
    if isinstance(block, bool):
        return block
    return True


# ══════════════════════════════════════════════════════════════
#  ۱) پولبک در روند — قاعدهٔ نسخهٔ ۱.۰ (بایت‌به‌بایت، فقط بسته‌بندی‌شده)
# ══════════════════════════════════════════════════════════════
def detect_trend_pullback(st: MarketState, sym: str, acfg: dict,
                          scfg: dict) -> Optional[Setup]:
    """پولبک در روند: H4+H1 هم‌جهت، ADX بالای آستانه، RSI در ناحیهٔ پولبک."""
    if not strategy_enabled(scfg, "trend_pullback"):
        return None
    adx_min = _num(acfg, "adx_min_trend", 20)
    adx_strong = _num(acfg, "adx_strong", 25)
    if st.adx < adx_min or not st.h1_agrees:
        return None
    if st.trend == "bullish" and st.rsi < 45:
        direction, level = "BUY", st.support
        turn = st.rsi_rising and 30 <= st.rsi
        why_rsi = f"RSI={fa_num(f'{st.rsi:.0f}')} زیر ۴۵ است (ناحیهٔ پولبک)"
    elif st.trend == "bearish" and st.rsi > 55:
        direction, level = "SELL", st.resistance
        turn = (not st.rsi_rising) and st.rsi <= 70
        why_rsi = f"RSI={fa_num(f'{st.rsi:.0f}')} بالای ۵۵ است (ناحیهٔ اصلاح)"
    else:
        return None

    strong = st.adx >= adx_strong
    quality = 3 if (strong and turn) else (2 if (strong or turn) else 1)
    reasons = [
        f"روند ۴ ساعته {'صعودی' if st.trend == 'bullish' else 'نزولی'} و تایم‌فریم "
        f"۱ ساعته هم‌جهت است",
        f"ADX={fa_num(f'{st.adx:.0f}')} → {'روند قوی' if strong else 'روند متوسط'}",
        why_rsi + (" و رو به برگشت است" if turn else " ولی هنوز تایید برگشت نیامده"),
    ]
    return Setup("trend_pullback", sym, direction, quality, st.price, level, reasons)


# ══════════════════════════════════════════════════════════════
#  ۲) بازگشت از کف/سقف رنج
# ══════════════════════════════════════════════════════════════
def detect_range_reversion(st: MarketState, sym: str, acfg: dict,
                           scfg: dict) -> Optional[Setup]:
    """بازگشت از کف/سقف رنج: ADX پایین + قیمت نزدیک سطح + RSI اشباع و برگشت.

    این همان بازاری است که وتوی «بازار رنج» قبلاً کل نماد را حذف می‌کرد؛
    حالا به‌جای حذف، یک ستاپ *مضاد‌روند* با امتیاز کمتر و ردهٔ B پیشنهاد
    می‌شود. حد ضرر آن‌سوی همان سطح رنج می‌نشیند، نه بر پایهٔ ATR خالی.
    """
    if not strategy_enabled(scfg, "range_reversion"):
        return None
    block = (scfg or {}).get("range_reversion") or {}
    if not isinstance(block, dict):
        block = {}
    adx_min = _num(acfg, "adx_min_trend", 20)
    if st.adx >= adx_min or st.atr <= 0:
        return None
    band = _num(block, "band_atr", 1.0)
    rsi_buy = _num(block, "rsi_buy", 32)
    rsi_sell = _num(block, "rsi_sell", 68)

    best: Optional[tuple[float, str, float, str]] = None
    if st.support and st.rsi <= rsi_buy and st.rsi_rising:
        dist = abs(st.price - st.support) / st.atr
        if dist <= band:
            best = (dist, "BUY", st.support, "حمایت")
    if st.resistance and st.rsi >= rsi_sell and not st.rsi_rising:
        dist = abs(st.price - st.resistance) / st.atr
        if dist <= band and (best is None or dist < best[0]):
            best = (dist, "SELL", st.resistance, "مقاومت")
    if best is None:
        return None

    dist, direction, level, kind = best
    # کیفیت ۳ = قیمت به‌قدر نصفِ باند به سطح چسبیده (واکنش تازه‌تر)
    quality = 3 if dist <= band / 2.0 else 2
    side_fa = "کف" if direction == "BUY" else "سقف"
    reasons = [
        f"بازار در فاز رنج است (ADX={fa_num(f'{st.adx:.0f}')} زیر "
        f"{fa_num(f'{adx_min:.0f}')}) — معاملهٔ روند در آن معنا ندارد",
        f"قیمت {fa_num(f'{dist:.1f}')} برابر ATR از {kind} رنج "
        f"({fa_num(f'{level:.5g}')}) فاصله دارد",
        (f"RSI={fa_num(f'{st.rsi:.0f}')} در اشباع فروش و رو به بالا است — "
         f"برگشت از {side_fa} رنج تایید می‌شود"
         if direction == "BUY" else
         f"RSI={fa_num(f'{st.rsi:.0f}')} در اشباع خرید و رو به پایین است — "
         f"برگشت از {side_fa} رنج تایید می‌شود"),
    ]
    return Setup("range_reversion", sym, direction, quality, st.price, level, reasons)


# ══════════════════════════════════════════════════════════════
#  ۳) شکست تازهٔ دامنه
# ══════════════════════════════════════════════════════════════
def detect_breakout(st: MarketState, sym: str, acfg: dict,
                    scfg: dict) -> Optional[Setup]:
    """شکست *تازهٔ* دامنهٔ N کندلی H1 با بافر ATR.

    شرط «تازه» عمدی است: اگر فقط بگوییم «قیمت بالای سقف دامنه است»، روی
    هر کندل بعدی هم دوباره سیگنال می‌داد (اسپم). پس کندل *قبلی* باید هنوز
    داخل دامنه بوده باشد — یعنی همین کندل، شکست را ساخته است.
    """
    if not strategy_enabled(scfg, "breakout"):
        return None
    block = (scfg or {}).get("breakout") or {}
    if not isinstance(block, dict):
        block = {}
    if st.atr <= 0 or st.range_high <= 0 or st.range_low <= 0:
        return None
    if st.adx < _num(block, "adx_min", 20):
        return None
    buf = _num(block, "buffer_atr", 0.25) * st.atr
    adx_strong = _num(acfg, "adx_strong", 25)
    strong = st.adx >= adx_strong

    direction = ""
    if st.price > st.range_high + buf and st.prev_close <= st.prev_range_high + buf:
        direction, level = "BUY", st.range_high
    elif st.price < st.range_low - buf and st.prev_close >= st.prev_range_low - buf:
        direction, level = "SELL", st.range_low
    if not direction:
        return None

    quality = 3 if (strong and st.h1_agrees) else (2 if (strong or st.h1_agrees) else 1)
    side_fa = "سقف" if direction == "BUY" else "کف"
    edge = st.range_high if direction == "BUY" else st.range_low
    buf_mult = _num(block, "buffer_atr", 0.25)
    reasons = [
        f"قیمت همین کندل از {side_fa} دامنهٔ {fa_num(f'{edge:.5g}')} "
        f"با بافر {fa_num(f'{buf_mult:.2f}')}×ATR بیرون زد",
        f"ADX={fa_num(f'{st.adx:.0f}')} → {'روند قوی' if strong else 'روند متوسط'} "
        f"(شکست بدون روند معمولاً برمی‌گردد)",
        ("تایم‌فریم ۱ ساعته هم‌جهت است" if st.h1_agrees
         else "⚠️ تایم‌فریم ۱ ساعته هم‌جهت نیست — شکست نیاز به تایید دارد"),
    ]
    return Setup("breakout", sym, direction, quality, st.price, level, reasons)


# ══════════════════════════════════════════════════════════════
#  گردآوری
# ══════════════════════════════════════════════════════════════
def build_setups(st: MarketState, sym: str, acfg: dict,
                 scfg: Optional[dict] = None) -> list[Setup]:
    """همهٔ ستاپ‌های نامزد این نماد، مرتب‌شده از بهترین به بدترین.

    مرتب‌سازی: کیفیت نزولی، سپس اولویت استراتژی (پولبک ← شکست ← رنج).
    منطق مرتب‌سازی در داور هم تکرار می‌شود (`best_setup`) تا اگر کسی این
    تابع را مستقیم صدا زد، همان ترتیب را ببیند.
    """
    scfg = scfg or {}
    out = [
        detect_trend_pullback(st, sym, acfg, scfg),
        detect_range_reversion(st, sym, acfg, scfg),
        detect_breakout(st, sym, acfg, scfg),
    ]
    setups = [s for s in out if s is not None]
    setups.sort(key=lambda s: (-s.quality, -STRATEGY_PRIORITY.get(s.key, 0)))
    return setups


def best_setup(setups: Optional[list], scfg: Optional[dict] = None) -> Optional[Setup]:
    """ستاپ برتر از میان ستاپ‌های یک نماد (با احترام به خاموش‌بودن استراتژی)."""
    scfg = scfg or {}
    live = [s for s in (setups or []) if s.key in STRATEGY_KEYS
            and strategy_enabled(scfg, s.key)]
    if not live:
        return None
    return max(live, key=lambda s: (s.quality, STRATEGY_PRIORITY.get(s.key, 0)))
