#!/usr/bin/env python3
"""Download historical OHLC candles from Dukascopy using dukascopy-node.

Requires Node.js/npm and network access. This script does not modify config.yaml
or the live data source. Output is stored under data/historical/dukascopy/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path

SYMBOLS = {
    "EURUSD": "eurusd",
    "GBPUSD": "gbpusd",
    "USDJPY": "usdjpy",
    "USDCAD": "usdcad",
    "AUDUSD": "audusd",
    "USDCHF": "usdchf",
    # Dukascopy's XAU/USD spot instrument; deliberately not GC=F futures.
    "XAUUSD": "xauusd",
}
TIMEFRAMES = ("m15", "h1", "h4")


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must be YYYY-MM-DD") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-date", type=parse_date, default=dt.date(2026, 4, 13))
    parser.add_argument("--to-date", type=parse_date, default=dt.date(2026, 10, 13))
    parser.add_argument("--output", type=Path, default=Path("data/historical/dukascopy"))
    parser.add_argument("--symbols", nargs="+", choices=sorted(SYMBOLS), default=list(SYMBOLS))
    parser.add_argument("--timeframes", nargs="+", choices=TIMEFRAMES, default=list(TIMEFRAMES))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.from_date >= args.to_date:
        parser.error("--from-date must be earlier than --to-date")
    if not args.dry_run and not (shutil.which("npx") or shutil.which("npx.cmd")):
        print("ERROR: Node.js/npm (npx) is required. Install Node.js 18+ first.", file=sys.stderr)
        return 2

    failures = 0
    for symbol in args.symbols:
        for timeframe in args.timeframes:
            destination = args.output / symbol / timeframe.upper()
            command = [
                "npx", "--yes", "dukascopy-node",
                "-i", SYMBOLS[symbol],
                "-from", args.from_date.isoformat(),
                "-to", args.to_date.isoformat(),
                "-t", timeframe,
                "-f", "csv",
                "-dir", str(destination),
            ]
            print("$ " + " ".join(command))
            if args.dry_run:
                continue
            destination.mkdir(parents=True, exist_ok=True)
            try:
                result = subprocess.run(command, check=False)
            except OSError as exc:
                print(f"ERROR {symbol}/{timeframe}: {exc}", file=sys.stderr)
                failures += 1
                continue
            if result.returncode:
                print(f"ERROR {symbol}/{timeframe}: downloader exited {result.returncode}", file=sys.stderr)
                failures += 1

    if failures:
        print(f"Completed with {failures} failed download(s). Check the provider response and instrument availability.", file=sys.stderr)
        return 1
    print(f"Download commands completed. Next run: python scripts/backtest/validate_data.py --input {args.output}")
    print("Note: command success does not prove full date coverage; use the validation report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
