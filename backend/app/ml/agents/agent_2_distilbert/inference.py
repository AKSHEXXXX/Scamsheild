import logging

logger = logging.getLogger("scamshield.agent.2.distilbert")

def predict_text(text: str) -> dict:
    logger.debug("[Agent 2] DistilBERT — NOT_READY (GPU required)")
    return {"verdict": "error", "score": -1, "reasons": ["DistilBERT requires GPU — not deployed yet"], "metadata": {}}
