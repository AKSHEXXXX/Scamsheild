import re
import math


KNOWN_GOOD_HANDLES = {
    "paytm", "ybl", "upi", "oksbi", "okaxis", "okhdfcbank", "okicici",
    "axisbank", "hdfcbank", "icici", "sbi", "ibl", "axl", "ptsbi",
    "pthdfc", "ptaxis", "ptyes", "okbizaxis", "okbizhdfcbank"
}

HIGH_TRUST_HANDLES = {
    "paytm", "ybl", "upi", "oksbi", "okaxis", "okhdfcbank",
    "okicici", "axisbank", "hdfcbank", "icici", "sbi"
}

KNOWN_SAFE_PREFIXES = {
    "hello", "help", "support", "customer-care", "bill-payment", "billpay",
    "merchant", "store", "shop", "restaurant", "cafe", "coffee", "grocery",
    "electricity", "water", "gas", "mobile", "recharge", "rent", "fees",
    "school", "college", "university", "hospital", "clinic", "pharmacy",
    "rahul.sharma", "rahul", "rohit", "amit", "somen", "sheehan", "john",
    "jane", "office", "admin", "accounts", "billing", "invoice", "taxi",
    "cab", "delivery", "service", "vendor", "official", "payments",
    "subscription", "donation", "temple", "trust", "ngo"
}

SCAM_PREFIX_KEYWORDS = {
    "urgent", "prize", "winner", "kyc", "verify", "reward", "refund",
    "cashback", "free", "lottery", "gift", "otp", "pin", "blocked",
    "suspended", "claim", "bonus", "loan", "approve", "collect", "support",
    "bank", "icici", "hdfc", "sbi", "paytm", "phonepe", "gpay"
}

URGENCY_KEYWORDS = {
    "urgent", "immediately", "now", "today", "within", "expire", "expires",
    "last chance", "blocked", "suspended", "limited", "final warning"
}

PRIZE_KEYWORDS = {
    "prize", "winner", "lottery", "reward", "cashback", "gift", "bonus",
    "free", "claim", "jackpot", "congratulations"
}

KYC_OTP_KEYWORDS = {
    "kyc", "otp", "pin", "password", "verify", "verification", "update",
    "reactivate", "account locked", "blocked", "suspended", "login"
}

COLLECT_KEYWORDS = {
    "collect", "request", "approve", "approval", "mandate", "autopay",
    "pay request", "requested money"
}

FEATURE_ORDER = [
    "vpa_present", "vpa_valid_format", "vpa_prefix_len", "vpa_prefix_entropy",
    "vpa_prefix_digit_count", "vpa_prefix_alpha_count", "vpa_prefix_special_count",
    "vpa_prefix_digit_ratio", "vpa_prefix_is_digits_only", "vpa_prefix_has_dot",
    "vpa_prefix_has_hyphen", "vpa_prefix_has_scam_keyword",
    "vpa_prefix_scam_keyword_count", "vpa_prefix_known_safe",
    "vpa_handle_known_good", "vpa_handle_high_trust", "vpa_handle_unknown",
    "vpa_handle_paytm", "vpa_handle_ybl", "vpa_handle_upi",
    "vpa_handle_oksbi", "vpa_handle_okaxis", "vpa_handle_okhdfcbank",
    "vpa_handle_okicici", "vpa_handle_axisbank", "vpa_handle_hdfcbank",
    "vpa_handle_icici", "vpa_handle_sbi",
    "message_len", "message_entropy", "message_word_count",
    "message_urgency_keyword_count", "message_prize_keyword_count",
    "message_kyc_otp_keyword_count", "message_collect_keyword_count",
    "message_amount_mention", "message_amount_value_max",
    "message_multiplier_promise", "message_contains_phone",
    "message_contains_url", "message_contains_otp_pattern",
    "message_scam_keyword_density", "message_sentiment_polarity",
    "message_sentiment_urgency_score",
    "transaction_type_collect", "transaction_type_send",
    "collect_with_scam_context", "unknown_handle_with_scam_context",
    "known_handle_with_safe_prefix", "known_handle_safe_message",
    "whitelist_exact_match", "whitelist_prefix_match",
]


def _safe_str(x):
    if x is None:
        return ""
    return str(x).strip()


def shannon_entropy(s):
    s = _safe_str(s)
    if not s:
        return 0.0
    counts = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    ent = 0.0
    for count in counts.values():
        p = count / n
        ent -= p * math.log2(p)
    return ent


def split_vpa(vpa):
    vpa = _safe_str(vpa).lower()
    if "@" not in vpa:
        return vpa, ""
    prefix, handle = vpa.rsplit("@", 1)
    return prefix.strip(), handle.strip()


def normalize_transaction_type(transaction_type=None, message=""):
    tx = _safe_str(transaction_type).upper()
    msg = _safe_str(message).lower()
    if tx in {"COLLECT", "REQUEST", "PULL", "MANDATE"}:
        return "COLLECT"
    if tx in {"SEND", "PAY", "PUSH"}:
        return "SEND"
    if any(k in msg for k in COLLECT_KEYWORDS):
        return "COLLECT"
    return "SEND"


def count_keyword_hits(text, keywords):
    low = _safe_str(text).lower()
    return sum(1 for kw in keywords if kw in low)


def extract_amounts(text):
    low = _safe_str(text).lower()
    amounts = []
    for m in re.finditer(r"(?:rs\.?|inr|rupees?|\u20b9)\s*([0-9]+(?:\.[0-9]+)?)", low):
        try:
            amounts.append(float(m.group(1)))
        except Exception:
            pass
    for m in re.finditer(r"([0-9]+(?:\.[0-9]+)?)\s*(?:rs\.?|inr|rupees?)", low):
        try:
            amounts.append(float(m.group(1)))
        except Exception:
            pass
    return amounts


def has_multiplier_promise(text):
    low = _safe_str(text).lower()
    patterns = [
        r"pay\s*\d+\s*(?:and|get|to get)\s*\d+",
        r"send\s*\d+\s*(?:and|get|to get)\s*\d+",
        r"double\s+your\s+money",
        r"2x|3x|5x|10x",
        r"pay.*get",
    ]
    return int(any(re.search(p, low) for p in patterns))


def safe_prefix_match(prefix):
    p = _safe_str(prefix).lower()
    if p in KNOWN_SAFE_PREFIXES:
        return 1
    stripped = re.sub(r"[0-9]+$", "", p).strip(".-_")
    if stripped in KNOWN_SAFE_PREFIXES:
        return 1
    if any(p.startswith(x + ".") or p.startswith(x + "-") for x in KNOWN_SAFE_PREFIXES):
        return 1
    return 0


def exact_whitelist_match(vpa, whitelist=None):
    if whitelist is None:
        whitelist = {}
    v = _safe_str(vpa).lower()
    exact = set(x.lower() for x in whitelist.get("exact_vpas", []))
    return int(v in exact)


def prefix_whitelist_match(prefix, whitelist=None):
    if whitelist is None:
        whitelist = {}
    p = _safe_str(prefix).lower()
    prefixes = set(x.lower() for x in whitelist.get("safe_prefixes", []))
    if p in prefixes:
        return 1
    stripped = re.sub(r"[0-9]+$", "", p).strip(".-_")
    return int(stripped in prefixes)


def extract_features(vpa, message="", transaction_type=None, whitelist=None):
    vpa = _safe_str(vpa).lower()
    message = _safe_str(message)
    prefix, handle = split_vpa(vpa)
    tx_type = normalize_transaction_type(transaction_type, message)

    prefix_len = len(prefix)
    prefix_digit_count = sum(ch.isdigit() for ch in prefix)
    prefix_alpha_count = sum(ch.isalpha() for ch in prefix)
    prefix_special_count = sum((not ch.isalnum()) for ch in prefix)
    prefix_scam_hits = count_keyword_hits(prefix, SCAM_PREFIX_KEYWORDS)

    msg_words = re.findall(r"[a-zA-Z0-9]+", message.lower())
    msg_word_count = len(msg_words)
    urgency_hits = count_keyword_hits(message, URGENCY_KEYWORDS)
    prize_hits = count_keyword_hits(message, PRIZE_KEYWORDS)
    kyc_hits = count_keyword_hits(message, KYC_OTP_KEYWORDS)
    collect_hits = count_keyword_hits(message, COLLECT_KEYWORDS)
    msg_scam_hits = urgency_hits + prize_hits + kyc_hits + collect_hits

    amounts = extract_amounts(message)
    amount_max = max(amounts) if amounts else 0.0

    handle_known_good = int(handle in KNOWN_GOOD_HANDLES)
    handle_high_trust = int(handle in HIGH_TRUST_HANDLES)
    handle_unknown = int(bool(handle) and handle not in KNOWN_GOOD_HANDLES)

    prefix_safe = safe_prefix_match(prefix)
    whitelist_exact = exact_whitelist_match(vpa, whitelist)
    whitelist_prefix = prefix_whitelist_match(prefix, whitelist)

    scam_context = int((msg_scam_hits >= 1) or (prefix_scam_hits >= 1))
    safe_message = int(msg_scam_hits == 0 and collect_hits == 0 and amount_max < 10000)

    features = {
        "vpa_present": int(bool(vpa)),
        "vpa_valid_format": int(bool(prefix) and bool(handle) and re.fullmatch(r"[a-zA-Z0-9._\-]+@[a-zA-Z0-9._\-]+", vpa) is not None),
        "vpa_prefix_len": prefix_len,
        "vpa_prefix_entropy": shannon_entropy(prefix),
        "vpa_prefix_digit_count": prefix_digit_count,
        "vpa_prefix_alpha_count": prefix_alpha_count,
        "vpa_prefix_special_count": prefix_special_count,
        "vpa_prefix_digit_ratio": prefix_digit_count / max(1, prefix_len),
        "vpa_prefix_is_digits_only": int(prefix.isdigit() and prefix_len > 0),
        "vpa_prefix_has_dot": int("." in prefix),
        "vpa_prefix_has_hyphen": int("-" in prefix),
        "vpa_prefix_has_scam_keyword": int(prefix_scam_hits > 0),
        "vpa_prefix_scam_keyword_count": prefix_scam_hits,
        "vpa_prefix_known_safe": prefix_safe,
        "vpa_handle_known_good": handle_known_good,
        "vpa_handle_high_trust": handle_high_trust,
        "vpa_handle_unknown": handle_unknown,
        "vpa_handle_paytm": int(handle == "paytm"),
        "vpa_handle_ybl": int(handle == "ybl"),
        "vpa_handle_upi": int(handle == "upi"),
        "vpa_handle_oksbi": int(handle == "oksbi"),
        "vpa_handle_okaxis": int(handle == "okaxis"),
        "vpa_handle_okhdfcbank": int(handle == "okhdfcbank"),
        "vpa_handle_okicici": int(handle == "okicici"),
        "vpa_handle_axisbank": int(handle == "axisbank"),
        "vpa_handle_hdfcbank": int(handle == "hdfcbank"),
        "vpa_handle_icici": int(handle == "icici"),
        "vpa_handle_sbi": int(handle == "sbi"),
        "message_len": len(message),
        "message_entropy": shannon_entropy(message),
        "message_word_count": msg_word_count,
        "message_urgency_keyword_count": urgency_hits,
        "message_prize_keyword_count": prize_hits,
        "message_kyc_otp_keyword_count": kyc_hits,
        "message_collect_keyword_count": collect_hits,
        "message_amount_mention": int(len(amounts) > 0),
        "message_amount_value_max": float(amount_max),
        "message_multiplier_promise": has_multiplier_promise(message),
        "message_contains_phone": int(bool(re.search(r"(\+?\d[\d\-\s]{7,}\d)", message))),
        "message_contains_url": int(bool(re.search(r"https?://|www\.", message.lower()))),
        "message_contains_otp_pattern": int(bool(re.search(r"\botp\b|one[- ]?time password|\b\d{4,6}\b", message.lower()))),
        "message_scam_keyword_density": msg_scam_hits / max(1, msg_word_count),
        "message_sentiment_polarity": 0.0,
        "message_sentiment_urgency_score": urgency_hits + collect_hits + kyc_hits,
        "transaction_type_collect": int(tx_type == "COLLECT"),
        "transaction_type_send": int(tx_type == "SEND"),
        "collect_with_scam_context": int(tx_type == "COLLECT" and scam_context == 1),
        "unknown_handle_with_scam_context": int(handle_unknown == 1 and scam_context == 1),
        "known_handle_with_safe_prefix": int(handle_high_trust == 1 and prefix_safe == 1),
        "known_handle_safe_message": int(handle_high_trust == 1 and safe_message == 1),
        "whitelist_exact_match": whitelist_exact,
        "whitelist_prefix_match": whitelist_prefix,
    }

    return [features.get(k, 0) for k in FEATURE_ORDER]
