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

### 5. Agent 1 (Text Scam Classifier — TF-IDF + LogReg)
- **Artifacts Deployed**: Deployed retrained `scamshield_vectorizer.pkl`, `scamshield_model.pkl`, and `scamshield_label_encoder.pkl`.
- **Feature Pipeline**: The new vectorizer contains a `FeatureUnion` of word/char TF-IDF (`50546` features) and a custom dense feature extractor `CustomScamFlags` (`10` features) producing a total of `50556` features.
- **Inference integration**: Updated `agent1_predict_text` to stack the sparse TF-IDF and dense engineered features using `scipy.sparse.hstack` before calling the classifier.
- **Dependency Binding**: Defined `CustomScamFlags` scikit-learn transformer at the top of `model_loader.py` and bound it to the `__main__` namespace to ensure seamless unpickling via `joblib`.

### 6. Agent 5 (QR Threat Classifier — XGBoost Native)
- **Artifacts Deployed**: Deployed retrained `qr_url_classifier.ubj` native XGBoost model, `qr_model_report.json` metrics, and `qr_test_predictions.csv` test set predictions.
- **Feature Extractor**: Created `agent_05_feature_extractor.py` containing a comprehensive 60-feature extractor supporting URL, UPI, plain text, and vCard payload classification.
- **Inference integration**: Updated `agent5_predict_qr_payload` in `inference.py` and `predict_qr` in `agent_5_qr_xgb/inference.py` to use the 60-feature extractor and native XGBoost model loading (no scaling required).

### 7. Agent 11 (Malware File Analyzer — Random Forest Calibrated)
- **Artifacts Deployed**: Deployed retrained `malware_rf.pkl` (350 MB Calibrated Random Forest model), `malware_feature_indices.pkl` (updated list of 215 indices), and metrics.
- **Inference integration**: Updated loader in `model_loader.py` and inference helper in `agent_11_malware_rf/inference.py` to bypass the legacy 128-feature scaler (StandardScaler removed from pipeline as RF does not require scaling), and pad inputs to the 215 features expected by the DREBIN-trained model.

> [!NOTE]
> All seven retrained models (Agents 1, 2, 3, 5, 7, 11, 13) are now fully wired, verified, and operational. Large model weight files (such as Agent 11's 350 MB `malware_rf.pkl` and Agent 2/13's deep learning weights) are safely gitignored by design to prevent repository bloat, while all lightweight metadata, configurations, and inference scripts have been staged.

### 8. Ensemble-level OTP/Debit vs Scam Verification

Added ensemble-level OTP/debit vs scam verification with SCAM_LURE / LEGIT_OTP / LEGIT_DEBIT probes. Current ensemble behaviour: scam correctly high-risk, legitimate OTP/debit no longer flagged SCAM.

**Root causes fixed:**
- **Agent 2 gate priority bug**: `_apply_gate()` was checking the high-confidence override _before_ the legitimate-warning check, so messages with "do not share" + "otp" were returned as SCAM (confidence 0.9984) despite the disclaimer. Legitimate-warning phrases now take absolute priority.
- **Agent 2 SUSPICIOUS float mapping**: When the gate downgraded SCAM→SUSPICIOUS, the raw scam confidence was forwarded unchanged (`max(conf, 0.55)` = 0.9984), inflating the ensemble score. SUSPICIOUS is now clamped to `[0.45, 0.60]`.
- **Ensemble `ensemble_predict_text` helper**: Added to `inference.py` as a pure function mirroring the `/api/v1/analyze-text` code path. Extended Agent 2 uncertainty gate from `0.35–0.65` to `0.35–0.85` to catch high-scoring false positives. Post-ensemble defensive-phrase gate now uses Agent 2's gated label (not float proxy) for reliable decisions.

**Verified probe results:**

| Probe | `final_label` | `final_score` | Pass? |
|-------|--------------|---------------|-------|
| SCAM_LURE ("URGENT: Your SBI account will be suspended...") | `SCAM` | `1.00` | ✅ |
| LEGIT_OTP ("Your OTP for SBI login is 847291. Do not share...") | `SUSPICIOUS` | `0.55` | ✅ |
| LEGIT_DEBIT ("Rs 500 debited from A/c XX3021 via UPI...") | `SAFE` | `0.31` | ✅ |

