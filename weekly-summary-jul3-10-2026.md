# ScamShield — Weekly Activity Summary (July 3–10, 2026)

---

## 1. ScamShield Monorepo (iOS + Backend + Android)

**Repos:** `github.com/AKSHEXXXX/Scamsheild` / `github.com/Thebinaryztechnologies/Scam-sheild`

---

### 1.1 Security Audit Fixes — July 7

Two batches of pentest-driven security hardening across backend and iOS. **11 findings fixed.**

| Finding | Description | Fix |
|---|---|---|
| **F-07** | Space-separated single characters bypassed ML vectorization (e.g., "H E L P" passed as benign) | Collapse consecutive single-char tokens before vectorization |
| **F-10** | `upi://` links routed through URL endpoint instead of `/check-qr` | Reject `upi://` scheme in URL endpoint, redirect to QR-check |
| **F-12** | Brand guard flagged trusted domains like `hdfc.com` as `high_risk` | Exact-match suppression on whitelisted brand domains |
| **C-02** | Auth token parsed from request body before validation — could read body twice | `auth-before-parse` middleware: reject unauthenticated requests before parsing body |
| **H-02** | Missing security headers | Added `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` |
| **C-06** | CORS allowed overly broad methods | Tightened to `GET, POST, PUT, DELETE, OPTIONS` |
| **C-08** | Score thresholds and agent count leaked in public `/api/v1/config` | Removed `score_thresholds`, agent listings from public endpoint |
| **C-05** | `regex_high` override set a `min_score: 60` floor — inflated low-risk scans | Changed to additive `boost: 15` instead of a hard floor |
| **iOS hardening** | Client lacked awareness of backend degradation state | Added client-side scam signal handling, degraded-state UI |
| **Regression** | `_check_ip_reputation()` lost in prior cleanup | Restored function |
| **Account** | Unused `settings` reference in `account.py` caused import warning | Removed |

---

### 1.2 ML Agent Deployments & Fixes — July 4–10

| Date | Agent | Change | Detail |
|---|---|---|---|
| Jul 10 | **Agent 2** | Added transformer support | `transformers>=4.30.0` in requirements, DistilBERT FP32 (516 MB) + INT8 quantized, `.dockerignore` excludes weights, downloaded at build via R2 |
| Jul 7 | **Agent 5** | Fixed silent failure in production | Removed deprecated `qr_url_scaler.pkl` (2-feature path), updated `qr_url_features.pkl` to 60-feature dimensionality, added `n_classes_` guard in XGBoost deserialization |
| Jul 7 | **Agent 1** | Fixed silent failure | TF-IDF inference wrapper was quietly returning zero scores — fixed deserialization path |
| Jul 4 | **Agent 2** | Deployed | Multilingual DistilBERT text scam classifier (Hindi/Devanagari supported natively) |
| Jul 4 | **Agent 13** | Wired | Transcript classifier integrated into ensemble |
| Jul 3 | **Agent 3** | Retrained | URL XGBoost — **AUC=1.0** (data leakage suspected, needs audit) |
| Jul 3 | **Agent 7** | Retrained | UPI classifier — **AUC=0.47** (below random, dataset needs overhaul) |
| Jul 3 | **Agent 1/5/11** | Updated classifiers | Deployed production-trained models |

**Ensemble Weight Tuning:**

| Weight | Before | After | Effect |
|---|---|---|---|
| `text_prob` (text scans) | 0.50 | **0.75** | Text scans can now reach `high_risk` threshold |
| `url_prob` (QR phishing) | 0.30 | **0.45** | QR scan scores increased ~15 points (e.g., 40→55) |
| `regex_high` override | `min_score: 60` floor | `boost: 15` additive | No longer inflates low-risk scans |
| OTP safeguards | None | Added `defensive_phrase_gate` | "OTP", "bank" phrases no longer trigger `high_risk` (75→58) |
| UPI `text_prob` | 0.05 | **0.15** | Higher weight on text signals in UPI scans |
| UPI `regex_score` | 0.05 | **0.15** | Higher weight on regex matches in UPI scans |

**Model Infrastructure:**

| Change | Detail |
|---|---|
| `malware_rf.pkl` compressed | 334 MB → 98 MB, re-pickled with protocol 4 for Railway Python 3.11 compat |
| Continuous retraining pipeline | Colab Pro → Drive trigger → quality gate → R2 promotion |
| Railway build | `railway.toml` added for Dockerfile-based build |
| Tests | 7 Supabase-dependent integration tests converted to mock-based (eliminated 429 flakiness) |
| Dependencies | `pillow 12.2`, `starlette 1.3`, `fastapi 0.139`, `python-multipart 0.0.31`, `pytest 9.0` — CVE fixes |

---

### 1.3 PostHog Analytics Integration — July 8–10

**The single largest feature this week.** Cross-platform analytics across backend, iOS, and Android.

**Backend (8 commits):**

| Commit | Change |
|---|---|
| `11c5add` | Initial PostHog event tracking — `capture()` on scan endpoints |
| `b201ce4` | Complete instrumentation: `scan_started`/`scan_completed`/`text_risk_analysis` |
| `6f0fdb5` | 500 error tracking with stack traces |
| `3198d83` | `agents_health_checked` event fired from `/health` endpoint |
| `fedf95f` | Extra properties: `top_signal`, `input_type` to all router scan events |
| `f840c35` | `text_risk_analysis` moved into analytics package |
| `86bd496`, `d413d12`, `affe427` | PostHog v6+ API compat fixes |

**iOS (6 commits):**

| Commit | Change |
|---|---|
| `41a6b1e` | PostHog SDK integration in `AnalyticsManager` |
| `6d6f505` | Session replay, feature flags |
| `d5f2703` | Exception autocapture + `captureException()` wrapper |
| `e849526` | NPS/feedback surveys enabled |
| `c737586` | `channel` + `verdict` added to `scan_started` / `scan_completed` |
| `cd1fad0` | Swift Gen 2 API migration for PostHog 3.64.1 |

**Android (1 commit):**

| Commit | Change |
|---|---|
| `2707e8e` | PostHog SDK, screen tracking, auth events, `identify()`/`reset()` |

**Events Tracked Across All Platforms:**

```
scan_started          → channel, input_type, top_signal
scan_completed        → channel, verdict, top_signal, score
text_risk_analysis    → per-agent scores, ensemble verdict
agents_health_checked → per-agent status from /health
500_error             → traceback, endpoint, user_id
sign_up / sign_in / sign_out
screen_view / page_view (iOS, Android, Web)
```

**PostHog Config:** Project key `phc_knJZQWprWxJSt9GNw3ZJUzQ9SgSHLMjTk3Ku4rH8VUVm`

---

### 1.4 Bug Fixes

| Bug | Root Cause | Fix |
|---|---|---|
| Referral `invite_lookup` crash | `maybe_single().execute()` returned `None` → `AttributeError: 'NoneType' object has no attribute 'get'` | None guard on all 8 call sites in `referral.py` |
| Login fires `login_completed` on cold start | Stale session in `UserDefaults` triggered completion before actual auth check | `LoginViewModel` checks session validity before emitting event |
| Redeem response shape mismatch | Backend returned wrong field names | Aligned response shape |
| Agent 8 logic errors | Exact-match vs containment logic inverted, short-name detection missing | Fixed |
| Image upload dual body | Backend only accepted `image` not `image_base64` | Accept both fields in `POST /api/v1/sandbox-image` |
| Account delete `settings` ref | Imported but unused `settings` in `account.py` | Removed |

---

### 1.5 Feature Expansions (Prior Weeks, Deployed Now)

| Feature | Detail |
|---|---|
| **PSP expansion** | 63 → 78 Payment Service Providers |
| **Brand list expansion** | 39 → 75 brands |
| **Health endpoint** | JSON logging, agent status reporting |
| **Grapify** | Integration |
| **Referral system** | Bonus scan system, cap enforcement on text/qr endpoints, referral analytics page, deep-link `/invite/:code → scamshield://scan` |
| **Delete account API** | Full delete-account flow via mobile API |
| **Admin temp-password flow** | Bootstrap admin flow with forced reset, RBAC setup |
| **Auth fix** | Post-reset login loop stopped; RBAC setup errors surfaced |
| **CORS hardening** | Aligned defaults |
| **Rate limiting** | Key-based + IP-based |
| **Health DB visibility** | Fixed |

---

## 2. ScamShield Web (Verifaipal)

**Repo:** `github.com/AKSHEXXXX/Scamshield_Web`

Framework: **Next.js** (Create Next App)

| Date | Commit | Change |
|---|---|---|
| Jul 9 | `4a740b5` | PostHog autocapture enabled — accurate bounce rate & session duration tracking |
| Jul 9 | `f939e60` | Vercel deploy prep: removed duplicate `next.config.mjs`, added favicon, PostHog analytics |
| Jul 6 | `c8cd1d2` | Catch-up commit |
| Jul 5 | `b917ebe` | Codebase reorganized, renamed to **Verifaipal**, UI updated |
| Jul 4 | `3741b1a` | Initial scaffold from Create Next App |

**State:** Early-stage web app. Transitioned from scaffold → branded UI → Vercel-deployed with PostHog analytics.

---

## 3. PostHog Integration — Complete Cross-Platform Coverage

| Platform | SDK | Features | Status |
|---|---|---|---|
| Backend (FastAPI) | `posthog` Python lib | Scan events, health events, 500 errors, per-agent reports | ✅ Complete |
| iOS (Swift) | PostHog Swift SDK v3.64.1 | Session replay, feature flags, surveys, autocapture, screen tracking | ✅ Complete |
| Android (Kotlin) | PostHog Android SDK | Screen tracking, auth events, `identify()`/`reset()` | ✅ Complete |
| Web (Next.js) | PostHog JS | Autocapture, bounce rate, session duration | ✅ Complete |

**PostHog Project Key:** `phc_knJZQWprWxJSt9GNw3ZJUzQ9SgSHLMjTk3Ku4rH8VUVm`

---

## 4. Blocked / Next Steps

| # | Item | Blocked By |
|---|---|---|
| 1 | **Upload Agent 2 weights to Cloudflare R2** — FP32 model (516 MB) + INT8 quantized + Agent 13 weights | R2 bucket `scamshield-models` not yet provisioned; `MODEL_DOWNLOAD_URL/KEY/SECRET/REGION` not set in Railway |
| 2 | **Fix bank credit alert false positive** (score 75, too high for legitimate SMS) | Agent 2 not loading in production — weights missing |
| 3 | **Fix adversarial padding false negative** (score 6, too low) | Agent 2 not loading in production — weights missing |
| 4 | **Agent 3 retrain** — AUC=1.0 suggests data leakage (overfitting) | Dataset audit required |
| 5 | **Agent 7 retrain** — AUC=0.47 below random | Dataset overhaul needed (class imbalance / wrong labels) |
| 6 | **Hindi/Devanagari integration** — Devanagari regex for Agent 14, Hindi scam keywords for Agent 6/8, fine-tuning data for Agent 2/13 | Requires Hindi scam dataset collection |
| 7 | **Apply Supabase migration** — `20250701000000_referral_and_notifications.sql` not yet run | Pending deployment window |
