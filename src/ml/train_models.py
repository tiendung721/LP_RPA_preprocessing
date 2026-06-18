from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

try:
    import joblib
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"Missing ML dependency: {exc}")

from ..normalizer import normalize_text
from .features import build_object_candidate_text

REQUIRED_COLUMNS = [
    "flow",
    "bank",
    "description",
    "correct_use_case",
    "correct_account",
    "review_status",
]

OBJECT_REQUIRED_COLUMNS = [
    "bank",
    "flow",
    "catalog",
    "description",
    "counterparty_raw",
    "counterparty_hint",
    "cleaned_description",
    "correct_use_case",
    "correct_account",
    "candidate_code",
    "candidate_name",
    "candidate_score",
    "candidate_source",
    "candidate_matched_on",
    "label",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Train offline accounting agent ML models from reviewed feedback")
    parser.add_argument("--feedback", default="data/training/reviewed_transactions.xlsx")
    parser.add_argument("--object-feedback", default="data/training/object_ranker_training.xlsx")
    parser.add_argument("--models-dir", default="models")
    parser.add_argument("--min-object-rows", type=int, default=50)
    args = parser.parse_args()

    feedback_path = Path(args.feedback)
    object_feedback_path = Path(args.object_feedback)
    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    if not feedback_path.exists():
        _create_template(feedback_path)
        print(f"Created feedback template: {feedback_path}")
    else:
        _train_transaction_classifier(feedback_path, models_dir)
    _train_object_ranker(object_feedback_path, models_dir, min_rows=args.min_object_rows)
    return 0


def _train_transaction_classifier(feedback_path: Path, models_dir: Path) -> None:
    df = pd.read_excel(feedback_path, dtype=object)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise SystemExit(f"Feedback file missing columns: {missing}")

    df = df[df["review_status"].astype(str).str.upper().isin(["OK", "APPROVED", "REVIEWED"])]
    df = df.dropna(subset=["description", "correct_use_case", "correct_account"])
    if df["correct_use_case"].nunique() < 2 or len(df) < 5:
        print("Not enough reviewed rows to train classifier. Need at least 5 rows and 2 use cases.")
        return

    texts = [
        " ".join([str(row.get("flow", "")), str(row.get("bank", "")), normalize_text(row.get("description", ""))])
        for _, row in df.iterrows()
    ]
    labels = [f"{row['correct_use_case']}|{row['correct_account']}" for _, row in df.iterrows()]
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ("clf", LogisticRegression(max_iter=1000)),
    ])
    model.fit(texts, labels)
    joblib.dump(model, models_dir / "transaction_classifier.joblib")
    print(f"Saved classifier: {models_dir / 'transaction_classifier.joblib'}")


def _train_object_ranker(object_feedback_path: Path, models_dir: Path, min_rows: int = 50) -> None:
    if not object_feedback_path.exists():
        print(f"Object ranker feedback file not found: {object_feedback_path}")
        return
    df = pd.read_excel(object_feedback_path, dtype=object)
    missing = [col for col in OBJECT_REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        print(f"Object ranker feedback missing columns; skipping object ranker: {missing}")
        return
    df = df.dropna(subset=["description", "candidate_code", "label"])
    df["label"] = df["label"].astype(int)
    if len(df) < min_rows or df["label"].nunique() < 2:
        print(f"Not enough object rows to train ranker. Need at least {min_rows} rows and both labels.")
        return

    texts = [
        build_object_candidate_text(_object_context(row), _object_candidate(row))
        for _, row in df.iterrows()
    ]
    labels = [int(row["label"]) for _, row in df.iterrows()]
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    model.fit(texts, labels)
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, models_dir / "object_ranker.joblib")
    print(f"Saved object ranker: {models_dir / 'object_ranker.joblib'}")


def _object_context(row: pd.Series) -> dict[str, object]:
    return {
        "bank": row.get("bank", ""),
        "flow": row.get("flow", ""),
        "catalog": row.get("catalog", ""),
        "use_case": row.get("correct_use_case", ""),
        "account": row.get("correct_account", ""),
        "description": row.get("description", ""),
        "counterparty_raw": row.get("counterparty_raw", ""),
        "counterparty_hint": row.get("counterparty_hint", ""),
        "service_hint": row.get("service_hint", ""),
        "tax_code": row.get("tax_code", ""),
    }


def _object_candidate(row: pd.Series) -> dict[str, object]:
    return {
        "code": row.get("candidate_code", ""),
        "name": row.get("candidate_name", ""),
        "score": row.get("candidate_score", ""),
        "source": row.get("candidate_source", ""),
        "matched_on": row.get("candidate_matched_on", ""),
        "tax_code": row.get("candidate_tax_code", ""),
        "group_name": row.get("candidate_group_name", ""),
        "group_code": row.get("candidate_group_code", ""),
    }


def _create_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(columns=[
        "source_file",
        "row_index",
        "bank",
        "flow",
        "description",
        "counterparty_raw",
        "correct_use_case",
        "correct_account",
        "correct_object_code",
        "correct_object_name",
        "review_status",
        "note",
    ])
    df.to_excel(path, index=False)


if __name__ == "__main__":
    raise SystemExit(main())

