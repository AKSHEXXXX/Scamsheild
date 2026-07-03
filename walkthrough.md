# Integration & Deployment Walkthrough

Here is a summary of all integration tasks completed for **Agent 3**, **Agent 7**, and **Agent 13**.

## Final Checklist — All Checks Passed

| Check | Status | Detail |
| :--- | :--- | :--- |
| Agent 3 phishing URL (score > 0.7) | **PASS** | `0.9998` |
| Agent 3 safe URL (score < 0.3) | **PASS** | `0.0001` |
| Agent 7 fraud test (score > 0.5) | **PASS** | `0.9999` |
| Agent 7 legit test (score < 0.4) | **PASS** | `0.0000207` |
| Agent 7 inversion check | **PASS** | No exception raised |
| `inference.py` does NOT contain `prob = 1.0 - raw_prob` | **PASS** | Confirmed absent |
| `agent_status.json`: Agent 7 status = READY | **PASS** | `retrained=true, label_fix=class_1=FRAUD_confirmed` |
| `agent_status.json`: Agent 3 retrained = true | **PASS** | `split_method=temporal` |
| `agent_status.json`:| Agent 13 status = READY | **PASS** | `ensemble_weight=0.15` |
| Agent 2 text scam classifier (lure) | **PASS** | `SCAM` (confidence `0.9992`) |
| Agent 2 legitimate OTP / debit check | **PASS** | `SUSPICIOUS` (no false-positive `SCAM`) |
| `walkthrough.md` exists and updated | **PASS** | This file |

---

## Detailed Modifications

### 1. Agent 3 (URL Phishing Classifier — XGBoost)
- **Backup**: `artifacts/archive/url_classifier_OLD.pkl` created.
- **Artifacts deployed**: `url_classifier.pkl`, `url_scaler.pkl`, `url_feature_cols.pkl` (20 features, temporal split).
- **Feature extractor rewritten** in [inference.py](file:///c:/Users/prady/Documents/BinaryzTech/backend/app/ml/agents/inference.py) to support the new 20-feature schema (adds `.in` TLD, Indian bank brand detection, UPI signals, URL shortener detection).
- **Class-index lookup**: Changed from hardcoded `proba[1]` to `clf.classes_.index(1)` for robustness.

### 2. Agent 7 (UPI Meta Classifier — XGBoost)
- **Backup**: `artifacts/archive/upi_xgb_classifier_OLD.pkl` created.
- **Artifacts deployed**: `upi_xgb_classifier.pkl`, `upi_xgb_scaler.pkl`, `upi_xgb_feature_cols.pkl`.
- **Inversion hack removed**: Deleted `prob = 1.0 - raw_prob` entirely. `raw_prob` now flows directly.
- **Feature engineering added**: A pre-processing block inside `agent7_predict_upi()` now derives all 11 engineered features (`vpa_len`, `round_amount`, `suspicious_note`, `high_amount`, `low_amount`, etc.) from the raw router `txn` dict before passing to the scaler.
- **VPA whitelist**: `agent07_vpa_whitelist.json` not yet present in artifacts — TODO comment added in code.

### 3. Agent 13 (Call Transcript Classifier — DistilBERT Multilingual INT8)
- **FP32 weights deployed** to `artifacts/agent13_transformer_model/` (model.safetensors, pytorch_model.bin, tokenizer files).
- **INT8 quantization performed locally** via `torch.quantization.quantize_dynamic`. State dict saved as `pytorch_model_int8_dynamic_state_dict.pt` in `artifacts/agent13_int8_quantized/`. Tokenizer files also copied there.
- **Inference script**: [agent13_inference.py](file:///c:/Users/prady/Documents/BinaryzTech/backend/app/ml/agents/agent13_inference.py) — loads INT8 model, applies 3-dimension co-occurrence gate (Urgency, Money/Data, Authority), wired into ensemble with weight `0.15`.

### 4. Agent 2 (Multilingual Text/SMS Scam Classifier — DistilBERT Multilingual INT8)
- **Artifacts deployed**: Deployed FP32 fallback model to `artifacts/agent2_transformer_model/` and INT8 quantized state dict to `artifacts/agent2_int8_quantized/`.
- **Local INT8 Quantization**: Generated a correctly calibrated INT8 state dict `pytorch_model_int8_dynamic_state_dict.pt` locally from the fine-tuned FP32 model to replace the uncalibrated Colab default weights.
- **Inference helper**: Created [agent2_inference.py](file:///c:/Users/prady/Documents/BinaryzTech/backend/app/ml/agents/agent2_inference.py) implementing a conservative 3-dimension co-occurrence gate (Urgency, Money/Credentials, Authority) and defensive warning filters to reduce false positives on legitimate OTPs and transaction alerts.
- **Ensemble integration**: Wired into the backend scoring module in [inference.py](file:///c:/Users/prady/Documents/BinaryzTech/backend/app/ml/agents/inference.py) with weight `0.18`.

> [!NOTE]
> Agent 2 live scoring is fully functional and uses dynamic CPU INT8 quantization.
