from app.config import settings


def compute_score(
    text_p: float,
    url_p: float,
    rule_p: float,
    blacklist_hit: bool,
) -> tuple[int, str]:
    bl = 1.0 if blacklist_hit else 0.0
    w = text_p * 0.35 + url_p * 0.30 + rule_p * 0.20 + bl * 0.15
    if blacklist_hit:
        w = max(w, 0.75)
    score = min(100, int(w * 100))

    threshold = settings.SENSITIVITY_THRESHOLD
    if score >= threshold:
        verdict = "high_risk"
    elif score >= threshold // 2:
        verdict = "suspicious"
    else:
        verdict = "low_risk"
    return score, verdict


def compute_ensemble_verdict(
    ml_url_prob: float,
    ml_qr_prob: float,
    ml_text_prob: float,
    rule_score: int,
    has_blacklisted_domain: bool,
    has_blacklisted_vpa: bool,
    has_blacklisted_phone: bool,
    impersonation_boost: int,
) -> tuple[int, str, dict]:
    url_p = ml_url_prob if ml_url_prob >= 0 else 0.0
    qr_p = ml_qr_prob if ml_qr_prob >= 0 else 0.0
    text_p = ml_text_prob if ml_text_prob >= 0 else 0.0

    url_combined = max(url_p, qr_p)

    blacklist_hit = has_blacklisted_domain or has_blacklisted_vpa or has_blacklisted_phone

    rule_p = min(1.0, rule_score / 100.0)
    rule_p = min(1.0, rule_p + impersonation_boost / 100.0)

    score, verdict = compute_score(
        text_p=text_p,
        url_p=url_combined,
        rule_p=rule_p,
        blacklist_hit=blacklist_hit,
    )

    return score, verdict, {
        "ml_text_prob": round(text_p, 4),
        "ml_url_prob": round(url_combined, 4),
        "rule_score_norm": round(rule_p, 4),
        "blacklist_hit": blacklist_hit,
    }
