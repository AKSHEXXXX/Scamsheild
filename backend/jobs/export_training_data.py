"""
Export labeled training data from MongoDB scans for model retraining.

Usage:
    python jobs/export_training_data.py [--output-dir ./data] [--only-labeled]

With --only-labeled:
    Only exports rows where the scan has user-submitted feedback labels
    ("scam" or "legit") in the feedback collection. Uses the user label
    as ground truth instead of the model's verdict.

Outputs:
    data/text_training.csv
    data/url_training.csv
    data/upi_training.csv
"""
import os
import sys
import re
import csv
import argparse
from urllib.parse import urlparse
from datetime import datetime, timezone


SUSPICIOUS_TLDS = {".xyz", ".info", ".ltd", ".top", ".cc", ".club", ".work", ".bid", ".loan", ".click", ".download", ".review", ".stream", ".science", ".party", ".racing", ".win", ".date", ".men", ".asia"}


def _get_db():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.database_ext import MongoDBClient
    MongoDBClient.connect()
    return MongoDBClient.db()


def _label_from_verdict(verdict: str) -> int:
    return 1 if verdict in ("high_risk", "SCAM") else 0


def _label_from_feedback(fb_label: str) -> int:
    return 1 if fb_label == "scam" else 0


def _build_feedback_map(db, channels):
    cursor = db.feedback.find(
        {"label": {"$in": ["scam", "legit"]}, "channel": {"$in": channels}},
        {"scan_id": 1, "label": 1, "_id": 0},
    )
    return {doc["scan_id"]: doc["label"] for doc in cursor}


def _export_with_feedback(db, match_filter, projection, output_path, csv_headers, row_builder, feedback_map):
    count = 0
    cursor = db.scans.find(match_filter, projection)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(csv_headers)
        for doc in cursor:
            sid = doc.get("scan_id", "")
            fb_label = feedback_map.get(sid)
            if fb_label:
                label = _label_from_feedback(fb_label)
            else:
                label = _label_from_verdict(doc.get("verdict", ""))
            row = row_builder(doc, label)
            if row:
                w.writerow(row)
                count += 1
    return count


def _export_only_labeled(db, match_filter, projection, output_path, csv_headers, row_builder, feedback_map):
    scan_ids = list(feedback_map.keys())
    if not scan_ids:
        return 0
    count = 0
    cursor = db.scans.find(
        {**match_filter, "scan_id": {"$in": scan_ids}},
        projection,
    )
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(csv_headers)
        for doc in cursor:
            sid = doc.get("scan_id", "")
            fb_label = feedback_map.get(sid)
            if not fb_label:
                continue
            label = _label_from_feedback(fb_label)
            row = row_builder(doc, label)
            if row:
                w.writerow(row)
                count += 1
    return count


def export_text_data(db, output_dir: str, only_labeled: bool = False, feedback_map: dict = None):
    match = {"channel": {"$in": ["text", "sms", "whatsapp", "email", "message"]}}
    proj = {"input_preview": 1, "verdict": 1, "score": 1, "scan_id": 1}
    path = os.path.join(output_dir, "text_training.csv")
    headers = ["text", "label", "score"]

    def builder(doc, label):
        text = (doc.get("input_preview") or "").strip()
        if len(text) < 10:
            return None
        return [text, label, doc.get("score", 0)]

    if only_labeled and feedback_map:
        count = _export_only_labeled(db, match, proj, path, headers, builder, feedback_map)
    else:
        count = _export_with_feedback(db, match, proj, path, headers, builder, feedback_map or {})
    print(f"Exported {count} text samples to {path}")


def _tld_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        parts = domain.split(".")
        if len(parts) >= 2:
            return "." + parts[-1].lower()
    except Exception:
        pass
    return ""


def _has_brand_token(url: str) -> bool:
    brand_tokens = ["google", "facebook", "amazon", "flipkart", "paytm", "phonepe", "whatsapp", "instagram", "netflix", "amazonpay", "gpay", "icici", "hdfc", "sbi", "axisbank", "amex", "visa", "mastercard"]
    lower = url.lower()
    return int(any(b in lower for b in brand_tokens))


def _url_features(url: str) -> dict:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path + parsed.query
    return {
        "url_length": len(url),
        "domain_length": len(domain),
        "num_subdomains": domain.count(".") - 1 if domain.count(".") > 1 else 0,
        "path_length": len(path),
        "num_special_chars": sum(1 for c in url if c in "=?-&_~%"),
        "has_ip": int(bool(re.search(r"\d+\.\d+\.\d+\.\d+", domain))),
        "has_suspicious_tld": int(_tld_from_url(url) in SUSPICIOUS_TLDS),
        "has_brand_token": _has_brand_token(url),
        "tld": _tld_from_url(url),
    }


def export_url_data(db, output_dir: str, only_labeled: bool = False, feedback_map: dict = None):
    match = {"$or": [
        {"channel": "url"},
        {"channel": {"$in": ["text", "sms", "whatsapp", "email", "message"]}, "input_preview": {"$regex": "https?://"}},
        {"channel": "qr", "input_preview": {"$regex": "https?://"}},
    ]}
    proj = {"input_preview": 1, "verdict": 1, "score": 1, "scan_id": 1}
    path = os.path.join(output_dir, "url_training.csv")
    headers = ["url", "label", "score", "tld", "url_length", "num_subdomains", "has_suspicious_tld", "has_brand_token"]

    def builder(doc, label):
        url = (doc.get("input_preview") or "").strip()
        if not url.startswith("http"):
            return None
        feats = _url_features(url)
        return [
            url, label, doc.get("score", 0),
            feats.get("tld", ""), feats.get("url_length", 0),
            feats.get("num_subdomains", 0),
            feats.get("has_suspicious_tld", 0),
            feats.get("has_brand_token", 0),
        ]

    if only_labeled and feedback_map:
        count = _export_only_labeled(db, match, proj, path, headers, builder, feedback_map)
    else:
        count = _export_with_feedback(db, match, proj, path, headers, builder, feedback_map or {})
    print(f"Exported {count} URL samples to {path}")


def export_upi_data(db, output_dir: str, only_labeled: bool = False, feedback_map: dict = None):
    match = {"channel": "upi"}
    proj = {"input_preview": 1, "verdict": 1, "score": 1, "result": 1, "scan_id": 1}
    path = os.path.join(output_dir, "upi_training.csv")
    headers = ["note", "label", "score"]

    def builder(doc, label):
        note = (doc.get("input_preview") or "").strip()
        if len(note) < 5:
            return None
        return [note, label, doc.get("score", 0)]

    if only_labeled and feedback_map:
        count = _export_only_labeled(db, match, proj, path, headers, builder, feedback_map)
    else:
        count = _export_with_feedback(db, match, proj, path, headers, builder, feedback_map or {})
    print(f"Exported {count} UPI samples to {path}")


def main():
    parser = argparse.ArgumentParser(description="Export training data from MongoDB")
    parser.add_argument("--output-dir", default="data", help="Output directory for CSV files")
    parser.add_argument("--only-labeled", action="store_true", help="Only export rows with user feedback labels")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    db = _get_db()
    if db is None:
        print("FATAL: MongoDB not connected")
        sys.exit(1)

    feedback_map = {}
    if args.only_labeled:
        feedback_map = _build_feedback_map(db, ["text", "sms", "whatsapp", "email", "message", "url", "qr", "upi"])
        print(f"Found {len(feedback_map)} scans with user feedback labels")

    export_text_data(db, args.output_dir, args.only_labeled, feedback_map)
    export_url_data(db, args.output_dir, args.only_labeled, feedback_map)
    export_upi_data(db, args.output_dir, args.only_labeled, feedback_map)
    print(f"Training data export complete — files in {args.output_dir}/")


if __name__ == "__main__":
    main()
