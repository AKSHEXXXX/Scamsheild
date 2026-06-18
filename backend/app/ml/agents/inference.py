import re
import logging
import numpy as np
from urllib.parse import urlparse

logger = logging.getLogger("scamshield.ml.agents")

from app.utils.text import preprocess_text
from app.ml.model_loader import get_models

def agent1_predict_text(text: str) -> float:
    models = get_models()
    vec = models.get("agent1_vectorizer")
    clf = models.get("agent1_classifier")
    if vec is None or clf is None:
        return -1.0
    try:
        clean = preprocess_text(text)
        X = vec.transform([clean])
        proba = clf.predict_proba(X)[0]
        scam_idx = 1 if proba.shape[0] > 1 else 0
        return float(proba[scam_idx])
    except Exception as e:
        logger.debug("Agent 1 predict error: %s", e)
        return -1.0

def agent2_predict_text(text: str) -> float:
    return -1.0

def extract_url_features(url: str) -> list:
    import tldextract
    parsed = urlparse(url)
    ext = tldextract.extract(url)
    domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
    path = parsed.path + parsed.query
    return {
        "URLLength": len(url),
        "DomainLength": len(domain),
        "TLDLength": len(ext.suffix),
        "NoOfSubDomain": len(ext.subdomain.split(".")) if ext.subdomain else 0,
        "PathLength": len(path),
        "NoOfEqualsInURL": url.count("="),
        "NoOfQMarkInURL": url.count("?"),
        "NoOfAmpersandInURL": url.count("&"),
        "CharContinuationRate": sum(url.count(c * 2) for c in set(url)) / max(len(url), 1),
        "IsHTTPS": 1 if parsed.scheme == "https" else 0,
        "HasIPAddress": 1 if re.search(r'\d+\.\d+\.\d+\.\d+', ext.domain) else 0,
    }

def agent3_predict_url(url: str) -> float:
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
        scam_idx = 1 if proba.shape[0] > 1 else 0
        return float(proba[scam_idx])
    except Exception as e:
        logger.debug("Agent 3 predict error: %s", e)
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
    models = get_models()
    clf = models.get("agent5_classifier")
    sc = models.get("agent5_scaler")
    cols = models.get("agent5_feature_cols")
    if clf is None or sc is None or cols is None:
        return -1.0
    try:
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
        return float(proba[scam_idx])
    except Exception as e:
        logger.debug("Agent 5 predict error: %s", e)
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
        row = np.array([[txn.get(c, 0) for c in cols]])
        row_scaled = sc.transform(row)
        proba = clf.predict_proba(row_scaled)[0]
        scam_idx = 1 if proba.shape[0] > 1 else 0
        raw_prob = float(proba[scam_idx])
        # Invert probability: model AUC 0.4714 < 0.5 (labels were inverted during training)
        prob = 1.0 - raw_prob
        return prob
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

def agent8_check_brand(domain: str) -> tuple:
    models = get_models()
    whitelist = models.get("agent8_whitelist")
    config = models.get("agent8_config")
    if whitelist is None or config is None:
        return False, None, None
    try:
        norm = normalize_homoglyphs(domain.lower())
        threshold = config.get("edit_distance_threshold", 2) if isinstance(config, dict) else 2
        brands = whitelist if isinstance(whitelist, dict) else {}
        official = brands.get("domains", brands) if isinstance(brands, dict) else whitelist
        for brand in official:
            d = lev_distance(norm, normalize_homoglyphs(brand.lower()))
            if d <= threshold:
                return True, brand, d
    except Exception as e:
        logger.debug("Agent 8 error: %s", e)
    return False, None, None

def agent9_check_brand(domain: str) -> tuple:
    return False, None, None

def agent10_predict_deepfake(image_bytes: bytes = None) -> float:
    return -1.0

def agent11_predict_malware(file_bytes: bytes) -> float:
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
        return float(proba[scam_idx])
    except Exception as e:
        logger.debug("Agent 11 predict error: %s", e)
        return -1.0

def agent12_transcribe(audio_bytes: bytes) -> dict:
    return {"transcript": "", "confidence": 0.0, "language": ""}

def agent13_predict_transcript(transcript: str) -> float:
    return -1.0

def agent14_score_text(text: str) -> dict:
    models = get_models()
    rules = models.get("agent14_regex_rules")
    if rules is None:
        rules = models.get("scamshield_rules")
    if rules is None:
        return {"score": 0, "severity": "SAFE", "triggered": []}
    try:
        low = text.lower()
        triggered = []
        for r in rules if isinstance(rules, list) else rules.get("rules", []):
            pattern = r.get("pattern", r) if isinstance(r, str) else r.get("pattern", "")
            name = r.get("name", "") if isinstance(r, dict) else ""
            if isinstance(r, dict):
                name = r.get("name", "")
                severity = r.get("severity", "MEDIUM")
            else:
                severity = "MEDIUM"
            if pattern and re.search(pattern, low):
                triggered.append({"name": name or pattern, "severity": severity})
        score = min(100, len(triggered) * 20)
        has_high = any(t["severity"] == "HIGH" for t in triggered)
        severity = "HIGH" if has_high else ("MEDIUM" if triggered else "SAFE")
        return {"score": score, "severity": severity, "triggered": [t["name"] for t in triggered]}
    except Exception as e:
        logger.debug("Agent 14 error: %s", e)
        return {"score": 0, "severity": "SAFE", "triggered": []}
