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

REQUIRED_COLUMNS = [
    "flow",
    "bank",
    "description",
    "correct_use_case",
    "correct_account",
    "review_status",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Train offline accounting agent ML models from reviewed feedback")
    parser.add_argument("--feedback", default="data/training/reviewed_transactions.xlsx")
    parser.add_argument("--models-dir", default="models")
    args = parser.parse_args()

    feedback_path = Path(args.feedback)
    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    if not feedback_path.exists():
        _create_template(feedback_path)
        print(f"Created feedback template: {feedback_path}")
        return 0

    df = pd.read_excel(feedback_path, dtype=object)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise SystemExit(f"Feedback file missing columns: {missing}")

    df = df[df["review_status"].astype(str).str.upper().isin(["OK", "APPROVED", "REVIEWED"])]
    df = df.dropna(subset=["description", "correct_use_case", "correct_account"])
    if df["correct_use_case"].nunique() < 2 or len(df) < 5:
        print("Not enough reviewed rows to train classifier. Need at least 5 rows and 2 use cases.")
        return 0

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
    return 0


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

