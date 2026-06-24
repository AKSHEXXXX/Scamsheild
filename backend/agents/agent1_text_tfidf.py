import pickle
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")

from utils.text import preprocess_text

def load(model_dir: Path) -> dict:
    vectorizer = pickle.load(open(model_dir / "text_tfidf_vectorizer.pkl", "rb"))
    classifier = pickle.load(open(model_dir / "text_logreg_classifier.pkl", "rb"))
    return {"vectorizer": vectorizer, "classifier": classifier}

def predict(text: str, artifacts: dict) -> float:
    cleaned = preprocess_text(text)
    vec = artifacts["vectorizer"].transform([cleaned])
    proba = artifacts["classifier"].predict_proba(vec)
    scam_idx = 1 if proba.shape[1] > 1 else 0
    return float(proba[0][scam_idx])
