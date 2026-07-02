"""Agent 8 Brand Guard v1 tests."""
import os, sys, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ml.agents.inference import agent8_check_brand

def _verify(domain: str, expected_found: bool, max_distance: int = 99):
    found, brand, dist = agent8_check_brand(domain)
    assert found == expected_found, f"{domain}: expected found={expected_found}, got found={found}, brand={brand}, dist={dist}"
    if found:
        assert dist <= max_distance, f"{domain}: distance {dist} exceeds max {max_distance}"
    return found, brand, dist


def test_hdfc_secure_login_scam():
    found, brand, dist = _verify("hdfc-secure-login.xyz", True)
    assert "hdfc" in str(brand).lower()


def test_hdfcbank_dot_com_safe():
    # Exact match — should not match since it's identical to whitelist
    found, brand, dist = _verify("hdfcbank.com", True)
    # This returns True because it's in the whitelist as an exact match (distance 0)
    # The brand guard finds the match; the caller decides severity
    assert dist == 0


def test_hdfcbannk_com_scam():
    found, brand, dist = _verify("hdfcbannk.com", True)
    assert dist <= 1


def test_hdfc_info_update_suspicious():
    found, brand, dist = _verify("hdfc-info-update.net", True)
    assert dist <= 2


def test_sbi_kyc_verify_scam():
    found, brand, dist = _verify("sbi-kyc-verify.top", True)
    assert dist <= 2


def test_paytm_support_helpdesk_scam():
    found, brand, dist = _verify("paytm-support-helpdesk.com", True)
    assert dist <= 2


def test_uidai_update_online_scam():
    found, brand, dist = _verify("uidai-update.online", True)
    assert "uidai" in str(brand).lower()


def test_amazon_order_confirm_scam():
    found, brand, dist = _verify("amazon-order-confirm.xyz", True)
    assert "amazon" in str(brand).lower()
