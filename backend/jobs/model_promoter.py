import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("scamshield.model_promoter")

_s3_client = None


def _get_s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client = boto3.client("s3",
            endpoint_url=os.getenv("R2_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("R2_SECRET_KEY"))
    return _s3_client


async def promote_model(colab_result: dict):
    s3 = _get_s3()
    bucket = os.getenv("R2_BUCKET_NAME")

    obj = s3.get_object(Bucket=bucket, Key="manifest.json")
    manifest = json.loads(obj["Body"].read())

    s3.put_object(Bucket=bucket,
                  Key="manifest_prev.json",
                  Body=json.dumps(manifest))

    parts = manifest["version"].split(".")
    parts[2] = str(int(parts[2]) + 1)
    manifest["version"] = ".".join(parts)

    for artifact in colab_result.get("artifacts", []):
        agent_name = artifact.split("_v")[0]
        if agent_name in manifest.get("agents", {}):
            manifest["agents"][agent_name]["artifact"] = f"models/{artifact}"
            manifest["agents"][agent_name]["status"] = "ready"

    try:
        s3.put_object(Bucket=bucket,
                      Key="manifest.json",
                      Body=json.dumps(manifest))
    except Exception as e:
        s3.copy_object(Bucket=bucket,
                       CopySource={"Bucket": bucket, "Key": "manifest_prev.json"},
                       Key="manifest.json")
        from utils.slack_alerts import send_slack
        await send_slack(f"🔴 Manifest rollback triggered: {e}")
        return

    from utils.slack_alerts import send_slack
    n = len(colab_result.get("artifacts", []))

    try:
        from app.database_ext import MongoDBClient
        db = MongoDBClient.db()
        if db is not None:
            db.retrain_log.insert_one({
                "timestamp": datetime.now(timezone.utc),
                "version": manifest["version"],
                "f1": colab_result.get("f1"),
                "auc": colab_result.get("auc"),
                "artifacts_updated": colab_result.get("artifacts", []),
                "triggered_by_count": 500,
            })
    except Exception as e:
        logger.warning("Failed to log retrain entry to MongoDB: %s", e)

    await send_slack(
        f"✅ Models promoted to v{manifest['version']}. "
        f"F1={colab_result.get('f1', 0):.4f} AUC={colab_result.get('auc', 0):.4f}. "
        f"{n} agents updated.")
