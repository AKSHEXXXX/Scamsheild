"""
Multilingual text processing for ScamShield agents.
Supports English, Hindi (Devanagari), and Arabic scripts.
"""

import re
import unicodedata
from typing import Literal

# ──────────────────────────────────────────────────────────────────────────────
# Script Detection
# ──────────────────────────────────────────────────────────────────────────────

_SCRIPT_RANGES = {
    "devanagari": (0x0900, 0x097F),  # Hindi
    "arabic": (0x0600, 0x06FF),      # Arabic
    "arabic_ext": (0x0750, 0x077F),  # Arabic Supplement
    "arabic_pres": (0xFB50, 0xFDFF), # Arabic Presentation Forms-A
    "arabic_pres_b": (0xFE70, 0xFEFF), # Arabic Presentation Forms-B
}

# Hinglish common patterns (Roman script Hindi)
_HINGLISH_KEYWORDS = {
    "kyc", "otp", "aadhaar", "pan", "bank", "account", "freeze", "block",
    "verify", "update", "urgent", "immediately", "prize", "lottery", "winner",
    "cashback", "reward", "offer", "limited", "hurry", "expire", "kyc", "link",
    "click", "download", "install", "app", "apk", "upi", "paytm", "phonepe",
    "gpay", "googlepay", "bhim", "refund", "tax", "income", "return", "job",
    "work", "home", "online", "earn", "money", "investment", "guaranteed",
    "double", "triple", "risk", "free", "profit", "loan", "credit", "card",
    "limit", "increase", "preapproved", "instant", "approval", "document",
    "suspend", "deactivate", "permanent", "legal", "action", "court", "police",
    "cyber", "cell", "crime", "arrest", "warrant", "fine", "penalty", "pay",
    "transfer", "deposit", "send", "receive", "approve", "authorize", "otp",
    "share", "forward", "message", "call", "number", "contact", "customer",
    "care", "support", "helpline", "tollfree", "official", "government", "govt",
    "income", "tax", "department", "refund", "due", "pending", "verify", "pan",
    "aadhar", "link", "last", "date", "today", "tomorrow", "immediately",
}

# Arabic scam keywords (transliterated + Arabic script)
_ARABIC_SCAM_KEYWORDS = {
    # Arabic script
    "احتيال", "نصب", "احتيالي", "بنك", "حساب", "بطاقة", "رقم", "سري", "كود",
    "تفعيل", "تحديث", "تحقق", "فوري", "عاجل", "جائزة", "يانصيب", "فائز",
    "مكافأة", "عرض", "محدود", "اسرع", "انتهی", "رابط", "اضغط", "حمل", "تطبيق",
    "ملف", "apk", "استرداد", "ضرائب", "دخل", "إقرار", "وظيفة", "عمل", "منزل",
    "اونلاين", "اكسب", "فلوس", "استثمار", "مضمون", "مضاعف", "ثلاثة", "خطر",
    "مجاني", "ربح", "قرض", "ائتمان", "بطاقة", "حد", "زيادة", "موافقة", "فورية",
    "مستند", "ايقاف", "الغاء", "دائم", "قانوني", "اجراء", "محكمة", "شرطة",
    "سايبر", "جريمة", "قبض", "مذكرة", "غرامة", "عقوبة", "ادفع", "تحويل",
    "ايداع", "ارسل", "استلم", "وافق", "فوض", "كود", "شارك", "ارسل", "رسالة",
    "اتصال", "رقم", "تواصل", "خدمة", "عملاء", "دعم", "خط", "ساخن", "رسمي",
    "حكومة", "ضرائب", "مصلحة", "استرداد", "مستحق", "معلق", "تحقق", "بطاقه",
    "هويه", "رابط", "اخر", "موعد", "اليوم", "غدا", "فورا",
    # Transliterated
    "ihtiyal", "nasb", "bank", "hisab", "bitaqa", "raqam", "sirri", "tawfiq",
    "tahdid", "tahqiq", "fawri", "ajil", "jaiza", "yanasib", "fayiz", "mukafa",
    "ard", "mahdud", "asra", "intiha", "ratab", "idghat", "haml", "tatbiq",
    "malaf", "istirad", "darayib", "dakhal", "iqrar", "wazifa", "amal", "manzil",
    "online", "iksib", "fulus", "istithmar", "madmun", "mudaf", "thalatha", "khatar",
    "mujtani", "ribh", "qard", "aitiman", "bitaqa", "hadd", "ziyada", "mawafaqa",
    "fawriya", "mustanad", "iqaq", "ilgha", "daim", "qanuni", "ijra", "mahkama",
    "shurta", "cyber", "jarima", "qabd", "mudhakkira", "gharama", "uquba", "adfa",
    "hawala", "idwa", "arsal", "istalam", "wafiq", "fawwad", "kawd", "sharik",
    "arsal", "risala", "ittisal", "raqam", "tawasul", "khidma", "wula", "damm",
    "khatt", "sakhun", "rasmi", "hukuma", "darayib", "maslaha", "istirad",
    "mustaq", "mualaq", "tahqiq", "bitaqat", "huwiya", "ratab", "akhir", "mawid",
    "alyawm", "ghadan", "fawran",
}

# Hindi scam keywords (Devanagari + transliterated)
_HINDI_SCAM_KEYWORDS = {
    # Devanagari
    "धोखाधड़ी", "जालसाजी", "बैंक", "खाता", "कार्ड", "नंबर", "गुप्त", "कोड",
    "सक्रिय", "अपडेट", "सत्यापन", "तुरंत", "आवश्यक", "पुरस्कार", "लॉटरी", "विजेता",
    "कैशबैक", "इनाम", "ऑफर", "सीमित", "जल्दी", "समाप्त", "लिंक", "क्लिक", "डाउनलोड",
    "इंस्टॉल", "ऐप", "एपीके", "यूपीआई", "पेटीएम", "फोनपे", "जीपे", "भीम", "रिफंड",
    "टैक्स", "आय", "रिटर्न", "नौकरी", "काम", "घर", "ऑनलाइन", "कमाएं", "पैसा",
    "निवेश", "गारंटी", "दोगुना", "तिगुना", "जोखिम", "मुफ्त", "लाभ", "ऋण", "क्रेडिट",
    "कार्ड", "सीमा", "बढ़ाएं", "पूर्व-स्वीकृत", "तत्काल", "अनुमोदन", "दस्तावेज",
    "निलंबित", "निष्क्रिय", "स्थायी", "कानूनी", "कार्रवाई", "अदालत", "पुलिस",
    "साइबर", "सेल", "अपराध", "गिरफ्तारी", "वारंट", "जुर्माना", "दंड", "भुगतान",
    "स्थानांतरण", "जमा", "भेजें", "प्राप्त करें", "स्वीकृत", "अधिकृत", "ओटीपी",
    "साझा", "अग्रेषित", "संदेश", "कॉल", "नंबर", "संपर्क", "ग्राहक", "सेवा", "सहायता",
    "हेल्पलाइन", "टोलफ्री", "आधिकारिक", "सरकार", "सरकारी", "आय", "कर", "विभाग",
    "रिफंड", "देय", "लंबित", "सत्यापित", "पैन", "आधार", "लिंक", "अंतिम", "तारीख",
    "आज", "कल", "तुरंत",
    # Transliterated
    "dhokhadhadi", "jalasazi", "bank", "khata", "card", "number", "gupt", "code",
    "sakriya", "update", "satyapan", "turant", "avashyak", "puraskar", "lottery",
    "vijeta", "cashback", "inam", "offer", "seemit", "jaldi", "samapt", "link",
    "click", "download", "install", "app", "apk", "upi", "paytm", "phonepe", "gpay",
    "bhim", "refund", "tax", "aay", "return", "naukri", "kaam", "ghar", "online",
    "kamaye", "paisa", "nivesh", "guarantee", "doguna", "tiguna", "jokhim", "muft",
    "labh", "rin", "credit", "card", "seema", "badhaye", "purva-swikrit", "tatkal",
    "anumodan", "dastavez", "nilambit", "nishkriya", "sthayi", "kanooni", "karwai",
    "adalat", "police", "cyber", "cell", "aparadh", "giraftari", "warrant", "jurmana",
    "dand", "bhugtan", "sthanantaran", "jama", "bhejein", "prapt karein", "swikrit",
    "adhikrit", "otp", "sajha", "agresarit", "sandesha", "call", "number", "samprak",
    "grahak", "seva", "sahayata", "helpline", "tollfree", "adhikarik", "sarkar",
    "sarkari", "aay", "kar", "vibhag", "refund", "deya", "lambit", "satyapit",
    "pan", "aadhaar", "link", "antim", "tarikh", "aaj", "kal", "turant",
}

# All scam keywords combined for cross-lingual detection
_ALL_SCAM_KEYWORDS = _HINGLISH_KEYWORDS | _ARABIC_SCAM_KEYWORDS | _HINDI_SCAM_KEYWORDS


def detect_script(text: str) -> set[str]:
    """Detect which scripts are present in the text."""
    scripts = set()
    for ch in text:
        code = ord(ch)
        for script, (start, end) in _SCRIPT_RANGES.items():
            if start <= code <= end:
                scripts.add(script)
                break
        else:
            if ch.isalpha() and code < 0x0300:  # Basic Latin
                scripts.add("latin")
    return scripts


def detect_language(text: str) -> Literal["en", "hi", "ar", "hinglish", "mixed", "unknown"]:
    """
    Detect primary language of text.
    Returns: 'en', 'hi', 'ar', 'hinglish', 'mixed', or 'unknown'
    """
    if not text or not text.strip():
        return "unknown"
    
    scripts = detect_script(text)
    
    # Pure script detection
    if scripts == {"devanagari"}:
        return "hi"
    if scripts == {"arabic"} or scripts == {"arabic_ext"} or scripts == {"arabic_pres"} or scripts == {"arabic_pres_b"}:
        return "ar"
    if scripts == {"latin"}:
        # Check for Hinglish keywords
        words = set(re.findall(r'\b\w+\b', text.lower()))
        hinglish_count = len(words & _HINGLISH_KEYWORDS)
        total_words = len(words)
        if total_words > 0 and hinglish_count / total_words > 0.1:
            return "hinglish"
        return "en"
    
    # Mixed scripts
    if len(scripts) > 1:
        return "mixed"
    
    return "unknown"


def normalize_multilingual(text: str) -> str:
    """
    Normalize text across multiple scripts for consistent processing.
    - NFKC normalization for Unicode
    - Leetspeak decoding for Latin script
    - Preserves VPA, phone, amount, URL tokens
    """
    if not text:
        return ""
    
    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)
    
    # Script-aware tokenization
    tokens = text.split()
    normalized = []
    
    for token in tokens:
        # Preserve structural tokens
        if _is_vpa(token) or _is_phone(token) or _is_amount(token) or _is_url(token):
            normalized.append(token)
            continue
        
        # Detect token script
        token_scripts = detect_script(token)
        
        if "latin" in token_scripts or token_scripts == {"latin"}:
            # Apply leetspeak for Latin tokens
            token = _apply_leetspeak(token)
        # For Devanagari/Arabic, keep as-is (NFKC already normalized)
        
        normalized.append(token)
    
    return " ".join(normalized)


# Token classifiers (copied from text_normalizer for self-contained module)
UPI_RE = re.compile(r"^[\w\.\-]+@[\w\.\-]+$")
PHONE_RE = re.compile(r"^\+?\d[\d\s\-\(\)]{6,}\d$")
AMOUNT_RE = re.compile(r"^(?:Rs\.?|₹|INR)?\s*\d+\.?\d*\s*(?:/?-?\s*\d+\.?\d*)?$", re.IGNORECASE)
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
LEETMAP = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "$": "s", "@": "a", "7": "t", "8": "b"}

def _is_vpa(token: str) -> bool:
    return bool(UPI_RE.match(token)) and "@" in token

def _is_phone(token: str) -> bool:
    return bool(PHONE_RE.match(token))

def _is_amount(token: str) -> bool:
    return bool(AMOUNT_RE.match(token.strip()))

def _is_url(token: str) -> bool:
    return bool(URL_RE.match(token))

def _apply_leetspeak(token: str) -> str:
    return "".join(LEETMAP.get(ch, ch) for ch in token)


def extract_multilingual_keywords(text: str, language: str | None = None) -> set[str]:
    """
    Extract scam-relevant keywords from text in any supported language.
    Returns normalized (lowercase) keywords found.
    """
    if not text:
        return set()
    
    if language is None:
        language = detect_language(text)
    
    # Normalize for matching
    normalized = normalize_multilingual(text).lower()
    words = set(re.findall(r'\b\w+\b', normalized))
    
    # Cross-lingual matching: check against all keyword sets
    found = words & _ALL_SCAM_KEYWORDS
    
    # Also check for partial matches in normalized text
    for kw in _ALL_SCAM_KEYWORDS:
        if len(kw) >= 4 and kw in normalized:
            found.add(kw)
    
    return found


def is_scam_keyword_present(text: str, language: str | None = None) -> bool:
    """Quick check if any scam keyword is present in text."""
    return len(extract_multilingual_keywords(text, language)) > 0


def get_language_specific_patterns(language: str) -> dict:
    """Get regex patterns specific to a language for scam detection."""
    patterns = {}
    
    if language in ("hi", "hinglish", "mixed"):
        patterns["hindi"] = [
            r"(अर्जेंट|अर्जन्ट|जरुरी|जरूरी)",  # urgent
            r"(केवाईसी|के वाय सी|kyc)",  # KYC
            r"(ओटीपी|ओ टी पी|otp)",  # OTP
            r"(आधार|आधार कार्ड|aadhaar|aadhar)",  # Aadhaar
            r"(पैन|पैन कार्ड|pan)",  # PAN
            r"(बैंक|बँक|bank)",  # bank
            r"(खाता|खाते|account)",  # account
            r"(फ्रीज|फ्रीज़|फ्रीझ|freeze|block|ब्लॉक)",  # freeze/block
            r"(सत्यापित|सत्यापन|verify|verification)",  # verify
            r"(पुरस्कार|इनाम|लॉटरी|विजेता|prize|lottery|winner)",  # prize
            r"(कैशबैक|रिवॉर्ड|कैश बैक|cashback|reward)",  # cashback
            r"(डबल|दोगुना|ट्रिपल|double|triple)",  # double/triple
            r"(नौकरी|काम|घर|job|work|home)",  # job
            r"(कमाएं|कमाई|earn|money|पैसा|पैसे)",  # earn money
            r"(निवेश|इन्वेस्टमेंट|investment|गारंटी|guarantee)",  # investment
            r"(लोन|क्रेडिट|loan|credit|कार्ड|card)",  # loan/credit
            r"(सीमा|लिमिट|बढ़ाएं|limit|increase)",  # limit increase
            r"(पूर्व.?स्वीकृत|प्री.?अप्रूव्ड|pre.?approved)",  # pre-approved
            r"(तत्काल|इंस्टेंट|instant|immediate)",  # instant
            r"(दस्तावेज|डॉक्यूमेंट|document)",  # document
            r"(निलंबित|निष्क्रिय|बंद|suspend|deactivate)",  # suspend
            r"(कानूनी|लीगल|legal|कार्रवाई|action)",  # legal action
            r"(अदालत|कोर्ट|court|पुलिस|police)",  # court/police
            r"(साइबर|cyber|सेल|cell|अपराध|crime)",  # cyber crime
            r"(गिरफ्तारी|अरेस्ट|arrest|वारंट|warrant)",  # arrest
            r"(जुर्माना|फाइन|fine|दंड|penalty)",  # fine
            r"(भुगतान|पेमेंट|payment|ट्रांसफर|transfer)",  # payment
            r"(जमा|डिपॉजिट|deposit|भेजें|भेजो|send)",  # deposit/send
            r"(प्राप्त|रिसीव|receive|स्वीकृत|approve)",  # receive/approve
            r"(अधिकृत|अथॉराइज|authorize|ओटीपी|otp)",  # authorize/otp
            r"(साझा|शेयर|share|फॉरवर्ड|forward)",  # share/forward
            r"(संदेश|मैसेज|message|कॉल|call)",  # message/call
            r"(नंबर|नम्बर|number|संपर्क|contact)",  # number/contact
            r"(ग्राहक|कस्टमर|customer|सेवा|सर्विस|service)",  # customer service
            r"(सहायता|हेल्प|help|हेल्पलाइन|helpline)",  # help
            r"(टोल.?फ्री|toll.?free|आधिकारिक|official)",  # tollfree/official
            r"(सरकार|गवर्नमेंट|government|govt)",  # government
            r"(आय|इनकम|income|कर|टैक्स|tax|विभाग|dept)",  # income tax
            r"(रिफंड|refund|देय|देयक|देय राशि|due)",  # refund/due
            r"(लंबित|पेंडिंग|pending|सत्यापित|verify)",  # pending/verify
            r"(पैन|pan|आधार|aadhaar|aadhar|लिंक|link)",  # PAN/Aadhaar/link
            r"(अंतिम|आखरी|last|तारीख|तिथि|date)",  # last date
            r"(आज|aaj|कल|kal|कल|tomorrow|तुरंत|immediately)",  # today/tomorrow/now
        ]
    
    if language in ("ar", "mixed"):
        patterns["arabic"] = [
            r"(عاجل|فوري|عاجلة)",  # urgent
            r"(تحقق|تفعيل|تحديث)",  # verify/activate/update
            r"(بنك|حساب|بطاقة|رقم|سري|كود)",  # bank/account/card/number/secret/code
            r"(جائزة|يانصيب|فائز|مكافأة|عرض|محدود)",  # prize/lottery/winner/reward/offer/limited
            r"(انتهی|انتهت|رابط|اضغط|حمل|تطبيق|ملف)",  # expired/link/click/download/app/file
            r"(استرداد|ضرائب|دخل|إقرار|وظيفة|عمل|منزل)",  # refund/tax/income/return/job/work/home
            r"(اونلاين|اكسب|فلوس|استثمار|مضمون|مضاعف|ثلاثة)",  # online/earn/money/investment/guaranteed/double/triple
            r"(خطر|مجاني|ربح|قرض|ائتمان|بطاقة|حد|زيادة)",  # risk/free/profit/loan/credit/card/limit/increase
            r"(موافقة|فورية|مستند|ايقاف|الغاء|دائم|قانوني)",  # approval/instant/document/stop/cancel/permanent/legal
            r"(اجراء|محكمة|شرطة|سايبر|جريمة|قبض|مذكرة)",  # action/court/police/cyber/crime/arrest/warrant
            r"(غرامة|عقوبة|ادفع|تحويل|ايداع|ارسل|استلم)",  # fine/penalty/pay/transfer/deposit/send/receive
            r"(وافق|فوض|كود|شارك|ارسل|رسالة|اتصال|رقم)",  # approve/authorize/code/share/send/message/call/number
            r"(تواصل|خدمة|عملاء|دعم|خط|ساخن|رسمي|حكومة)",  # contact/service/customers/support/line/hot/official/government
            r"(ضرائب|مصلحة|استرداد|مستحق|معلق|تحقق|بطاقه)",  # taxes/department/refund/due/pending/verify/card
            r"(هويه|رابط|اخر|موعد|اليوم|غدا|فورا)",  # ID/link/last/date/today/tomorrow/now
        ]
    
    # Always include English patterns
    patterns["english"] = [
        r"\b(urgent|immediately|verify|update|kyc|otp|aadhaar|aadhar|pan)\b",
        r"\b(bank|account|card|number|secret|code|freeze|block|suspend)\b",
        r"\b(prize|lottery|winner|cashback|reward|offer|limited|hurry|expire)\b",
        r"\b(link|click|download|install|app|apk|upi|paytm|phonepe|gpay)\b",
        r"\b(refund|tax|income|return|job|work|home|online|earn|money)\b",
        r"\b(investment|guaranteed|double|triple|risk|free|profit|loan|credit)\b",
        r"\b(card|limit|increase|preapproved|instant|approval|document)\b",
        r"\b(deactivate|permanent|legal|action|court|police|cyber|cell|crime)\b",
        r"\b(arrest|warrant|fine|penalty|pay|transfer|deposit|send|receive)\b",
        r"\b(approve|authorize|otp|share|forward|message|call|number|contact)\b",
        r"\b(customer|care|support|helpline|tollfree|official|government|govt)\b",
        r"\b(income|tax|department|refund|due|pending|verify|pan|aadhaar|aadhar)\b",
        r"\b(link|last|date|today|tomorrow|immediately)\b",
    ]
    
    return patterns


# Export all for easy importing
__all__ = [
    "detect_script",
    "detect_language",
    "normalize_multilingual",
    "extract_multilingual_keywords",
    "is_scam_keyword_present",
    "get_language_specific_patterns",
    "_ALL_SCAM_KEYWORDS",
    "_HINGLISH_KEYWORDS",
    "_ARABIC_SCAM_KEYWORDS",
    "_HINDI_SCAM_KEYWORDS",
]