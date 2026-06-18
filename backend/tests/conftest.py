import pytest

def pytest_configure(config):
    """Load ML models once at test session start."""
    from app.ml.model_loader import load_all
    load_all()
    from models.loader import load_all_models
    try:
        load_all_models()
    except RuntimeError:
        pass
