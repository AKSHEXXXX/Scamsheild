"""
Agent 13 — Call Transcript Fraud Classifier
--------------------------------------------
Primary model:  DistilBERT multilingual fine-tuned for safe / suspicious / scam
Deployment:     INT8 dynamic-quantized state_dict  (CPU-safe, no GPU required)
Fallback:       Full FP32 transformer from agent13_transformer_model/
                (only used if INT8 artifact is not available)

Co-occurrence gate (required before returning SCAM):
    At least 2 of 3 dimensions must be present in the transcript:
      - Urgency keywords
      - Money / data request keywords
      - Unfamiliar authority claim keywords
    If only 1 dimension → SUSPICIOUS
    If 0 dimensions and model says scam → SUSPICIOUS

NOTE: Model weights (model.safetensors / pytorch_model_int8_dynamic_state_dict.pt)
      must be placed in the artifact directories listed below before inference works.
      Until then the module loads, but predict() returns a SAFE fallback with
      model_loaded=False so the ensemble is not contaminated.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("scamshield.ml.agents.agent13")

# ---------------------------------------------------------------------------
# Paths (resolved relative to this file → works from any working directory)
# ---------------------------------------------------------------------------
_AGENTS_DIR = Path(__file__).resolve().parent
_ARTIFACTS_DIR = _AGENTS_DIR.parent / "artifacts"

INT8_MODEL_DIR = _ARTIFACTS_DIR / "agent13_int8_quantized"
FULL_MODEL_DIR = _ARTIFACTS_DIR / "agent13_transformer_model"

# ---------------------------------------------------------------------------
# Label constants  (must match config.json: 0=safe, 1=suspicious, 2=scam)
# ---------------------------------------------------------------------------
LABELS = ["safe", "suspicious", "scam"]
LABEL2ID = {label: i for i, label in enumerate(LABELS)}
ID2LABEL = {i: label for label, i in LABEL2ID.items()}

# ---------------------------------------------------------------------------
# Co-occurrence gate keyword dimensions
# These match the task spec exactly; extended with originals from the notebook.
# ---------------------------------------------------------------------------
_URGENCY_KEYWORDS = [
    "urgent", "immediately", "blocked", "arrested", "freeze", "turant",
    "abhi", "band", "jaldi", "today", "final warning", "block", "suspend",
    "suspended", "arrest", "case", "fir", "deactivate", "expire", "last chance",
]

_MONEY_DATA_KEYWORDS = [
    "send", "transfer", "otp", "pin", "account number", "upi", "paisa",
    "rupees", "wallet", "pay", "payment", "bhejo", "fee", "deposit",
    "processing", "collect request", "qr", "refund", "cashback", "loan",
    "investment", "crypto", "bitcoin", "tax", "fine", "charge", "rs",
    "₹", "password", "cvv", "aadhaar", "pan", "kyc", "login code",
    "seed phrase", "bank details", "card details", "verification code",
]

_AUTHORITY_KEYWORDS = [
    "cbi", "police", "rbi", "court", "customs", "income tax", "cyber cell",
    "cyber crime", "tax department", "government", "officer",
]


def _count_active_dimensions(text: str) -> int:
    """Return how many of the 3 co-occurrence dimensions appear in text."""
    t = text.lower()
    dims = 0
    if any(k in t for k in _URGENCY_KEYWORDS):
        dims += 1
    if any(k in t for k in _MONEY_DATA_KEYWORDS):
        dims += 1
    if any(k in t for k in _AUTHORITY_KEYWORDS):
        dims += 1
    return dims


# ---------------------------------------------------------------------------
# Model loader  (lazy singleton — loaded once on first predict call)
# ---------------------------------------------------------------------------
_model = None
_tokenizer = None
_model_loaded: bool = False
_model_type: str = "not_loaded"


def _try_load_model():
    """
    Attempt to load the INT8 quantized model first, falling back to the full
    FP32 transformer. Sets module-level globals and logs the outcome.
    """
    global _model, _tokenizer, _model_loaded, _model_type

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
    except ImportError:
        logger.error(
            "[agent13] transformers/torch not installed — agent13 will not run"
        )
        return

    # ------------------------------------------------------------------
    # Try INT8 quantized first (production artifact)
    # ------------------------------------------------------------------
    int8_weights = INT8_MODEL_DIR / "pytorch_model_int8_dynamic_state_dict.pt"
    int8_tokenizer_cfg = INT8_MODEL_DIR / "tokenizer_config.json"

    if int8_weights.exists() and int8_tokenizer_cfg.exists():
        try:
            _tokenizer = AutoTokenizer.from_pretrained(str(INT8_MODEL_DIR))
            base = AutoModelForSequenceClassification.from_pretrained(
                str(FULL_MODEL_DIR)
            )
            quantized = torch.quantization.quantize_dynamic(
                base, {torch.nn.Linear}, dtype=torch.qint8
            )
            state_dict = torch.load(str(int8_weights), map_location="cpu")
            quantized.load_state_dict(state_dict, strict=False)
            quantized.eval()
            _model = quantized
            _model_loaded = True
            _model_type = "distilbert-multilingual-int8"
            logger.info(
                "[agent13] INT8 quantized model loaded ✓ from %s", INT8_MODEL_DIR
            )
            return
        except Exception as e:
            logger.warning("[agent13] INT8 load failed (%s), trying FP32 fallback", e)

    # ------------------------------------------------------------------
    # Fallback: full FP32 model
    # ------------------------------------------------------------------
    full_weights_a = FULL_MODEL_DIR / "model.safetensors"
    full_weights_b = FULL_MODEL_DIR / "pytorch_model.bin"
    full_tokenizer_cfg = FULL_MODEL_DIR / "tokenizer_config.json"

    if (full_weights_a.exists() or full_weights_b.exists()) and full_tokenizer_cfg.exists():
        try:
            _tokenizer = AutoTokenizer.from_pretrained(str(FULL_MODEL_DIR))
            _model = AutoModelForSequenceClassification.from_pretrained(
                str(FULL_MODEL_DIR)
            )
            _model.eval()
            _model_loaded = True
            _model_type = "distilbert-multilingual-fp32"
            logger.warning(
                "[agent13] Loaded FALLBACK full FP32 model (INT8 weights not found). "
                "Place pytorch_model_int8_dynamic_state_dict.pt in %s for production.",
                INT8_MODEL_DIR,
            )
            return
        except Exception as e:
            logger.error("[agent13] FP32 fallback load also failed: %s", e)

    # ------------------------------------------------------------------
    # Neither artifact present — log clearly, do NOT crash
    # ------------------------------------------------------------------
    logger.error(
        "[agent13] No model weights found. "
        "Place model files in:\n  INT8: %s\n  FP32: %s\n"
        "agent13_predict() will return SAFE (model_loaded=False) until weights are present.",
        INT8_MODEL_DIR,
        FULL_MODEL_DIR,
    )


# ---------------------------------------------------------------------------
# Public inference function
# ---------------------------------------------------------------------------

def agent13_predict(transcript: str) -> dict:
    """
    Classify a call transcript as SCAM / SUSPICIOUS / SAFE.

    Parameters
    ----------
    transcript : str
        Raw text transcript (Hinglish, English, or mixed).

    Returns
    -------
    dict with keys:
        label      : "SCAM" | "SUSPICIOUS" | "SAFE"
        confidence : float  0.0 – 1.0
        agent      : "agent13"
        model      : str  (model variant name)
    """
    global _model, _tokenizer, _model_loaded

    # Guard: non-string or empty input
    if not isinstance(transcript, str):
        try:
            transcript = str(transcript)
        except Exception:
            transcript = ""
    transcript = transcript.strip()

    # Lazy load on first call
    if _model is None:
        _try_load_model()

    # If model still not loaded, return safe fallback without crashing
    if not _model_loaded or _model is None or _tokenizer is None:
        return {
            "label": "SAFE",
            "confidence": 0.0,
            "agent": "agent13",
            "model": "not_loaded",
            "model_loaded": False,
            "note": "Model weights not found — place artifacts in agent13_int8_quantized/ or agent13_transformer_model/",
        }

    if not transcript:
        return {
            "label": "SAFE",
            "confidence": 1.0,
            "agent": "agent13",
            "model": _model_type,
            "model_loaded": True,
        }

    try:
        import torch
        import numpy as np

        with torch.no_grad():
            inputs = _tokenizer(
                transcript,
                truncation=True,
                padding=True,
                max_length=256,
                return_tensors="pt",
            )
            logits = _model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()

        raw_idx = int(np.argmax(probs))
        raw_label = ID2LABEL[raw_idx]
        confidence = float(probs[raw_idx])

        # ------------------------------------------------------------------
        # Co-occurrence gate — only applied when raw model says SCAM
        # ------------------------------------------------------------------
        dim_count = _count_active_dimensions(transcript)
        final_label = raw_label

        if raw_label == "scam":
            if dim_count >= 2:
                final_label = "scam"        # Confirmed — 2+ dimensions present
            elif dim_count == 1:
                final_label = "suspicious"  # Downgrade: only 1 dimension
            else:
                final_label = "suspicious"  # 0 dimensions → still suspicious, not safe

        # Return with uppercased label to match spec
        return {
            "label": final_label.upper(),
            "confidence": round(confidence, 4),
            "agent": "agent13",
            "model": _model_type,
            "model_loaded": True,
        }

    except Exception as e:
        logger.error("[agent13] Prediction error: %s", e)
        return {
            "label": "SAFE",
            "confidence": 0.0,
            "agent": "agent13",
            "model": _model_type,
            "model_loaded": _model_loaded,
            "error": str(e),
        }
