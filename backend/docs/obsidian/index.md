# ScamShield Backend — Code Graph

Open this folder in Obsidian to navigate the codebase visually.

## Entry Points
- [[main]] — FastAPI app, router registration, lifespan events
- [[routers/scan]] — Unified `/api/v1/scan` endpoint
- [[routers/text]] — `POST /api/v1/analyze-text`
- [[routers/url]] — `POST /api/v1/analyze-url` / `/api/v1/check-url`
- [[routers/qr]] — `POST /api/v1/check-qr`
- [[routers/upi]] — `POST /api/v1/analyze-upi`
- [[routers/image]] — `POST /api/v1/sandbox-image` / `/api/v1/sandbox-file`
- [[routers/audio]] — `POST /api/v1/analyze-audio` (stub)
- [[routers/meta]] — `/health`, `/api/v1/config`, `/api/v1/agents`, `/api/v1/report`, `/api/v1/history`

## Agent Layer
- [[agents/agent1_text_tfidf]] — TF-IDF + Logistic Regression text classifier
- [[agents/agent15_ensemble]] — Weighted ensemble scorer + hard overrides
- [[agents/agent4_blacklist]] — Domain blacklist checker

## ML Core (inference)
- [[app/ml/agents/inference]] — All 15 agent inference functions
- [[app/ml/ensemble]] — Ensemble scoring engine (alternative path)
- [[app/ml/model_loader]] — Model loading, status registry
- [[app/ml/upi_heuristic_engine]] — UPI rule engine (YAML-driven)

## Core App
- [[app/config]] — Environment config, settings singleton
- [[app/database]] — Supabase client (lazy singleton)
- [[app/database_ext]] — MongoDB + Redis connection management
- [[app/auth]] — JWT authentication, `require_user()`
- [[app/helpers]] — `persist_scan()`, `get_config_dict()`
- [[app/models]] — Pydantic request/response models
- [[app/analyzer]] — Full multi-agent orchestrator (image pipeline)
- [[app/ocr]] — Tesseract OCR pipeline
- [[app/scoring]] — Score thresholds, `_compute_verdict()`

## Data & Scripts
- [[scripts/download_models]] — Model artifact downloader
- [[scripts/ingest_threats]] — Threat intel feed ingestion
- [[scripts/setup]] — Setup script

## Dependencies Map

```
main → routers/* → app/auth → app/database
                 → app/helpers → app/database
                 → app/ml/agents/inference → app/ml/model_loader
                                          → app/utils/text
                 → agents/agent15_ensemble → artifacts/ensemble_weights.json
                 → agents/agent1_text_tfidf
                 → agents/agent4_blacklist
```

```
app/ml/model_loader → all _load_agent*() functions
                   → artifacts/*.pkl, *.json, *.yaml
```

```
app/analyzer → app/ml/model_loader
             → app/ml/agents/inference
             → app/ml/ensemble
             → app/ocr
             → supabase (blacklist checks)
```
