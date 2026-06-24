"""
Build suite v2 from real labeled examples in Mongo.

Reads scans + feedback, buckets by content pattern, applies the 20-minimum
freeze rule, and writes a versioned JSON suite under tests/suites/v2/.

Usage:
    python jobs/build_suite_v2.py
"""
import os, sys, json, re
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "suites" / "v2"
MAX_PER_BUCKET = 30
MIN_PER_BUCKET = 20

BUCKETS = [
    {
        "name": "banking_kyc_link",
        "patterns": [
            r"\bkyc\b", r"\baadhaar\b", r"\bpan\s*(card|number)?\b",
            r"\bdebit\s*card\b", r"\bcredit\s*card\b", r"\baccount\s*(block|suspend|expire)",
            r"\bupdate.*(pan|kyc|aadhaar)", r"\b(icici|hdfc|sbi|axis|kotak).*login",
            r"\bpaypal\b", r"\bnet\s*banking\b",
        ],
    },
    {
        "name": "delivery_scams",
        "patterns": [
            r"\b(fedex|dhl|ups|usps|india\s*post|speed\s*post)\b",
            r"\b(customs|clearance|import\s*fee|shipping\s*fee)",
            r"\bpackage.*(delay|hold|fee|pay)", r"\bdelivery.*(fee|pay|confirm)",
        ],
    },
    {
        "name": "job_scams",
        "patterns": [
            r"\bwork\s*from\s*home\b", r"\bdata\s*entry\b",
            r"\bearn\s*(per|every|a\s*day|money|cash)", r"\bpart\s*time\b",
            r"\bno\s*experience\b", r"\bflexible\s*hours?\b",
            r"\bonline\s*(job|work|earning)", r"\bridge\s*global\b",
            r"\btelecommute\b", r"\bhome\s*based\b",
            r"\bdaily\s*(payout|salary|income|earning)",
            r"\bregister.*(free|now|today).*(earn|work)",
        ],
    },
    {
        "name": "investment_crypto",
        "patterns": [
            r"\binvestment?\b", r"\bcrypto\b", r"\bbitcoin\b",
            r"\bguaranteed\s*returns?\b", r"\bsignal\s*group\b",
            r"\bstock[s]?\s*tip[s]?\b", r"\bforex\b", r"\btrading\b",
            r"\b(high|huge|massive).*returns?\b",
            r"\bdouble.*(money|investment)", r"\bpassive\s*income\b",
        ],
    },
    {
        "name": "upi_scams",
        "patterns": [
            r"\b(double|triple).*money\b", r"\brefund\b",
            r"\bcashback\b", r"\bupi.*(limit|update|verify)",
            r"\bcollect.*(request|money|payment)",
            r"\bscan.*(qr|pay)", r"\b(google\s*pay|gpay|phonepe|paytm).*(cash|prize|win)",
        ],
    },
    {
        "name": "romance_emotional",
        "patterns": [
            r"\blove\b", r"\b(romance|dating|match|matrimonial)",
            r"\bsoulmate\b", r"\bforeign.*(lover|friend|soldier|army)",
            r"\bgift\s*(card|coupon|voucher).*(love|send)",
        ],
        "placeholder": True,
    },
    {
        "name": "benign_transactional",
        "patterns": [
            r"\botp\b", r"\bbill\s*(payment|due|receipt)",
            r"\b(statement|transaction).*successful\b",
            r"\b(amount|rs\.?|₹)\s*\d+.*(debited|credited)",
            r"\bthank\s*you\s*for\s*your\s*purchase\b",
            r"\breceipt\b", r"\bpayment\s*(received|done|successful)",
        ],
        "label_filter": "legit",
    },
    {
        "name": "benign_chats",
        "patterns": [
            r"\bmeeting\b", r"\blunch\b", r"\b(catch|talk)\s*(up|soon|later)",
            r"\b(see|call)\s*you\b", r"\bhow\s*are\s*you\b",
            r"\b(ok|okay|sure|fine|great)", r"\b(tomorrow|today|evening|morning)\b",
            r"\bfamily\b", r"\bfriend\b", r"\b(coming|reached|reaching)\b",
        ],
        "label_filter": "legit",
    },
    {
        "name": "benign_urls",
        "patterns": [
            r"https?://(www\.)?(google|amazon|flipkart|youtube|github|stackoverflow|medium|wikipedia)",
            r"https?://.*\.(gov\.in|org|edu)(/|$)",
            r"(news|blog|article|recipe|tutorial)",
        ],
        "label_filter": "legit",
    },
    {
        "name": "unicode_leet",
        "patterns": [
            r"[^\x00-\x7F]",  # any non-ASCII
            r"[0@$£€§]", r"[α-ωΑ-Ωа-яА-Я]", r"𝓯𝓻𝓮𝓮",
            r"[\U0001d400-\U0001d419\U0001d41a-\U0001d433]",
            r"[\U0001d468-\U0001d481\U0001d482-\U0001d49b]",
            r"[\U0001d504-\U0001d50d\U0001d50e-\U0001d51c\U0001d51e-\U0001d537]",
            r"[\u0300-\u036f]", r"[\u1d00-\u1d7f]",
        ],
    },
    {
        "name": "digital_arrest",
        "patterns": [
            r"\barrest\b", r"\bwarrant\b", r"\bcyber\s?cell\b",
            r"\bdigital\s?arrest\b", r"\blegal\s?notice\b",
            r"\b(aadhaar|pan).{0,20}(illegal|fraud|block|suspend)\b",
            r"\bmoney.?launder\b",
        ],
    },
]


def _get_db():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.database_ext import MongoDBClient
    MongoDBClient.connect()
    return MongoDBClient.db()


def _match_bucket(bucket: dict, text: str) -> bool:
    for p in bucket["patterns"]:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


SEED_PATH = OUTPUT_DIR / "suite_v2_seed.json"


def _load_seeds() -> dict:
    if not SEED_PATH.exists():
        return {}
    with open(SEED_PATH) as f:
        data = json.load(f)
    seeds = {}
    for entry in data.get("seeds", []):
        seeds[entry["bucket"]] = entry["samples"]
    return seeds


def build():
    db = _get_db()
    if db is None:
        print("FATAL: MongoDB not connected")
        sys.exit(1)

    label_filter = db.feedback.distinct("scan_id", {"label": {"$in": ["scam", "legit"]}})
    cursor = db.scans.find(
        {"scan_id": {"$in": label_filter}},
        {"scan_id": 1, "input_preview": 1, "channel": 1, "verdict": 1, "score": 1},
    )
    scans_by_id = {}
    for doc in cursor:
        scans_by_id[doc["scan_id"]] = doc

    fb_cursor = db.feedback.find(
        {"label": {"$in": ["scam", "legit"]}, "scan_id": {"$in": list(scans_by_id.keys())}},
        {"scan_id": 1, "label": 1, "reason": 1},
    )
    fb_by_scan = {}
    for fb in fb_cursor:
        sid = fb["scan_id"]
        fb_by_scan.setdefault(sid, []).append(fb)

    seeds = _load_seeds()
    suite = []
    skipped_buckets = []
    for bucket in BUCKETS:
        name = bucket["name"]
        label_filter_val = bucket.get("label_filter")
        matches = []
        for sid, scan in scans_by_id.items():
            text = scan.get("input_preview", "") or ""
            if not text:
                continue
            if not _match_bucket(bucket, text):
                continue
            fbs = fb_by_scan.get(sid, [])
            if not fbs:
                continue
            for fb in fbs:
                if label_filter_val and fb["label"] != label_filter_val:
                    continue
                matches.append({
                    "scan_id": sid,
                    "channel": scan.get("channel", "unknown"),
                    "text": text[:300],
                    "verdict": scan.get("verdict", "unknown"),
                    "score": scan.get("score", -1),
                    "feedback_label": fb["label"],
                    "feedback_reason": (fb.get("reason") or "")[:200],
                })
                break

        total = len(matches)
        if total < MIN_PER_BUCKET:
            seed_samples = seeds.get(name, [])
            if seed_samples:
                matches = []
                for s in seed_samples:
                    matches.append({
                        "scan_id": "seed",
                        "channel": s.get("channel", "unknown"),
                        "text": s["text"][:300],
                        "verdict": s.get("verdict", "unknown"),
                        "score": s.get("score", -1),
                        "feedback_label": s.get("label", "scam"),
                        "feedback_reason": "seed example",
                    })
                total = len(matches)
                print(f"  {name}: using {total} seed examples (no real feedback samples)")
            else:
                skipped_buckets.append({"bucket": name, "found": total})
                continue

        selected = matches[:MAX_PER_BUCKET]
        entry = {
            "bucket": name,
            "description": bucket.get("description", ""),
            "total_available": total,
            "samples": selected,
        }
        suite.append(entry)
        print(f"  {name}: {len(selected)} samples (of {total} available)")

    suite_doc = {
        "suite_version": "v2.0",
        "built_at": datetime.now(timezone.utc).isoformat() + "Z",
        "total_buckets": len(suite),
        "total_samples": sum(len(b["samples"]) for b in suite),
        "buckets": suite,
        "skipped_buckets": skipped_buckets,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "suite_v2.json"
    with open(path, "w") as f:
        json.dump(suite_doc, f, indent=2, default=str)
    print(f"\nSuite v2 written to {path}")
    print(f"  Buckets: {len(suite)} (skipped {len(skipped_buckets)})")
    print(f"  Total samples: {suite_doc['total_samples']}")
    if skipped_buckets:
        print(f"  Skipped (below {MIN_PER_BUCKET}): {[s['bucket'] for s in skipped_buckets]}")


if __name__ == "__main__":
    build()
