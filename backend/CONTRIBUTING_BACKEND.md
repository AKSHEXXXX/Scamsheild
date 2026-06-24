# Contributing to ScamShield Backend

## Adding a New Agent

1. Create the inference function in `app/ml/agents/inference.py`
2. Add a `_load_agentN_*()` function in `app/ml/model_loader.py`
3. Add status entry in `app/ml/artifacts/agent_status.json`
4. Add weight entry in `app/ml/artifacts/ensemble_weights.json` for each scan_type
5. Wire into the relevant router(s) in `routers/`
6. Add unit tests in `tests/test_agentN.py`
7. Regenerate code graph: `python scripts/generate_code_graph.py`
8. Run full test suite: `pytest tests/ -v`

## Adding a New Endpoint

1. Create a new file in `routers/` following the existing pattern
2. Register the router in `main.py`
3. Define request/response models in `app/models.py`
4. Add tests in `tests/`
5. Add the endpoint to the unified scanner in `routers/scan.py` if applicable

## Agent Status Conventions

| Status | Meaning | Ensemble Behavior |
|--------|---------|-------------------|
| `READY` | Production-grade, fully tested | Full weight applied |
| `BETA` | Functional but limited training data | Full weight, flagged in `/api/v1/agents` |
| `NOT_READY` | Stub returning -1 | Excluded from ensemble (weight 0) |

## Code Conventions

- **No comments in production code** unless explaining business logic
- **Pydantic models** for all request/response schemas
- **One agent per concern** — no cross-agent dependencies
- **Async endpoints** for I/O (DB calls, HTTP fetches); sync for CPU-bound ML
- **Environment variables** through `app/config.py` only
- **Logging** via `logging.getLogger("scamshield.module")`

## PR Checklist

- [ ] Tests pass: `pytest tests/ -v`
- [ ] No new warnings at startup
- [ ] `/health` returns 200 with correct model count
- [ ] Code graph regenerated
- [ ] Architecture audit updated
