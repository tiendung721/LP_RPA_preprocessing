import pandas as pd

from src.ml.build_training_data import build_training_frames
from src.ml.train_models import _train_object_ranker


def _safe_record():
    return {
        "source_file": "sample.xlsx",
        "original_row_index": 2,
        "bank": "ACB",
        "flow": "bao_no",
        "processing_status": "OK",
        "original_content": "TT CHO RIGHT TARGET",
        "normalized_content": "TT CHO RIGHT TARGET",
        "counterparty_raw": "",
        "entities": {
            "counterparty_hint": "RIGHT TARGET",
            "cleaned_description": "TT CHO RIGHT TARGET",
            "intent": "THANH TOAN",
            "service_hint": "",
            "tax_code": "",
        },
        "object_match_source": "catalog_phrase",
        "matched_object_code": "RIGHT",
        "matched_object_name": "Cong ty RIGHT TARGET",
        "use_case": "Chi phí thanh toán",
        "debit_account": "331",
        "credit_account": "1121CT",
        "confidence": 0.95,
        "matched_candidates": [
            {"code": "RIGHT", "name": "Cong ty RIGHT TARGET", "score": 100, "source": "catalog_phrase", "matched_on": "RIGHT TARGET"},
            {"code": "WRONG", "name": "Cong ty WRONG TARGET", "score": 96, "source": "entity_match", "matched_on": "TARGET"},
        ],
    }


def _unsafe_record():
    record = _safe_record()
    record["object_match_source"] = "fuzzy_name"
    record["matched_object_code"] = "FUZZY"
    return record


def test_build_training_frames_creates_pairwise_object_rows_only_from_safe_labels():
    frames = build_training_frames([_safe_record(), _unsafe_record()])
    object_df = frames["object"]

    assert len(object_df) == 2
    assert set(object_df["candidate_code"]) == {"RIGHT", "WRONG"}
    assert object_df.set_index("candidate_code").loc["RIGHT", "label"] == 1
    assert object_df.set_index("candidate_code").loc["WRONG", "label"] == 0


def test_train_object_ranker_writes_model(tmp_path):
    object_path = tmp_path / "object_ranker_training.xlsx"
    models_dir = tmp_path / "models"
    df = build_training_frames([_safe_record()])["object"]
    pd.concat([df, df], ignore_index=True).to_excel(object_path, index=False)

    _train_object_ranker(object_path, models_dir, min_rows=2)

    assert (models_dir / "object_ranker.joblib").exists()
