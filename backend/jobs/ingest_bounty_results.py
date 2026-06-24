"""
Ingest bounty test result JSON files into Mongo bounty_results collection.

Usage:
    python jobs/ingest_bounty_results.py [--file output/bounty_*.json] [--dir output/]
"""
import os, sys, json, glob, argparse
from datetime import datetime, timezone
from pathlib import Path


def _get_db():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.database_ext import MongoDBClient
    MongoDBClient.connect()
    return MongoDBClient.db()


def ingest_one(db, filepath: str) -> dict:
    with open(filepath) as f:
        data = json.load(f)
    doc = {
        "deployment_id": data.get("deployment_id", "unknown"),
        "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "pass_count": data.get("pass_count", 0),
        "fail_count": data.get("fail_count", 0),
        "total": data.get("total", 0),
        "failures_by_category": data.get("failures_by_category", {}),
        "elapsed_seconds": data.get("elapsed_seconds", 0),
    }
    db.bounty_results.update_one(
        {"deployment_id": doc["deployment_id"], "timestamp": doc["timestamp"]},
        {"$set": doc},
        upsert=True,
    )
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Single JSON result file")
    parser.add_argument("--dir", default="output", help="Directory containing bounty_*.json files")
    args = parser.parse_args()

    db = _get_db()
    if db is None:
        print("FATAL: MongoDB not connected")
        sys.exit(1)

    files = []
    if args.file:
        files = [args.file]
    else:
        files = sorted(glob.glob(os.path.join(args.dir, "bounty_*.json")))

    if not files:
        print(f"No bounty result files found in {args.dir}")
        sys.exit(1)

    total = 0
    for fp in files:
        doc = ingest_one(db, fp)
        total += 1
        ratio = doc["pass_count"] / max(doc["total"], 1) * 100
        print(f"  [{doc['deployment_id'][:12]}] {doc['pass_count']}/{doc['total']} pass ({ratio:.0f}%)")

    print(f"\nIngested {total} result(s) into Mongo bounty_results")


if __name__ == "__main__":
    main()
