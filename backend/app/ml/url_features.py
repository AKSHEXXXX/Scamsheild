"""Single source of truth for Agent 3 (URL phishing) feature extraction.

Both the training pipeline (``training/train_url_model.py``) and the two
inference entry points (``url_model.predict_url_risk`` and
``agents.inference.agent3_predict_url``) import ``extract_url_features`` from
here so that training and serving compute *identical* features. Previously the
two inference paths had diverging hand-rolled implementations, which produced a
train/serve skew that turned Agent 3's ensemble contribution into noise.

Design rules:

* **No label-derived features.** ``TLDLegitimateProb`` and ``URLCharProb`` from
  the PhiUSIIL dataset are computed from the training labels (target leakage)
  and are deliberately excluded. Every feature below is a pure function of the
  URL string.
* **Deterministic and offline.** Only the URL text is used — no network calls,
  no page-content features.
"""

import re
from urllib.parse import urlparse

import tldextract

# Ordered list of the features this module emits. The persisted
# ``url_feature_cols.pkl`` must match this exactly; the training script writes
# it from ``FEATURE_COLUMNS`` so the two can never drift.
FEATURE_COLUMNS = [
    "URLLength",
    "DomainLength",
    "TLDLength",
    "NoOfSubDomain",
    "PathLength",
    "NoOfEqualsInURL",
    "NoOfQMarkInURL",
    "NoOfAmpersandInURL",
    "NoOfDigitsInURL",
    "DigitRatioInURL",
    "CharContinuationRate",
    "HasIPAddress",
    "IsHTTPS",
]

_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def _char_continuation_rate(url: str) -> float:
    """Longest run of consecutive alphabetic characters, normalised by length.

    Phishing URLs tend to break up words with digits/punctuation, lowering this
    ratio. Defined once here so training and serving agree.
    """
    if len(url) <= 1:
        return 0.0
    longest = 0
    current = 0
    for ch in url:
        if ch.isalpha():
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return round(longest / len(url), 4)


def extract_url_features(url: str) -> dict:
    """Extract the leakage-free URL feature dict used by Agent 3.

    Returns a dict keyed by :data:`FEATURE_COLUMNS`. Robust to URLs with or
    without an explicit scheme.
    """
    url = (url or "").strip()
    has_scheme = bool(_SCHEME_RE.match(url))
    parsed = urlparse(url if has_scheme else "http://" + url)

    host = parsed.hostname or ""
    ext = tldextract.extract(url if has_scheme else "http://" + url)
    domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
    subdomain = ext.subdomain or ""

    path = (parsed.path or "") + (parsed.query or "")
    digits = sum(c.isdigit() for c in url)
    length = max(len(url), 1)

    return {
        "URLLength": len(url),
        "DomainLength": len(domain),
        "TLDLength": len(ext.suffix or ""),
        "NoOfSubDomain": len([p for p in subdomain.split(".") if p]) if subdomain else 0,
        "PathLength": len(path),
        "NoOfEqualsInURL": url.count("="),
        "NoOfQMarkInURL": url.count("?"),
        "NoOfAmpersandInURL": url.count("&"),
        "NoOfDigitsInURL": digits,
        "DigitRatioInURL": round(digits / length, 4),
        "CharContinuationRate": _char_continuation_rate(url),
        "HasIPAddress": 1 if _IP_RE.match(host) else 0,
        "IsHTTPS": 1 if (has_scheme and parsed.scheme == "https") else 0,
    }
