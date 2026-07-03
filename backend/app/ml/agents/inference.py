import re
import logging
import numpy as np
from urllib.parse import urlparse

logger = logging.getLogger("scamshield.ml.agents")

from app.utils.text import preprocess_text
from app.ml.model_loader import get_models, is_agent_healthy, record_agent_error, record_agent_success

# Agent 13 — DistilBERT multilingual INT8 call transcript fraud classifier
# Ensemble weight: 0.15 (conservative until validated in production)
try:
    from app.ml.agents.agent13_inference import agent13_predict as _agent13_predict
    _AGENT13_AVAILABLE = True
except Exception as _a13_err:
    logger.warning("[agent13] Import failed — %s. Using stub fallback.", _a13_err)
    _AGENT13_AVAILABLE = False
    _agent13_predict = None

# Agent 2 — DistilBERT multilingual text/SMS scam classifier
# Ensemble weight: 0.18
try:
    from app.ml.agents.agent2_inference import agent2_predict as _agent2_predict
    _AGENT2_AVAILABLE = True
except Exception as _a2_err:
    logger.warning("[agent2] Import failed — %s. Using stub fallback.", _a2_err)
    _AGENT2_AVAILABLE = False
    _agent2_predict = None

def agent1_predict_text(text: str) -> float:
    if not is_agent_healthy("agent1"):
        return -1.0
    models = get_models()
    vec = models.get("agent1_vectorizer")
    clf = models.get("agent1_classifier")
    if vec is None or clf is None:
        return -1.0
    try:
        clean = preprocess_text(text)
        if isinstance(vec, dict):
            tfidf_vec = vec.get("tfidf_vectorizer")
            custom_flags = vec.get("custom_flags")
            if tfidf_vec is not None and custom_flags is not None:
                from scipy.sparse import hstack
                X_tfidf = tfidf_vec.transform([clean])
                X_flags = custom_flags.transform([clean])
                X = hstack([X_tfidf, X_flags])
            else:
                X = tfidf_vec.transform([clean]) if tfidf_vec else vec.transform([clean])
        else:
            X = vec.transform([clean])
        proba = clf.predict_proba(X)[0]
        scam_idx = 1 if proba.shape[0] > 1 else 0
        record_agent_success("agent1")
        return float(proba[scam_idx])
    except Exception as e:
        logger.debug("Agent 1 predict error: %s", e)
        record_agent_error("agent1")
        return -1.0

def agent2_predict_text(text: str) -> float:
    """
    Returns a 0.0-1.0 scam probability for the ensemble.
    Ensemble weight: 0.18 (applied by the caller).
    Returns -1.0 (skip signal) when model is not loaded.

    Label mapping:
      SCAM       -> raw confidence (high)
      SUSPICIOUS -> clamped to [0.45, 0.60]  — uncertain, not near-SCAM
      SAFE       -> min(confidence, 0.25)
    """
    if not _AGENT2_AVAILABLE or _agent2_predict is None:
        return -1.0
    try:
        result = _agent2_predict(text)
        if not result.get("model_loaded", False):
            return -1.0
        label      = result.get("label", "SAFE").upper()
        confidence = float(result.get("confidence", 0.0))
        if label == "SCAM":
            return confidence
        elif label == "SUSPICIOUS":
            # Gate has already downgraded this from SCAM. Clamp to moderate range
            # so it contributes uncertainty without dominating the ensemble.
            return min(max(confidence * 0.6, 0.45), 0.60)
        else:
            return min(confidence, 0.25)
    except Exception as e:
        logger.debug("Agent 2 predict error: %s", e)
        return -1.0



def agent2_predict_text_full(text: str) -> dict:
    """Returns the full dict from the Agent 2 classifier."""
    if not _AGENT2_AVAILABLE or _agent2_predict is None:
        return {"label": "SAFE", "confidence": 0.0, "agent": "agent2",
                "model": "not_loaded", "model_loaded": False}
    try:
        return _agent2_predict(text)
    except Exception as e:
        logger.debug("Agent 2 full predict error: %s", e)
        return {"label": "SAFE", "confidence": 0.0, "agent": "agent2",
                "model": "error", "model_loaded": False, "error": str(e)}

def extract_url_features(url: str) -> dict:
    """
    Extract 20 lexical URL features matching the retrained Agent 3 XGBoost model.
    Column order is enforced by url_feature_cols.pkl at inference time.
    """
    import tldextract
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    ext = tldextract.extract(url)
    domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
    full_url_lower = url.lower()

    # Known URL shorteners
    _SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "ow.ly", "goo.gl",
                   "rb.gy", "cutt.ly", "is.gd", "buff.ly", "adf.ly"}
    # Indian bank brand keywords
    _BANK_BRANDS = ["sbi", "hdfc", "icici", "axis", "kotak", "pnb", "bob",
                    "canara", "union", "yes bank", "rbl", "iob", "boi"]
    # UPI-related signals
    _UPI_SIGNALS = ["upi", "paytm", "phonepe", "gpay", "googlepay", "bhim",
                    "bhimpay", "upi-update", "kyc", "payment", "wallet"]

    return {
        "url_length":           len(url),
        "domain_length":        len(domain),
        "tld_length":           len(ext.suffix) if ext.suffix else 0,
        "subdomain_count":      len(ext.subdomain.split(".")) if ext.subdomain else 0,
        "path_length":          len(parsed.path),
        "has_https":            1 if parsed.scheme == "https" else 0,
        "has_ip":               1 if re.search(r"\d+\.\d+\.\d+\.\d+", ext.domain or "") else 0,
        "count_=":              url.count("="),
        "count_?":              url.count("?"),
        "count_&":              url.count("&"),
        "count_@":              url.count("@"),
        "count_-":              url.count("-"),
        "count__":              url.count("_"),
        "count_/":              url.count("/"),
        "count_.":              url.count("."),
        "char_continuation_rate": sum(url.count(c * 2) for c in set(url)) / max(len(url), 1),
        "is_shortener":         1 if any(s in full_url_lower for s in _SHORTENERS) else 0,
        "has_.in":              1 if ext.suffix in ("in", "co.in") else 0,
        "indian_bank_brand":    1 if any(b in full_url_lower for b in _BANK_BRANDS) else 0,
        "upi_related":          1 if any(s in full_url_lower for s in _UPI_SIGNALS) else 0,
    }


def agent3_predict_url(url: str) -> float:
    if not is_agent_healthy("agent3"):
        return -1.0
    models = get_models()
    clf = models.get("agent3_classifier")
    sc = models.get("agent3_scaler")
    cols = models.get("agent3_feature_cols")
    if clf is None or sc is None or cols is None:
        return -1.0
    try:
        feats = extract_url_features(url)
        row = np.array([[feats.get(c, 0) for c in cols]])
        row_scaled = sc.transform(row)
        proba = clf.predict_proba(row_scaled)[0]
        # Robustly find the index of the phishing/fraud class (label=1)
        classes = list(clf.classes_)
        scam_idx = classes.index(1) if 1 in classes else (1 if len(classes) > 1 else 0)
        record_agent_success("agent3")
        return float(proba[scam_idx])
    except Exception as e:
        logger.debug("Agent 3 predict error: %s", e)
        record_agent_error("agent3")
        return -1.0

def agent4_check_blacklist(url: str) -> tuple:
    import tldextract
    models = get_models()
    blacklist = models.get("agent4_blacklist", set())
    try:
        ext = tldextract.extract(url)
        domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        if domain in blacklist:
            return True, domain
    except Exception:
        pass
    return False, None

def agent5_predict_qr_payload(payload: str) -> float:
    if not is_agent_healthy("agent5"):
        return -1.0
    models = get_models()
    clf = models.get("agent5_classifier")
    sc = models.get("agent5_scaler")
    cols = models.get("agent5_feature_cols")
    if clf is None or cols is None:
        return -1.0
    try:
        if sc is None:
            # New 60-feature model
            from app.ml.agents.agent_5_qr_xgb.agent_05_feature_extractor import extract_features
            feats = extract_features(payload)
            row = np.array([[feats.get(c, 0.0) for c in cols]], dtype=np.float32)
            proba = clf.predict_proba(row)[0]
        else:
            # Old fallback 13-feature model
            feats = {c: 0 for c in cols}
            feats["PayloadLen"] = len(payload)
            feats["IsURL"] = 1 if payload.startswith(("http://", "https://")) else 0
            feats["IsUPI"] = 1 if "@" in payload and ("pay" in payload.lower() or "upi" in payload.lower()) else 0
            feats["IsHTTPS"] = 1 if payload.startswith("https://") else 0
            feats["NumDigits"] = sum(c.isdigit() for c in payload)
            feats["NumDots"] = payload.count(".")
            feats["NumSlash"] = payload.count("/")
            feats["NumDash"] = payload.count("-")
            feats["NumAt"] = payload.count("@")
            feats["NumEquals"] = payload.count("=")
            feats["NumQMark"] = payload.count("?")
            feats["NumAmpersand"] = payload.count("&")
            keywords = ["otp", "kyc", "verify", "urgent", "refund", "free", "prize", "win", "cashback", "reward"]
            feats["HasSuspiciousKeyword"] = 1 if any(k in payload.lower() for k in keywords) else 0
            row = np.array([[feats.get(c, 0) for c in cols]])
            row_scaled = sc.transform(row)
            proba = clf.predict_proba(row_scaled)[0]
            
        scam_idx = 1 if proba.shape[0] > 1 else 0
        record_agent_success("agent5")
        return float(proba[scam_idx])
    except Exception as e:
        logger.debug("Agent 5 predict error: %s", e)
        record_agent_error("agent5")
        return -1.0

def agent6_scan_upi(txn: dict) -> dict:
    models = get_models()
    engine = models.get("agent6_upi_engine")
    if engine is None:
        return {"score": 0, "severity": "SAFE", "triggered_rules": [], "explanation": "UPI engine not loaded"}
    try:
        return engine.scan(txn)
    except Exception as e:
        logger.debug("Agent 6 error: %s", e)
        return {"score": 0, "severity": "SAFE", "triggered_rules": [], "explanation": str(e)}

def agent7_predict_upi(txn: dict) -> float:
    models = get_models()
    clf = models.get("agent7_classifier")
    sc = models.get("agent7_scaler")
    cols = models.get("agent7_feature_cols")
    if clf is None or sc is None or cols is None:
        return -1.0
    try:
        # Derive engineered features from raw input
        vpa = str(txn.get("vpa", ""))
        amount = float(txn.get("amount", 0))

        engineered = {
            "amount":       amount,
            "has_note":     int(bool(txn.get("has_note", False))),
            "note_len":     int(txn.get("note_len", 0)),
            "vpa_len":      len(vpa),
            "round_amount": int(amount % 100 == 0),
            "odd_hour":     int(bool(txn.get("odd_hour", False))),
            "suspicious_note": int(any(kw in vpa.lower() for kw in [
                "prize", "winner", "lottery", "reward", "free",
                "lucky", "gift", "offer", "win", "cash"
            ])),
            # TODO: add agent07_vpa_whitelist.json check here
            # to cap fraud_score at 0.2 for whitelisted VPA domains
            "tx_velocity_24h": float(txn.get("tx_velocity_24h", 0)),
            "new_payee":    int(bool(txn.get("new_payee", False))),
            "high_amount":  int(amount > 10000),
            "low_amount":   int(amount < 100),
        }

        # Build row in exact column order from feature_cols pkl
        row = np.array([[engineered.get(c, 0) for c in cols]])
        row_scaled = sc.transform(row)
        proba = clf.predict_proba(row_scaled)[0]
        # Robustly find the fraud class index (class 1 = FRAUD_confirmed)
        classes = list(clf.classes_)
        scam_idx = classes.index(1) if 1 in classes else (1 if len(classes) > 1 else 0)
        raw_prob = float(proba[scam_idx])
        # Confidence gate: suppress predictions near 0.5 (model is uncertain)
        if abs(raw_prob - 0.5) < 0.12:
            return 0.0
        return raw_prob
    except Exception as e:
        logger.debug("Agent 7 predict error: %s", e)
        return -1.0

def lev_distance(a: str, b: str) -> int:
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (0 if a[i - 1] == b[j - 1] else 1))
            prev = temp
    return dp[n]

def normalize_homoglyphs(s: str) -> str:
    table = str.maketrans({"0": "o", "1": "l", "5": "s", "3": "e", "4": "a", "8": "b", "@": "a", "$": "s", "|": "i"})
    s = s.translate(table).replace("rn", "m").replace("vv", "w")
    return s

def _normalize_brand(s: str) -> str:
    DIGIT_SUBS = str.maketrans("01345", "oieas")
    return normalize_homoglyphs(s.lower().translate(DIGIT_SUBS))

def agent8_check_brand(domain: str) -> tuple:
    if not is_agent_healthy("agent8"):
        return False, None, None
    models = get_models()
    whitelist = models.get("agent8_whitelist")
    config = models.get("agent8_config")
    if whitelist is not None and config is not None:
        try:
            norm = _normalize_brand(domain)
            threshold = config.get("suspicious_threshold", config.get("threshold", 2)) if isinstance(config, dict) else 2
            brands = whitelist if isinstance(whitelist, dict) else {}
            official = brands.get("domains", brands) if isinstance(brands, dict) else whitelist
            for brand in official:
                d = lev_distance(norm, _normalize_brand(brand))
                if d <= threshold:
                    record_agent_success("agent8")
                    return True, brand, d
        except Exception as e:
            logger.debug("Agent 8 error: %s", e)
            record_agent_error("agent8")
    brand_patterns = [
        (r"\bhdfc\b", "HDFC Bank"),
        (r"\bsbi\b", "SBI"),
        (r"\bicici\b", "ICICI Bank"),
        (r"\baxis(?:\s*|-)*bank\b", "Axis Bank"),
        (r"\bkotak\b", "Kotak Mahindra"),
        (r"\bpaytm\b", "Paytm"),
        (r"\bgoogle(?:\s*|-)*(?:pay|login|account|verify)\b", "Google"),
        (r"\bgpay\b", "Google Pay"),
        (r"\bphonepe\b", "PhonePe"),
        (r"\bamazon(?:\s*|-)*(?:pay|login|in|com|prime|account|order)\b", "Amazon"),
        (r"\bflipkart\b", "Flipkart"),
        (r"\bwhatsapp\b", "WhatsApp"),
        (r"\btelegram\b", "Telegram"),
        (r"\bnetflix\b", "Netflix"),
        (r"\bpaypal\b", "PayPal"),
        (r"\bvisa\b", "Visa"),
        (r"\bmastercard\b", "Mastercard"),
        (r"\bup(?:i|i\s*)payment\b", "UPI Payment"),
        (r"\baadhaar\b", "Aadhaar"),
        (r"\bkyc\b", "KYC"),
        (r"\buidai\b", "UIDAI"),
    ]
    try:
        lower = domain.lower()
        for pattern, brand_name in brand_patterns:
            if re.search(pattern, lower):
                record_agent_success("agent8")
                return True, brand_name, 0
    except Exception:
        record_agent_error("agent8")
    record_agent_success("agent8")
    return False, None, None

def agent9_check_brand(domain: str) -> tuple:
    return False, None, None

def agent10_predict_deepfake(image_bytes: bytes = None) -> float:
    return -1.0

def agent11_predict_malware(file_bytes: bytes) -> float:
    if not is_agent_healthy("agent11"):
        return -1.0
    models = get_models()
    clf = models.get("agent11_classifier")
    sc = models.get("agent11_scaler")
    indices = models.get("agent11_feature_indices")
    if clf is None:
        return -1.0
    try:
        n = len(indices) if indices else 2381
        feats = np.zeros(n)
        for i, b in enumerate(file_bytes[:n]):
            if i < n:
                feats[i] = b / 255.0
        feats = feats.reshape(1, -1)
        if sc is not None:
            feats = sc.transform(feats)
        proba = clf.predict_proba(feats)[0]
        scam_idx = 1 if proba.shape[0] > 1 else 0
        record_agent_success("agent11")
        return float(proba[scam_idx])
    except Exception as e:
        logger.debug("Agent 11 predict error: %s", e)
        record_agent_error("agent11")
        return -1.0

def agent12_transcribe(audio_bytes: bytes) -> dict:
    return {"transcript": "", "confidence": 0.0, "language": ""}

def agent13_predict_transcript(transcript: str) -> float:
    """
    Returns a 0.0–1.0 scam score for the ensemble.
    SCAM=1.0, SUSPICIOUS=0.5, SAFE=0.0
    Ensemble weight: 0.15 (applied by the caller/ensemble scorer).
    Falls back to -1.0 (agent skip) if model is not loaded.
    """
    if not _AGENT13_AVAILABLE or _agent13_predict is None:
        # Graceful skip — ensemble ignores -1.0 scores
        return -1.0
    try:
        result = _agent13_predict(transcript)
        if not result.get("model_loaded", False):
            return -1.0
        label = result.get("label", "SAFE").upper()
        confidence = float(result.get("confidence", 0.0))
        if label == "SCAM":
            return confidence
        elif label == "SUSPICIOUS":
            return confidence * 0.5
        else:
            return 0.0
    except Exception as e:
        logger.debug("Agent 13 predict error: %s", e)
        return -1.0


def agent13_predict_transcript_full(transcript: str) -> dict:
    """
    Returns the full dict from the Agent 13 DistilBERT classifier.
    Keys: label, confidence, agent, model, model_loaded
    """
    if not _AGENT13_AVAILABLE or _agent13_predict is None:
        return {"label": "SAFE", "confidence": 0.0, "agent": "agent13",
                "model": "not_loaded", "model_loaded": False}
    try:
        return _agent13_predict(transcript)
    except Exception as e:
        logger.debug("Agent 13 full predict error: %s", e)
        return {"label": "SAFE", "confidence": 0.0, "agent": "agent13",
                "model": "error", "model_loaded": False, "error": str(e)}

_BUILTIN_RULES = [
    # Digital arrest / legal threat scams (all lowercase — searched against text.lower())
    {"name": "DIGITAL_ARREST",   "pattern": r"\b(cyber\s?cell|cyber\s?crime|digital\s?arrest)\b", "severity": "HIGH"},
    {"name": "DIGITAL_ARREST",   "pattern": r"\b(aadha?ar.{0,30}(freeze|block|suspend|illegal|fraud|crime|misuse|link))\b", "severity": "HIGH"},
    {"name": "DIGITAL_ARREST",   "pattern": r"\b(pan.{0,30}(freeze|block|suspend|illegal|fraud|crime|misuse|money.?launder))\b", "severity": "HIGH"},
    {"name": "DIGITAL_ARREST",   "pattern": r"\b(warrant.{0,20}(arrest|jail|custody|issue))\b", "severity": "HIGH"},
    {"name": "DIGITAL_ARREST",   "pattern": r"\b(arrest.{0,20}(pay|fine|avoid|warrant|jail|custody))\b", "severity": "HIGH"},
    {"name": "DIGITAL_ARREST",   "pattern": r"\b(legal.?action.{0,20}(immediate|within|24|urgent)).{0,30}(pay|fine|fee|penalty|arrest)\b", "severity": "HIGH"},
    {"name": "DIGITAL_ARREST",   "pattern": r"\b(notice.{0,15}(appear|court|police|arrest)).{0,30}(pay|fine|fee|call|contact)\b", "severity": "HIGH"},

    # UPI double-money / lottery / prize scams (all lowercase)
    {"name": "UPI_DOUBLE_MONEY", "pattern": r"\b(congratulations|you.?(ve|have)\s?(won|been.?selected)|lucky.?winner|prize.?winner).{0,30}(lakh|crore|rupees?|rs|prize|lottery|draw|jackpot)\b", "severity": "HIGH"},
    {"name": "UPI_DOUBLE_MONEY", "pattern": r"\b(double|triple).{0,20}(your.?)?money\b", "severity": "HIGH"},
    {"name": "UPI_DOUBLE_MONEY", "pattern": r"\b(send|pay|transfer|deposit).{0,20}(registration|processing|handling|service).{0,20}(fee|charge|amount)\b", "severity": "HIGH"},
    {"name": "UPI_DOUBLE_MONEY", "pattern": r"\b(cashback|refund|bonus|reward).{0,30}(claim|send|pay|deposit|credit|transfer)\b", "severity": "HIGH"},
    {"name": "UPI_DOUBLE_MONEY", "pattern": r"\b(lucky.?draw|cash.?prize|winning).{0,30}(registration|processing|fee|deposit|pay)\b", "severity": "HIGH"},

    # Fake job scams (all lowercase)
    {"name": "FAKE_JOB",         "pattern": r"\b(work.?from.?home|wfh|online.?job|home.?based|data.?entry).{0,60}(fee|deposit|registration|charge|pay|invest)\b", "severity": "HIGH"},
    {"name": "FAKE_JOB",         "pattern": r"\b(part.?time|freelance|remote.?job).{0,60}(fee|deposit|registration|charge|pay|invest)\b", "severity": "HIGH"},
    {"name": "FAKE_JOB",         "pattern": r"\b(registration.{0,10}(fee|charge|amount)|joining.{0,10}(fee|deposit)|register.{0,10}(fee|charge|amount)).{0,30}(job|work|position|earning|income|salary)\b", "severity": "HIGH"},
    {"name": "FAKE_JOB",         "pattern": r"\b(earn|make|daily|monthly|weekly).{0,30}(salary|income|money|cash|payout|earning).{0,60}(fee|deposit|registration|charge|register)\b", "severity": "HIGH"},
    {"name": "FAKE_JOB",         "pattern": r"\b(registration|joining|register).{0,20}(fee|charge|deposit|amount).{0,30}(job|work|position|earn|income)\b", "severity": "HIGH"},
    {"name": "FAKE_JOB",         "pattern": r"\b(work from home|part.?time job|earn per hour|liking videos|youtube task|registration fee)\b", "severity": "HIGH"},

    # OTP safety warning (benign — reduces suspicion)
    {"name": "otp_safety_warning", "pattern": r"\b(otp|one.?time.?pin).{0,50}(do not share|never share|don.?t share|is your|valid for)\b", "severity": "NONE"},

    # OTP solicitation (scam — increases suspicion)
    {"name": "otp_solicitation",  "pattern": r"\b(share.{0,10}otp|send.{0,10}otp|enter.{0,10}otp|otp.{0,10}will be sent|request.{0,10}otp)\b", "severity": "HIGH"},

    # Parcel / customs scams
    {"name": "PARCEL_SCAM",      "pattern": r"\b(parcel.*held|customs.*fee|release.*package|delivery.*pending.*pay|clearance fee)\b", "severity": "HIGH"},

    # Crypto / investment scams
    {"name": "CRYPTO_SCAM",      "pattern": r"\b(guaranteed.*return|300%|500%|crypto.*invest|send.*bitcoin|send.*btc)\b", "severity": "HIGH"},

    # Emergency transfer scams
    {"name": "EMERGENCY_SCAM",   "pattern": r"\b(stuck at airport|hospital.*send money|lost.*wallet.*transfer|nephew.*urgently)\b", "severity": "HIGH"},

    # Utility threat scams
    {"name": "UTILITY_SCAM",     "pattern": r"\b(electricity.*disconnect|gas.*cut|connection.*cut.*tonight|bill.*pending.*call)\b", "severity": "HIGH"},

    # Social engineering without scam keywords (F-05-1)
    {"name": "SOCIAL_ENGINEERING", "pattern": r"\b(unusual login|suspicious activity|confirm identity|verify your account|security alert|account accessed|new device login|unrecognized device)\b", "severity": "HIGH"},

    # Synonym substitution: account freeze/block without OTP (F-05-3)
    {"name": "SYNONYM_SUBSTITUTION", "pattern": r"\b(unauthorized.{0,20}(withdrawal|transaction|access|attempt)|account.{0,10}(freeze|restricted|limited|hold|suspended)|confirm.{0,15}(details|identity|information))\b", "severity": "HIGH"},

    # Fake payment proof (F-05-4): "I sent money, check screenshot, ship now"
    {"name": "FAKE_PAYMENT",     "pattern": r"\b(sent.{0,20}(rupees?|rs|amount|money|payment|phonepe|gpay|paytm)).{0,30}(screenshot|screenshot|ss|proof).{0,40}(ship|dispatch|send|deliver|do not wait|bank delay|bank takes time)\b", "severity": "HIGH"},

    # Character-spaced text reassembly (F-05-2): normalized by spacing
    {"name": "SPACED_EVASION",   "pattern": r"\b(s.h.a.r.e|s.e.n.d|o.t.p|k.y.c|a.c.c.o.u.n.t|f.r.e.e.z.e|b.l.o.c.k|s.c.a.m|f.r.a.u.d|p.a.y)\b", "severity": "HIGH"},
]

def _looks_like_gibberish(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) < 8:
        return False
    alpha = sum(c.isalpha() for c in stripped)
    if alpha == 0:
        return True
    ratio = sum(1 for c in stripped if c.isalpha() or c.isspace()) / len(stripped)
    if ratio < 0.4:
        return True
    vowel_ratio = sum(1 for c in stripped.lower() if c in "aeiou") / max(alpha, 1)
    if vowel_ratio < 0.05 and alpha > 5:
        return True
    return False


def agent14_score_text(text: str) -> dict:
    models = get_models()
    rules = models.get("agent14_regex_rules")

    if _looks_like_gibberish(text):
        logger.debug("Gibberish guard triggered for text: %.40s", text)
        return {"score": 0, "severity": "SAFE", "triggered": [], "regex_safe": False}
    if rules is None:
        rules = models.get("scamshield_rules")
    artifact_rules = []
    if rules is not None:
        try:
            for r in rules if isinstance(rules, list) else rules.get("rules", []):
                pattern = r.get("pattern", r) if isinstance(r, str) else r.get("pattern", "")
                name = r.get("name", "") if isinstance(r, dict) else ""
                severity = r.get("severity", "MEDIUM") if isinstance(r, dict) else "MEDIUM"
                if pattern:
                    artifact_rules.append({"name": name or pattern, "pattern": pattern, "severity": severity})
        except Exception:
            pass

    all_rules = artifact_rules + _BUILTIN_RULES

    try:
        low = text.lower()
        seen = set()
        triggered = []
        for r in all_rules:
            if isinstance(r, dict):
                pattern = r.get("pattern", "")
                name = r.get("name", "")
                severity = r.get("severity", "MEDIUM")
            else:
                continue
            if not pattern:
                continue
            if pattern in seen:
                continue
            seen.add(pattern)
            if re.search(pattern, low):
                triggered.append({"name": name, "severity": severity})
        cat_count = len(set(t["name"] for t in triggered if t["severity"] != "NONE"))
        score = min(100, cat_count * 20)
        has_high = any(t["severity"] == "HIGH" for t in triggered)
        severity = "HIGH" if has_high else ("MEDIUM" if triggered else "SAFE")
        triggered_names = list(dict.fromkeys(t["name"] for t in triggered))
        regex_safe = all(t["severity"] == "NONE" for t in triggered) if triggered else False
        return {"score": score, "severity": severity, "triggered": triggered_names, "regex_safe": regex_safe}
    except Exception as e:
        logger.debug("Agent 14 error: %s", e)
        return {"score": 0, "severity": "SAFE", "triggered": [], "regex_safe": False}


# ─── Defensive-phrase patterns that indicate a legitimate banking message ────
_DEFENSIVE_PHRASES = re.compile(
    r"do\s+not\s+share|never\s+share|don['\u2019]t\s+share"
    r"|no\s+one\s+from\s+(the\s+)?bank|bank\s+will\s+never\s+ask"
    r"|official\s+bank\s+support|call\s+official|beware\s+of\s+fraud",
    re.IGNORECASE,
)


def ensemble_predict_text(msg: str) -> dict:
    """
    Pure-function mirror of the /api/v1/analyze-text code path.

    Runs Agent 14 (regex) + Agent 1 (TF-IDF) + Agent 2 (DistilBERT,
    extended uncertainty gate 0.35-0.85) + Agent 15 (ensemble scorer),
    then applies a post-ensemble defensive-phrase soft-downgrade.

    Returns:
        {
          "final_label": "SCAM" | "SUSPICIOUS" | "SAFE",
          "final_score": float,   # 0.0-1.0  (scam_score / 100)
          "raw_score":   int,     # 0-100 scam_score from Agent 15
          "per_agent": {
              "agent1":  float | None,
              "agent2":  float | None,
              "agent14": {"score": int, "severity": str, "triggered": list},
              "agent15": int,
          },
          "defensive_phrase_gate": bool,
        }
    """
    from app.preprocessing.text_normalizer import normalize
    from agents.agent15_ensemble import compute as _a15_compute

    text = normalize(msg)

    # ── Agent 14: regex rule engine ──────────────────────────────────────────
    regex_result    = agent14_score_text(text)
    regex_score     = regex_result["score"]
    regex_severity  = regex_result["severity"]
    regex_triggered = regex_result["triggered"]
    regex_high      = regex_severity == "HIGH"
    regex_safe      = regex_result.get("regex_safe", False)

    # ── Agent 1: TF-IDF + LogReg (uses agent1_predict_text which handles
    #    the FeatureUnion dict and scipy.sparse.hstack correctly) ────────────
    raw_a1 = agent1_predict_text(text)   # returns float in [0,1] or -1.0
    agent1_prob = raw_a1 if raw_a1 >= 0 else None

    # ── Agent 2: DistilBERT (extended gate 0.35-0.85) ────────────────────────
    # The gate is wider than the router's 0.35-0.65 so that high-scoring but
    # potentially wrong Agent 1 predictions (e.g. OTP / debit alerts that share
    # banking vocabulary with scams) are still checked semantically.
    agent2_prob   = None
    agent2_label  = None        # full SCAM/SUSPICIOUS/SAFE label from gate
    agent2_invoked = False
    if agent1_prob is not None and 0.35 <= agent1_prob <= 0.85:
        if _AGENT2_AVAILABLE and _agent2_predict is not None:
            try:
                # Capture full dict so we can use the gated label for decisions
                a2_full = agent2_predict_text_full(text)
                if a2_full.get("model_loaded", False):
                    agent2_label  = a2_full.get("label", "SAFE").upper()
                    # Convert label to float using the clamped mapping
                    a2_raw = agent2_predict_text(text)
                    if a2_raw >= 0:
                        agent2_prob    = a2_raw
                        agent2_invoked = True
            except Exception as _e:
                logger.warning("ensemble_predict_text: Agent 2 error: %s", _e)

    # ── Fuse into a single text_prob ─────────────────────────────────────────
    # When Agent 2 runs: weighted blend that reduces Agent 1 dominance.
    # Weights: Agent1=0.55, Agent2=0.45.
    if agent2_invoked and agent2_prob is not None and agent1_prob is not None:
        blended_text_prob = agent1_prob * 0.55 + agent2_prob * 0.45
    else:
        blended_text_prob = agent1_prob if agent1_prob is not None else -1.0

    signals = {
        "text_prob":       blended_text_prob,
        "blacklist_hit":   False,
        "brand_flag":      False,
        "upi_rule_score":  0,
        "upi_xgb_prob":    -1,
        "deepfake_prob":   -1,
        "malware_prob":    -1,
        "call_fraud_prob": -1,
        "regex_score":     regex_score,
        "regex_high":      regex_high,
        "regex_triggered": regex_triggered,
        "regex_safe":      regex_safe,
        "url_risk_boost":  0,
    }
    result     = _a15_compute(signals, scan_type="text")
    raw_score  = result["scam_score"]
    verdict_15 = result["verdict"]

    # ── Post-ensemble: defensive-phrase soft-downgrade ───────────────────────
    # Messages containing explicit safety disclaimers ("do not share", etc.)
    # are capped at SUSPICIOUS when Agent 2 confirms they are not SCAM.
    # Uses the gated label (not the float) so it is immune to float-mapping changes.
    defensive_gate_applied = False
    if _DEFENSIVE_PHRASES.search(text):
        # Agent 2 verdict: treat SAFE or SUSPICIOUS as "not a scam"
        a2_not_scam = True   # default: trust the defensive phrase when Agent 2 unavailable
        if agent2_invoked and agent2_label is not None:
            a2_not_scam = agent2_label != "SCAM"
        if a2_not_scam and raw_score > 60:
            raw_score  = 58
            verdict_15 = "suspicious"
            defensive_gate_applied = True

    _LABEL_MAP = {"low_risk": "SAFE", "suspicious": "SUSPICIOUS", "high_risk": "SCAM"}
    final_label = _LABEL_MAP.get(verdict_15, "SUSPICIOUS")
    final_score = round(raw_score / 100.0, 4)

    return {
        "final_label": final_label,
        "final_score": final_score,
        "raw_score":   raw_score,
        "per_agent": {
            "agent1":  round(agent1_prob, 4) if agent1_prob is not None else None,
            "agent2":  round(agent2_prob, 4) if agent2_prob is not None else None,
            "agent14": {"score": regex_score, "severity": regex_severity,
                        "triggered": regex_triggered},
            "agent15": raw_score,
        },
        "defensive_phrase_gate": defensive_gate_applied,
    }
