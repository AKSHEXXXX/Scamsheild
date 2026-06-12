import re

RISK_KEYWORDS = [
    r"account blocked",
    r"urgent kyc",
    r"verify now",
    r"lottery",
    r"refund",
    r"otp",
    r"suspended",
    r"click here",
    r"update your",
    r"limited time",
    r"won",
    r"prize",
    r"free",
    r"immediate action",
    r"security alert",
    r"unauthorized",
    r"login",
    r"password",
    r"bank",
    r"credit card",
    r"debit card",
    r"upi",
    r"send money",
    r"scan",
    r"qr code",
    r"customer care",
    r"help line",
    r"toll-free",
    r"claim",
    r"offer",
    r"discount",
    r"gift",
    r"voucher",
    r"cashback",
    r"reward",
    r"points",
    r"expires",
    r"deadline",
    r"warning",
    r"your account",
    r"access",
    r"restricted",
    r"terminated",
]

def text_risk_analysis(text: str):
    low = text.lower()
    hits = [k for k in RISK_KEYWORDS if re.search(k, low)]
    score = min(100, len(hits) * 20)
    matched = [k.title() for k in hits]
    return score, matched