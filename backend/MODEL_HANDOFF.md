# Model Handoff Contract — ScamShield

## Directory Structure

Each agent lives under `backend/ml/agents/agent_N_name/` with this layout:

```
agent_N_name/
  __init__.py         # empty (package marker)
  inference.py        # your predict/score entrypoint (REQUIRED)
  model/              # model artifacts (pickle, onnx, weights, tokenizer)
    ...your files...
  requirements.txt    # extra pip deps if any (OPTIONAL)
```

The **8 agent folders** already exist with stubs:

| Folder | Agent | Input | Output |
|--------|-------|-------|--------|
| `agent_1_text_tfidf` | TF-IDF + Logistic Regression | text: str | probability: float (0–1) |
| `agent_2_distilbert` | DistilBERT text classifier | text: str | probability: float (0–1) |
| `agent_3_url_xgb` | URL Phishing XGBoost | url: str | probability: float (0–1) |
| `agent_5_qr_xgb` | QR Payload XGBoost | payload: str | probability: float (0–1) |
| `agent_7_upi_meta_xgb` | UPI Meta XGBoost | txn: dict | probability: float (0–1) |
| `agent_9_brand_bilstm` | Brand BiLSTM | domain: str | (is_brand: bool, brand_name: str) |
| `agent_11_malware_rf` | Malware Random Forest | file_bytes: bytes | probability: float (0–1) |
| `agent_13_call_logreg` | Call transcript LR | transcript: str | probability: float (0–1) |

## Canonical Entrypoint Signatures (V2 — Standardized)

Every agent MUST implement exactly ONE of these functions in `inference.py`.
The return dict MUST contain these keys:

| Key | Type | Required | Notes |
|-----|------|----------|-------|
| `verdict` | str | YES | One of: `"safe"`, `"suspicious"`, `"high_risk"`, `"scam"`, `"error"` |
| `score` | int | YES | `-1` = error, `0–100` = scam likelihood |
| `reasons` | list[str] | YES | Human-readable reasons; empty list is OK |
| `metadata` | dict | YES | Optional extra data; empty dict `{}` is OK |

### Text agents (1, 2, 13)

```python
def predict_text(text: str) -> dict:
    """Return dict with verdict, score (0-100), reasons, metadata.
       Return {"verdict": "error", "score": -1, ...} on failure."""
    ...
```

### URL agent (3)

```python
def predict_url(url: str) -> dict:
    """Return dict with verdict, score, reasons, metadata. -1 on failure."""
    ...
```

### QR agent (5)

```python
def predict_qr(qr_string: str) -> dict:
    """Return dict with verdict, score, reasons, metadata. -1 on failure."""
    ...
```

### UPI agent (7)

```python
def predict_upi(transaction: dict) -> dict:
    """
    transaction = {"amount": float, "note": str, "vpa": str, "channel": str}
    Return dict with verdict, score, reasons, metadata. -1 on failure.
    """
    ...
```

### Brand agent (9)

```python
def check_brand(domain: str, brand_name: str = "") -> dict:
    """
    Return dict with verdict, score (0 or 100), reasons, metadata.
    metadata should contain {"matched": bool, "matched_brand": str}.
    """
    ...
```

### Malware agent (11)

```python
def predict_file(features: dict) -> dict:
    """
    features = {"file_bytes": bytes, ...}
    Return dict with verdict, score, reasons, metadata. -1 on failure.
    """
    ...
```

## Constraints

| Rule | Reason |
|------|--------|
| No outbound HTTP | SSRF prevention |
| No filesystem writes | Stateless design |
| No direct DB access | All DB writes through `persist_scan` |
| Must handle missing model files gracefully | Lazy loading; return -1.0 if artifact not found |
| Keep inference.py < 200 lines | Maintainability |
| Log via `logging.getLogger("scamshield.agent_N")` | Consistent structured logging |
| Max input: text ≤ 4096 chars, URL ≤ 2048 chars | Already enforced at API boundary |

## Integration Checklist

- [ ] Model artifacts placed in `model/` directory
- [ ] `inference.py` has the correct `predict_*` / `check_*` function
- [ ] Function returns -1.0 on error (never raises)
- [ ] `requirements.txt` added if extra pip deps are needed
- [ ] Model loads within 5 seconds on first call
- [ ] No side effects on import (lazy load inside the function)
- [ ] Add `inference_test.py` with 3+ test cases

## After Handoff

1. I (backend) update the wiring in `app/ml/model_loader.py` to discover the new agent
2. I update `agents/agent15_ensemble.py` to include the new agent's signals
3. CI runs; verify startup logs show `Agent N loaded ✓`
4. Deploy to Railway
