import asyncio
import base64
import csv
import io
import json
import logging
import os
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from utils.slack_alerts import send_slack
from jobs.quality_gate import quality_gate

logger = logging.getLogger("scamshield.colab_retrainer")

GDRIVE_TRIGGER_FILE_NAME = os.getenv("GDRIVE_TRIGGER_FILE_NAME", "retrain_trigger.json")
GDRIVE_ARTIFACTS_FOLDER_ID = os.getenv("GDRIVE_ARTIFACTS_FOLDER_ID", "")
GDRIVE_TRAINING_DATA_FOLDER_ID = os.getenv("GDRIVE_TRAINING_DATA_FOLDER_ID", "")


def _get_drive_service():
    sa_json = json.loads(base64.b64decode(os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")))
    creds = service_account.Credentials.from_service_account_info(
        sa_json, scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)


async def trigger_colab_retraining(batch_records: list):
    if not GDRIVE_ARTIFACTS_FOLDER_ID or not GDRIVE_TRAINING_DATA_FOLDER_ID:
        logger.warning("Drive folder IDs not configured — skipping retraining")
        return False

    drive = _get_drive_service()

    tmp_csv = "/tmp/retrain_batch.csv"
    with open(tmp_csv, "w", newline="") as f:
        if batch_records:
            writer = csv.DictWriter(f, fieldnames=batch_records[0].keys())
            writer.writeheader()
            writer.writerows(batch_records)

    media = MediaFileUpload(tmp_csv, mimetype="text/csv")
    drive.files().create(
        body={"name": "retrain_batch.csv",
              "parents": [GDRIVE_TRAINING_DATA_FOLDER_ID]},
        media_body=media).execute()
    logger.info("Uploaded retrain_batch.csv (%d records)", len(batch_records))

    trigger_content = json.dumps({
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(batch_records),
        "status": "pending",
    }).encode()
    media_trigger = MediaFileUpload(
        io.BytesIO(trigger_content), mimetype="application/json", resumable=False)
    drive.files().create(
        body={"name": GDRIVE_TRIGGER_FILE_NAME,
              "parents": [GDRIVE_TRAINING_DATA_FOLDER_ID]},
        media_body=media_trigger).execute()
    logger.info("Uploaded trigger file %s", GDRIVE_TRIGGER_FILE_NAME)

    TIMEOUT = 7200
    POLL_INTERVAL = 60
    elapsed = 0
    while elapsed < TIMEOUT:
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        results = drive.files().list(
            q=f"name='training_complete.json' and "
              f"'{GDRIVE_ARTIFACTS_FOLDER_ID}' in parents",
            fields="files(id, name)").execute()
        files = results.get("files", [])
        if files:
            file_id = files[0]["id"]
            request = drive.files().get_media(fileId=file_id)
            buf = io.BytesIO()
            MediaIoBaseDownload(buf, request).next_chunk()
            result = json.loads(buf.getvalue())

            drive.files().delete(fileId=file_id).execute()

            try:
                for old_file in drive.files().list(
                    q=f"name='retrain_batch.csv' and "
                      f"'{GDRIVE_TRAINING_DATA_FOLDER_ID}' in parents",
                    fields="files(id)").execute().get("files", []):
                    drive.files().delete(fileId=old_file["id"]).execute()
            except Exception:
                pass

            try:
                for old_file in drive.files().list(
                    q=f"name='{GDRIVE_TRIGGER_FILE_NAME}' and "
                      f"'{GDRIVE_TRAINING_DATA_FOLDER_ID}' in parents",
                    fields="files(id)").execute().get("files", []):
                    drive.files().delete(fileId=old_file["id"]).execute()
            except Exception:
                pass

            if result.get("status") == "complete":
                return await quality_gate(result)
            else:
                await send_slack(
                    f"⚠️ Colab training failed: {result.get('error', 'unknown error')}")
                return False

    await send_slack(
        "⚠️ Colab retraining TIMEOUT after 2hrs. Manual check required.")
    return False
