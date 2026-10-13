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

from validate_data import inspect_csv

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


def csv_snapshot(destination: Path) -> dict[Path, tuple[int, int]]:
    """Record CSV metadata so a stale file cannot prove a new download succeeded."""
    snapshot = {}
    if destination.exists():
        for path in destination.rglob("*.csv"):
            try:
                stat = path.stat()
                snapshot[path] = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                continue
    return snapshot


def check_download_outputs(destination: Path, before: dict[Path, tuple[int, int]]) -> list[str]:
    """Return errors for missing, unchanged, empty, or invalid downloader output."""
    after = csv_snapshot(destination)
    changed = [
        path for path, metadata in after.items()
        if before.get(path) != metadata
    ]
    errors = []
    if not changed:
        return [f"No new or changed CSV output found under {destination}"]

    for path in changed:
        try:
            if path.stat().st_size == 0:
                errors.append(f"{path}: downloader created an empty (0-byte) file")
                continue
        except OSError as exc:
            errors.append(f"{path}: cannot inspect output ({exc})")
            continue

        report = inspect_csv(path)
        if report["status"] != "PASS":
            details = "; ".join(report["errors"][:3]) or "CSV failed OHLC validation"
            errors.append(f"{path}: invalid CSV output: {details}")
    return errors


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
            before = csv_snapshot(destination)
            try:
                result = subprocess.run(command, check=False)
            except OSError as exc:
                print(f"ERROR {symbol}/{timeframe}: could not start downloader: {exc}", file=sys.stderr)
                failures += 1
                continue
            if result.returncode:
                print(f"ERROR {symbol}/{timeframe}: downloader exited {result.returncode}", file=sys.stderr)
                failures += 1
                continue

            output_errors = check_download_outputs(destination, before)
            if output_errors:
                for error in output_errors:
                    print(f"ERROR {symbol}/{timeframe}: {error}", file=sys.stderr)
                failures += 1
            else:
                print(f"OK {symbol}/{timeframe}: new CSV output passed structural/OHLC validation")

    if failures:
        print(
            f"FAILED: {failures} symbol/timeframe download(s) did not produce valid new CSV data. "
            "Check the provider response, instrument availability, and downloader logs.",
            file=sys.stderr,
        )
        return 1
    print(f"All download commands produced valid new CSV output. Next run: python scripts/backtest/validate_data.py --input {args.output}")
    print("Note: this confirms non-empty, structurally valid output, not full date coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
