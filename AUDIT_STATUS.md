# ScamShield — Audit Resolution Status

**Date:** 2026-07-07  
**iOS Branch:** IOS  
**Scope:** Cross-referencing COMPLETE_RED_TEAM_AUDIT.md, AGENT_AUDIT_UPDATED.md, weakness-report-IOS.md, backend-weakness-report-v2.1.0.md

---

## iOS Changes — What Was Fixed

### Round 1 (Prior session — user's changes)

| Issue | Fix | Files |
|-------|-----|-------|
| CF1 — Agent 1 offline false negatives | `ClientScamSignals` 7-dimension on-device detector + `effectiveVerdict` escalation | `AnalysisResult.swift` |
| CF3 — Thresholds too tight | `isBorderlineScore` + `BorderlineScoreWarning` + verdict escalation | `AnalysisResult.swift`, `Components.swift`, `ResultViews.swift` |
| T4 — Obfuscated scam missed | Client-side urgency/financial/threat/homoglyph detection | `AnalysisResult.swift` |
| T5 — Hindi scam missed | `hindiScamPatterns` dimension in `ClientScamSignals` | `AnalysisResult.swift` |
| M4 — QR endpoint missing `flagged_urls` | `NSDataDetector` URL scraping fallback in `toDomain()` | `DTOs.swift` |
| CF1 UI — no signal when Agent 1 null | `AgentSignalsDTO` + console warning when `text_tfidf_prob == nil` | `DTOs.swift` |
| CF1 VM — no preflight check | `preflightScamCheck()` logs before API call | `SubmitAnalysisUseCase.swift` |
| Hindi OCR — Vision English-only | `recognitionLanguages = ["en-IN", "hi-IN", "en-US"]` | `SubmitAnalysisUseCase.swift` |

### Round 2 (This session)

| Issue | Fix | Files |
|-------|-----|-------|
| CF1 UI — degraded backend invisible to user | `AgentDegradedWarning` card shown in result when `backendDegraded = true` | `Components.swift`, `ResultViews.swift`, `AnalysisResult.swift`, `DTOs.swift` |
| CF3 degraded — lower escalation threshold | `backendDegraded && triggeredCount >= 2` → escalate to suspicious | `AnalysisResult.swift` |
| F-09 — empty/short text scores 34 | Text length gate in `analyzeText()` — rejects < 10 chars client-side | `ViewModels.swift` |
| M-02 — empty QR not rejected | Empty payload gate in `analyzeQR()` | `ViewModels.swift` |
| URL shortener blind spot | `urlShortener` 8th dimension in `ClientScamSignals` | `AnalysisResult.swift` |
| Test compile failure | Default values for `backendScanId` and `backendDegraded` in struct | `AnalysisResult.swift` |

---

## What iOS CANNOT Fix — Backend Required

### 🔴 P0 — Deploy Blockers

#### Agent 1 (TF-IDF) Completely Offline
**Evidence:** `text_tfidf_prob: null` on 100% of text scans (14/14 tested)  
**Root causes to check in order:**
1. `scamshield_model.pkl` / `scamshield_vectorizer.pkl` missing or corrupted in Railway deployment
2. scikit-learn version mismatch (training vs production)
3. Silent exception swallowed in `agent_1_text_tfidf/inference.py`

**Minimum fix:**
```python
# Add explicit logging in inference.py
import logging
logger = logging.getLogger(__name__)

def predict_text_tfidf(text: str):
    try:
        vectorized = vectorizer.transform([text])
        prob = model.predict_proba(vectorized)[0][1]
        logger.info(f"Agent1 TF-IDF: {prob:.3f}")
        return float(prob)
    except Exception as e:
        logger.error(f"Agent1 FAILED: {e}", exc_info=True)
        return None  # Don't fail silently
```

#### Verdict Thresholds Too Tight (CF3 / C-01 / C-02)
- `text_prob` weight is `0.50` → max score from text = 50/100, can never reach `high_risk` threshold of 70
- `regex_high` override floors score at exactly 60 (clamps instead of stacking)
- Extreme scam (police + digital arrest + OTP + financial threat) scores **34** → `low_risk`

**Fix:**
```json
// ensemble_weights.json
"text": { "text_prob": 0.75 }  // was 0.50

// ensemble_overrides.json
{ "condition": "regex_high", "boost": 15 }  // was min_score: 60 (floor)
```

#### `/api/v1/config` Leaks Detection Thresholds
Scammers can query this unauthenticated endpoint to A/B test scam templates:
```python
# Remove from public response:
# - score_thresholds
# - agents (total/ready breakdown)
# - model_version
```

---

### 🟠 P1 — High Priority

#### Agent 14 Regex Engine — F1=0.33, 60-70% Miss Rate (CF2)
Only active text agent. Additive uncapped scoring, English-only patterns.

**Fix:** Replace additive scoring with co-occurrence requirement (≥3 dimensions):
```python
URGENCY = ["urgent", "immediately", "act now", "turant", "jaldi", "तुरंत"]
THREATS = ["suspended", "blocked", "arrest", "warrant", "band", "गिरफ्तार"]
FINANCIAL = ["account", "payment", "otp", "aadhaar", "bank"]
IMPERSONATION = ["police", "cbi", "cyber cell", "rbi", "income tax"]

# Score only when ≥3 dimensions co-occur
if dimensions_active >= 3:
    base_score = 55  # Not just keyword accumulation
```

#### Agent 6 UPI Heuristic — Misses Free-Text UPI (H-02 / F-10)
Only handles structured JSON. `"Send ₹10k to scammer@paytm for refund fee"` → score 0.

**Fix:** Add `parse_upi_from_text()` using regex for `\b[\w\.-]+@[\w\.-]+\b` + amount pattern.

#### Agent 8 Brand Guard — Misses Homoglyph URLs (H-03 / H-02)
`amaz0n-secure.com` → score 0. Digit substitutions not normalized.

**Fix:**
```python
DIGIT_MAP = str.maketrans("01345", "oieas")
domain_normalized = domain.lower().translate(DIGIT_MAP)
# Then run Levenshtein on normalized form
```

#### OTP Messages Scored Suspicious (F-02 / H-04)
`"Your OTP is 449201. Do not share it. - HDFC Bank"` → score 60, `suspicious`.  
`OTP_REQUEST` regex has `severity=HIGH` triggering hard override to 60.

**Fix:**
```yaml
# In scamshield_rules.yaml
- id: otp_safety_warning     # Do not share + time limit = LEGITIMATE
  severity: NONE
  pattern: "(otp|one.?time).*(do not share|never share|valid for \d+ min)"

- id: otp_solicitation       # "Share your OTP" = SCAM
  severity: HIGH
  pattern: "(share (your )?(otp|pin)|otp.*(share karo|dalein))"
```

#### IP-Address URLs Score 0 (F-11 / H-03)
`http://185.220.101.45/bank-verify` → score 0.

**Fix in `routers/url.py`:**
```python
import re
IP_RE = re.compile(r'^https?://(\d{1,3}\.){3}\d{1,3}')
if IP_RE.match(url):
    return early_return(score=75, verdict="high_risk")
```

---

### 🟠 P1 — Missing Scam Categories (H-01)

These common scams return `low_risk`. Add to `scamshield_rules.yaml`:

```yaml
- id: job_scam_wfh
  severity: HIGH
  pattern: "(work from home|earn per hour|liking videos|youtube task|registration fee)"

- id: parcel_customs_scam
  severity: HIGH
  pattern: "(parcel.*held|customs.*fee|clearance fee|release.*package)"

- id: crypto_guaranteed
  severity: HIGH
  pattern: "(guaranteed.*return|300%|500%|crypto.*invest|send.*bitcoin|send.*btc)"

- id: emergency_transfer_scam
  severity: HIGH
  pattern: "(stuck at airport|hospital.*send money|lost.*wallet.*transfer)"

- id: utility_threat_scam
  severity: HIGH
  pattern: "(electricity.*disconnect|gas.*cut|connection.*cut.*tonight)"
```

---

### 🟡 P2 — Medium Priority

| Issue | File | Fix |
|-------|------|-----|
| Sandbox image 100% broken (OCR_FAILED) | Dockerfile | `RUN apt-get install -y tesseract-ocr tesseract-ocr-hin` |
| Two production backends (different schemas) | `.env` / Railway | Decommission `scamsheild-production-2f8f.up.railway.app`, use one URL |
| Spaced-character evasion ("U R G E N T" scores 2) | `utils/text.py` | Collapse space-separated single letters before vectorizing |
| Scam buried in long text (TF-IDF dilution) | Agent 1 | Sliding window max-pool over text chunks |
| Agent 2 DistilBERT silent stub | `inference.py` | Deploy CPU-quantized sentence-transformers (22MB model) |
| Agent 7 UPI XGBoost inverted labels | Training | Retrain with corrected labels; validate AUC ≥ 0.80 |
| Agent 3 URL XGBoost AUC=1.0 (data leakage) | Training | Temporal train/test split; add WHOIS age + homoglyph features |
| `hdfc.com` → high_risk (brand guard FP) | `inference.py` | Suppress brand match when `domain == matched_brand` exactly |
| `localhost` → high_risk (false positive) | `routers/url.py` | Whitelist RFC1918 + loopback addresses |
| `javascript:` QR not rejected at backend | `routers/qr.py` | Reject `javascript:`, `data:`, `vbscript:` schemes |
| URL shorteners not boosted at backend | `routers/url.py` | Add `+20` boost for known shortener domains |
| Quota keyed on `X-Device-Id` header (bypassable) | `routers/` | Key quota on JWT `sub` claim, not client header |
| Auth checked after body parsing (DoS vector) | Middleware | Add middleware to check `Authorization` before JSON parsing |

---

## Summary Scorecard

| Category | Before iOS Round 2 | After iOS Round 2 |
|----------|--------------------|-------------------|
| CF1 (Agent 1 offline) | ⚠️ Partial (console log only) | ✅ UI warning + lower escalation threshold |
| CF3 (thresholds) | ⚠️ Client-side escalation only | ✅ + degraded-aware escalation at ≥2 signals |
| F-09 (empty text) | ❌ Sends to API, scores 34 | ✅ Rejected client-side |
| M-02 (empty QR) | ❌ Sends to API | ✅ Rejected client-side |
| URL shortener detection | ❌ Not detected | ✅ 8th client-side dimension |
| Hindi OCR | ✅ (Vision hi-IN already set) | ✅ |

**iOS can mitigate but not fix:** Agent 1 offline (the underlying backend bug remains).  
**Requires backend:** All P0/P1/P2 items in the table above.

---

**End of Audit Status — 2026-07-07**
