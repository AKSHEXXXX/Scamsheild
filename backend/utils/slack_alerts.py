import httpx
import os

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

async def send_slack(message: str, channel: str = "#ml-alerts"):
    if not SLACK_WEBHOOK_URL:
        print(f"[SLACK SKIPPED] {message}")
        return
    async with httpx.AsyncClient() as client:
        await client.post(SLACK_WEBHOOK_URL,
            json={"text": message, "channel": channel})
