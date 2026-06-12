def compliance_score(text_score: int, flagged_urls: list[dict], sensitivity_threshold: int,
                     impersonation_boost: int = 0) -> tuple[int, str]:
    domain_risk = 0
    for url in flagged_urls:
        if url.get("reputation") == "malicious":
            domain_risk = 100
            break

    score = round(0.6 * text_score + 0.4 * domain_risk) + impersonation_boost
    if score >= sensitivity_threshold:
        verdict = "high_risk"
    elif score >= sensitivity_threshold // 2:
        verdict = "suspicious"
    else:
        verdict = "low_risk"
    return min(100, score), verdict