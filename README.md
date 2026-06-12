# ScamShield Backend

FastAPI backend for ScamShield — a mobile app that detects scams in SMS, messages, and screenshots using keyword/heuristic analysis, OCR, and threat-intel blacklists.

## What Was Built

### Backend API (FastAPI)
- **Text Analysis** — Scans messages for scam indicators: blacklisted UPI IDs, fraud phone numbers, malicious URLs, pressure tactics (100+ keywords), brand impersonation (`.con` typosquat detection + fake brand comms)
- **OCR Sandbox** — Extracts text from screenshots using Tesseract OCR, then runs the same analysis pipeline
- **Reporting** — Users can submit fraud reports (UPI, phone, link, other) with channel context (WhatsApp, SMS, phone call, email)
- **History** — Per-user scan/report history with counts breakdown (messages vs screenshots vs reports)
- **Config** — Server-driven settings (daily scan credit cap, sensitivity threshold, ad frequency) fetched at runtime

### Authentication
- **Device-ID based** — Anonymous users identified via `X-Device-Id` header, no sign-up required
- **Supabase Auth optional** — Authenticated users can pass a Bearer JWT to get user-level history across devices
- **Credit-capped scanning** — Daily scan limit enforced per device/user, configured server-side

### Detection Engine
- **UPI/VPA lookup** — Checks against blacklisted UPI IDs in Supabase
- **Phone number lookup** — Matches against known fraud numbers (Indian format, +91 flexible)
- **URL sandboxing** — Follows redirects, extracts final domain, checks reputation against blacklisted domains
- **Keyword pressure analysis** — 100+ regex patterns covering: KYC fraud, parcel/courier scams, income tax threats, legal notices, lottery/prize, tech support, order/refund phishing, urgency escalation, brand impersonation
- **Scoring formula** — Weighted combination (60% text analysis + 40% domain risk + optional impersonation boost), clamped to 0-100, mapped to low_risk / suspicious / high_risk verdicts

### Data Layer (Supabase)
| Table | Purpose |
|---|---|
| `app_config` | Single-row server configuration |
| `scans` | Scan telemetry with device/user isolation |
| `reports` | User-submitted fraud reports |
| `blacklisted_vpas` | Known fraudulent UPI IDs |
| `blacklisted_numbers` | Known scam phone numbers |
| `blacklisted_domains` | Malicious/phishing domains |

### Threat Intelligence
- **Nightly ingestion** — GitHub Actions cron pulls from OpenPhish and PhishTank, upserts domains into blacklist
- **Extensible** — Feed list in `scripts/ingest_threats.py` can add phone/UPI sources

### CI & Quality
- **Labeled test fixture** — 10 known-scam + 10 known-legitimate messages enforce a scams-high / legit-low split
- **CI pipeline** — Runs all tests on every push/PR; Supabase-dependent tests skip gracefully if credentials aren't set
- **Regression protection** — Any tuning change that fixes one scam but breaks legitimate messages is caught automatically

## Architecture

```
backend/
├── app/
│   ├── analytics.py    # 100+ scam keyword patterns
│   ├── analyzer.py     # Core detection engine
│   ├── auth.py         # Device-ID + JWT auth
│   ├── config.py       # Environment settings
│   ├── database.py     # Supabase client (lazy init)
│   ├── models.py       # Pydantic schemas
│   ├── ocr.py          # Tesseract OCR
│   ├── sandbox.py      # URL sandboxing
│   └── scoring.py      # Risk scoring formula
├── scripts/
│   ├── schema.sql      # Full database schema
│   ├── setup.py        # One-time project setup
│   └── ingest_threats.py  # Nightly threat intel sync
├── tests/
│   ├── test_main.py        # Unit + labeled split tests
│   └── labeled_samples.py  # 10 scam / 10 legit fixture
├── main.py             # FastAPI app
├── Dockerfile          # Python 3.11 + Tesseract
└── requirements.txt
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/api/v1/config` | GET | App configuration (credit cap, threshold, etc.) |
| `/api/v1/analyze-text` | POST | Analyze text for scams |
| `/api/v1/sandbox-image` | POST | OCR screenshot + analyze |
| `/api/v1/report` | POST | Submit fraud report |
| `/api/v1/history` | GET | User scan/report history |
| `/api/v1/scan/{id}` | GET | Single scan detail |

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # Fill in SUPABASE_URL and SUPABASE_SERVICE_KEY
uvicorn main:app --reload
```

## Tests

```bash
pytest tests/ -v
```

The labeled split test (10 scam + 10 legitimate messages) runs automatically to catch regressions. Supabase-dependent tests skip when credentials aren't set.

## Deployment

Build and run the Docker container with `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `ENVIRONMENT` configured as environment variables. The service listens on port 8000 by default (overridable via `PORT`).
