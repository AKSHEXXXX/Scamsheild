import re

RISK_KEYWORDS = [
    # --- Original patterns ---
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
    # --- Legal / financial threats ---
    r"\bfine[sd]?\b",
    r"\bpenalty",
    r"\blegal\s*(?:action|notice|threat|proceeding)",
    r"\bcourt",
    r"\bnotice\s*(?:of|from)",
    r"\barrest",
    r"\binvestigation",
    r"\bcase\s*(?:no|#|number|id|filed|registered)",
    r"\bdocket",
    # --- Government impersonation ---
    r"\bincome\s*tax",
    r"\bcustoms",
    r"\bdepartment",
    r"\bgovernment",
    # --- Order / transaction references ---
    r"\border\s*(?:no|#|number|id)",
    r"\border\s*id",
    r"\btransaction",
    r"\breference\s*(?:no|#|number)",
    r"\binvoice",
    r"\breceipt",
    # --- Payment & billing ---
    r"\bpayment?\s*(?:failed|declined|pending|due|overdue|received)",
    r"\bsubscription",
    r"\boutstanding",
    r"\bdue\s*amount",
    r"\bpending\s*(?:amount|payment|dues)",
    # --- Waiver / settlement ---
    r"\bwaive",
    r"\bsettle",
    r"\bresolve",
    r"\bpay\s*(?:now|today|immediately)",
    # --- Urgency escalation ---
    r"\bwithin\s*\d+",
    r"\bact\s*(?:now|fast|quickly)",
    r"\bdon[\'\u2019]t\s*ignore",
    r"\bfinal\s*(?:notice|warning|reminder)",
    r"\blast\s*(?:chance|call|notice|reminder)",
    # --- Parcel / courier (common Indian scam) ---
    r"\bparcel",
    r"\bcourier",
    r"\bdelivery",
    r"\bshipment",
    r"\bpackage",
    r"\bconsignment",
    # --- KYC extended ---
    r"\bkyc\s*(?:update|fail|expire|pending|verification)",
    # --- Tech support ---
    r"\btech\s*support",
    r"\bremote\s*(?:access|support|login)",
    r"\binstall\s*(?:app|software|anydesk|teamviewer)",
]

def text_risk_analysis(text: str):
    low = text.lower()
    hits = [k for k in RISK_KEYWORDS if re.search(k, low)]
    score = min(100, len(hits) * 20)
    matched = [k.title() for k in hits]
    return score, matched