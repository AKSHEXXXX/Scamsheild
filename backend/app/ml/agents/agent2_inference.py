"""
Agent 2 — Multilingual Text / SMS Scam Classifier
--------------------------------------------------
Base model:  distilbert-base-multilingual-cased (fine-tuned)
Task:        Binary classification — safe (0) / scam (1)
Deployment:  INT8 dynamic-quantized state dict (CPU-safe)
Fallback:    FP32 model.safetensors from agent2_transformer_model/

Co-occurrence safety gate reduces false positives on legitimate
OTP / banking alerts by downgrading SCAM → SUSPICIOUS unless
at least 2 of 3 signal dimensions are active in the message.

Metrics (test set, 1183 samples):
  accuracy  0.9932   precision  0.9813   recall 0.9887
  F1        0.9850   AUC-ROC    0.9998
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("scamshield.ml.agents.agent2")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_AGENTS_DIR   = Path(__file__).resolve().parent
_ARTIFACTS    = _AGENTS_DIR.parent / "artifacts"

INT8_MODEL_DIR = _ARTIFACTS / "agent2_int8_quantized"
FP32_MODEL_DIR = _ARTIFACTS / "agent2_transformer_model"

# ---------------------------------------------------------------------------
# Label constants  (config.json: 0=safe, 1=scam)
# ---------------------------------------------------------------------------
_SAFE  = "SAFE"
_SUSP  = "SUSPICIOUS"
_SCAM  = "SCAM"

# ---------------------------------------------------------------------------
# Co-occurrence gate — 3 signal dimensions
# ---------------------------------------------------------------------------
_DIM_A_URGENCY = [
    "urgent", "immediately", "blocked", "freeze", "suspend", "suspended",
    "abhi", "turant", "band", "verify now",
]
_DIM_B_MONEY = [
    "otp", "pin", "cvv", "password", "bank account", "upi", "send money",
    "transfer", "payment", "kyc", "login",
]
_DIM_C_AUTHORITY = [
    "rbi", "sbi", "hdfc", "icici", "police", "cbi", "court", "customs",
    "income tax", "cyber cell",
]
# Strong credential / money solicitation phrases (for high-confidence override)
_STRONG_CRED = [
    "share otp", "send otp", "cvv", "pin", "password", "bank account",
    "send money", "transfer money", "upi id", "kyc",
]

_LEGIT_WARNINGS = [
    "do not share", "never share", "don't share", "dont share",
    "no one from the bank", "not share this otp"
]


def _dim_count(text_lower: str) -> int:
    dims = 0
    if any(k in text_lower for k in _DIM_A_URGENCY):  dims += 1
    if any(k in text_lower for k in _DIM_B_MONEY):    dims += 1
    if any(k in text_lower for k in _DIM_C_AUTHORITY): dims += 1
    return dims


def _apply_gate(raw_label: str, confidence: float, text: str) -> str:
    """
    Apply the co-occurrence safety gate to reduce false positives.
    Only downgrades SCAM — never upgrades SAFE → SCAM.

    Priority (highest first):
    1. Explicit legitimate-warning phrases  → cap at SUSPICIOUS
    2. High-confidence + strong solicitation → SCAM
    3. Co-occurrence dimension count        → SCAM (>=2) or SUSPICIOUS (<2)
    """
    if raw_label != _SCAM:
        return raw_label

    t = text.lower()

    # ── Priority 1: explicit defensive disclaimers always win ────────────────
    # Messages that contain "do not share", "never share", etc. are definitively
    # NOT asking the user to hand over credentials — cap at SUSPICIOUS.
    if any(w in t for w in _LEGIT_WARNINGS):
        return _SUSP

    # ── Priority 2: high-confidence model + strong credential solicitation ───
    # Only applied when no legitimate warning is present.
    if confidence > 0.95 and any(k in t for k in _STRONG_CRED):
        return _SCAM

    # ── Priority 3: co-occurrence gate ──────────────────────────────────────
    dims = _dim_count(t)
    if dims >= 2:
        return _SCAM
    # 0 or 1 dimension → downgrade
    return _SUSP



# ---------------------------------------------------------------------------
# Lazy model singleton
# ---------------------------------------------------------------------------
_model        = None
_tokenizer    = None
_model_loaded = False
_model_type   = "not_loaded"


# Scam class index — resolved after model load via id2label
_scam_class_idx: int = 1


def _get_scam_idx() -> int:
    """Determine which output index maps to 'scam' from model config."""
    if _model is None:
        return 1
    try:
        id2label = _model.config.id2label  # e.g. {0: "safe", 1: "scam"}
        for idx, label in id2label.items():
            if str(label).lower() in ("scam", "spam", "fraud", "malicious"):
                return int(idx)
    except Exception:
        pass
    return 1  # fallback: class 1 = scam (standard convention)


def _try_load_model() -> None:
    global _model, _tokenizer, _model_loaded, _model_type, _scam_class_idx

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
    except ImportError:
        logger.error("[agent2] transformers/torch not installed")
        return

    # ---------------------------------------------------------------------------
    # Always use FP32 tokenizer + FP32 config for correct id2label mapping.
    # The INT8 dir config.json has no id2label field (Colab artifact gap).
    # ---------------------------------------------------------------------------
    fp32_tok_cfg = FP32_MODEL_DIR / "tokenizer_config.json"
    if not fp32_tok_cfg.exists():
        logger.error("[agent2] FP32 tokenizer missing at %s", FP32_MODEL_DIR)
        return

    try:
        _tokenizer = AutoTokenizer.from_pretrained(str(FP32_MODEL_DIR))
    except Exception as e:
        logger.error("[agent2] Tokenizer load failed: %s", e)
        return

    # ---------------------------------------------------------------------------
    # Attempt 1 — INT8 .pt file
    # The Colab script may have saved either:
    #   a) torch.save(model)         → object with .forward
    #   b) torch.save(model.state_dict()) → plain dict
    # We try (a) first, then (b) loaded into the FP32 base model.
    # ---------------------------------------------------------------------------
    int8_weights = INT8_MODEL_DIR / "pytorch_model_int8_dynamic_state_dict.pt"
    if int8_weights.exists():
        try:
            obj = torch.load(str(int8_weights), map_location="cpu", weights_only=False)

            if hasattr(obj, "forward"):
                # Full model serialised — use directly.
                # Override config with FP32 config so id2label is correct.
                try:
                    from transformers import DistilBertConfig
                    fp32_cfg = DistilBertConfig.from_pretrained(str(FP32_MODEL_DIR))
                    obj.config = fp32_cfg
                except Exception:
                    pass
                obj.eval()
                _model        = obj
                _model_type   = "distilbert-multilingual-int8"
                _model_loaded = True
                _scam_class_idx = _get_scam_idx()
                logger.info(
                    "[agent2] Full INT8 model object loaded (scam_idx=%d)", _scam_class_idx
                )
                return

            if isinstance(obj, dict):
                # State dict — load into FP32 base model.
                # Using strict=True catches key-mismatch early so we know if it works.
                try:
                    base = AutoModelForSequenceClassification.from_pretrained(
                        str(FP32_MODEL_DIR)
                    )
                    base.load_state_dict(obj, strict=True)
                    base.eval()
                    _model        = base
                    _model_type   = "distilbert-multilingual-from-int8-weights"
                    _model_loaded = True
                    _scam_class_idx = _get_scam_idx()
                    logger.info(
                        "[agent2] INT8 state dict loaded into FP32 base (scam_idx=%d)",
                        _scam_class_idx,
                    )
                    return
                except RuntimeError:
                    logger.debug("[agent2] Strict state dict load failed — key mismatch")

        except Exception as e:
            logger.warning("[agent2] INT8 .pt load failed (%s), falling back to FP32", e)

    # ---------------------------------------------------------------------------
    # Attempt 2 — FP32 model (safetensors or pytorch_model.bin)
    # ---------------------------------------------------------------------------
    fp32_weights_ok = (
        (FP32_MODEL_DIR / "model.safetensors").exists()
        or (FP32_MODEL_DIR / "pytorch_model.bin").exists()
    )
    if fp32_weights_ok:
        try:
            _model = AutoModelForSequenceClassification.from_pretrained(
                str(FP32_MODEL_DIR)
            )
            _model.eval()
            _model_type   = "distilbert-multilingual-fp32"
            _model_loaded = True
            _scam_class_idx = _get_scam_idx()
            logger.warning(
                "[agent2] FP32 fallback model loaded (scam_idx=%d). "
                "Deploy INT8 state dict for production.",
                _scam_class_idx,
            )
            return
        except Exception as e:
            logger.error("[agent2] FP32 fallback also failed: %s", e)

    logger.error(
        "[agent2] No usable model weights found.\n  INT8: %s\n  FP32: %s",
        INT8_MODEL_DIR,
        FP32_MODEL_DIR,
    )



# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def agent2_predict(text: str) -> dict:
    """
    Classify a text/SMS message as SCAM / SUSPICIOUS / SAFE.

    Parameters
    ----------
    text : str
        Raw message text (English, Hindi, Hinglish, or mixed).

    Returns
    -------
    dict with keys:
        label      : "SCAM" | "SUSPICIOUS" | "SAFE"
        confidence : float  0.0 – 1.0
        agent      : "agent2"
        model      : str
        model_loaded : bool
    """
    global _model, _tokenizer, _model_loaded

    # Input sanitisation
    if not isinstance(text, str):
        try:   text = str(text)
        except Exception: text = ""
    text = text.strip()

    if _model is None:
        _try_load_model()

    if not _model_loaded or _model is None or _tokenizer is None:
        return {
            "label": _SAFE, "confidence": 0.0,
            "agent": "agent2", "model": "not_loaded", "model_loaded": False,
            "note": "Model weights not found — place files in agent2_int8_quantized/ or agent2_transformer_model/",
        }

    if not text:
        return {
            "label": _SAFE, "confidence": 1.0,
            "agent": "agent2", "model": _model_type, "model_loaded": True,
        }

    try:
        import torch
        import numpy as np

        with torch.no_grad():
            inputs = _tokenizer(
                text, truncation=True, padding=True,
                max_length=128, return_tensors="pt",
            )
            logits = _model(**inputs).logits
            probs  = torch.softmax(logits, dim=-1)[0].cpu().numpy()

        # config.json: 0=safe, 1=scam (dynamically determined)
        scam_prob = float(probs[_scam_class_idx])
        safe_prob = float(probs[1 - _scam_class_idx])

        if scam_prob >= 0.5:
            raw_label  = _SCAM
            confidence = scam_prob
        else:
            raw_label  = _SAFE
            confidence = safe_prob

        final_label = _apply_gate(raw_label, confidence, text)

        return {
            "label":       final_label,
            "confidence":  round(confidence, 4),
            "agent":       "agent2",
            "model":       _model_type,
            "model_loaded": True,
        }

    except Exception as e:
        logger.error("[agent2] Prediction error: %s", e)
        return {
            "label": _SAFE, "confidence": 0.0,
            "agent": "agent2", "model": _model_type,
            "model_loaded": _model_loaded, "error": str(e),
        }
