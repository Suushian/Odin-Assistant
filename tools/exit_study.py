#!/usr/bin/env python3
"""
🧪 مطالعهٔ «خروج» و «فیلتر» روی سیگنال‌های ثبت‌شده — بدون اجرای دوبارهٔ موتور.

ایده: یک‌بار موتور را با `--debug-signals` اجرا می‌کنیم (گران است: ~۳۵ دقیقه برای
۲۴ ماه). بعد همان مجموعهٔ سیگنال‌ها را با چند **سیاست خروج** و چند **فیلتر ورود**
دوباره بازی می‌کنیم (چند ثانیه). چون ورودی‌ها ثابت‌اند، تفاوت نتایج فقط از خودِ
سیاست می‌آید — همان چیزی که برای تصمیم‌گیری لازم است.

سیاست‌های پیش‌ثبت‌شده (`--policies all`):
    base       همان رفتار تولید: TP=2R، انقضای ۲۴ ساعت (شاهد)
    tp15       هدف ۱٫۵R
    tp10       هدف ۱R
    be1        حد ضرر سربه‌سر بعد از +۱R (هدف ۲R)
    exp48      هدف ۲R، انقضای ۴۸ ساعت
    exp72      هدف ۲R، انقضای ۷۲ ساعت
    be1_exp48  سربه‌سر + ۴۸ ساعت
    partial1   نصف در ۱R + سربه‌سر + بقیه تا ۲R (۴۸ ساعت)
    trail      سربه‌سر در ۱R، بعد ترییلینگ ۰٫۵R از سقف (۴۸ ساعت)
    tp15_be1   هدف ۱٫۵R + سربه‌سر (۴۸ ساعت)

ورود جایگزین: `--limit-breakout-bars 8` → ستاپ‌های شکست با اردر لیمیت روی قیمت
اعلام‌شده پر می‌شوند (نه ورود بازار)؛ اگر تا ۸ کندل پر نشد، معامله انجام نمی‌شود.

فیلترها (روی همان سیگنال‌ها): `--min-adx`, `--min-score`, `--only-strategies`,
`--exclude-symbols`, `--hours 7-20`, `--tiers A,B`.

مثال:
    python tools/exit_study.py --data-dir ~/odin-m15 \
        --signals reports/backtest/v1.1.1-study-signals.csv \
        --out reports/backtest --label ex1 --policies all
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.backtest import DEFAULT_SLIPPAGE, DEFAULT_SPREAD, read_data  # noqa: E402


# ══════════════════════════════════════════════════════════════
#  سیاست‌های خروج
# ══════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Policy:
    key: str
    fa: str
    tp_r: float | None = 2.0
    be_at: float | None = None            # از +nR، حد ضرر به نقطهٔ ورود
    trail_after: float | None = None      # از +nR، ترییلینگ فعال می‌شود
    trail_dist: float = 0.5               # فاصلهٔ ترییلینگ از سقف (R)
    partials: tuple = ()                  # ((level_r, fraction), ...)
    expiry_h: float = 24.0


POLICIES: dict[str, Policy] = {p.key: p for p in (
    Policy("base", "شاهد: ۲R / ۲۴ ساعت"),
    Policy("tp15", "هدف ۱٫۵R", tp_r=1.5),
    Policy("tp10", "هدف ۱R", tp_r=1.0),
    Policy("be1", "سربه‌سر بعد از ۱R", be_at=1.0),
    Policy("exp48", "هدف ۲R / ۴۸ ساعت", expiry_h=48.0),
    Policy("exp72", "هدف ۲R / ۷۲ ساعت", expiry_h=72.0),
    Policy("be1_exp48", "سربه‌سر ۱R + ۴۸ ساعت", be_at=1.0, expiry_h=48.0),
    Policy("partial1", "نصف در ۱R + بقیه ۲R", be_at=1.0, partials=((1.0, 0.5),),
           expiry_h=48.0),
    Policy("trail", "سربه‌سر ۱R + ترییلینگ ۰٫۵R", be_at=1.0, trail_after=1.5,
           trail_dist=0.5, expiry_h=48.0),
    Policy("tp15_be1", "هدف ۱٫۵R + سربه‌سر", tp_r=1.5, be_at=1.0, expiry_h=48.0),
    # دور دوم: آیا «بیشتر نگه‌داشتن» بهتر می‌شود؟ و آیا هدف ۲R خودش زیان‌بار است؟
    Policy("exp96", "هدف ۲R / ۹۶ ساعت", expiry_h=96.0),
    Policy("exp120", "هدف ۲R / ۱۲۰ ساعت", expiry_h=120.0),
    Policy("tp15_exp72", "هدف ۱٫۵R / ۷۲ ساعت", tp_r=1.5, expiry_h=72.0),
    Policy("noTP72", "بدون هدف / ۷۲ ساعت", tp_r=None, expiry_h=72.0),
    Policy("noTP120", "بدون هدف / ۱۲۰ ساعت", tp_r=None, expiry_h=120.0),
    # دور سوم: مرز «نگه‌داشتن» کجاست؟
    Policy("exp144", "هدف ۲R / ۱۴۴ ساعت", expiry_h=144.0),
    Policy("exp168", "هدف ۲R / ۱۶۸ ساعت", expiry_h=168.0),
    Policy("exp240", "هدف ۲R / ۲۴۰ ساعت", expiry_h=240.0),
    Policy("tp15_exp120", "هدف ۱٫۵R / ۱۲۰ ساعت", tp_r=1.5, expiry_h=120.0),
    Policy("tp10_exp120", "هدف ۱R / ۱۲۰ ساعت", tp_r=1.0, expiry_h=120.0),
    Policy("tp25_exp144", "هدف ۲٫۵R / ۱۴۴ ساعت", tp_r=2.5, expiry_h=144.0),
    Policy("tp30_exp144", "هدف ۳R / ۱۴۴ ساعت", tp_r=3.0, expiry_h=144.0),
)}


# ══════════════════════════════════════════════════════════════
#  شبیه‌سازی یک معامله
# ══════════════════════════════════════════════════════════════
EPS = 1e-9          # مقایسهٔ سطوح با تلورانس: قیمت دقیقاً روی سطح هم «لمس» است


def simulate(o, h, l, t, i0: int, direction: str, entry: float, sl0: float,
             risk: float, expiry_ts, pol: Policy) -> dict | None:
    """از کندل i0 به بعد؛ خروج با قانون `pol` و همان فرض‌های ابزار بک‌تست.

    اولویت درون‌کندلی: حد ضرر > هدف (بدبینانه) — مثل `tools/backtest.py`.
    """
    buy = direction == "BUY"
    sl = sl0
    remaining = 1.0
    realized = 0.0
    done = [False] * len(pol.partials)
    bars = 0
    for k in range(i0, len(o)):
        op, hi, lo = float(o[k]), float(h[k]), float(l[k])
        bars += 1
        # ۱) حد ضرر (گپ بدتر از حد ضرر → همان قیمت گپ)
        if buy:
            if op <= sl:
                realized += remaining * ((op - entry) / risk)
                return _done(realized, t[k], "GAP_SL", bars)
            if lo <= sl:
                realized += remaining * ((sl - entry) / risk)
                return _done(realized, t[k], "SL" if remaining > 0.999 else "SL_PART", bars)
        else:
            if op >= sl:
                realized += remaining * ((entry - op) / risk)
                return _done(realized, t[k], "GAP_SL", bars)
            if hi >= sl:
                realized += remaining * ((entry - sl) / risk)
                return _done(realized, t[k], "SL" if remaining > 0.999 else "SL_PART", bars)

        fav = (hi - entry) if buy else (entry - lo)      # بهترین حالت کندل
        fav_r = fav / risk

        # ۲) خروج‌های جزئی
        for idx, (level, frac) in enumerate(pol.partials):
            if not done[idx] and fav_r >= level - EPS:
                done[idx] = True
                remaining -= frac
                realized += frac * level
                if pol.be_at is not None:
                    sl = entry if buy else entry

        # ۳) هدف نهایی
        if pol.tp_r is not None and fav_r >= pol.tp_r - EPS:
            realized += remaining * pol.tp_r
            return _done(realized, t[k], "TP", bars)

        # ۴) انتقال حد ضرر (از کندل بعد اعمال می‌شود؛ محافظه‌کارانه)
        if pol.be_at is not None and fav_r >= pol.be_at - EPS:
            sl = max(sl, entry) if buy else min(sl, entry)
        if pol.trail_after is not None and fav_r >= pol.trail_after - EPS:
            move = max(0.0, fav_r - pol.trail_dist) * risk
            new = entry + move if buy else entry - move
            sl = max(sl, new) if buy else min(sl, new)

        # ۵) انقضا — خروج روی بازِ همان کندل (مثل ابزار اصلی)
        if t[k] >= expiry_ts:
            realized += remaining * (((op - entry) if buy else (entry - op)) / risk)
            return _done(realized, t[k], "EXPIRED", bars)
    return None


def _done(r: float, ts, result: str, bars: int) -> dict:
    return {"r": r, "exit_ts": pd.Timestamp(ts), "result": result, "bars": bars}


# ══════════════════════════════════════════════════════════════
#  آمار
# ══════════════════════════════════════════════════════════════
def stats(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0}
    r = np.array([x["r"] for x in trades], dtype=float)
    wins, losses = r[r > 0], r[r <= 0]
    equity = np.cumsum(r)
    peak = np.maximum.accumulate(equity)
    dd = float((equity - peak).min())
    return {
        "trades": len(r),
        "win_rate": float(len(wins) / len(r)),
        "avg_r": float(r.mean()),
        "total_r": float(r.sum()),
        "profit_factor": float(wins.sum() / -losses.sum()) if losses.sum() else float("inf"),
        "max_dd_r": dd,
        "avg_win_r": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss_r": float(losses.mean()) if len(losses) else 0.0,
        "exits": {k: int(v) for k, v in pd.Series(
            [x["result"] for x in trades]).value_counts().items()},
    }


def by(trades: list[dict], key) -> dict:
    out: dict[str, list] = {}
    for x in trades:
        out.setdefault(str(key(x)), []).append(x)
    return {k: stats(v) for k, v in sorted(out.items())}


# ══════════════════════════════════════════════════════════════
#  بارگذاری سیگنال‌ها + فیلترها
# ══════════════════════════════════════════════════════════════
def _bool(s) -> bool:
    return str(s).strip().lower() in ("true", "1", "yes", "بله")


def load_signals(paths: list[Path], a) -> pd.DataFrame:
    frames = [pd.read_csv(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df["now"] = pd.to_datetime(df["now"])
    if "sent" in df.columns:
        df = df[df["sent"].map(_bool)]
    if a.only_strategies:
        keep = {s.strip() for s in a.only_strategies.split(",") if s.strip()}
        df = df[df["strategy"].isin(keep)]
    if a.exclude_strategies:
        drop = {s.strip() for s in a.exclude_strategies.split(",") if s.strip()}
        df = df[~df["strategy"].isin(drop)]
    if a.exclude_symbols:
        drop = {s.strip().upper() for s in a.exclude_symbols.split(",") if s.strip()}
        df = df[~df["symbol"].isin(drop)]
    if a.tiers:
        keep = {t.strip() for t in a.tiers.split(",") if t.strip()}
        df = df[df["tier"].fillna("").isin(keep)]
    if a.min_score is not None:
        df = df[df["score"] >= a.min_score]
    if a.min_adx is not None and "adx" in df.columns:
        df = df[df["adx"] >= a.min_adx]
    if a.hours:
        lo, hi = (int(x) for x in a.hours.split("-"))
        hh = df["now"].dt.hour
        df = df[(hh >= lo) & (hh <= hi)]
    return df.sort_values("now").reset_index(drop=True)


# ══════════════════════════════════════════════════════════════
#  اجرای یک سیاست
# ══════════════════════════════════════════════════════════════
def run_policy(sig: pd.DataFrame, bars: dict, spread: dict, slippage: float,
               pol: Policy, max_open: int, limit_bars: int,
               limit_strategies: set[str]) -> dict:
    trades, open_until = [], []
    blocked = unfilled = missing = 0
    dumped = []
    for row in sig.itertuples(index=False):
        now = row.now
        open_until = [t for t in open_until if t > now]
        sym = row.symbol
        if sym not in bars:
            missing += 1
            continue
        b = bars[sym]
        i0 = int(np.searchsorted(b["ts"], np.datetime64(now), side="left"))
        if i0 >= len(b["ts"]) or b["ts"][i0] != np.datetime64(now):
            missing += 1
            continue
        if len(open_until) >= max_open:
            blocked += 1
            continue

        pip = float(b["pip"])
        cost = (spread.get(sym, 1.0) / 2 + slippage) * pip
        plan = float(row.entry)
        sl = float(row.sl)
        risk = abs(plan - sl)
        if risk <= 0:
            continue
        buy = row.dir == "BUY"

        # ── ورود: بازار روی بازِ همین کندل، یا لیمیت روی قیمت اعلام‌شده
        if limit_bars and row.strategy in limit_strategies:
            fill = -1
            for k in range(i0, min(i0 + limit_bars, len(b["ts"]))):
                if (buy and b["l"][k] <= plan) or ((not buy) and b["h"][k] >= plan):
                    fill = k
                    break
            if fill < 0:
                unfilled += 1
                continue
            entry = plan                       # لیمیت بدون هزینهٔ تعقیب
            i0 = fill
        else:
            entry = float(b["o"][i0]) + (cost if buy else -cost)

        expiry = pd.Timestamp(now) + timedelta(hours=pol.expiry_h)
        r = simulate(b["o"], b["h"], b["l"], b["ts"], i0, row.dir, entry, sl, risk,
                     expiry, pol)
        if r is None:                          # داده تمام شد
            continue
        exit_ts = r["exit_ts"]
        trades.append({
            "symbol": sym, "strategy": row.strategy, "dir": row.dir,
            "tier": row.tier, "score": int(row.score), "now": now,
            "r": r["r"], "result": r["result"], "bars": r["bars"],
            "exit_ts": exit_ts,
        })
        open_until.append(exit_ts)
        dumped.append({"now": now, "symbol": sym, "strategy": row.strategy,
                       "dir": row.dir, "entry": entry, "plan": plan, "sl": sl,
                       "r": r["r"], "result": r["result"], "exit_ts": exit_ts})

    trades.sort(key=lambda x: x["exit_ts"])
    for x in trades:
        x["year"] = str(x["now"].year)
    out = stats(trades)
    out.update({
        "blocked_capacity": blocked, "unfilled_limit": unfilled,
        "missing_bar": missing,
        "per_year": by(trades, lambda x: x["year"]),
        "per_strategy": by(trades, lambda x: x["strategy"]),
        "per_symbol": by(trades, lambda x: x["symbol"]),
    })
    out["_dumped"] = dumped
    return out


# ══════════════════════════════════════════════════════════════
#  گزارش
# ══════════════════════════════════════════════════════════════
def render(results: list[tuple[Policy, dict]], meta: dict) -> str:
    L = ["# مطالعهٔ خروج/فیلتر — " + meta["label"], ""]
    L.append(f"- سیگنال‌ها: {meta['signals']} (پس از فیلتر) · سقف پوزیشن: "
             f"{meta['max_open']} · اسلیپیج: {meta['slippage']} پیپ")
    if meta.get("limit_bars"):
        L.append(f"- ورود لیمیت برای {', '.join(sorted(meta['limit_strategies']))}"
                 f" — اعتبار {meta['limit_bars']} کندل")
    for k, v in (meta.get("filters") or {}).items():
        L.append(f"- فیلتر {k}: {v}")
    L += ["", "| سیاست | معامله | نرخ برد | میانگین R | مجموع R | PF | حداکثر افت | "
              "۲۰۲۳ | ۲۰۲۴ | TP% | SL% | منقضی% |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for pol, s in results:
        if not s.get("trades"):
            L.append(f"| {pol.key} | ۰ | — | — | — | — | — | — | — | — | — | — |")
            continue
        ex = s["exits"]
        n = s["trades"]
        y = s["per_year"]
        L.append(
            f"| `{pol.key}` {pol.fa} | {n} | {s['win_rate']*100:.1f}% | "
            f"{s['avg_r']:+.3f} | {s['total_r']:+.1f} | {s['profit_factor']:.2f} | "
            f"{s['max_dd_r']:+.1f} | "
            f"{(y.get('2023', {}).get('avg_r', 0)):+.3f} | "
            f"{(y.get('2024', {}).get('avg_r', 0)):+.3f} | "
            f"{ex.get('TP', 0)/n*100:.0f}% | "
            f"{(ex.get('SL', 0)+ex.get('SL_PART', 0))/n*100:.0f}% | "
            f"{ex.get('EXPIRED', 0)/n*100:.0f}% |")
    L.append("")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="مطالعهٔ خروج/فیلتر روی سیگنال‌های ثبت‌شده")
    ap.add_argument("--data-dir", required=True, type=Path)
    ap.add_argument("--signals", required=True, nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "backtest")
    ap.add_argument("--label", default="exit-study")
    ap.add_argument("--tz", default="auto")
    ap.add_argument("--policies", default="all")
    ap.add_argument("--max-open", type=int, default=2)
    ap.add_argument("--slippage", type=float, default=DEFAULT_SLIPPAGE)
    ap.add_argument("--limit-breakout-bars", type=int, default=0)
    ap.add_argument("--limit-strategies", default="breakout")
    ap.add_argument("--only-strategies", default="")
    ap.add_argument("--exclude-strategies", default="")
    ap.add_argument("--exclude-symbols", default="")
    ap.add_argument("--tiers", default="")
    ap.add_argument("--min-score", type=int, default=None)
    ap.add_argument("--min-adx", type=float, default=None)
    ap.add_argument("--hours", default="", help="۷-۲۰ = فقط ساعت‌های UTC در این بازه")
    ap.add_argument("--dump-trades", action="store_true",
                    help="CSV معامله‌ها را هم بنویس (برای مقایسه با ابزار اصلی)")
    a = ap.parse_args(argv)

    print("📥 خواندن داده…")
    data = read_data(a.data_dir, a.tz)
    bars = {}
    for sym, df in data.items():
        bars[sym] = {
            "ts": df.index.values.astype("datetime64[ns]"),
            "o": df["Open"].to_numpy(dtype=float),
            "h": df["High"].to_numpy(dtype=float),
            "l": df["Low"].to_numpy(dtype=float),
            "pip": 0.01 if sym.endswith("JPY") else 0.0001,
        }

    sig = load_signals(a.signals, a)
    print(f"📊 سیگنال‌های قابل بازی: {len(sig)}")

    keys = list(POLICIES) if a.policies == "all" else [k.strip() for k in a.policies.split(",")]
    limit_strategies = {s.strip() for s in a.limit_strategies.split(",") if s.strip()}

    results = []
    for key in keys:
        pol = POLICIES[key]
        s = run_policy(sig, bars, DEFAULT_SPREAD, a.slippage, pol, a.max_open,
                       a.limit_breakout_bars, limit_strategies)
        if a.dump_trades:
            pd.DataFrame(s.pop("_dumped")).to_csv(
                a.out / f"{a.label}-{key}-trades.csv", index=False)
        else:
            s.pop("_dumped", None)
        results.append((pol, s))
        print(f"   • {key:<11} معامله {s.get('trades', 0):>4} | برد "
              f"{s.get('win_rate', 0)*100:>5.1f}% | میانگین {s.get('avg_r', 0):+.3f} | "
              f"مجموع {s.get('total_r', 0):+7.1f} | PF {s.get('profit_factor', 0):.2f}"
              + (f" | لیمیت‌نشده {s['unfilled_limit']}" if s.get("unfilled_limit") else ""))

    meta = {
        "label": a.label, "signals": len(sig), "max_open": a.max_open,
        "slippage": a.slippage, "limit_bars": a.limit_breakout_bars,
        "limit_strategies": limit_strategies,
        "filters": {k: v for k, v in {
            "only_strategies": a.only_strategies, "exclude_strategies": a.exclude_strategies,
            "exclude_symbols": a.exclude_symbols, "tiers": a.tiers,
            "min_score": a.min_score, "min_adx": a.min_adx, "hours": a.hours,
        }.items() if v not in ("", None)},
    }
    a.out.mkdir(parents=True, exist_ok=True)
    md = render(results, meta)
    (a.out / f"{a.label}.md").write_text(md, encoding="utf-8")
    (a.out / f"{a.label}.json").write_text(json.dumps(
        {"meta": meta, "results": {pol.key: s for pol, s in results}},
        ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print()
    print(md)
    print(f"💾 {a.out / (a.label + '.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
