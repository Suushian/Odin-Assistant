"""بررسی سریع کیفیت سیگنال — یک فرمان، دو گزارش آمادهٔ ارسال.

این اسکریپت کاری تکراری را جمع می‌کند:
  ۱) پوشهٔ داده را پیدا/اعتبارسنجی می‌کند و می‌گوید چند نماد دیده است
  ۲) بک‌تست پایه را می‌گیرد (پیکربندی فعلی)
  ۳) جاروی آستانهٔ امتیاز را اجرا می‌کند (۵،۶،۷،۸)
  ۴) از روی JSON تولیدشده، خلاصهٔ «به تفکیک استراتژی» و «به تفکیک امتیاز» را
     روی صفحه چاپ می‌کند و مسیر دقیق فایل‌هایی که باید فرستاده شوند را می‌نویسد

اجرا:
    python tools/quality_check.py --data-dir "%USERPROFILE%\\odin-m15"
    python tools/quality_check.py --data-dir ~/odin-m15 --jobs 2
    python tools/quality_check.py --data-dir ~/odin-m15 --from 2024-01-01 --to 2025-12-31

گزینهٔ --skip-run فقط خلاصهٔ گزارش‌های موجود را می‌خواند (بدون اجرای بک‌تست).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKTEST = ROOT / "tools" / "backtest.py"
DEFAULT_LABEL = "quality-baseline"


# ══════════════════════════════════════════════════════════════
#  پیدا کردن پوشهٔ داده
# ══════════════════════════════════════════════════════════════
def resolve_data_dir(raw: str | None) -> Path | None:
    """پوشهٔ داده را از آرگومان، متغیر محیطی یا مسیرهای مرسوم پیدا می‌کند."""
    cands: list[Path] = []
    if raw:
        cands.append(Path(os.path.expandvars(raw)).expanduser())
    if os.environ.get("ODIN_M15_DIR"):
        cands.append(Path(os.environ["ODIN_M15_DIR"]).expanduser())
    home = Path.home()
    cands += [home / "odin-m15", home / "Documents" / "odin-m15",
              ROOT / "odin-m15", ROOT / "data" / "m15"]
    for c in cands:
        if c.is_dir() and any(c.glob("*.csv")):
            return c
    return None


def data_files(data_dir: Path) -> dict[str, Path]:
    """{نماد: فایل} — همان قاعدهٔ نام‌گذاری `read_data` در بک‌تست."""
    out: dict[str, Path] = {}
    for p in sorted(data_dir.glob("*.csv")):
        stem = p.stem.upper()
        if stem.endswith(("_M5", "_H1", "_H4")):
            continue
        name = stem[:-4] if stem.endswith("_M15") else stem
        out[name] = p
    return out


# ══════════════════════════════════════════════════════════════
#  خلاصه‌سازی گزارش (تابع خالص — تست‌پذیر بدون داده)
# ══════════════════════════════════════════════════════════════
def summarize(stats: dict, *, min_trades: int = 30) -> list[str]:
    """خطوط خلاصهٔ فارسی از یک دیکشنری stats بک‌تست."""
    L: list[str] = []
    L.append(f"معاملهٔ بسته: {stats.get('trades', 0)} · "
             f"نرخ برد: {100 * float(stats.get('hit_rate', 0)):.1f}% · "
             f"میانگین R: {float(stats.get('avg_r', 0)):+.3f} · "
             f"PF: {float(stats.get('profit_factor', 0)):.2f} · "
             f"افت: {float(stats.get('max_dd_r', 0)):+.1f}R")

    bad, good = [], []
    for name, row in (stats.get("per_strategy") or {}).items():
        if row["trades"] < min_trades:
            continue
        (good if row["avg_r"] > 0 else bad).append((name, row))
    if good or bad:
        L.append("به تفکیک استراتژی (فقط گروه‌های با ≥"
                 f"{min_trades} معامله):")
        for name, row in sorted((bad + good), key=lambda x: -x[1]["avg_r"]):
            mark = "✅" if row["avg_r"] > 0 else "❌"
            L.append(f"  {mark} {name:<16} {row['trades']:>4} معامله · "
                     f"برد {100 * row['win_rate']:.1f}% · "
                     f"میانگین R {row['avg_r']:+.3f} · مجموع {row['total_r']:+.1f}")

    bands = [(k, v) for k, v in (stats.get("per_score") or {}).items()
             if v["trades"] >= min_trades]
    if bands:
        L.append("به تفکیک امتیاز:")
        for k, v in sorted(bands, key=lambda x: int(x[0])):
            L.append(f"  • امتیاز {k:<2} {v['trades']:>4} معامله · "
                     f"برد {100 * v['win_rate']:.1f}% · میانگین R {v['avg_r']:+.3f}")
    return L


def advice(stats: dict, *, min_trades: int = 30) -> list[str]:
    """پیشنهادِ سرانگشتی — فقط بر پایهٔ همین اعداد (نه چیز دیگر)."""
    out: list[str] = []
    rows = {k: v for k, v in (stats.get("per_strategy") or {}).items()
            if v["trades"] >= min_trades}
    if not rows:
        return ["نمونهٔ کافی برای هیچ استراتژی نیست — بازهٔ داده را بزرگ‌تر کن."]
    worst = min(rows.items(), key=lambda kv: kv[1]["avg_r"])
    best = max(rows.items(), key=lambda kv: kv[1]["avg_r"])
    if worst[1]["avg_r"] < 0:
        out.append(f"استراتژی «{worst[0]}» میانگین R منفی دارد "
                   f"({worst[1]['avg_r']:+.3f}) → کاندیدِ خاموش‌کردن در strategy_gate.")
    if best[1]["avg_r"] > 0:
        out.append(f"استراتژی «{best[0]}» تنها گروهِ سودده است "
                   f"({best[1]['avg_r']:+.3f}) → اول همین را تقویت کن.")
    if all(v["avg_r"] < 0 for v in rows.values()):
        out.append("همهٔ گروه‌ها منفی‌اند → مسئله درستاپ نیست؛ سطح ورود/خروج یا هزینه است.")
    return out


def read_report(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("stats")
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
#  اجرا
# ══════════════════════════════════════════════════════════════
def run_backtest(args_list: list[str]) -> int:
    cmd = [sys.executable, str(BACKTEST)] + args_list
    print("   $ " + " ".join(cmd[1:]))
    return subprocess.call(cmd, cwd=str(ROOT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="بررسی سریع کیفیت سیگنال (v1.6.0)")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--out", default=str(ROOT / "reports" / "quality"))
    ap.add_argument("--from", dest="start", default="")
    ap.add_argument("--to", dest="end", default="")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--sweep", default="5,6,7,8")
    ap.add_argument("--skip-run", action="store_true",
                    help="فقط خلاصهٔ گزارش‌های موجود را بخوان")
    args = ap.parse_args(argv)

    data_dir = resolve_data_dir(args.data_dir)
    print("═" * 62)
    print("🔎 بررسی کیفیت سیگنال — ODIN")
    print("═" * 62)
    if data_dir is None:
        print("❌ پوشهٔ دادهٔ M15 پیدا نشد.")
        print("   یک پوشه با فایل‌های CSV بساز (مثلاً EURUSD_M15.csv) و بده:")
        print('     python tools/quality_check.py --data-dir "%USERPROFILE%\\odin-m15"')
        print("   هر فایل باید ستون‌های time (یا date+time) و open/high/low/close داشته باشد.")
        return 2
    files = data_files(data_dir)
    print(f"📁 داده: {data_dir}")
    print(f"   {len(files)} نماد: {', '.join(sorted(files)) or '—'}")
    if len(files) < 2:
        print("⚠️ کمتر از دو نماد: نتیجهٔ بک‌تست قابل اتکا نیست.")

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    base_json = out / f"{DEFAULT_LABEL}.json"

    if not args.skip_run:
        common = ["--data-dir", str(data_dir), "--out", str(out)]
        if args.start:
            common += ["--from", args.start]
        if args.end:
            common += ["--to", args.end]
        print("\n۱) بک‌تست پایه…")
        rc = run_backtest(common + ["--label", DEFAULT_LABEL, "--jobs", str(args.jobs)])
        if rc != 0:
            print("❌ بک‌تست پایه ناموفق بود.")
            return rc
        print("\n۲) جاروی آستانهٔ امتیاز…")
        rc = run_backtest(common + ["--sweep-min-score", args.sweep, "--jobs", str(args.jobs)])
        if rc != 0:
            print("⚠️ جارو ناموفق بود؛ ادامه با گزارش پایه.")

    stats = read_report(base_json)
    if stats is None:
        print(f"\n❌ گزارش پیدا نشد: {base_json}")
        print("   --skip-run را برداری تا اجرا شود.")
        return 2

    print("\n" + "─" * 62)
    print("📊 خلاصه")
    for line in summarize(stats):
        print("  " + line)
    for line in advice(stats):
        print("  💡 " + line)

    print("\n" + "─" * 62)
    print("📤 این دو فایل را بفرست:")
    for p in (base_json, out / "sweep-min-score.md"):
        print(f"   {p}  {'✓' if p.exists() else '✗ (ساخته نشد)'}")
    print("   (یا فقط همین متن بالا را کپی کن)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
