"""Regression tests for historical-download output validation."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "backtest"))

from download_data import check_download_outputs, csv_snapshot
from validate_data import inspect_csv

VALID_CSV = (
    "timestamp,open,high,low,close,volume\n"
    "2026-10-12 10:00:00,1.1,1.2,1.0,1.15,100\n"
)


class HistoricalCsvValidationTests(unittest.TestCase):
    def test_empty_csv_is_explicitly_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "EURUSD" / "M15" / "empty.csv"
            path.parent.mkdir(parents=True)
            path.write_text("", encoding="utf-8")
            report = inspect_csv(path)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("Empty CSV file (0 bytes)", report["errors"])

    def test_missing_csv_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "EURUSD" / "M15"
            destination.mkdir(parents=True)
            self.assertTrue(check_download_outputs(destination, {}))

    def test_empty_download_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "EURUSD" / "M15"
            destination.mkdir(parents=True)
            before = csv_snapshot(destination)
            (destination / "empty.csv").write_text("", encoding="utf-8")
            errors = check_download_outputs(destination, before)
            self.assertTrue(any("empty (0-byte)" in error for error in errors), errors)

    def test_valid_new_csv_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "EURUSD" / "M15"
            destination.mkdir(parents=True)
            before = csv_snapshot(destination)
            (destination / "candles.csv").write_text(VALID_CSV, encoding="utf-8")
            self.assertEqual(check_download_outputs(destination, before), [])

    def test_header_without_data_rows_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "candles.csv"
            path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
            report = inspect_csv(path)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("No valid OHLC rows", report["errors"])

    def test_unchanged_stale_csv_does_not_count_as_new_output(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "EURUSD" / "M15"
            destination.mkdir(parents=True)
            stale = destination / "old.csv"
            stale.write_text(VALID_CSV, encoding="utf-8")
            before = csv_snapshot(destination)
            self.assertTrue(check_download_outputs(destination, before))


if __name__ == "__main__":
    unittest.main()
