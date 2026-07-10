"""Reproducible training pipeline for Agent 3 — URL Phishing Classifier.

This script regenerates the four Agent 3 artifacts:

    url_classifier.pkl      XGBoost model
    url_scaler.pkl          StandardScaler fitted on the training split
    url_feature_cols.pkl    ordered feature-column list
    url_model_report.json   honest metrics + provenance metadata

It exists to close a gap: the original artifacts were committed without the
training code, and their report showed ``auc/accuracy/f1 == 1.0`` — the classic
fingerprint of target leakage. Two things caused that:

1. **Label leakage.** The old feature set carried ``TLDLegitimateProb`` and
   ``URLCharProb`` (and, in the 50-feature run the report described,
   ``URLSimilarityIndex``). These PhiUSIIL columns are derived from the labels,
   so a single one drives AUC to ~1.0. They are dropped here — features come
   solely from :func:`app.ml.url_features.extract_url_features`, the same
   function used at inference time (no train/serve skew).

2. **Optimistic split.** A random row split lets the same domain land in both
   train and test. We use a ``GroupShuffleSplit`` keyed on the registered
   domain so no domain is shared across the split.

IMPORTANT — dataset limitation (read the PR / report ``notes`` field):
PhiUSIIL's legitimate class is a biased sample — effectively all legitimate
URLs are bare ``www.`` homepages with no path, over HTTPS. A leakage-free model
therefore still scores very high AUC on held-out PhiUSIIL domains by leaning on
``PathLength`` / ``IsHTTPS``, but it does NOT generalise: it over-flags
legitimate URLs that happen to carry a path (e.g. ``https://github.com/a/b``).
Reaching a genuinely trustworthy ~0.92-0.97 model requires diversified
legitimate negatives (pathful URLs, non-www domains), not just leakage removal.

Usage::

    python -m app.ml.training.train_url_model \
        --csv /path/to/PhiUSIIL_Phishing_URL_Dataset.csv

The dataset is the PhiUSIIL Phishing URL Dataset (UCI ML Repository id 967,
235,795 rows). label 1 = legitimate, 0 = phishing.
"""

import argparse
import json
import logging
from pathlib import Path

import joblib
import pandas as pd
import tldextract
import xgboost as xgb
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

from app.ml.url_features import FEATURE_COLUMNS, extract_url_features

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("scamshield.train.url")

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"
DATASET_NAME = "PhiUSIIL Phishing URL Dataset (UCI ML Repository id 967)"


def build_feature_matrix(urls: pd.Series) -> pd.DataFrame:
    rows = [extract_url_features(u) for u in urls]
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)


def registered_domains(urls: pd.Series) -> pd.Series:
    ext = tldextract.TLDExtract(suffix_list_urls=())  # offline snapshot
    return urls.map(lambda u: ext(u).top_domain_under_public_suffix or u)


def train(csv_path: str, test_size: float = 0.2, random_state: int = 42) -> dict:
    logger.info("Loading dataset from %s", csv_path)
    df = pd.read_csv(csv_path)
    if "URL" not in df.columns or "label" not in df.columns:
        raise ValueError("CSV must contain 'URL' and 'label' columns (PhiUSIIL schema)")

    # PhiUSIIL: label 1 = legitimate, 0 = phishing. Agent 3 predicts P(phishing),
    # so the positive class is the phishing rows.
    y = (df["label"] == 0).astype(int).values

    logger.info("Extracting %d leakage-free features from %d URLs", len(FEATURE_COLUMNS), len(df))
    X = build_feature_matrix(df["URL"])

    # Domain-grouped split: no registered domain appears in both train and test.
    groups = registered_domains(df["URL"])
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    logger.info("Split: %d train / %d test rows (grouped by domain)", len(train_idx), len(test_idx))

    scaler = StandardScaler().fit(X_train)
    X_train_s = scaler.transform(X_train)
    X_test_s = scaler.transform(X_test)

    params = dict(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.8,
        reg_lambda=2.0,
        min_child_weight=5,
        eval_metric="logloss",
        n_jobs=-1,
    )
    model = xgb.XGBClassifier(**params)
    model.fit(X_train_s, y_train)

    proba = model.predict_proba(X_test_s)[:, 1]
    preds = (proba >= 0.5).astype(int)
    metrics = {
        "auc": round(float(roc_auc_score(y_test, proba)), 4),
        "accuracy": round(float(accuracy_score(y_test, preds)), 4),
        "f1": round(float(f1_score(y_test, preds)), 4),
    }
    logger.info("Held-out metrics: %s", metrics)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACT_DIR / "url_classifier.pkl")
    joblib.dump(scaler, ARTIFACT_DIR / "url_scaler.pkl")
    joblib.dump(list(FEATURE_COLUMNS), ARTIFACT_DIR / "url_feature_cols.pkl")

    report = {
        **metrics,
        "best_params": params,
        "num_features": len(FEATURE_COLUMNS),
        "features": list(FEATURE_COLUMNS),
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "dataset": DATASET_NAME,
        "split": "GroupShuffleSplit by registered domain (no domain shared across split)",
        "leakage_features_removed": ["TLDLegitimateProb", "URLCharProb", "URLSimilarityIndex"],
        "notes": (
            "AUC is high because PhiUSIIL's legitimate class is a biased sample "
            "(virtually all legitimate URLs are bare www. homepages with no path, over HTTPS); "
            "this is a dataset-composition artifact, NOT label leakage. The model over-flags "
            "legitimate URLs that carry a path. Trustworthy generalisation requires diversified "
            "legitimate negatives (pathful URLs, non-www domains)."
        ),
    }
    (ARTIFACT_DIR / "url_model_report.json").write_text(json.dumps(report, indent=4))
    logger.info("Wrote artifacts to %s", ARTIFACT_DIR)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="Path to PhiUSIIL_Phishing_URL_Dataset.csv")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    train(args.csv, test_size=args.test_size, random_state=args.random_state)


if __name__ == "__main__":
    main()
