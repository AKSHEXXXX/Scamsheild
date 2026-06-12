# ScamShield Backend

FastAPI backend for ScamShield — a mobile app that detects scams in SMS, messages, and screenshots using keyword/heuristic analysis, OCR, and threat-intel blacklists.

## Architecture

```
backend/
├── app/
│   ├── analytics.py    # 100+ scam keyword patterns
│   ├── analyzer.py     # Core detection engine
│   ├── auth.py         # Device-ID + JWT auth
│   ├── config.py       # Environment settings
│   ├── database.py     # Supabase client
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
| `/api/v1/config` | GET | App configuration |
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

Labeled split tests (10 scams + 10 legit) run automatically to prevent regressions.
Integration tests against Supabase require `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` env vars.

## Deployment

Build the Docker image and set these environment variables:

| Variable | Value |
|---|---|
| `SUPABASE_URL` | `https://pmwdoxemzdupicidzmze.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Your service role key |
| `ENVIRONMENT` | `production` |
