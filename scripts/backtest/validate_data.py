#!/usr/bin/env python3
"""Validate Dukascopy CSV OHLC files and write a machine-readable audit report."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path

MINUTES = {"M15": 15, "H1": 60, "H4": 240}
ALIASES = {
    "timestamp": {"timestamp", "datetime", "date", "time", "gmt time", "utc", "timestamputc"},
    "open": {"open", "o"},
    "high": {"high", "h"},
    "low": {"low", "l"},
    "close": {"close", "c"},
    "volume": {"volume", "vol", "v", "tickvolume"},
}


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def parse_timestamp(value: str) -> dt.datetime:
    value = value.strip().replace("Z", "+00:00")
    # ISO timestamps and common Dukascopy CSV timestamp formats.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M"):
        try:
            parsed = dt.datetime.strptime(value, fmt)
            return parsed.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def inspect_csv(path: Path) -> dict:
    base = {"file": str(path), "rows": 0, "errors": [], "duplicate_timestamps": 0,
            "non_monotonic_timestamps": 0, "invalid_ohlc_rows": 0, "gaps_over_one_bar": 0,
            "longest_gap_minutes": None, "start_utc": None, "end_utc": None,
            "columns": [], "status": "FAIL"}
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                base["errors"].append("Missing CSV header")
                return base
            base["columns"] = reader.fieldnames
            lookup = {norm(name): name for name in reader.fieldnames}
            mapped = {}
            for canonical, aliases in ALIASES.items():
                for key, original in lookup.items():
                    if key in {norm(alias) for alias in aliases}:
                        mapped[canonical] = original
                        break
            missing = [key for key in ("timestamp", "open", "high", "low", "close") if key not in mapped]
            if missing:
                base["errors"].append("Missing required columns: " + ", ".join(missing))
                return base

            records = []
            for line_no, row in enumerate(reader, start=2):
                if not any((value or "").strip() for value in row.values()):
                    continue
                try:
                    stamp = parse_timestamp(row[mapped["timestamp"]])
                    o, h, low, c = (float(row[mapped[k]]) for k in ("open", "high", "low", "close"))
                    if not all(map(lambda x: x == x and abs(x) != float("inf"), (o, h, low, c))):
                        raise ValueError("non-finite OHLC")
                    if low > min(o, c) or h < max(o, c) or low > h:
                        base["invalid_ohlc_rows"] += 1
                    records.append((stamp, o, h, low, c))
                except (ValueError, TypeError, KeyError, OverflowError) as exc:
                    base["errors"].append(f"Line {line_no}: invalid timestamp/OHLC ({exc})")
            if not records:
                base["errors"].append("No valid OHLC rows")
                return base

            stamps = [record[0] for record in records]
            unique = sorted(set(stamps))
            base["rows"] = len(records)
            base["duplicate_timestamps"] = len(stamps) - len(set(stamps))
            base["non_monotonic_timestamps"] = sum(stamps[i] < stamps[i - 1] for i in range(1, len(stamps)))
            base["start_utc"] = unique[0].isoformat()
            base["end_utc"] = unique[-1].isoformat()
            gaps = [(unique[i] - unique[i - 1]).total_seconds() / 60 for i in range(1, len(unique))]
            # Gap counts are raw observations, including normal market closures.
            base["gaps_over_one_bar"] = sum(gap > 0 for gap in gaps)
            base["longest_gap_minutes"] = max(gaps) if gaps else 0
            base["note"] = "Gap metrics include weekends/market closures; inspect before treating gaps as missing bars."
            base["status"] = "PASS" if not base["errors"] and not base["invalid_ohlc_rows"] and not base["duplicate_timestamps"] and not base["non_monotonic_timestamps"] else "FAIL"
    except (OSError, UnicodeError, csv.Error) as exc:
        base["errors"].append(f"Cannot read CSV: {exc}")
    return base


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/historical/dukascopy"))
    parser.add_argument("--report", type=Path, default=Path("data/historical/validation-report.json"))
    args = parser.parse_args()
    files = sorted(args.input.rglob("*.csv")) if args.input.exists() else []
    if not files:
        print(f"ERROR: no CSV files found under {args.input}")
        return 2

    results = [inspect_csv(path) for path in files]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "input_directory": str(args.input),
        "files_checked": len(results),
        "files_passed": sum(item["status"] == "PASS" for item in results),
        "files_failed": sum(item["status"] != "PASS" for item in results),
        "results": results,
    }, indent=2), encoding="utf-8")

    for item in results:
        print(f'{item["status"]:4} {item["file"]}: rows={item["rows"]}, '
              f'{item["start_utc"]} -> {item["end_utc"]}, '
              f'duplicates={item["duplicate_timestamps"]}, invalid_ohlc={item["invalid_ohlc_rows"]}')
        for error in item["errors"][:5]:
            print(f'     {error}')
    print(f"Report: {args.report}")
    return 0 if all(item["status"] == "PASS" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
