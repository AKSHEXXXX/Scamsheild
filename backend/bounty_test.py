"""
Bounty test suite -- runs all scenarios against the live deploy endpoint.
Reports pass/fail matrix, elapsed time, and hits the dashboard for FN/FP deltas.

Usage:
    python bounty_test.py [--deploy-url URL] [--minutes N]
"""

import os, sys, json, time, argparse, urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from httpx import Client

DEPLOY = "https://scam-sheild-production.up.railway.app"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://pmwdoxemzdupicidzmze.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
THRESH_LOW = 35
THRESH_HIGH = 62


def get_token(client: Client, _base: str) -> str:
    """Get a JWT from the project's Supabase auth using service key."""
    if not SUPABASE_SERVICE_KEY:
        print("  SKIP: SUPABASE_SERVICE_KEY not set")
        return ""
    email = "bounty-runner@scamshield.com"
    pw = "BountyTest2024!"
    svc_hdr = {"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
    anon_hdr = {"apikey": SUPABASE_ANON_KEY}
    r = client.post(f"{SUPABASE_URL}/auth/v1/admin/users", json={
        "email": email, "password": pw, "email_confirm": True,
    }, headers=svc_hdr)
    if r.status_code not in (200, 201) and "already exists" not in r.text:
        print(f"  admin create user err: {r.status_code} {r.text[:200]}")
    r2 = client.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        json={"email": email, "password": pw, "gotrue_meta_security": {}},
        headers=anon_hdr)
    if r2.status_code == 200:
        return r2.json()["access_token"]
    print(f"  login err: {r2.status_code} {r2.text[:200]}")
    return ""


def analyze_text(client: Client, base: str, token: str, text: str) -> dict:
    r = client.post(f"{base}/api/v1/analyze-text", json={"text": text, "os": "Android"},
                    headers={"Authorization": f"Bearer {token}"})
    return {"status": r.status_code, **r.json()} if r.status_code == 200 else {"status": r.status_code, "error": r.text[:300]}


def analyze_url(client: Client, base: str, token: str, url: str) -> dict:
    r = client.post(f"{base}/api/v1/analyze-url", json={"url": url, "os": "Android"},
                    headers={"Authorization": f"Bearer {token}"})
    return {"status": r.status_code, **r.json()} if r.status_code == 200 else {"status": r.status_code, "error": r.text[:300]}


def analyze_upi(client: Client, base: str, token: str, note: str,
                amount: int = 0, vpa: str = "") -> dict:
    r = client.post(f"{base}/api/v1/analyze-upi",
                    json={"note": note, "amount": amount, "vpa": vpa,
                          "channel": "sms", "os": "Android"},
                    headers={"Authorization": f"Bearer {token}"})
    return {"status": r.status_code, **r.json()} if r.status_code == 200 else {"status": r.status_code, "error": r.text[:300]}


def analyze_qr(client: Client, base: str, token: str, payload: str) -> dict:
    r = client.post(f"{base}/api/v1/check-qr", json={"payload": payload, "os": "Android"},
                    headers={"Authorization": f"Bearer {token}"})
    return {"status": r.status_code, **r.json()} if r.status_code == 200 else {"status": r.status_code, "error": r.text[:300]}


def check_verdict(data: dict, expected_min: int, expected_max: int = 100) -> bool:
    score = data.get("scam_score", data.get("score", 0))
    return expected_min <= score <= expected_max


FAILURE_CATEGORIES = {
    "FN-URL": lambda ch, lb, ok: ch == "url" and lb in ("shortened generic", "shortened + brand", "brand in subdomain", "suspicious TLD", "suspicious TLD .xyz", "brand + susp TLD") and not ok,
    "FN-TEXT": lambda ch, lb, ok: ch == "text" and lb in ("scam KYC+URL", "scam lottery", "scam urgency", "scam free + URL", "scam brand KYC", "scam OTP urgency", "scam fake job") and not ok,
    "FP-LEGIT": lambda ch, lb, ok: ch in ("url", "text", "upi") and lb in ("benign google", "benign amazon", "benign hello", "benign meeting", "benign package delay", "benign collect", "benign send", "brand VPA benign", "benign vpa hello") and not ok,
    "EVASION": lambda ch, lb, ok: ch == "text" and lb in ("unicode_leet", "zero_width", "homoglyph") and not ok,
    "QR-MISS": lambda ch, lb, ok: ch == "qr" and not ok,
}


def _classify_failures(results: list) -> dict:
    cats = {}
    for ch, lb, ok, sc, vd in results:
        if ok:
            continue
        for cat_name, matcher in FAILURE_CATEGORIES.items():
            if matcher(ch, lb, ok):
                cats.setdefault(cat_name, []).append({"label": lb, "channel": ch, "score": sc, "verdict": vd})
    return cats


def hit_dashboard(client: Client, base: str, token: str, minutes: int = 60) -> dict:
    r = client.get(f"{base}/api/v1/internal/dashboard?minutes={minutes}",
                   headers={"x-internal-key": "ss-dash-internal-key-2026"})
    result = {"status": r.status_code, "elapsed_ms": r.elapsed.total_seconds() * 1000}
    if r.status_code == 200:
        result["data"] = r.json()
    else:
        result["error"] = r.text[:500]
    return result


def json_dump(obj):
    return json.dumps(obj, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deploy-url", default=DEPLOY)
    parser.add_argument("--minutes", type=int, default=43200)
    args = parser.parse_args()

    base = args.deploy_url.rstrip("/")
    print(f"Bounty test -- {base}\n")

    client = Client(timeout=30)
    token = get_token(client, base)
    if not token:
        print("[FAIL] No JWT token -- aborting.")
        sys.exit(1)
    print(f"[PASS] Token acquired ({token[:20]}...)\n")

    results = []
    start_ts = datetime.now(timezone.utc)

    # -- URL tests ---------------------------------------------------------
    print("=== URL tests ===")
    url_cases = [
        ("shortened generic",      "https://bit.ly/phish-test",          20, 100),
        ("shortened + brand",      "https://bit.ly/google-login",        30, 100),
        ("suspicious TLD",         "https://free-prize-xyz.info/claim",  20, 100),
        ("brand in subdomain",     "https://paytm-login.security-verify.com/login", 30, 100),
        ("benign google",          "https://www.google.com",              0,  45),
        ("benign amazon",          "https://www.amazon.com/dp/12345",     0,  45),
        ("suspicious TLD .xyz",    "https://prize-winner.xyz/claim",    20, 100),
        ("brand + susp TLD",       "https://flipkart-offer.xyz/win",     35, 100),
    ]
    for label, url, lo, hi in url_cases:
        t0 = time.perf_counter()
        data = analyze_url(client, base, token, url)
        elapsed = (time.perf_counter() - t0) * 1000
        ok = data["status"] == 200 and check_verdict(data, lo, hi)
        score = data.get("scam_score", data.get("score", "ERR"))
        verdict = data.get("verdict", "ERR")
        results.append(("url", label, ok, score, verdict))
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label:25s} score={score:<4d} verdict={verdict:15s} ({elapsed:.0f}ms)")
        if not ok:
            print(f"          expected [{lo}, {hi}] got {score}")

    # -- UPI tests ---------------------------------------------------------
    print("\n=== UPI tests ===")
    upi_cases = [
        ("benign collect",         "Collect from person@upi",             0,  45, 0, ""),
        ("benign send",            "Send money to friend@upi",            0,  45, 0, ""),
        ("keyword + brand VPA",    "fake-scam@paytm",                   40, 100, 0, "fake-scam@paytm"),
        ("keyword + amount",       "Pay 5000 to get 50000",             40, 100, 5000, ""),
        ("urgent + brand VPA",     "urgent-payment@icici",              20, 100, 0, "urgent-payment@icici"),
        ("brand VPA benign",       "bill-payment@axisbank",              0,  50, 0, "bill-payment@axisbank"),
        ("keyword alert",          "scam-alert@ybl",                    40, 100, 0, "scam-alert@ybl"),
        ("benign vpa hello",       "hello@paytm",                        0,  50, 0, "hello@paytm"),
    ]
    for label, note, lo, hi, amt, vpa in upi_cases:
        t0 = time.perf_counter()
        data = analyze_upi(client, base, token, note, amt, vpa)
        elapsed = (time.perf_counter() - t0) * 1000
        ok = data["status"] == 200 and check_verdict(data, lo, hi)
        score = data.get("scam_score", data.get("score", "ERR"))
        verdict = data.get("verdict", "ERR")
        results.append(("upi", label, ok, score, verdict))
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label:25s} score={score:<4d} verdict={verdict:15s} ({elapsed:.0f}ms)")
        if not ok:
            print(f"          expected [{lo}, {hi}] got {score}")

    # -- Text/SMS tests ----------------------------------------------------
    print("\n=== Text tests ===")
    text_cases = [
        ("benign hello",           "Hello",                              0,  THRESH_LOW),
        ("scam KYC+URL",           "Your KYC is expiring, click https://bit.ly/kyc-update", 40, 100),
        ("scam lottery",           "Congratulations! You won a lottery of $1M", 40, 100),
        ("scam urgency",           "Your account will be suspended immediately", 40, 100),
        ("benign meeting",         "Meeting at 3pm tomorrow",            0,  45),
        ("scam free + URL",        "Free iPhone, claim now at https://claim-xyz.info/win", 40, 100),
        ("scam brand KYC",         "Dear customer, update PAN at https://sbi-secure.cc/verify", 40, 100),
        ("scam OTP urgency",       "Your OTP is 123456. Share it immediately to avoid suspension.", 40, 100),
        ("benign package delay",   "Your package is delayed by 2 days",  0,  50),
        ("scam fake job",          "Work from home, earn 50k per week, no experience needed", 30, 100),
    ]
    for label, text, lo, hi in text_cases:
        t0 = time.perf_counter()
        data = analyze_text(client, base, token, text)
        elapsed = (time.perf_counter() - t0) * 1000
        ok = data["status"] == 200 and check_verdict(data, lo, hi)
        score = data.get("scam_score", data.get("score", "ERR"))
        verdict = data.get("verdict", "ERR")
        results.append(("text", label, ok, score, verdict))
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label:25s} score={score:<4d} verdict={verdict:15s} ({elapsed:.0f}ms)")
        if not ok:
            print(f"          expected [{lo}, {hi}] got {score}")

    # -- QR tests ----------------------------------------------------------
    print("\n=== QR tests ===")
    qr_cases = [
        ("QR URL shortened",       "https://bit.ly/phish-test",          40, 100),
        ("QR URL shortened+brand", "https://bit.ly/google-login",        45, 100),
        ("QR UPI scam+keyword",    "fake-scam@paytm",                   65, 100),
        ("QR WiFi config",         "WIFI:T:WPA;S:MyNetwork;P:pass123;;", 0,  20),
        ("QR plain text",          "Hello from QR",                      0,  THRESH_LOW),
        ("QR UPI urgent",          "urgent-payment@icici",              20, 100),
    ]
    for label, payload, lo, hi in qr_cases:
        t0 = time.perf_counter()
        data = analyze_qr(client, base, token, payload)
        elapsed = (time.perf_counter() - t0) * 1000
        ok = data["status"] == 200 and check_verdict(data, lo, hi)
        score = data.get("scam_score", data.get("score", "ERR"))
        verdict = data.get("verdict", "ERR")
        results.append(("qr", label, ok, score, verdict))
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label:25s} score={score:<4d} verdict={verdict:15s} ({elapsed:.0f}ms)")
        if not ok:
            print(f"          expected [{lo}, {hi}] got {score}")

    # -- Summary -----------------------------------------------------------
    total = len(results)
    passed = sum(1 for r in results if r[3] != "ERR" and r[2])
    failed = total - passed
    elapsed_total = (datetime.now(timezone.utc) - start_ts).total_seconds()

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed, {failed} failed ({elapsed_total:.1f}s)")
    print()

    by_channel = {}
    for ch, label, ok, score, verdict in results:
        by_channel.setdefault(ch, []).append((label, ok, score, verdict))

    for ch in sorted(by_channel):
        items = by_channel[ch]
        ch_pass = sum(1 for _, ok, _, _ in items if ok)
        print(f"  {ch}: {ch_pass}/{len(items)} passed")

    # -- Dashboard ---------------------------------------------------------
    print(f"\n=== Dashboard (last {args.minutes}m) ===")
    dash = hit_dashboard(client, base, token, args.minutes)
    dash_status = dash["status"]
    dash_ms = dash.get("elapsed_ms", 0)
    print(f"  HTTP {dash_status} -- {dash_ms:.0f}ms")
    if dash_status == 200 and "data" in dash:
        d = dash["data"]
        overview = d.get("overview", {})
        print(f"  Total scans:        {overview.get('total_scans', '?')}")
        hr = overview.get('high_risk_ratio', '?')
        if isinstance(hr, (int, float)):
            print(f"  High risk ratio:     {hr:.2%}")
        else:
            print(f"  High risk ratio:     {hr}")
        fn_fp = d.get("approx_fn_fp", {})
        print(f"  FN/FP by channel:    {json.dumps(fn_fp, default=str)}")
        agent_q = d.get("agent_quality", {})
        print(f"  Agents loaded:       {agent_q.get('agents_loaded', '?')}/{agent_q.get('total_agents', '?')}")
        anom = d.get("anomalies", [])
        print(f"  Anomalies:           {len(anom)}")
        print(f"  Full dashboard: {json_dump(d)[:1500]}")

        if dash_ms > 300:
            print(f"\n  [WARN] Dashboard latency {dash_ms:.0f}ms exceeds 300ms target")
        else:
            print(f"  [PASS] Dashboard under 300ms target")

    # -- Write results file ------------------------------------------------
    deploy_id = (dash.get("data", {}).get("deployment_id") if isinstance(dash.get("data"), dict) else None) or base.split("//")[-1].split(".")[0]
    fail_cats = _classify_failures(results)
    out = {
        "deployment_id": deploy_id,
        "timestamp": start_ts.isoformat(),
        "elapsed_seconds": elapsed_total,
        "pass_count": passed,
        "fail_count": failed,
        "total": total,
        "failures_by_category": {k: [r["label"] for r in v] for k, v in fail_cats.items()},
        "results": [
            {"channel": ch, "label": lb, "ok": ok, "score": sc, "verdict": vd}
            for ch, lb, ok, sc, vd in results
        ],
        "dashboard": dash,
    }
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / f"bounty_{deploy_id}_{start_ts.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nReport written to {report_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
