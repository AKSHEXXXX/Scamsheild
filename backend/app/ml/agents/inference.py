import re
import logging
import numpy as np
from urllib.parse import urlparse

logger = logging.getLogger("scamshield.ml.agents")

from app.utils.text import preprocess_text
from app.ml.model_loader import get_models, is_agent_healthy, record_agent_error, record_agent_success

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
        scam_idx = 1 if proba.shape[0] > 1 else 0
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
        row = np.array([[txn.get(c, 0) for c in cols]])
        row_scaled = sc.transform(row)
        proba = clf.predict_proba(row_scaled)[0]
        scam_idx = 1 if proba.shape[0] > 1 else 0
        raw_prob = float(proba[scam_idx])
        # Labels were inverted during training (class 1 = legit, class 0 = fraud).
        # Invert so that high prob = fraud. Effective AUC after inversion: ~0.53.
        prob = 1.0 - raw_prob
        # Confidence gate: suppress predictions near 0.5 (model is uncertain)
        if abs(prob - 0.5) < 0.12:
            return 0.0
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

def _normalize_brand(s: str) -> str:
    DIGIT_SUBS = str.maketrans("01345", "oieas")
    return normalize_homoglyphs(s.lower().translate(DIGIT_SUBS))

def _extract_label(s: str) -> str:
    """Reduce a domain/URL/free-form string to its bare registrable label
    (e.g. 'hdfcbank.com' / 'https://hdfcbank.com/login' -> 'hdfcbank').
    Falls back to the raw lowercased, alnum-only string when it doesn't
    look like a real domain (tldextract finds no registrable label)."""
    raw = (s or "").strip().lower()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    raw = raw.split("/")[0].split("@")[-1]
    try:
        import tldextract
        ext = tldextract.extract(raw)
        if ext.domain:
            return ext.domain
    except Exception:
        pass
    return re.sub(r"[^a-z0-9]", "", raw)

# Brand token -> (official_domain, display_name), built once from the
# whitelist pickle. Comparing against the short brand TOKEN (e.g. "hdfcbank")
# instead of the full domain string (e.g. "hdfcbank.com") is what makes
# edit-distance/containment checks meaningful — comparing full domains
# (including TLD) made every real-world lookalike distance too large to
# ever match, which was the root cause of the v1 false negatives.
_BRAND_TOKENS_CACHE = None
_BRAND_TOKENS_SOURCE_ID = None

def _get_brand_tokens(whitelist: dict) -> dict:
    global _BRAND_TOKENS_CACHE, _BRAND_TOKENS_SOURCE_ID
    if _BRAND_TOKENS_CACHE is not None and _BRAND_TOKENS_SOURCE_ID == id(whitelist):
        return _BRAND_TOKENS_CACHE
    tokens = {}
    for official_domain, display_name in whitelist.items():
        label = _extract_label(official_domain)
        if label and label not in tokens:
            tokens[label] = (official_domain, display_name)
        short = display_name.lower().split()[0]
        short_norm = _normalize_brand(short)
        if short_norm and short_norm not in tokens:
            tokens[short_norm] = (official_domain, display_name)
    _BRAND_TOKENS_CACHE = tokens
    _BRAND_TOKENS_SOURCE_ID = id(whitelist)
    return tokens

# Re-tuned for the label-based comparison above (short brand tokens, not
# full domain+TLD strings). 2 tolerates a single homoglyph/typo swap
# (e.g. "sbl"->"sbi", "paytrn"->"paytm" folds to distance 2 via rn->m)
# without over-matching short, unrelated brand tokens.
BRAND_EDIT_DISTANCE_THRESHOLD = 2

def agent8_check_brand(domain: str) -> tuple:
    if not is_agent_healthy("agent8"):
        return False, None, None
    models = get_models()
    whitelist = models.get("agent8_whitelist")
    if whitelist is not None and isinstance(whitelist, dict):
        try:
            input_label = _extract_label(domain)
            norm_input = _normalize_brand(input_label)
            if input_label:
                tokens = _get_brand_tokens(whitelist)
                # A) Exact match to a known brand token -> brand identified, distance 0
                if input_label in tokens:
                    record_agent_success("agent8")
                    _, display_name = tokens[input_label]
                    return True, display_name, 0
                # B) fuzzy match / containment across all brand tokens
                for brand_token, (official_domain, display_name) in tokens.items():
                    norm_brand = _normalize_brand(brand_token)
                    d = lev_distance(norm_input, norm_brand)
                    # B1) fuzzy match: small edit distance from a known brand token
                    # (catches homoglyph/typo swaps like "sbl"/"paytrn").
                    if 0 < d <= BRAND_EDIT_DISTANCE_THRESHOLD:
                        record_agent_success("agent8")
                        return True, display_name, d
                    # B2) containment: brand token embedded with extra content
                    # (catches "hdfcbank-secure" via full token, or
                    #  "hdfc-secure-login" via short token).
                    if len(input_label) > len(brand_token) and brand_token in norm_input:
                        record_agent_success("agent8")
                        extra = len(input_label) - len(brand_token)
                        return True, display_name, min(extra, 2)
            record_agent_success("agent8")
        except Exception as e:
            logger.debug("Agent 8 error: %s", e)
            record_agent_error("agent8")
    brand_patterns = [
        # NOTE: hdfc/sbi/icici/axis/kotak/paytm are intentionally NOT listed
        # here anymore — they're now handled by the whitelist-token logic
        # above, which correctly distinguishes a short legitimate variant
        # ("hdfc.com") from a lookalike ("hdfcbank-secure"). A blunt \bhdfc\b
        # substring match would re-flag "hdfc.com" as impersonation (the
        # word boundary at the dot still matches), undoing that fix.
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
    low = transcript.lower()
    call_scam_signals = [
        r"(officer|inspector|cbi|ed|narcotics|police)",
        r"(your\s+son|your\s+daughter|your\s+relative|family\s+member).{0,30}(accident|arrest|hospital|trouble)",
        r"(otp|bank\s+detail|account\s+detail|debit\s+card|cvv|pin|password)",
        r"(send\s+money|transfer\s+money|pay\s+now|payment\s+now|deposit\s+money)",
        r"(immediately|right\s+now|asap|don.t\s+delay|hurry|urgent|time\s+is\s+running)",
        r"(legal\s+action|case\s+filed|warrant|arrest|summons|notice\s+from\s+court)",
        r"(your\s+aadhaar|your\s+pan|your\s+account|your\s+card).{0,20}(block|suspend|freeze|deactivat)",
        r"(prize|lottery|won|winner|gift|cashback|refund).{0,30}(fee|charge|tax|processing)",
    ]
    score = 0
    for pat in call_scam_signals:
        if re.search(pat, low):
            score = min(100, score + 25)
    if score > 0:
        return score / 100.0
    return -1.0

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
