import json
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("download_models")

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "app" / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
VERSION_FILE = ARTIFACT_DIR / ".manifest_version"


def download_public_url(name: str, url: str):
    import httpx
    dest = ARTIFACT_DIR / name
    logger.info("Downloading %s from %s ...", name, url)
    r = httpx.get(url, timeout=300, follow_redirects=True)
    r.raise_for_status()
    dest.write_bytes(r.content)
    logger.info("Downloaded %s (%d bytes)", name, len(r.content))


def download_s3(name: str, bucket: str, key: str, endpoint: str, access_key: str, secret_key: str, region: str):
    import boto3
    dest = ARTIFACT_DIR / name
    logger.info("Downloading s3://%s/%s ...", bucket, key)
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    client = session.client("s3", endpoint_url=endpoint if endpoint != "aws" else None)
    client.download_file(bucket, key, str(dest))
    logger.info("Downloaded %s", name)


def unzip_file(zip_name: str):
    import zipfile
    zip_path = ARTIFACT_DIR / zip_name
    extract_to = ARTIFACT_DIR / zip_name.replace(".zip", "")
    logger.info("Extracting %s ...", zip_name)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)
    zip_path.unlink()
    logger.info("Extracted to %s", extract_to)


def main():
    manifest_url = os.environ.get("MODEL_DOWNLOAD_URL", "")
    if not manifest_url:
        logger.info("MODEL_DOWNLOAD_URL not set — skipping model download")
        return

    logger.info("Fetching manifest from %s", manifest_url)
    import httpx
    resp = httpx.get(manifest_url, timeout=30)
    resp.raise_for_status()
    manifest = resp.json()

    manifest_version = manifest.get("version", "")
    cached_version = VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else ""

    if manifest_version and manifest_version == cached_version:
        logger.info("Manifest version %s already deployed — skipping download", manifest_version)
        return

    access_key = os.environ.get("MODEL_DOWNLOAD_KEY", "")
    secret_key = os.environ.get("MODEL_DOWNLOAD_SECRET", "")
    region = os.environ.get("MODEL_DOWNLOAD_REGION", "auto")

    for entry in manifest.get("files", []):
        name = entry["name"]
        source = entry.get("source", "url")
        if source == "s3":
            download_s3(
                name=name,
                bucket=entry["bucket"],
                key=entry["key"],
                endpoint=entry.get("endpoint", "aws"),
                access_key=access_key,
                secret_key=secret_key,
                region=region,
            )
        else:
            download_public_url(name, entry["url"])

    for name in manifest.get("unzip", []):
        zip_path = ARTIFACT_DIR / name
        if zip_path.exists():
            unzip_file(name)

    if manifest_version:
        VERSION_FILE.write_text(manifest_version)
        logger.info("Cached manifest version %s", manifest_version)

    logger.info("All models downloaded successfully")


if __name__ == "__main__":
    main()
