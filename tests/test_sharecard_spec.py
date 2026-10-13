"""Pure Python share-card spec parity tests; no Qt dependency."""
from src.report.sharecard import build_share_spec

SIGNAL = {
    "symbol": "EURUSD",
    "direction": "BUY",
    "entry": 1.1000,
    "sl": 1.0980,
    "tp": 1.1040,
    "pip": 0.0001,
    "score": 8,
    "max_score": 11,
    "rr": 2.0,
}

def test_default_version_matches_js_fallback():
    assert build_share_spec(SIGNAL)["version"] == "vdev"

def test_explicit_version_is_preserved():
    assert build_share_spec(SIGNAL, version="0.28.0")["version"] == "v0.28.0"

if __name__ == "__main__":
    test_default_version_matches_js_fallback()
    test_explicit_version_is_preserved()
    print("SHARECARD SPEC OK — default and explicit version parity")
