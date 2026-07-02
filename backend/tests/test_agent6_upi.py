"""Agent 6 UPI Heuristic Engine tests."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ml.upi_heuristic_engine import UPIHeuristicEngine

RULES_PATH = os.path.join(os.path.dirname(__file__), "..", "app", "ml", "artifacts", "upi_heuristic_rules.yaml")
engine = UPIHeuristicEngine(RULES_PATH)


def _txn(vpa: str) -> dict:
    return {"vpa": vpa, "timestamp": "2026-07-01T14:30:00Z", "amount": 100}


def test_hello_at_paytm_safe():
    r = engine.scan(_txn("hello@paytm"))
    assert r["score"] < 15, f"Expected < 15, got {r['score']}"


def test_bill_payment_at_axisbank_safe():
    r = engine.scan(_txn("bill-payment@axisbank"))
    assert r["score"] < 15, f"Expected < 15, got {r['score']}"


def test_friend_at_upi_safe():
    r = engine.scan(_txn("friend@upi"))
    assert r["score"] < 15, f"Expected < 15, got {r['score']}"


def test_prize_winner_scam():
    r = engine.scan(_txn("prize-winner@random123"))
    assert r["score"] >= 60, f"Expected >= 60, got {r['score']} ({r['severity']})"


def test_govt_refund_scam():
    r = engine.scan(_txn("govt-refund@upi-help"))
    assert r["score"] >= 60, f"Expected >= 60, got {r['score']} ({r['severity']})"


def test_kyc_update_typo_scam():
    r = engine.scan(_txn("kyc-update@axisbannk"))
    assert r["score"] >= 60, f"Expected >= 60, got {r['score']} ({r['severity']})"
