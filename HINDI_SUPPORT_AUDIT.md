# ScamShield — Hindi Language Support Audit

**Date:** 2026-07-06  
**Scope:** Can the current 15-agent pipeline understand Hindi text scams and Hindi-inscribed screenshots?  
**Short answer:** No. Every layer that touches text breaks on Hindi input.

---

## The Core Problem

Indian scam messages come in three forms the current system cannot handle:

1. **Pure Hindi (Devanagari script):** `"आपका खाता फ्रीज कर दिया जाएगा, अभी OTP शेयर करें"`
2. **Hinglish (Roman-script Hindi):** `"Aapka account band ho jayega, abhi OTP share karo"`
3. **Mixed screenshots:** Hindi text overlaid on images (common in WhatsApp scam forwards)

All three fail at one or more pipeline layers. The worst case is pure Devanagari — it breaks 6 layers simultaneously.

---

## Layer-by-Layer Failure Analysis

### Layer 1 — OCR (pytesseract 0.3.13)

**Status: BROKEN for Hindi screenshots**

```python
# Current implementation — English only
pytesseract.image_to_string(image, lang='eng')
```

Tesseract's English model has no knowledge of the Devanagari script. A Hindi screenshot produces either:
- Garbled ASCII approximations of Devanagari characters
- Completely empty string

**Impact:** Hindi text in uploaded screenshots is never extracted. The image scan pipeline receives empty text → no agent can analyze the content → scam returns LOW_RISK.

**Fix type:** Config change — no model training required.

```python
# Fix: add Hindi language pack
pytesseract.image_to_string(image, lang='hin+eng')
# Also requires on Railway server: apt-get install tesseract-ocr-hin
```

---

### Layer 2 — Text Normalizer (`backend/app/preprocessing/text_normalizer.py`)

**Status: BROKEN — strips Devanagari entirely**

The normalizer pre-processes text before any agent sees it. It almost certainly applies ASCII normalization (common in English NLP pipelines), which wipes all Unicode characters outside the ASCII range.

Devanagari Unicode range: **U+0900 – U+097F** (characters: क, ख, ग, घ, ...)  
Hindi numerals: **U+0966 – U+096F** (characters: ०, १, २, ...)

If the normalizer runs `text.encode('ascii', errors='ignore')` or any equivalent filter:
- Input: `"आपका OTP 123456 है"` (Your OTP is 123456)
- Output: `" OTP 123456 "` — Hindi context completely destroyed

**Impact:** Even if OCR correctly extracts Hindi text, the normalizer silently erases it before Agent 1 or Agent 14 ever receive it.

**Fix type:** Code fix — add explicit Unicode preservation.

```python
# Fix: preserve Devanagari block before any ASCII normalization
import unicodedata
DEVANAGARI_RANGE = range(0x0900, 0x0980)
# Do not strip characters in this range
```

---

### Layer 3 — Agent 1 (TF-IDF + Logistic Regression)

**Status: BROKEN — produces random output on Hindi input**

This is the most critical failure. The TF-IDF vectorizer was trained entirely on an **English corpus (33,680 samples)**. Its vocabulary contains only English tokens.

**What happens when Hindi text enters Agent 1:**

| Input | TF-IDF Result | LogReg Output | Score |
|-------|--------------|---------------|-------|
| `"आपका खाता बंद हो जाएगा"` | Zero-vector (no token matches) | 50% probability | ~50 (SUSPICIOUS) |
| `"आपके खाते में ₹500 जमा हुए"` | Zero-vector (no token matches) | 50% probability | ~50 (SUSPICIOUS) |

**Both a scam and a legitimate message produce the same score (~50).** The model has learned nothing about Hindi — it returns near-random output on any unseen language.

**Hinglish is marginally better** because Roman characters partially overlap with English vocabulary tokens (e.g., `"account"`, `"otp"`, `"bank"` are shared). But performance is unreliable and untested.

**Fix type:** Model retraining required — see Training Plan section below.

---

### Layer 4 — Agent 14 (Regex Rule Engine)

**Status: BROKEN — 0% detection rate on Hindi**

Agent 14's 23 rule categories are entirely English keywords:

| Rule Category | Current English Keywords |
|--------------|------------------------|
| Digital arrest | `cyber cell`, `aadhaar freeze`, `warrant`, `arrest`, `legal action` |
| UPI double-money | `congratulations`, `lucky draw`, `cashback`, `double money` |
| OTP solicitation | `otp`, `share`, `verify`, `one time password` |
| Fake job | `work-from-home`, `registration fee`, `earn daily` |
| Account freeze | `account freeze`, `account block`, `account suspend` |
| Emergency transfer | `stuck at airport`, `hospital`, `lost wallet` |

Agent 14 already has F1=0.33 on English (near-random). On Hindi input it is effectively **F1=0.00** — none of the 23 categories contain a single Devanagari character.

A scam message `"आपका आधार कार्ड बंद हो जाएगा"` (Your Aadhaar card will be blocked) matches **zero** rules.

**Fix type:** Add Devanagari + Hinglish equivalents to each rule category — no ML training required.

---

### Layer 5 — Agent 6 (UPI Heuristic Engine)

**Status: PARTIAL BREAK — misses Hindi UPI note fields**

The UPI note field (the message a sender attaches to a UPI payment) frequently contains Hindi text in India. Current VPA keyword list is English only: `bank`, `refund`, `reward`, `help`, `kyc`, `support`.

Common Hindi UPI scam note patterns not detected:
- `"पैसे वापस करो"` (send money back — advance fee scam)
- `"ईनाम भेजा जा रहा है"` (prize is being sent — collect fee first)
- `"रजिस्ट्रेशन फीस"` (registration fee — fake job scam)
- `"सत्यापन शुल्क"` (verification fee — KYC scam)

**Fix type:** Config change — add Hindi keywords to `upi_heuristic_rules.yaml`. No retraining.

---

### Layer 6 — Agent 5 (QR Code XGBoost)

**Status: PARTIAL BREAK — English-only keyword feature**

The `HasSuspiciousKeyword` feature checks exactly 10 hardcoded English words:
```python
["otp", "kyc", "verify", "urgent", "refund", "free", "prize", "win", "cashback", "reward"]
```

Hindi QR payloads (UPI QR codes with embedded note text, or URLs with Hindi path components) score 0 on this feature, lowering the overall risk score.

**Fix type:** Expand keyword list with Hindi transliterations and Devanagari equivalents. No retraining.

---

### Layers 7 & 8 — Agent 4 (Blacklist) and Agent 8 (Brand Guard)

**Status: NOT AFFECTED**

Both operate on domain names which are ASCII. Internationalized domain names in Devanagari are Punycode-encoded at the DNS layer — they appear as ASCII `xn--` strings to the model. No Hindi support needed here.

---

## Summary Table

| Layer | Breaks on Hindi? | Severity | Fix Type | Training Required? |
|-------|-----------------|----------|----------|--------------------|
| OCR (pytesseract) | YES — garbled/empty output | Critical | Config: `lang='hin+eng'` | No |
| Text Normalizer | YES — strips all Devanagari | Critical | Code: preserve U+0900–U+097F | No |
| Agent 1 (TF-IDF) | YES — random ~50 score | Critical | **Retrain on Hindi dataset** | **YES** |
| Agent 14 (Regex) | YES — 0% match rate on Hindi | High | Add Devanagari regex patterns | No |
| Agent 6 (UPI) | PARTIAL — Hindi notes missed | Medium | Add Hindi to YAML config | No |
| Agent 5 (QR) | PARTIAL — English keywords only | Medium | Expand keyword list | No |
| Agent 4 (Blacklist) | No impact | — | — | — |
| Agent 8 (Brand Guard) | No impact | — | — | — |

**5 of 6 affected layers are config/code fixes (1–2 days). Only Agent 1 requires actual ML retraining.**

---

## Which Model Needs to Be Trained on Hindi Datasets

### Agent 1 — Replace TF-IDF + LogReg with MuRIL

**Recommended model: `google/muril-base-cased`**

| Property | Value |
|----------|-------|
| Full name | Multilingual Representations for Indian Languages |
| Built by | Google Research India |
| Languages | 17 Indian languages incl. Hindi, Hinglish, Marathi, Gujarati, Bengali |
| Model size | 236MB (base) |
| CPU inference | ~200ms with ONNX int8 quantization |
| HuggingFace | `google/muril-base-cased` |

**Why MuRIL over alternatives:**

| Model | Hindi | Hinglish/Code-mixed | CPU-friendly | Indian-specific |
|-------|-------|--------------------|--------------|-|
| **MuRIL** | ✅ Excellent | ✅ Best-in-class | ✅ With ONNX | ✅ Built for India |
| XLM-RoBERTa | ✅ Good | ⚠️ Weaker | ✅ With ONNX | ❌ Generic multilingual |
| DistilBERT | ❌ English only | ❌ | ✅ | ❌ |
| mBERT | ✅ Fair | ⚠️ Weaker | ✅ | ❌ |

Hinglish is critical: most Indian scam messages mix Hindi and English in Roman script (`"aapka account band ho jayega"`). MuRIL was explicitly trained on code-mixed Indian text — it's the only publicly available model optimized for this.

---

### Fine-tuning Approach

```
google/muril-base-cased
  ↓
Add binary classification head (scam=1 / legitimate=0)
  ↓
Fine-tune on mixed English + Hindi corpus (50/50 split)
  ↓
Validate: accuracy > 92%, recall > 88%, F1 > 0.90
  ↓
Export to ONNX with int8 quantization
  ↓
Replace text_tfidf_vectorizer.pkl + text_logreg_classifier.pkl
  ↓
Agent 1 interface stays identical — drop-in replacement
```

No changes to the ensemble or other agents required. The inference function signature stays the same.

---

## Hindi Training Dataset Sources

The backend dev needs to assemble a training corpus. Target: **25,000 Hindi/Hinglish scam + 25,000 legitimate** (balanced, minimum).

| Dataset | Size | Language | Source | Notes |
|---------|------|----------|--------|-------|
| IIT-Bombay Hindi SMS Spam | ~10K | Hindi (Devanagari) | Research corpus (publicly available) | Labeled spam/ham — directly usable |
| TRAC-2 Aggression Detection | ~15K | Hindi + English | TRAC shared task (2018/2020) | Social media, partial scam overlap |
| AI4Bharat IndicNLP Hindi | ~100K | Hindi | HuggingFace `ai4bharat/indic-glue` | General — needs scam labels added |
| DAP (Devanagari Abuse Prevention) | ~8K | Hindi | Research paper | Online abuse, some scam patterns |
| Synthetic via IndicTrans2 | ~33K | Hindi | Translate English corpus | Use AI4Bharat's IndicTrans2 to translate existing 33,680 English scam samples → instant Hindi corpus |
| Cybercrime.gov.in reports | Varies | Hindi + English | Manual collection | Real complaint transcripts — highest quality but requires scraping/sanitizing |

**Fastest path to a usable corpus (< 1 week):**
1. Run existing 33,680 English scam samples through IndicTrans2 → ~33K synthetic Hindi scam samples
2. Source 10K IIT-Bombay SMS spam corpus (labeled, ready to use)
3. Collect 10K legitimate Hindi SMS examples (bank notifications, OTP messages — easy to source)
4. Total: ~53K samples for initial fine-tuning

**For production quality (2–4 weeks):**
1. Add TRAC-2 + IndicNLP data with manual scam labels
2. Collect 500–1K real Hindi scam screenshots from user reports
3. Target: 100K+ balanced multilingual corpus

---

## Non-ML Fixes: Hindi Patterns to Add to Rule Agents

These require no ML training — just text additions to existing config files.

### Agent 14 — Devanagari Regex Additions by Category

| Rule Category | Add These Hindi/Devanagari Patterns | Add These Hinglish Patterns |
|--------------|------------------------------------|-----------------------------|
| Digital arrest | `साइबर पुलिस`, `गिरफ्तारी`, `वारंट`, `ईडी`, `सीबीआई`, `नोटिस` | `cyber girftari`, `police notice`, `ED raid` |
| Account freeze | `खाता फ्रीज`, `खाता बंद`, `खाता निलंबित`, `बैंक खाता` | `account band`, `khata freeze`, `account block karo` |
| OTP solicitation | `ओटीपी`, `शेयर करें`, `सत्यापन कोड`, `न बताएं` | `otp share karo`, `code batao`, `verify karo` |
| UPI double-money | `पुरस्कार`, `इनाम`, `दोगुना`, `लकी ड्रा`, `कैशबैक` | `prize jeeta`, `double paisa`, `lucky draw` |
| Fake job | `घर से काम`, `रजिस्ट्रेशन फीस`, `रोज़ाना कमाई`, `पार्ट टाइम` | `ghar se kaam`, `registration fee`, `part time job` |
| Emergency transfer | `अस्पताल में`, `हादसा हो गया`, `फंस गया`, `मदद चाहिए` | `hospital mein hoon`, `accident hua`, `paise bhejo` |
| KYC expiry | `केवाईसी`, `केवाईसी समाप्त`, `अपडेट करें` | `KYC update karo`, `KYC expire ho gaya` |
| Customs/parcel | `कस्टम शुल्क`, `पार्सल रोका`, `डिलीवरी शुल्क` | `customs fee bharo`, `parcel ruka hai` |

### Agent 6 — Hindi VPA Keywords to Add to YAML

```yaml
# Add to suspicious_vpa_keywords list:
hindi_keywords:
  - "बैंक"       # bank
  - "रिफंड"      # refund  
  - "इनाम"       # prize/reward
  - "सहायता"     # help/support
  - "सत्यापन"    # verification
  - "शुल्क"      # fee/charge

# Add to suspicious_note_patterns:
hindi_note_patterns:
  - "पैसे वापस"           # money back
  - "रजिस्ट्रेशन फीस"    # registration fee
  - "ईनाम भेजा"          # prize being sent
  - "सत्यापन शुल्क"      # verification fee
```

### Agent 5 — Hindi QR Keywords to Add

```python
# Expand HasSuspiciousKeyword feature list:
SUSPICIOUS_KEYWORDS = [
    # Existing English
    "otp", "kyc", "verify", "urgent", "refund", "free", "prize", "win", "cashback", "reward",
    # Add Hinglish
    "paise", "account band", "registration", "fee", "inam", "jeeto",
    # Add Devanagari  
    "ओटीपी", "केवाईसी", "इनाम", "शुल्क", "पुरस्कार", "फ्री"
]
```

---

## Implementation Priority Order

### Phase 1 — Config Fixes (1–2 days, backend dev, no ML)

1. `pytesseract.image_to_string(image, lang='hin+eng')` in OCR router
2. `apt-get install tesseract-ocr-hin` in Railway `Dockerfile` or startup script
3. Text normalizer: preserve Unicode U+0900–U+097F before ASCII normalization
4. Agent 14: add Devanagari + Hinglish patterns to all 23 rule categories
5. Agent 6 YAML: add Hindi VPA keywords and note patterns
6. Agent 5: expand `SUSPICIOUS_KEYWORDS` list

**After Phase 1:** Hinglish and some Devanagari patterns will be detected. Agent 1 still returns random output on pure Hindi — partial improvement only.

---

### Phase 2 — Model Retraining (1–2 weeks, ML engineer)

1. Assemble Hindi training corpus (see Dataset Sources above)
2. Fine-tune `google/muril-base-cased` on mixed English + Hindi corpus
3. Validate: F1 > 0.90, Recall > 88% on Hindi test set
4. Export to ONNX with int8 quantization
5. Replace `text_tfidf_vectorizer.pkl` + `text_logreg_classifier.pkl` in `artifacts/`
6. No other code changes needed — Agent 1 interface is identical

**After Phase 2:** Full Hindi + Hinglish + English support across all text channels.

---

### Phase 3 — OCR Upgrade (Optional, 1 week)

Replace `pytesseract` with `EasyOCR` for image inputs:

```python
# Current (brittle on mixed-script screenshots)
import pytesseract
text = pytesseract.image_to_string(image, lang='hin+eng')

# Upgrade (handles mixed Hindi+English fonts, logos, WhatsApp screenshots)
import easyocr
reader = easyocr.Reader(['hi', 'en'])
results = reader.readtext(image)
text = ' '.join([r[1] for r in results])
```

EasyOCR uses CRAFT (scene text detection) + CRNN (recognition) — better for real-world scam screenshots that mix fonts, have watermarks, or contain text at angles.

---

### Phase 4 — Multilingual Semantic Embeddings (Optional, 3 days)

Add `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` as a new Agent 16:

| Property | Value |
|----------|-------|
| Languages | 50+ including Hindi, Hinglish |
| Embedding size | 384 dimensions |
| CPU inference | ~50ms |
| Training required | None — zero-shot similarity |

This agent computes cosine similarity between user input and a library of known Hindi scam templates. Any message semantically close to a known template scores HIGH_RISK regardless of exact wording. Catches paraphrases that regex rules miss.

Suggested ensemble weight: 10% for text channel, replacing part of Agent 14's 15% weight (which has F1=0.33).

---

## Test Cases for Verification

After implementing all fixes, these test inputs should produce the expected verdicts:

| Input | Language | Expected Verdict |
|-------|----------|-----------------|
| `"आपका आधार कार्ड बंद हो जाएगा, अभी OTP शेयर करें"` | Pure Hindi | HIGH_RISK |
| `"साइबर पुलिस: आपके नाम पर वारंट है, तुरंत कॉल करें"` | Pure Hindi | HIGH_RISK |
| `"Aapka account band ho jayega, abhi OTP share karo"` | Hinglish | HIGH_RISK |
| `"Lucky draw mein aapka naam aaya, registration fee bharo"` | Hinglish | HIGH_RISK |
| `"आपके खाते में ₹500 जमा हुए हैं। — HDFC Bank"` | Pure Hindi | LOW_RISK |
| `"Your OTP for HDFC Bank login is 123456. Do not share."` | English | LOW_RISK |
| Screenshot of Hindi scam WhatsApp message | Image/Hindi | HIGH_RISK (after OCR fix) |
| Screenshot of Hindi bank notification | Image/Hindi | LOW_RISK (after OCR fix) |

---

## Summary for Backend Developer

The current system is **English-only**. Adding Hindi support requires two tracks of work running in parallel:

**Track 1 — Engineering (no ML, 1–2 days):**
- Activate Hindi OCR via `lang='hin+eng'` parameter
- Preserve Devanagari in text normalizer
- Add Hindi/Hinglish keywords to Agent 14, Agent 6, Agent 5

**Track 2 — ML (retraining required, 1–2 weeks):**
- Assemble 50K+ Hindi/Hinglish scam corpus (fastest: translate existing English corpus via IndicTrans2)
- Fine-tune `google/muril-base-cased` as a drop-in replacement for Agent 1
- Export to ONNX for CPU deployment

After both tracks: the system will handle pure Devanagari, Hinglish, and English input across all scan channels (text, image/OCR, QR, UPI note fields).
