import re, json, math
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import numpy as np

try:
    import tldextract
except Exception:
    tldextract = None
try:
    import qrcode
except Exception:
    qrcode = None
try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

SHORTENER_DOMAINS = {
    'bit.ly','tinyurl.com','t.co','goo.gl','ow.ly','is.gd','buff.ly','cutt.ly',
    'rebrand.ly','rb.gy','s.id','shorturl.at','lnkd.in','bitly.com','qrco.de','q-r.to','qr1.be'
}

BRANDS = {
    'google':['google','gmail','gpay'], 'phonepe':['phonepe'], 'paytm':['paytm'],
    'amazon':['amazon'], 'flipkart':['flipkart'], 'apple':['apple','icloud'],
    'microsoft':['microsoft','office','outlook'], 'facebook':['facebook','meta'],
    'instagram':['instagram'], 'whatsapp':['whatsapp'], 'hdfc':['hdfc'],
    'icici':['icici'], 'sbi':['sbi'], 'axis':['axisbank','axis'], 'kotak':['kotak'],
    'yesbank':['yesbank','yes-bank'], 'bank':['bank']
}

SCAM_KEYWORDS = {
    'urgent','immediately','verify','blocked','suspended','limited','kyc','update kyc',
    'account locked','password','otp','pin','reward','cashback','prize','winner','claim',
    'lottery','refund','gift','free','click','login','secure your account','reactivate',
    'unauthorized','risk','payment failed','collect request','approve','expire','expires'
}
URGENCY_WORDS = {'urgent','now','immediately','today','within','expires','expire','limited time','last chance','blocked','suspended'}
SUSPICIOUS_TOKENS = {'login','verify','secure','account','update','banking','wallet','kyc','otp','bonus','free','gift','claim','auth','signin','password','support','customer-care','refund'}
LEGIT_UPI_HANDLES = {'okaxis','okhdfcbank','okicici','oksbi','ybl','ibl','axl','paytm','ptsbi','pthdfc','ptaxis','upi'}

FEATURE_ORDER = [
    'payload_len', 'payload_entropy', 'payload_digit_count', 'payload_alpha_count',
    'payload_special_count', 'payload_space_count', 'payload_non_ascii_count',
    'payload_type_url', 'payload_type_upi', 'payload_type_plain_text',
    'payload_type_vcard', 'payload_type_phone', 'payload_type_email',
    'qr_version_estimate', 'qr_error_correction_level_num', 'url_len',
    'url_domain_len', 'url_tld_len', 'url_subdomain_count', 'url_path_len',
    'url_query_len', 'url_num_query_params', 'url_has_https', 'url_has_ip',
    'url_num_dots', 'url_num_hyphens', 'url_num_digits', 'url_num_at',
    'url_num_question', 'url_num_ampersand', 'url_num_equals', 'url_num_percent',
    'url_is_shortened', 'url_suspicious_token_count', 'url_suspicious_token_density',
    'url_brand_mentioned', 'url_brand_domain_mismatch', 'url_punycode',
    'url_port_present', 'upi_present', 'upi_vpa_present', 'upi_vpa_handle_known',
    'upi_vpa_handle_unknown', 'upi_amount_present', 'upi_amount_value',
    'upi_amount_high', 'upi_payee_name_present', 'upi_transaction_note_suspicious',
    'upi_collect_like', 'upi_param_count', 'text_scam_keyword_count',
    'text_scam_keyword_density', 'text_urgency_score', 'text_contains_otp',
    'text_contains_phone', 'text_contains_email', 'text_contains_currency',
    'vcard_field_count', 'brand_name_count', 'short_url_count'
]

def _safe_str(x):
    if x is None: return ''
    return str(x).strip()

def shannon_entropy(s: str) -> float:
    s = _safe_str(s)
    if not s: return 0.0
    probs = [float(s.count(c)) / len(s) for c in set(s)]
    return -sum(p * math.log(p, 2) for p in probs)

def classify_payload_type(payload: str) -> str:
    p = _safe_str(payload).lower()
    if not p: return 'plain_text'
    if p.startswith(('http://', 'https://')): return 'url'
    if p.startswith('upi://') or 'pa=' in p or ('@' in p and any(h in p for h in LEGIT_UPI_HANDLES)): return 'upi'
    if p.startswith('begin:vcard'): return 'vcard'
    if re.match(r'^tel:\+?\d+$', p) or (p.startswith('+') and p[1:].isdigit()): return 'phone'
    if re.match(r'^mailto:[^@\s]+@[^@\s]+\.[^@\s]+$', p) or ('@' in p and '.' in p and not p.startswith('upi://')): return 'email'
    return 'plain_text'

def get_domain_parts(url: str):
    try:
        parsed = urlparse(url)
        host = parsed.netloc.split(':')[0]
        if tldextract:
            ext = tldextract.extract(url)
            return parsed, host, ext.domain, ext.suffix, ext.subdomain, ext.registered_domain
        else:
            parts = host.split('.')
            if len(parts) >= 2:
                reg = '.'.join(parts[-2:])
                sub = '.'.join(parts[:-2])
                return parsed, host, parts[-2], '', sub, reg
            return parsed, host, host, '', '', host
    except Exception:
        class Dummy:
            scheme = 'http'
            netloc = ''
            path = ''
            query = ''
        return Dummy(), '', '', '', '', ''

def brand_mismatch(payload: str, registered_domain: str) -> tuple:
    low = payload.lower()
    reg = str(registered_domain).lower()
    mentioned_brand = None
    for brand, aliases in BRANDS.items():
        if any(a in low for a in aliases):
            mentioned_brand = brand
            break
    if not mentioned_brand:
        return 0, 0, 0
    if reg:
        brand_aliases = BRANDS[mentioned_brand]
        matches_domain = any(a in reg for a in brand_aliases)
        return 1, 1, int(not matches_domain)
    return 1, 0, 0

def looks_like_ip(host: str) -> bool:
    return bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host))

def scam_keyword_stats(text: str) -> tuple:
    t = _safe_str(text).lower()
    if not t: return 0, 0.0, 0
    words = re.findall(r'[a-zA-Z0-9\-_]+', t)
    n = len(words)
    if n == 0: return 0, 0.0, 0
    hits = sum(1 for w in words if w in SCAM_KEYWORDS)
    urgency = sum(1 for w in words if w in URGENCY_WORDS)
    return hits, hits / n, urgency

def estimate_qr_version(payload, error_correction='M'):
    p = _safe_str(payload)
    if not p: return 0
    if qrcode:
        try:
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=1)
            qr.add_data(p); qr.make(fit=True)
            return int(qr.version or 0)
        except Exception:
            pass
    l = len(p)
    return 1 if l < 25 else 3 if l < 50 else 5 if l < 100 else 8 if l < 200 else 12 if l < 500 else 20

def error_correction_num(level='M'):
    return {'L':1,'M':2,'Q':3,'H':4}.get(str(level or 'M').upper(), 2)

def extract_url_features(payload):
    p = _safe_str(payload); parsed, host, domain, suffix, subdomain, registered = get_domain_parts(p); low = p.lower()
    query, path = parsed.query or '', parsed.path or ''; qs = parse_qs(query)
    suspicious = sum(1 for tok in SUSPICIOUS_TOKENS if tok in low)
    brand_count, brand_mentioned, brand_domain_mismatch = brand_mismatch(p, registered)
    shortened = int(registered in SHORTENER_DOMAINS or host in SHORTENER_DOMAINS)
    return {
        'url_len':len(p),'url_domain_len':len(registered),'url_tld_len':len(suffix),'url_subdomain_count':len([x for x in subdomain.split('.') if x]) if subdomain else 0,
        'url_path_len':len(path),'url_query_len':len(query),'url_num_query_params':len(qs),'url_has_https':int(parsed.scheme.lower() == 'https'),'url_has_ip':int(looks_like_ip(host)),
        'url_num_dots':p.count('.'),'url_num_hyphens':p.count('-'),'url_num_digits':sum(ch.isdigit() for ch in p),'url_num_at':p.count('@'),'url_num_question':p.count('?'),'url_num_ampersand':p.count('&'),'url_num_equals':p.count('='),'url_num_percent':p.count('%'),
        'url_is_shortened':shortened,'url_suspicious_token_count':suspicious,'url_suspicious_token_density':suspicious / max(1, len(re.findall(r'[a-zA-Z0-9]+', p))),
        'url_brand_mentioned':brand_mentioned,'url_brand_domain_mismatch':brand_domain_mismatch,'url_punycode':int('xn--' in host),'url_port_present':int(':' in parsed.netloc),
        'brand_name_count':brand_count,'short_url_count':shortened,
    }

def extract_upi_features(payload):
    p = _safe_str(payload); low = p.lower(); parsed = urlparse(p if '://' in p else 'upi://pay?' + p); qs = parse_qs(parsed.query)
    pa = qs.get('pa', [''])[0] if qs.get('pa') else ''
    if not pa:
        m = re.search(r'([a-zA-Z0-9._\-]{2,})@([a-zA-Z0-9._\-]{2,})', p)
        if m: pa = m.group(0)
    handle = pa.split('@')[-1].lower() if '@' in pa else ''
    amount, amount_present = 0.0, 0
    for k in ['am','amount']:
        if qs.get(k):
            try: amount = float(qs[k][0]); amount_present = 1
            except Exception: pass
    note = ' '.join(qs.get('tn', []) + qs.get('note', [])); kw, _, urgency = scam_keyword_stats(note)
    return {
        'upi_present':int(low.startswith('upi://') or bool(pa)),'upi_vpa_present':int(bool(pa)),'upi_vpa_handle_known':int(handle in LEGIT_UPI_HANDLES),'upi_vpa_handle_unknown':int(bool(handle) and handle not in LEGIT_UPI_HANDLES),
        'upi_amount_present':amount_present,'upi_amount_value':float(amount),'upi_amount_high':int(amount >= 10000),'upi_payee_name_present':int(bool(qs.get('pn'))),'upi_transaction_note_suspicious':int(kw > 0 or urgency > 0),'upi_collect_like':int('collect' in low or 'approve' in low or 'request' in low),'upi_param_count':len(qs)
    }

def extract_features(payload: str, qr_version=None, error_correction_level='M') -> dict:
    payload = _safe_str(payload); ptype = classify_payload_type(payload); f = {k:0.0 for k in FEATURE_ORDER}
    f.update({'payload_len':len(payload),'payload_entropy':shannon_entropy(payload),'payload_digit_count':sum(ch.isdigit() for ch in payload),'payload_alpha_count':sum(ch.isalpha() for ch in payload),'payload_special_count':sum(not ch.isalnum() and not ch.isspace() for ch in payload),'payload_space_count':sum(ch.isspace() for ch in payload),'payload_non_ascii_count':sum(ord(ch)>127 for ch in payload),'payload_type_url':int(ptype=='url'),'payload_type_upi':int(ptype=='upi'),'payload_type_plain_text':int(ptype=='plain_text'),'payload_type_vcard':int(ptype=='vcard'),'payload_type_phone':int(ptype=='phone'),'payload_type_email':int(ptype=='email'),'qr_version_estimate':int(qr_version) if qr_version not in [None,''] else estimate_qr_version(payload),'qr_error_correction_level_num':error_correction_num(error_correction_level)})
    if ptype == 'url': f.update(extract_url_features(payload))
    elif ptype == 'upi': f.update(extract_upi_features(payload))
    else:
        kw, dens, urg = scam_keyword_stats(payload)
        f.update({'text_scam_keyword_count':kw,'text_scam_keyword_density':dens,'text_urgency_score':urg,'text_contains_otp':int(bool(re.search(r'\botp\b|one time password', payload.lower()))),'text_contains_phone':int(bool(re.search(r'(\+?\d[\d\-\s]{7,}\d)', payload))),'text_contains_email':int(bool(re.search(r'[^@\s]+@[^@\s]+\.[^@\s]+', payload))),'text_contains_currency':int(bool(re.search(r'(₹|rs\.?|inr|usd|aed|\$)', payload.lower()))),'vcard_field_count':payload.count('\n') + payload.count(';') if ptype=='vcard' else 0})
        bc, _, _ = brand_mismatch(payload, ''); f['brand_name_count'] = bc
    if ptype in {'upi','url'}:
        kw, dens, urg = scam_keyword_stats(unquote(payload)); f['text_scam_keyword_count'] = max(f.get('text_scam_keyword_count',0), kw); f['text_scam_keyword_density'] = max(f.get('text_scam_keyword_density',0), dens); f['text_urgency_score'] = max(f.get('text_urgency_score',0), urg)
    return {k:float(f.get(k, 0.0)) for k in FEATURE_ORDER}

def triggered_features(payload: str, feature_dict: dict) -> list:
    checks = {
        'long_payload':feature_dict.get('payload_len',0)>=160,'high_entropy':feature_dict.get('payload_entropy',0)>=4.5,'shortened_url':feature_dict.get('url_is_shortened',0)==1,'brand_domain_mismatch':feature_dict.get('url_brand_domain_mismatch',0)==1,'ip_address_url':feature_dict.get('url_has_ip',0)==1,'suspicious_url_tokens':feature_dict.get('url_suspicious_token_count',0)>=2,'upi_unknown_handle':feature_dict.get('upi_vpa_handle_unknown',0)==1,'upi_high_amount':feature_dict.get('upi_amount_high',0)==1,'upi_collect_like':feature_dict.get('upi_collect_like',0)==1,'scam_keywords':feature_dict.get('text_scam_keyword_count',0)>=2,'urgency_language':feature_dict.get('text_urgency_score',0)>=1,'large_qr_version':feature_dict.get('qr_version_estimate',0)>=10
    }
    return [k for k,v in checks.items() if v]
