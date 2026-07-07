# ScamShield — ML Agent Production Readiness Audit

**Date:** 2026-07-02  
**Audited by:** Claude Code (sourced from live `Thebinaryztechnologies/Scam-sheild` backend repo)  
**Scope:** All 15 prediction agents used in the scam detection pipeline

---

## Quick Summary

| # | Agent Name | Type | FP Risk | FN Risk | Verdict |
|---|-----------|------|---------|---------|---------|
| 1 | Text TF-IDF + Logistic Regression | ML Model | Low | Medium | ✅ READY (caveat) |
| 2 | DistilBERT Text Classifier | ML Stub | N/A | Critical | ❌ NOT READY |
| 3 | URL XGBoost Classifier | ML Model | Low | High | ⚠️ QUESTIONABLE |
| 4 | URL Blacklist Checker | Rule-based | None | Low | ✅ READY |
| 5 | QR Code XGBoost Classifier | ML Model | Low | Medium | ✅ READY (caveat) |
| 6 | UPI Heuristic Rule Engine | Rule-based | Low | Medium | ✅ READY |
| 7 | UPI Meta XGBoost | ML Model | N/A | N/A | ❌ NOT READY — DISABLED |
| 8 | Brand Guard v1 (Edit Distance + Regex) | Heuristic | High | Medium | ⚠️ QUESTIONABLE |
| 9 | Brand Guard v2 (Siamese BiLSTM) | ML Stub | N/A | N/A | ❌ NOT READY |
| 10 | Deepfake Detector (DeiT) | ML Stub | N/A | Critical | ❌ NOT READY |
| 11 | Malware File Analyzer (Random Forest) | ML Model | Low | High | ⚠️ QUESTIONABLE |
| 12 | Whisper ASR | ML Stub | N/A | N/A | ❌ NOT READY |
| 13 | Call Transcript Fraud Detector | Regex Stub | Low | Critical | ❌ NOT READY |
| 14 | Regex Rule Engine | Rule-based | **High** | Medium | ⚠️ NOT PRODUCTION READY |
| 15 | Ensemble Scorer | Meta-Agent | Inherited | Inherited | ⚠️ READY (bounded by inputs) |

**Totals:** 4 READY · 5 NOT READY · 4 QUESTIONABLE · 1 DISABLED · 1 meta-agent

---

## Agent 1 — Text Scam Classifier (TF-IDF + Logistic Regression)

**File:** `backend/app/ml/agents/agent_1_text_tfidf/inference.py`  
**Artifacts:** `scamshield_vectorizer.pkl`, `scamshield_model.pkl`

| Metric | Value |
|--------|-------|
| Training set | 33,680 samples |
| Test set | 8,421 samples |
| Accuracy | 96% |
| Precision | 0.96 |
| Recall | **0.84** |
| F1 | 0.89 |

**Verdict: ✅ READY WITH CAVEATS**

**Loophole — Weak recall (16% miss rate):**  
Misses 1 in 6 scam messages. TF-IDF is a bag-of-words model — it cannot understand context, paraphrasing, or semantic meaning. It fails on:
- Transliterated Hindi/Hinglish scam messages ("aapka account band ho jayega")
- Novel scam templates not in the training corpus
- Scam text where keywords are split with punctuation or spaces ("O.T.P", "s c a m")

**Root cause:** Architecture limitation, not a training data problem. LogReg + TF-IDF is fundamentally incapable of capturing meaning. The 16% miss rate is a hard floor for this approach. Needs a semantic model (DistilBERT, sentence transformers) to improve.

**Recommendation:** Acceptable for production as primary text signal. Pair with Agent 14 (regex) to catch simple keyword patterns, but fix Agent 14 first (see below).

---

## Agent 2 — DistilBERT Text Classifier

**File:** `backend/app/ml/agents/agent_2_distilbert/inference.py`  
**Artifacts:** None found in `artifacts/` folder

| Metric | Value |
|--------|-------|
| Model | DistilBERT-base-uncased |
| Status | GPU stub |
| Returns | `{"error": "DistilBERT requires GPU — not deployed yet"}` |

**Verdict: ❌ NOT READY**

**Root cause:** Three blockers:
1. No GPU in Railway deployment environment
2. No `.pt` model weights in the artifacts folder (model was never saved/exported)
3. No CPU fallback implemented — returns an error that silently contributes 0 to the ensemble

**What this means in production:** The text channel is missing its best model. Agent 1 (TF-IDF) compensates but with 16% miss rate.

**Fix:** Deploy CPU-quantized DistilBERT (ONNX export, `int8` quantization reduces model to ~65MB and runs at ~150ms/call on CPU). Alternatively, use a sentence-transformers model (`all-MiniLM-L6-v2`) which is smaller and already optimized for CPU.

---

## Agent 3 — URL Phishing Classifier (XGBoost)

**File:** `backend/app/ml/agents/agent_3_url_xgb/inference.py`  
**Artifacts:** `url_classifier.pkl`, `url_scaler.pkl`, `url_feature_cols.pkl`

| Metric | Value |
|--------|-------|
| Training set | 188,636 samples |
| Test set | 47,159 samples |
| Accuracy | **100%** ⚠️ |
| AUC | **1.0** ⚠️ |
| F1 | **1.0** ⚠️ |
| Features | 11 URL structure features |

**Verdict: ⚠️ QUESTIONABLE — Perfect scores indicate a problem**

**Loophole — AUC 1.0 on a phishing dataset is a red flag:**  
No real-world phishing detection task produces AUC 1.0 without data leakage or an unrealistically easy test set. The 11 engineered features are:
- `URLLength`, `DomainLength`, `TLDLength`, `NoOfSubDomain`, `PathLength`
- `NoOfEqualsInURL`, `NoOfQMarkInURL`, `NoOfAmpersandInURL`
- `CharContinuationRate`, `IsHTTPS`, `HasIPAddress`

These features describe **how a URL looks structurally** — they were sufficient to separate the training data perfectly, but they are all trivially gameable:
- `https://g00gle-secure.com/login` → IsHTTPS=1, short domain, no IP → scores SAFE
- A 2025 phishing URL that uses a clean HTTPS short domain (common since Let's Encrypt) passes all checks

**Root cause:** Training data likely came from old phishing URL datasets (pre-2020) where phishing URLs were long, used IPs, and lacked HTTPS. Modern phishing URLs look structurally identical to legitimate ones. No WHOIS domain age, no certificate transparency check, no URL text NLP — the 11 features are necessary but not sufficient.

**Recommendation:** Do NOT rely on this model alone for URL verdicts. Add features: domain registration age (WHOIS), SSL certificate age, redirect chain depth, presence of URL shorteners, and run adversarial test with modern HTTPS short-domain phishing URLs before shipping.

---

## Agent 4 — URL Blacklist Checker

**File:** `backend/agents/agent4_blacklist.py`  
**Artifacts:** `url_blacklist.pkl`

| Metric | Value |
|--------|-------|
| Blacklist size | 437,255 domains |
| Sources | OpenPhish, Phishing.Database |
| Last updated | 2026-06-18 |
| Lookup method | Set membership (O(1)) |

**Verdict: ✅ READY**

Works exactly as designed. Domain is extracted via `tldextract` and checked against a set of known phishing domains. When a match is found, the ensemble forces a minimum score of 80.

**Caveat:** Purely reactive — only catches domains already reported. Zero-day phishing URLs (newly registered domains) always pass through. Requires a cron job to refresh the blacklist regularly from OpenPhish and PhishTank feeds.

---

## Agent 5 — QR Code Payload Classifier (XGBoost)

**File:** `backend/app/ml/agents/agent_5_qr_xgb/inference.py`  
**Artifacts:** `qr_url_classifier.pkl`, `qr_url_scaler.pkl`, `qr_url_features.pkl`

| Metric | Value |
|--------|-------|
| Training set | 16,000 samples |
| Test set | 4,000 samples |
| Accuracy | 98.63% |
| AUC | 0.9863 |
| Features | 13 payload features |

**Verdict: ✅ READY WITH CAVEATS**

**Loophole 1 — Small dataset (20K total):**  
20,000 samples is thin for a QR payload classifier. QR codes are used for URLs, UPI payments, contact cards, WiFi credentials, and text. With only 20K samples the model has limited exposure to the diversity of real-world QR payloads.

**Loophole 2 — Hardcoded keyword list is brittle:**  
The `HasSuspiciousKeyword` feature checks for exactly 10 hardcoded words:
```
["otp", "kyc", "verify", "urgent", "refund", "free", "prize", "win", "cashback", "reward"]
```
Any scam QR code that doesn't use these exact English words gets a 0 on this feature. Scam QR codes with Hindi transliteration, regional language keywords, or novel phishing vocabulary are completely undetected.

**Root cause:** Weak dataset diversity + brittle hardcoded keyword list. Expand training set to 100K+, replace hardcoded keywords with a learned embedding feature.

---

## Agent 6 — UPI Heuristic Rule Engine

**File:** `backend/app/ml/upi_heuristic_engine.py`  
**Config:** `upi_heuristic_rules.yaml`

| Metric | Value |
|--------|-------|
| Rule count | 12 YAML rules |
| Rule types | Amount thresholds, VPA keywords, timing, recipient status |
| Scoring | base_weight + multi_rule_boost × (n_rules - 1), capped at 100 |

**Rules include:**
- New recipient + high amount (≥ ₹10,000)
- Suspicious VPA keywords: `bank`, `refund`, `reward`, `help`, `support`, `kyc`
- Odd-hours transactions (0–5 AM)
- Round-number high amounts (multiples of ₹10K+)
- Collect request with keywords: `receive money`, `approve`, `verify`, `cashback`

**Verdict: ✅ READY**

Well-designed for known UPI scam patterns. The YAML-driven rule system is easy to extend.

**Caveat:** Rule-based systems cannot detect novel scam patterns not yet in the YAML. Missing coverage:
- Split-payment scams (multiple small transfers to evade amount thresholds)
- Fake merchant VPAs that use legitimate-looking domain names
- Family impersonation via UPI note ("Mom, it's me, please send urgently")

---

## Agent 7 — UPI Meta XGBoost

**File:** `backend/app/ml/agents/agent_7_upi_meta_xgb/inference.py`  
**Artifacts:** `upi_xgb_classifier.pkl`, `upi_xgb_scaler.pkl`, `upi_xgb_feature_cols.pkl`

| Metric | Value |
|--------|-------|
| Training set | 200,000 samples |
| Test set | 50,000 samples |
| AUC | **0.4714** — worse than random |
| Features | 4 only: `amount`, `has_note`, `note_len`, `vpa_len` |
| Status | **EXPLICITLY DISABLED** (code sets `upi_xgb_prob: -1`, weight=0%) |

**Verdict: ❌ NOT READY — DISABLED IN CODE**

**Root cause 1 — Label inversion bug in training:**  
During training, class 1 was labeled `legit` instead of `scam`. The model learned the inverted relationship. The code applies a workaround (`1 - predicted_probability`) but the AUC remains 0.4714 — the inversion fix doesn't fully compensate because the model learned noise, not signal.

**Root cause 2 — Feature poverty:**  
Only 4 features were used on 250,000 rows. `amount`, `has_note`, `note_len`, and `vpa_len` are essentially uncorrelated with whether a UPI transaction is fraudulent. Legitimate high-value transactions and fraudulent ones have the same amount distribution. The model had almost no signal to learn from.

**What this means:** The model performs slightly worse than flipping a coin. Deploying it would actively harm prediction quality.

**Fix required:**  
- Correct label inversion in training pipeline (class 1 = scam)
- Add features: VPA domain age, merchant category code, device fingerprint match, transaction velocity (n transactions in last 24h), recipient account age, geo-distance between sender/receiver
- Retrain from scratch; do not fine-tune the corrupted model

---

## Agent 8 — Brand Guard v1 (Levenshtein Distance + Homoglyph + Regex)

**File:** `backend/app/ml/agents/inference.py` (`agent8_check_brand`)  
**Artifacts:** `brand_whitelist.pkl`, `brand_guard_config.pkl`

| Metric | Value |
|--------|-------|
| Brand regex coverage | 21 major brands |
| Edit distance threshold | ≤ 2 |
| Homoglyph substitutions | 10 character substitutions (0→o, 1→l, 5→s, 3→e, etc.) |

**Brands covered by regex:** HDFC, SBI, ICICI, Axis, Kotak, Yes Bank, Federal, IDBI, RBL, IOB, IndusInd, Google, PhonePe, GPay, Paytm, Amazon, Flipkart, BHIM, NPCI, Microsoft, Apple

**Verdict: ⚠️ QUESTIONABLE — False positive risk is high**

**Loophole 1 — Edit distance ≤ 2 is too loose:**  
With threshold 2, any domain within 2 character edits of a brand name triggers a brand flag. This catches `amaz0n.com` (1 edit ✅) but also catches:
- `axis.io` — distance 0 to "axis" → triggers Axis Bank flag for any legitimate tech company named "Axis"
- `paytm.in.xyz` — subdomain structure confused by domain normalization
- Short 4-5 character legitimate domains that happen to be close to a brand name

**Loophole 2 — Homoglyph substitution is one-directional and incomplete:**  
Only 10 ASCII lookalike substitutions are applied (e.g., `0→o`). Unicode homoglyph attacks using Cyrillic, Greek, or other scripts bypass this entirely:
- `аmazon.com` (Cyrillic `а` ≠ Latin `a`) → not normalized → passes homoglyph check
- `ɡoogle.com` (IPA `ɡ` ≠ Latin `g`) → not normalized

**Root cause:** No context awareness. Pure distance matching cannot distinguish a legitimate domain from an impersonation without knowing the entity behind the domain.

**Fix:** Tighten edit distance to ≤ 1 for brand names with ≤ 8 characters. Add Unicode NFKC normalization before homoglyph substitution to cover Cyrillic/Greek lookalikes. Consider adding WHOIS lookup to verify domain owner against brand whitelist.

---

## Agent 9 — Brand Guard v2 (Siamese BiLSTM)

**File:** `backend/app/ml/agents/agent_9_brand_bilstm/inference.py`  
**Artifacts:** None

| Metric | Value |
|--------|-------|
| Model | Siamese BiLSTM (character-level similarity) |
| Status | GPU stub |
| Returns | Error verdict |

**Verdict: ❌ NOT READY**

Same blockers as Agent 2: GPU dependency, no model weights in artifacts, no CPU fallback. Intended to replace Agent 8's heuristic distance matching with a learned similarity model, but never deployed.

---

## Agent 10 — Deepfake / Image Forensics Detector (DeiT)

**File:** `backend/app/ml/agents/inference.py` (`agent10_predict_deepfake`)  
**Artifacts:** None

| Metric | Value |
|--------|-------|
| Model | DeiT (Data-efficient Image Transformer) — intended |
| Status | Returns `-1.0` unconditionally |
| Ensemble weight (image channel) | 5% |

**Verdict: ❌ NOT READY**

**Root cause:** The function is a two-line stub. No model is loaded, no image is analyzed. The function returns `-1.0` silently — there is no error, no log, no warning. The ensemble interprets `-1.0` as "no signal" and zeros out the deepfake contribution.

**What this means:** The image and video channels in the system have no deepfake detection. A scammer can send a deepfake video of a government official demanding payment and the system will analyze it with 0% deepfake signal.

---

## Agent 11 — Malware File Analyzer (Random Forest)

**File:** `backend/app/ml/agents/agent_11_malware_rf/inference.py`  
**Artifacts:** `malware_rf.pkl`, `malware_scaler.pkl`, `malware_feature_indices.pkl`

| Metric | Value |
|--------|-------|
| Model | Random Forest |
| Feature extraction | First 2,381 bytes of file, normalized to [0,1] |
| Training data | Unknown |
| Accuracy | Unknown |

**Verdict: ⚠️ QUESTIONABLE**

**Loophole — Byte truncation is trivially evaded:**  
The model only analyzes the first 2,381 bytes of a file. Any attacker who knows this (and most malware authors would test against common scanners) can:
1. Prepend a legitimate file header (PDF magic bytes: `%PDF-`, PNG: `\x89PNG`, DOCX: `PK\x03\x04`) to a malicious payload
2. The first 2,381 bytes look completely clean → model scores SAFE
3. Actual payload executes after those bytes

**Missing analysis techniques** that are standard in malware detection:
- File entropy (compressed/encrypted malware has high entropy)
- PE/ELF header analysis (imports, sections, entry point anomalies)
- Embedded URL extraction (malware calling home)
- String-based IOC matching (mutex names, registry keys, C2 domains)
- File signature mismatch detection (file extension vs actual magic bytes)

**Root cause:** Byte array approach treats malware detection as an image classification problem (raw bytes as pixels). It works on training data but provides minimal real-world protection because it reads only the header region where legitimate-looking bytes are easy to place.

---

## Agent 12 — Whisper ASR (Audio Transcription)

**File:** Not implemented  
**Artifacts:** None

| Metric | Value |
|--------|-------|
| Model | OpenAI Whisper (intended) |
| Status | Not implemented — no code, no artifacts |
| Ensemble weight (audio channel) | `call_fraud`: 40%, `text`: 40% |

**Verdict: ❌ NOT READY**

**Root cause:** No implementation at all. No audio input pipeline, no Whisper model, no transcript output. Since Agent 13 (call transcript analyzer) depends entirely on Agent 12 to produce a transcript, both agents are non-functional. The audio channel effectively produces zero detection signal.

**Impact:** Voice scams (phone call fraud, vishing, tech support scams) are completely undetected by the ML pipeline.

---

## Agent 13 — Call Transcript Fraud Detector

**File:** `backend/app/ml/agents/agent_13_call_logreg/inference.py` (stub)  
**Real implementation:** `backend/app/ml/agents/inference.py` (`agent13_predict_transcript`)

| Metric | Value |
|--------|-------|
| Rule count | 8 regex patterns |
| Scoring | +25 per matched pattern, capped at 100 |
| Returns | `-1.0` if no patterns match |
| Ensemble weight (audio channel) | 40% |

**8 regex patterns cover:**
1. Official impersonation (cyber cell, CBI, police, inspector, ED)
2. Family emergency scam (accident, arrested, hospital)
3. OTP / bank detail requests
4. Urgent money transfer (send now, transfer immediately)
5. Legal threat (warrant, arrest, legal action)
6. Account/document freeze (Aadhaar, PAN, bank account)
7. Lottery / prize with fee (winner, prize, pay fee)
8. Scam keyword combinations

**Verdict: ❌ NOT READY**

**Loophole 1 — Depends on non-functional Agent 12:**  
No Whisper → no transcript → Agent 13 receives empty string → returns `-1.0` → ensemble gets zero signal for call fraud.

**Loophole 2 — 8 literal English regex patterns cannot cover voice fraud:**  
- Scammers speaking entirely in Hindi, Marathi, Tamil, Telugu, or Gujarati bypass all 8 patterns
- Paraphrased scam scripts ("your account has been marked as suspicious and will be closed unless verified") don't match literal keywords
- Social engineering that avoids trigger words entirely is undetectable

**Root cause:** Double dependency on a non-functional agent (Agent 12) plus over-reliance on exact English keyword matching for a linguistically diverse fraud landscape.

---

## Agent 14 — Regex Rule Engine

**File:** `backend/app/ml/agents/inference.py` (`agent14_score_text`)  
**Artifacts:** `scamshield_rules_v2.pkl`

| Metric | Value |
|--------|-------|
| Built-in rule categories | 23 |
| Scoring | +20 per matched category, capped at 100 |
| Test F1 | **0.3255** (32.55%) |
| Test set size | 5,573 labeled samples |
| Ensemble weight (text) | 15% |
| Override power | `regex_high` → mandatory +15 boost to final score |

**23 rule categories include:**  
Digital arrest, UPI double-money, fake job, OTP solicitation (vs OTP safety), parcel/customs, crypto scams, emergency transfer, utility threats, social engineering, account freeze, fake payment proof, character-spaced evasion (s.e.n.d), and more.

**Verdict: ⚠️ NOT PRODUCTION READY**

**Critical issue — F1 of 0.33 is near-random:**  
At 32.55% F1, this agent misclassifies approximately 2 out of every 3 predictions. A random classifier on a balanced dataset would score F1=0.50. This agent is performing **below random chance** as measured by F1.

Despite this, it carries 15% ensemble weight AND has direct override power (`regex_high` trigger forces +15 mandatory boost on the final score). This means Agent 14's false positives directly elevate innocent messages to SUSPICIOUS or HIGH_RISK.

**Loophole — Additive scoring with no context check creates systematic false positives:**

The scoring adds +20 per unique category matched with no requirement for co-occurrence or context. A legitimate banking OTP message:
```
"Your OTP for HDFC Bank account verification is 123456. Valid for 10 minutes. Do not share with anyone."
```
Triggers: OTP-solicitation (+20), bank (+20), account (+20), verify (+20) = **80 points → HIGH RISK**

This is a legitimate message that gets flagged as high-risk. The gibberish guard (vowel ratio check) protects against some cases but not this type.

**Root cause — Logic flaw, not dataset problem:**  
The fundamental design is broken: independent keyword category scoring treats each matched category as independent evidence of a scam. In reality, the co-occurrence context determines whether the same words indicate a scam or a legitimate message. "OTP + bank + verify" in a bank notification is legitimate; "OTP + bank + verify + share + please" from an unknown number is suspicious. The current scoring cannot distinguish these cases.

**Fix required:**
1. Replace additive scoring with co-occurrence logic: require ≥2 categories from different "sides" (urgency + request + unfamiliar sender) to trigger HIGH_RISK
2. Add sender context signal (known institution vs unknown number)
3. Lower override power: `regex_high` should cap at +8 boost (not +15) until F1 exceeds 0.7
4. Re-evaluate on a balanced test set of ≥20K samples

---

## Agent 15 — Ensemble Scorer (Weighted Aggregation)

**File:** `backend/agents/agent15_ensemble.py`  
**Config:** `ensemble_weights.json`, `ensemble_overrides.json`

**Channel-specific weights:**

| Signal | Text | URL | QR | UPI | Image | File | Audio |
|--------|------|-----|----|-----|-------|------|-------|
| text_prob (Agent 1) | 65% | 10% | 10% | 5% | 20% | 10% | 40% |
| url_prob (Agent 3/5) | 10% | 60% | 35% | 5% | 5% | 5% | 5% |
| upi_rule (Agent 6) | 5% | 5% | 15% | **80%** | 0% | 0% | 0% |
| brand_flag (Agent 8) | 10% | 20% | 15% | 5% | 0% | 0% | 5% |
| regex (Agent 14) | 15% | 5% | 10% | 10% | 25% | 25% | 5% |
| malware (Agent 11) | 0% | 0% | 0% | 0% | 35% | 45% | 0% |
| call_fraud (Agent 13) | 0% | 0% | 0% | 0% | 0% | 0% | 40% |
| upi_xgb (Agent 7) | 0% | 0% | 0% | **0% (DISABLED)** | 0% | 0% | 0% |

**Hard override floors:**

| Condition | Action |
|-----------|--------|
| Blacklist domain hit | min score = 80 |
| UPI rule score ≥ 70 | min score = 65 |
| Brand flag triggered | min score = 65 |
| Deepfake prob > 0.85 | min score = 70 |
| Malware prob > 0.7 | min score = 70 |
| `regex_high` triggered | +15 mandatory boost |
| Digital arrest rule | min score = 68 |
| UPI double-money rule | min score = 65 |
| Fake job rule | min score = 60 |

**Verdict: ⚠️ READY (quality ceiling bounded by weakest inputs)**

The ensemble architecture is sound: channel-specific weights, multi-signal boosting, and hard overrides for critical signals all make sense. However, the ensemble inherits systematic problems from its inputs:

**Inherited false positive bias from Agent 14:**  
Agent 14 has F1=0.33 and carries 15% weight. When it fires `regex_high` (which happens on legitimate bank messages), it forces a mandatory +15 boost regardless of what other agents say. The ensemble cannot override this floor.

**Silent false negatives from 5 stub agents:**  
Agents 2, 9, 10, 12, 13 are stubs returning -1 or error. Their ensemble weights remain non-zero in the config but their contributions are always 0. The ensemble believes it's getting 5 additional signals but is effectively operating with 10 active agents at best.

**Override stacking:**  
In the worst case: blacklist floor (80) + Agent 14 `regex_high` boost (+15) = 95 score. If Agent 14 fired a false positive, a legitimate URL that happens to be on a stale blacklist entry gets flagged as near-certain scam. Stacking of independent floor mechanisms without conflict resolution can produce inflated scores.

---

## Production Readiness Matrix

| Agent | Key Metric | Dataset | FP Risk | FN Risk | Root Issue | Verdict |
|-------|-----------|---------|---------|---------|-----------|---------|
| 1 — Text TF-IDF | F1: 0.89, Recall: 84% | 42K | Low | **Medium** | Architecture limits novel/regional text | ✅ READY |
| 2 — DistilBERT | N/A | None | N/A | **Critical** | No GPU, no model weights | ❌ NOT READY |
| 3 — URL XGBoost | AUC: **1.0** | 236K | Low | **High** | Overfit/data-leaked on lab data | ⚠️ QUESTIONABLE |
| 4 — Blacklist | 100% deterministic | 437K domains | None | **Low** | Zero-day gap only | ✅ READY |
| 5 — QR XGBoost | AUC: 0.9863 | 20K | Low | **Medium** | Thin dataset, brittle keywords | ✅ READY |
| 6 — UPI Heuristic | 100% on known rules | 12 YAML rules | Low | **Medium** | Rule brittleness, no ML fallback | ✅ READY |
| 7 — UPI XGBoost | AUC: **0.4714** | 250K | N/A | N/A | Label inversion + 4-feature poverty | ❌ DISABLED |
| 8 — Brand Guard v1 | Edit dist ≤ 2 | 21 brands | **High** | Medium | Threshold too loose, no Unicode | ⚠️ QUESTIONABLE |
| 9 — Brand BiLSTM | N/A | None | N/A | N/A | No GPU, no model weights | ❌ NOT READY |
| 10 — Deepfake | Returns -1.0 | None | N/A | **Critical** | Not implemented | ❌ NOT READY |
| 11 — Malware RF | Unknown | Unknown | Low | **High** | Byte truncation evadable | ⚠️ QUESTIONABLE |
| 12 — Whisper ASR | N/A | None | N/A | N/A | Not implemented | ❌ NOT READY |
| 13 — Call Transcript | 8 regex rules | None | Low | **Critical** | Depends on Agent 12 stub | ❌ NOT READY |
| 14 — Regex Engine | F1: **0.3255** | 5.5K | **High** | Medium | Additive scoring, no context | ⚠️ NOT PRODUCTION READY |
| 15 — Ensemble | Bounded by inputs | — | Inherited | Inherited | Weakest inputs contaminate output | ⚠️ READY |

---

## Priority Fixes for Backend Developer

### 🔴 Critical — Fix Before Production Launch

**1. Agent 14 — Replace additive keyword scoring with contextual logic**  
F1=0.33 is the single biggest source of false positives in the entire system. It has override power over the ensemble. Until fixed, the system regularly marks legitimate bank OTP messages as HIGH_RISK.
- Require co-occurrence: ≥2 categories from distinct "risk dimensions" (urgency + explicit request + unfamiliar action)
- Add negative signals that suppress false positives (known bank domain in sender, message < 100 chars, only contains digits and a date)
- Lower `regex_high` override boost from +15 to +5 until F1 > 0.70
- Retrain/re-evaluate on ≥20K balanced samples

**2. Agent 7 — Fix label inversion and retrain from scratch**  
AUC of 0.4714 means this model is actively harmful if re-enabled. The entire 250K training run was wasted due to a label encoding bug.
- Fix: ensure class 1 = FRAUD, class 0 = LEGITIMATE in all training code
- Add features: VPA domain age, merchant category code, transaction velocity (last 24h), recipient account age, device fingerprint match, geo-distance
- Minimum 8-10 features before retraining is worth attempting
- Validate AUC > 0.80 before adding back to ensemble

**3. Agent 3 — Adversarial validation before trusting AUC 1.0**  
Perfect scores on a held-out test set from the same distribution are meaningless if the test set doesn't reflect modern phishing.
- Generate adversarial test set: HTTPS URLs, short domains, no IPs, no suspicious subdomains — all structurally clean but confirmed phishing
- Add features: WHOIS domain registration date (< 30 days = high risk), SSL certificate age, redirect chain count, URL shortener detection
- If adversarial AUC < 0.85, model must be retrained with expanded feature set

### 🟡 High Priority

**4. Agent 11 — Expand beyond raw byte analysis**  
- Add: Shannon entropy calculation, magic byte / file signature detection, PE header parsing (imports, section names, entry point offset), embedded URL extraction from file content
- Test against files with clean headers but malicious payloads

**5. Agent 8 — Tighten brand matching threshold and expand Unicode coverage**  
- Edit distance threshold: ≤ 1 for brand names ≤ 8 characters
- Apply Unicode NFKC normalization before homoglyph substitution to catch Cyrillic/Greek lookalikes
- Add whitelist exceptions for common legitimate short-domain patterns (`.io`, `.co`, `.ai` startups)

### 🟢 Medium Priority (Stubs to Activate)

**6. Agent 2 — Deploy CPU-quantized DistilBERT**  
Export to ONNX with `int8` quantization. Model shrinks to ~65MB, inference ~150ms on CPU. Will significantly improve text recall from 84% toward 95%+.

**7. Agents 12 + 13 — Disable audio channel weights until Whisper is deployed**  
Until Agent 12 is functional, set `call_fraud` weight to 0% in `ensemble_weights.json` for the audio channel. Currently the ensemble acts as if it analyzed audio transcripts when it analyzed nothing. Set the audio channel to use only Agent 1 (text fallback) with weight 100% until Whisper is ready.

---

## Summary

Of the 15 agents, **4 are production-ready** (Agents 1, 4, 5, 6), **5 are completely non-functional stubs** (Agents 2, 9, 10, 12, 13), **4 have serious quality concerns** (Agents 3, 8, 11, 14), **1 is explicitly disabled for being harmful** (Agent 7), and **1 is a meta-agent bounded by the quality of its inputs** (Agent 15).

The most urgent issue is **Agent 14's F1 of 0.33** combined with its override power in the ensemble — this is actively generating false positives on legitimate messages today. The second most urgent is **Agent 7's label inversion bug** which needs a full retrain before that model can contribute anything useful to UPI fraud detection.
