# ScamShield Backend Overview

## Folder Structure

```
backend/
├── main.py                    # FastAPI app, router registration, lifespan
├── config.py                  # Root-level config (legacy)
├── Dockerfile                 # Container image definition
├── pyproject.toml             # Project metadata, dependencies
│
├── routers/                   # HTTP endpoints (one per channel)
│   ├── meta.py                # /health, /config, /agents, /report, /history
│   ├── scan.py                # Unified /api/v1/scan endpoint
│   ├── text.py                # /api/v1/analyze-text
│   ├── url.py                 # /api/v1/analyze-url, /check-url
│   ├── qr.py                  # /api/v1/check-qr
│   ├── upi.py                 # /api/v1/analyze-upi
│   ├── image.py               # /api/v1/sandbox-image, /sandbox-file
│   └── audio.py               # /api/v1/analyze-audio (stub)
│
├── agents/                    # Standalone agent modules
│   ├── agent1_text_tfidf.py   # TF-IDF + Logistic Regression
│   ├── agent4_blacklist.py    # Blacklist domain checker
│   └── agent15_ensemble.py    # Weighted ensemble scorer
│
├── app/                       # Core application logic
│   ├── config.py              # Settings singleton (env vars)
│   ├── auth.py                # JWT authentication
│   ├── database.py            # Supabase client
│   ├── database_ext.py        # MongoDB + Redis connections
│   ├── helpers.py             # persist_scan(), get_config_dict()
│   ├── models.py              # Pydantic request/response models
│   ├── analytics.py           # Text risk analysis rules
│   ├── analyzer.py            # Multi-agent orchestrator (image pipeline)
│   ├── ocr.py                 # Tesseract OCR pipeline
│   ├── sandbox.py             # Isolated file analysis
│   ├── scoring.py             # Score thresholds, verdict mapping
│   │
│   └── ml/                    # ML model layer
│       ├── model_loader.py    # Load all 15 agents
│       ├── ensemble.py        # Ensemble scoring engine
│       ├── text_model.py      # Text model wrapper
│       ├── url_model.py       # URL model wrapper
│       ├── qr_model.py        # QR model wrapper
│       ├── upi_heuristic_engine.py  # UPI rule engine
│       ├── agents/
│       │   └── inference.py   # All 15 agent inference functions
│       └── artifacts/         # Model files, weights, status
│           ├── agent_status.json
│           ├── ensemble_weights.json
│           ├── ensemble_overrides.json
│           └── *.pkl, *.yaml, *.json
│
├── schemas/                   # Shared Pydantic schemas
│   └── scan_result.py         # SignalsBlock, ScanResult
│
├── scripts/                   # Utility scripts
│   ├── download_models.py     # Download model artifacts
│   ├── ingest_threats.py      # Threat intel feed ingestion
│   ├── generate_code_graph.py # Generate Obsidian code graph
│   └── setup.py               # Setup script
│
├── tests/                     # Pytest test suite
│   ├── test_text.py, test_url.py, test_qr.py, test_upi.py
│   ├── test_image.py, test_ocr.py, test_audio.py
│   ├── test_report.py, test_main.py
│   ├── labeled_samples.py     # Sample payloads for testing
│   └── conftest.py            # Fixtures
│
├── docs/                      # Documentation
│   ├── graph/                 # Code dependency graphs
│   └── obsidian/              # Obsidian-compatible code graph
│
├── ARCHITECTURE_AUDIT.md      # Architecture conformity report
├── BACKEND_OVERVIEW.md        # This file
└── CONTRIBUTING_BACKEND.md    # Rules for contributors
```

## Security & Observability

### Authentication & Zero-Trust Ingress

- **JWT validation**: Every endpoint calls `require_user()` which validates the Supabase JWT and returns the user ID
- **Rate limiting** (Redis-backed):
  - Per-IP: 60 requests/min per route (configurable via `RATE_LIMIT_IP`)
  - Per-user: 100 requests/min per route (configurable via `RATE_LIMIT_USER`)
  - IP reputation: `ti:ip:{ip}` Redis key checked at request start
    - `malicious` reputation → immediate 403
    - `suspicious` reputation → 5 req/min throttle
- **Device posture**: `/api/v1/scan` accepts `posture` field (rooted/emulator/jailbreak flags from mobile SDKs), stored in MongoDB scans

### Structured Logging & PII Safety

All structured events via `app/logging_utils.py` → `log_event()`:

```python
log_event("scan_completed", scan_id=id, user_id=uid, channel="text",
          verdict="high_risk", score=85, agent_ids=[1, 14, 15])
```

PII sanitization rules applied before any log output:
- Phone numbers: `+91XXXXXXXX12` → `+91XXXXXX12`
- UPI IDs: `user@payu` → `us***@payu`
- Email addresses: `john.doe@gmail.com` → `jo***@gmail.com`
- URLs: truncated to `https://domain/path...?...`
- Device IDs: SHA-256 hashed (first 16 chars)

### Anomaly Monitoring

A background task runs `jobs/anomaly_monitor.py` every 10 minutes:
- Queries MongoDB `scans` for last 10 minutes vs 24-hour rolling baseline
- Detects:
  - **high_risk spike**: >80% of scans are high-risk
  - **traffic surge**: 5x normal volume
  - **traffic drop**: zero scans when baseline >10
- Writes anomalies to MongoDB `anomalies` collection (30-day TTL)
- Future: alert webhook (Slack/email) on anomaly detection

## Data & Threat Intel Layer

The backend uses three storage systems with clear source-of-truth boundaries:

| Store | Source of Truth For | Legacy Usage | Notes |
|-------|-------------------|-------------|-------|
| **Supabase** | Auth (users + JWT), app_config (feature flags) | Scans (legacy, dual-write), reports (legacy) | Auth is canonical; scans table is legacy — new reads come from MongoDB |
| **MongoDB** | Scan history, threat intel, model registry, analytics | — | Primary read target for `/api/v1/history` and `/api/v1/scan/{scan_id}` |
| **Redis** | Rate limiting, threat intel cache, config cache | — | Volatile cache only — data loss is acceptable |

### Supabase (primary OLTP)
- **Auth**: JWT user management via Supabase Auth
- **Scans**: Immutable scan history (Supabase `scans` table)
- **Reports**: User-submitted reports (Supabase `reports` table)
- **App config**: Feature flags and thresholds (Supabase `app_config` table)
- Persisted via `app/helpers.py` → `persist_scan()` and `routers/meta.py` → `persist_report()`

### MongoDB (analytics + threat intel)
7 collections, all defined in `app/data_intel/mongo_schemas.py`:

| Collection | Purpose | Key Index |
|------------|---------|-----------|
| `scans` | Full scan results for retraining & analytics | `{user_id, created_at}`, `{scan_id}` unique |
| `reports` | Fraud reports for trend analysis | `{value}`, `{report_id}` unique |
| `threat_intel_domains` | Phishing domain list from feeds | `{domain}` unique |
| `threat_intel_vpas` | Flagged UPI IDs | `{vpa}` unique |
| `threat_intel_numbers` | Flagged phone numbers | `{phone_number}` unique |
| `model_registry` | Agent version history and readiness | `{agent_id}` unique |
| `analytics_events` | Event log (90-day TTL) | `{event_type, timestamp}` |

Dual-write pattern:
- `persist_scan()` writes to both Supabase and MongoDB (`app/helpers.py`)
- `persist_report()` writes to both Supabase and MongoDB (`routers/meta.py`)
- Unified `/api/v1/scan` writes directly to MongoDB (`routers/scan.py`)
- Threat intel ingestion writes to MongoDB + warms Redis (`scripts/ingest_threats.py`)

### Redis (cache + rate limiting)
Keyspace conventions:

| Key pattern | TTL | Purpose |
|-------------|-----|---------|
| `rl:ip:{ip}:{route}` | 60s | Rate limit counter (60 req/min/IP) |
| `ti:domain:{domain}` | 24h | Threat intel cache |
| `ti:vpa:{vpa}` | 24h | Threat intel cache |
| `ti:phone:{phone}` | 24h | Threat intel cache |
| `cfg:app` | 5min | App config cache (reduces Supabase calls) |

Helpers in `app/data_intel/redis_ops.py`. All Redis calls are safe-fail (log warning, return None if disconnected).

## How the 15 Agents Connect to Endpoints

```
Unified Endpoint:  POST /api/v1/scan  (channel: sms|url|qr|upi|image|file|audio)
                         │
                    ┌────┴────┐
                    │  Router  │  (routers/scan.py)
                    └────┬────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
         channel=    channel=   channel=
         sms         url        upi
              │          │          │
    ┌─────────┴──┐  ┌───┴───┐  ┌──┴────────┐
    │ Agent 14   │  │Agent 4│  │Agent 6    │
    │ Agent 1    │  │Agent 3│  │Agent 7    │
    │ Agent 2(*) │  │Agent 8│  │Agent 1    │
    │ Agent 15   │  │Agent 15│  │Agent 14   │
    └─────────┬──┘  └───┬───┘  │Agent 15   │
              │          │      └───────────┘
              └──────────┼──────────┘
                         │
                   ┌─────┴─────┐
                   │ Agent 15  │
                   │ Ensemble  │
                   └─────┬─────┘
                         │
                   final_verdict, score
```

## Running Locally

```bash
cd backend
pip install -r requirements.txt
# Set env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, etc.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Running Tests

```bash
cd backend
pytest tests/ -v
```

## How to Open the Code Graph in Obsidian

1. Install Obsidian from https://obsidian.md
2. Open vault → select `backend/docs/obsidian`
3. Use the Graph View (Ctrl+G) to see all module dependencies
4. Regenerate with: `python scripts/generate_code_graph.py`
