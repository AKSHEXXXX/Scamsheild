# ScamShield Backend — System Overview

**Version:** 2.1.0  
**Deployment:** Railway (FastAPI on port 8080)  
**Last updated:** 2026-06-23

---

## 1. High-Level Architecture

```
┌─────────────┐     ┌─────────────────────────────────────┐
│ Android App  │────▶│                                     │
│ iOS App      │     │    FastAPI App (Railway)            │
│ Web/Mobile   │     │                                     │
└─────────────┘     │  ┌───────────────────────────────┐  │
                    │  │  Routers                      │  │
                    │  │  ┌─────┐ ┌──────┐ ┌───────┐  │  │
                    │  │  │text │ │url   │ │qr     │  │  │
                    │  │  ├─────┤ ├──────┤ ├───────┤  │  │
                    │  │  │upi  │ │image │ │audio  │  │  │
                    │  │  ├─────┤ ├──────┤ ├───────┤  │  │
                    │  │  │scan │ │meta  │ │dashbd │  │  │
                    │  │  └─────┘ └──────┘ └───────┘  │  │
                    │  └───────────────────────────────┘  │
                    │              │                       │
                    │  ┌──────────▼───────────────────┐   │
                    │  │  ML Agents (15 agents)        │   │
                    │  │  ┌──────┐ ┌───────┐ ┌─────┐  │   │
                    │  │  │1 TFIDF│ │2 Dist │ │3 URL│  │   │
                    │  │  │4 Blkl │ │5 QR   │ │6 UPI│  │   │
                    │  │  │7 UPIx │ │8 Brand│ │9 B2 │  │   │
                    │  │  │10 Dee │ │11 Mal │ │12 Wh│  │   │
                    │  │  │13 Cal │ │14 Regex│ │15 Ens│  │   │
                    │  │  └──────┘ └───────┘ └─────┘  │   │
                    │  └───────────────────────────────┘   │
                    │                                     │
┌─────────────┐     │  ┌───────────────────────────────┐  │
│ Supabase     │◀───▶│  │ Data stores                  │  │
│ (Auth +      │     │  │ ┌──────┐ ┌────┐ ┌────────┐  │  │
│  Config)     │     │  │ │Mongo │ │Redis│ │Supabase│  │  │
└─────────────┘     │  │ └──────┘ └────┘ └────────┘  │  │
                    │  └───────────────────────────────┘  │
┌─────────────┐     └─────────────────────────────────────┘
│ Internal Jobs │
│ - anomaly     │
│ - export      │
│ - build_v2    │
│ - ingest_bnty │
└─────────────┘
```

### Components

- **FastAPI app:** Single Python application handling all HTTP traffic. Runs on Railway with auto-scaling.
- **ML Agents:** 15 modular agents loaded at startup from pickle/joblib artifacts. Each agent produces a score and/or signals. Agents 2, 9, 10, 12, 13 are stubs (return -1 or default).
- **Supabase:** Authentication (JWT), app config (`app_config` table), user reports (`reports` table), scan history (legacy `scans` table).
- **MongoDB:** Primary scan store, feedback, analytics events, anomaly records, model registry, threat intelligence feeds, bounty results, daily feedback stats.
- **Redis:** Rate limiting (sorted sets with TTL), threat-intel cache (`ti:*`), config cache (`cfg:app`).
- **Internal Jobs:** Background tasks running on a schedule or on-demand.

---

## 2. Data Responsibilities and Flows

### 2.1 Supabase

| Table | Purpose | Written By | Read By |
|-------|---------|------------|---------|
| `auth.users` | User accounts and JWTs | Supabase Auth | `require_user()` in all endpoints |
| `app_config` | Sensitivity threshold, scan caps, feature flags | Admin panel | `get_config_dict()` → `/api/v1/config` |
| `scans` | Legacy scan records (id, user_id, verdict, result_json) | `persist_scan()` (text, url, upi, qr, image routers) | `/api/v1/history`, `/api/v1/scan/{id}` |
| `reports` | User-submitted fraud reports | `POST /api/v1/report` | `/api/v1/history` (count only) |
| `blacklisted_vpas` | Known fraud UPI IDs (legacy) | Admin panel | `analyze()` in `app/analyzer.py` |
| `blacklisted_numbers` | Known fraud phone numbers (legacy) | Admin panel | `analyze()` in `app/analyzer.py` |

**Auth model:** Supabase JWT bearer tokens. Service key used server-side only (bypasses RLS). Anon key never exposed to backend config.

### 2.2 MongoDB

| Collection | Purpose | Written By | Read By |
|-----------|---------|------------|---------|
| `scans` | Primary scan storage with full result objects | `save_scan()` from `mongo_ops` | `/api/v1/history`, `/api/v1/scan/{id}`, dashboard, suite v2 builder |
| `reports` | User-submitted fraud reports (redundant with Supabase) | `save_report()` from `mongo_ops` | Dashboard, export jobs |
| `feedback` | User labels on scan results | `POST /api/v1/feedback` → `save_feedback()` | Dashboard quality metrics, export training data |
| `anomalies` | System-detected unusual patterns | `jobs/anomaly_monitor.py` | Dashboard |
| `model_registry` | Per-deployment agent versions and metrics | `_sync_model_registry()` in `model_loader.py` | Dashboard, CI checks |
| `threat_intel_domains` | Domain reputation feeds | Ingest scripts | Dashboard, brand guard |
| `threat_intel_ips` | IP reputation data | Ingest scripts | Rate limiter (IP reputation) |
| `threat_intel_kyc` | KYC-related scam patterns | Ingest scripts | Dashboard |
| `threat_intel_upi` | UPI fraud indicators | Ingest scripts | Dashboard |
| `bounty_results` | Test suite outcome snapshots | `jobs/ingest_bounty_results.py` | Dashboard |
| `feedback_stats_daily` | Precomputed daily feedback aggregates | `compute_feedback_stats()` | Dashboard |

### 2.3 Redis

| Key Pattern | Purpose | Written By | Read By |
|------------|---------|------------|---------|
| `rl:ip:{ip}:{route}` | Per-IP rate limit window | RateLimitMiddleware | RateLimitMiddleware |
| `rl:user:{user_id}:{route}` | Per-user rate limit window | RateLimitMiddleware | RateLimitMiddleware |
| `ti:ip:{ip}` | Cached IP reputation | IP rep check | RateLimitMiddleware |
| `cfg:app` | Cached app config | Config cache | `get_config_dict()` |

---

## 3. Inference Pipeline

### 3.1 Common Flow

1. **Auth check** — `require_user()` extracts JWT from `Authorization: Bearer <token>`, validates with Supabase.
2. **Rate limit** — `RateLimitMiddleware` checks per-IP and per-user limits against Redis.
3. **Credit check** — `enforce_credit_cap()` verifies user hasn't exceeded daily scan quota.
4. **Preprocessing** — `normalize()` applies NFKC normalization, leetspeak decoding, spaced-char collapse.
5. **Agents** — Each enabled agent runs and produces a score + optional signals.
6. **Ensemble** — Agent 15 combines all signals using calibrated weight tables and hard overrides.
7. **Persistence** — Result saved to MongoDB (`scans`) and Supabase (`scans`).
8. **Response** — Verdict (`low_risk` / `suspicious` / `high_risk`), score (0–100), top reason, findings.

### 3.2 Endpoint Details

#### `POST /api/v1/analyze-text`

- **Input:** `{ text: string, os: "iOS" | "Android" }`
- **Preprocessing:** Unicode NFKC, URL extraction, phone/VPA/amount detection, leetspeak decoding
- **Agents:**
  - Agent 14 — Regex Rule Engine (36 rules, e.g. KYC, OTP, UPI urgency)
  - Agent 1 — TF-IDF + Logistic Regression (trained on labeled SMS)
  - Agent 2 — DistilBERT FP16 (stub, returns -1)
  - Agent 15 — Ensemble (combines text_prob, regex_score, url_risk_boost)
- **Edge cases:** Empty/whitespace-only/emoji-only text returns score=0 immediately, no agent runs.
- **Storage:** MongoDB `scans` + Supabase `scans`

#### `POST /api/v1/analyze-url`

- **Input:** `{ url: string, os: "iOS" | "Android" }`
- **Agents:**
  - Agent 14 — Regex on URL text
  - Agent 4 — Blacklist check (pickled set of ~5K scam domains; fallback to Supabase)
  - Agent 3 — URL XGBoost (62 URL features: length, subdomain count, HTTPS, IP address, etc.)
  - Agent 8 — Brand Guard v1 (edit-distance against known brand domains)
  - Agent 15 — Ensemble (url_prob, blacklist_hit, brand_flag, regex_score, url_risk_boost)
- **URL risk boost:** Computed from `url_features.py` — detects shortened URLs, suspicious TLDs, brand tokens, dangerous schemes (file/ftp), loopback/private-IP hosts, embedded credentials. No URL fetching (no SSRF).
- **Brand whitelist:** `TRUSTED_DOMAINS` set suppresses brand_flag for legitimate official domains (banks, govt, major brands).

#### `POST /api/v1/check-qr`

- **Input:** `{ payload: string, os: "iOS" | "Android" }`
- **Benign payload detection:** vCard (`BEGIN:VCARD`) and WiFi config (`WIFI:`) return immediately with score=5, `low_risk`.
- **URL QR:** Same pipeline as URL analysis.
- **UPI QR:** Decodes `upi://` params (VPA, merchant, amount), runs UPI heuristic (Agent 6) + UPI XGBoost (Agent 7).
- **Plain text QR:** Runs text pipeline (Agent 1, Agent 14).
- **Ensemble** combines all applicable signals.

#### `POST /api/v1/sandbox-image`

- **Input:** `{ image: base64_string, device_id?: string, fallback_reason?: string }`
- **Pipeline:**
  1. Decode base64 → PIL Image
  2. Preprocess: denoise → upscale (if <1000px) → adaptive threshold → deskew → sharpen
  3. Tesseract OCR (--oem 3 --psm 6, languages eng+hin; fallback psm 11, then no-language)
  4. Normalize extracted text
  5. Run Agent 14 regex on text
  6. `analyze()` function: UPI/VPA detection, phone blacklist, brand impersonation, URL analysis, ML ensemble
- **Rate limit:** 20 scans/day per user (separate bucket from text scans)

#### `POST /api/v1/analyze-upi`

- **Input:** `{ amount, note, vpa, channel, os }`
- **Agents:**
  - Agent 6 — UPI Heuristic Rule Engine (YAML-defined rules for amount, keyword, velocity patterns)
  - Agent 7 — UPI XGBoost (feature-based, probability inverted due to training label swap)
  - Agent 1 — TF-IDF on note + VPA text
  - Agent 14 — Regex on note
  - Agent 15 — Ensemble

### 3.3 Ensemble Scoring

Agent 15 combines signals using two mechanisms:

1. **Weighted sum:** Pre-calibrated weight tables per scan type (text, url, upi, qr). Each signal contributes proportionally.
2. **Hard overrides:** Specific signal combinations force a verdict regardless of weighted score (e.g., blacklisted domain → high_risk).

Final score is clamped to 0–100. Verdict thresholds:
- **high_risk:** score ≥ sensitivity_threshold (default 70)
- **suspicious:** score ≥ threshold/2 (default 35)
- **low_risk:** score < 35

---

## 4. Security & Privacy

### 4.1 Authentication

- **User endpoints:** All POST endpoints (analyze-text, analyze-url, check-qr, sandbox-image, analyze-upi, feedback, report) and GET history/scan require a valid Supabase JWT in the `Authorization` header.
- **Auth check order:** Header extracted via `authorization: str = Header(None)` BEFORE request body is parsed. Missing/invalid token returns 401 immediately without field-name leaks.
- **Internal endpoints:** `/api/v1/internal/*` gated by `INTERNAL_API_KEY` environment variable (Bearer token). If unset, auth is disabled.

### 4.2 Rate Limiting

- **Per-IP:** 60 requests/minute per route (5 if IP has suspicious reputation).
- **Per-user:** 100 requests/minute per route (when JWT present).
- **Per-tenant:** 500 requests/minute (future).
- **IP reputation:** Checked against Redis `ti:ip:*` cache. Malicious IPs get 403. Suspicious IPs get stricter limits.
- All limits controlled via `RATE_LIMIT_*` environment variables with default values.

### 4.3 PII Handling

- All structured logs pass through `sanitize_pii()` which masks:
  - Phone numbers: `+919876543210` → `+9198XXXXXX10`
  - UPI IDs: `user@bank` → `us***@bank`
  - Emails: `user@domain.com` → `us***@domain.com`
  - URLs: Domain preserved, path truncated to first 10 + last 7 chars
- No full message text, phone numbers, or raw URLs appear in logs.
- User IDs are SHA-256 hashed (first 16 hex chars) in logs.

### 4.4 Attack Surface Reduction

- **Swagger/OpenAPI:** Disabled entirely (`docs_url=None`, `redoc_url=None`, `openapi_url=None`). No `/docs`, `/redoc`, or `/openapi.json` in production.
- **Validation errors:** Global `RequestValidationError` handler returns `{"detail": "Invalid request body"}` — no Pydantic schema details leaked.
- **OS validation:** `os` field restricted to `Literal["iOS", "Android"]` on all input schemas. Invalid values return 422.
- **No SSRF:** URL fields are never fetched. URL analysis is purely feature-based (parse, extract, classify).

---

## 5. Evaluation & Monitoring

### 5.1 Dashboard (`GET /api/v1/internal/dashboard`)

| Section | Content | Source |
|---------|---------|--------|
| `overview` | Total scans, per-channel breakdown (count/high_risk/suspicious/low_risk), score percentiles | MongoDB `scans` |
| `quality.approx_fn_fp` | FN/FP candidates per channel, computed from feedback labels vs model verdicts | MongoDB `feedback` vs `scans` |
| `quality.by_agent` | Per-agent quality metrics from feedback | MongoDB `feedback` aggregated |
| `feedback` | Feedback counts by channel, scam/legit/unsure totals, top confusing scans | `compute_feedback_stats()` |
| `bounty` | Last 5 bounty test runs with pass/fail matrix | MongoDB `bounty_results` |
| `anomalies` | Recent system-detected anomalies | MongoDB `anomalies` (written by `jobs/anomaly_monitor.py`) |
| `delta_vs_previous_deploy` | High-risk ratio change, FN/FP candidate changes vs previous deploy snapshot | Snapshot JSON file |

### 5.2 Bounty Tests

- **Location:** `bounty_test.py` in project root
- **Coverage:** 32 scenarios across 4 channels (url: 8, upi: 8, text: 10, qr: 6)
- **Execution:** Runs against live deploy URL, requires Supabase JWT
- **Ingestion:** `jobs/ingest_bounty_results.py` reads `output/bounty_*.json` and writes to MongoDB `bounty_results`
- **Pass standard:** All 32 must pass for a clean deploy

### 5.3 Feedback System

- **Endpoint:** `POST /api/v1/feedback` with `{ scan_id, label, reason? }`
- **Valid labels:** `scam`, `legit`, `unsure`
- **Ownership check:** Users can only label their own scans
- **Storage:** MongoDB `feedback` collection
- **Usage:** Flows into `export_training_data.py` for retraining, and `build_suite_v2.py` for targeted test suites

### 5.4 Internal Health

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `GET /health` | App + DB connectivity check | None (public) |
| `GET /api/v1/internal/health-ocr` | Verifies Tesseract OCR pipeline works | INTERNAL_API_KEY |
| `GET /api/v1/internal/dashboard` | Full operational dashboard | INTERNAL_API_KEY |

---

## 6. Retrain Pipeline

See [docs/retrain_playbook.md](./retrain_playbook.md) for the complete retrain specification.

### Candidate Agents for Retrain

| Agent | Type | Retrain Priority | Label Source |
|-------|------|-----------------|--------------|
| Agent 1 | TF-IDF + LogReg | High | User feedback labels |
| Agent 3 | URL XGBoost | Medium | User feedback + manual review |
| Agent 5 | QR XGBoost | Low | User feedback |
| Agent 6 | UPI Heuristic | High (rules update) | Manual curation |
| Agent 7 | UPI XGBoost | Medium | User feedback |
| Agent 8 | Brand Guard v1 | Low | Manual curation |
| Agent 14 | Regex Rules | Ongoing | Pattern discovery from feedback |

### Label Data Flow

1. User submits feedback via `POST /api/v1/feedback`
2. Feedback stored in MongoDB `feedback` collection
3. `jobs/export_training_data.py` reads feedback + scans, exports CSV
4. `docs/retrain_playbook.md` describes holdout sets, cross-validation, and rollback gating
5. `jobs/inspect_training_data.py` validates class balance and top n-grams before retrain
6. `jobs/build_suite_v2.py` creates targeted test suites from feedback patterns

---

## 7. Internal Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| `jobs/anomaly_monitor.py` | Every 10 min | Monitors scan patterns, detects anomalies in score distributions |
| `jobs/export_training_data.py` | On-demand | Exports labeled scans + feedback to CSV for retraining |
| `jobs/build_suite_v2.py` | On-demand | Builds targeted test suites from Mongo scans + feedback |
| `jobs/ingest_bounty_results.py` | On-demand | Ingests bounty test output JSON into MongoDB |
| `jobs/inspect_training_data.py` | On-demand | Validates exported CSVs for class balance, top features |

---

## 8. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_URL` | Yes | — | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | — | Supabase service role key (server-side only) |
| `SUPABASE_ANON_KEY` | Yes | — | Supabase anon key (for admin API calls) |
| `MONGODB_URI` / `MONGO_URL` | Yes | — | MongoDB connection string |
| `REDIS_URL` | No | — | Redis connection string (rate limiting) |
| `INTERNAL_API_KEY` | No | — | Auth for `/api/v1/internal/*` endpoints |
| `ENVIRONMENT` | No | `development` | Runtime environment label |
| `SENSITIVITY_THRESHOLD` | No | `70` | Score threshold for high_risk verdict |
| `RATE_LIMIT_*` | No | (various) | Rate limit configuration |

---

## 9. Key Files Reference

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app creation, middleware, global exception handlers, lifespan |
| `app/auth.py` | JWT validation, credit cap enforcement |
| `app/config.py` | Settings from environment |
| `app/database.py` | Supabase client singleton |
| `app/database_ext.py` | MongoDB + Redis client classes |
| `app/models.py` | Pydantic request/response schemas |
| `app/rate_limiter.py` | Per-IP, per-user, per-tenant rate limiting middleware |
| `app/logging_utils.py` | Structured JSON logging with PII sanitization |
| `app/helpers.py` | Config retrieval, scan persistence |
| `app/analyzer.py` | Legacy analysis pipeline (image endpoint) |
| `app/ocr.py` | Tesseract OCR with preprocessing pipeline |
| `app/ml/model_loader.py` | Loads all 15 agents from pickle/joblib artifacts |
| `app/ml/agents/inference.py` | Agent inference functions (1–15) |
| `app/ml/url_features.py` | URL signal extraction (shortener, TLD, brand, loopback detection) |
| `app/data_intel/mongo_ops.py` | MongoDB read/write operations |
| `app/data_intel/dashboard_queries.py` | Dashboard aggregation queries |
| `routers/*.py` | API endpoint handlers |
| `jobs/*.py` | Background/on-demand job scripts |
| `bounty_test.py` | 32-scenario regression test suite |
