import logging

logger = logging.getLogger("scamshield.agent.13.call.logreg")

def predict_text(text: str) -> dict:
    logger.debug("[Agent 13] Call Transcript LR — NOT_READY (no artifacts deployed)")
    return {"verdict": "error", "score": -1, "reasons": ["Call Transcript LR artifacts not yet deployed"], "metadata": {}}
