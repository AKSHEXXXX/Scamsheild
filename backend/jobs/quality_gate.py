import logging
from utils.slack_alerts import send_slack

logger = logging.getLogger("scamshield.quality_gate")

F1_THRESHOLD = 0.94
AUC_THRESHOLD = 0.95

async def quality_gate(colab_result: dict) -> bool:
    f1 = colab_result.get("f1", 0)
    auc = colab_result.get("auc", 0)

    if f1 >= F1_THRESHOLD and auc >= AUC_THRESHOLD:
        await send_slack(
            f"✅ Quality gate PASSED. F1={f1:.4f} AUC={auc:.4f}. Promoting...")
        return True

    await send_slack(
        f"⚠️ Model promotion ABORTED. "
        f"F1={f1:.4f} (need {F1_THRESHOLD}), "
        f"AUC={auc:.4f} (need {AUC_THRESHOLD})")
    return False
