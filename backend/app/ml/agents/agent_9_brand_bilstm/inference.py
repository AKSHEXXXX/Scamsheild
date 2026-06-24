import logging

logger = logging.getLogger("scamshield.agent.9.brand.bilstm")

def check_brand(domain: str, brand_name: str = "") -> dict:
    logger.debug("[Agent 9] Siamese BiLSTM — NOT_READY (GPU required)")
    return {"verdict": "error", "score": -1, "reasons": ["Siamese BiLSTM requires GPU — not deployed yet"], "metadata": {}}
