"""CustomScamFlags transformer – must be importable for pickle loading."""
import re
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

SCAM_FLAG_PATTERNS = {
    "contains_url": re.compile(r"https?://", re.I),
    "contains_upi_id": re.compile(r"[\w.+-]+@[\w.]+", re.I),
    "contains_phone": re.compile(r"\b\d{10}\b"),
    "contains_amount": re.compile(r"(?:rs\.?\s*|inr\s*|\u20b9\s*)?\d+(?:\.\d+)?", re.I),
}
URGENCY_WORDS = {"urgent", "immediately", "action required", "suspended", "blocked", "expire", "warning", "alert", "security alert", "account suspended"}
PRIZE_WORDS = {"won", "winner", "prize", "reward", "cashback", "gift", "lottery", "free", "claim", "congratulations"}
KYC_OTP_WORDS = {"kyc", "otp", "update", "verify", "verification", "aadhaar", "pan", "bank", "account"}

class CustomScamFlags(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.feature_names_ = [
            "contains_url", "contains_upi_id", "contains_phone", "contains_amount",
            "urgency_count", "prize_count", "kyc_otp_count",
            "message_len", "digit_count", "exclamation_count",
        ]
    def fit(self, X, y=None):
        return self
    def transform(self, X):
        out = np.zeros((len(X), len(self.feature_names_)), dtype=np.float64)
        for i, text in enumerate(X):
            out[i, 0] = 1 if SCAM_FLAG_PATTERNS["contains_url"].search(text) else 0
            out[i, 1] = 1 if SCAM_FLAG_PATTERNS["contains_upi_id"].search(text) else 0
            out[i, 2] = 1 if SCAM_FLAG_PATTERNS["contains_phone"].search(text) else 0
            out[i, 3] = 1 if SCAM_FLAG_PATTERNS["contains_amount"].search(text) else 0
            out[i, 4] = sum(1 for w in URGENCY_WORDS if w in text.lower())
            out[i, 5] = sum(1 for w in PRIZE_WORDS if w in text.lower())
            out[i, 6] = sum(1 for w in KYC_OTP_WORDS if w in text.lower())
            out[i, 7] = len(text)
            out[i, 8] = sum(c.isdigit() for c in text)
            out[i, 9] = text.count("!")
        return out
    def get_feature_names_out(self, input_features=None):
        return np.array(self.feature_names_)
