from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.rpa_summary import SUMMARY_SHEET_NAME

FLOW_ACCOUNT_SIDE = {
    "bao_no": "debit_account",
    "bao_co": "credit_account",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build weakly supervised ML training files from RPA summary Excel")
    parser.add_argument("--summary", default="output/rpa_summary.xlsx", help="RPA summary Excel file")
    parser.add_argument("--tracking", default="", help="Legacy RPA tracking JSON file; overrides --summary when provided")
    parser.add_argument("--output-dir", default="data/training")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = _load_records(args.summary, args.tracking)
    frames = build_training_frames(records)
    reviewed_df = frames["reviewed"]
    object_df = frames["object"]
    exception_df = frames["exception"]

    reviewed_path = output_dir / "reviewed_transactions.xlsx"
    transaction_path = output_dir / "transaction_classifier_training.xlsx"
    object_path = output_dir / "object_ranker_training.xlsx"
    exception_path = output_dir / "exception_review_queue.xlsx"

    reviewed_df.to_excel(reviewed_path, index=False)
    reviewed_df.to_excel(transaction_path, index=False)
    object_df.to_excel(object_path, index=False)
    exception_df.to_excel(exception_path, index=False)

    summary = pd.DataFrame([
        {"metric": "source_rows", "value": len(records)},
        {"metric": "reviewed_transaction_rows", "value": len(reviewed_df)},
        {"metric": "object_training_rows", "value": len(object_df)},
        {"metric": "exception_review_rows", "value": len(exception_df)},
        {"metric": "unique_use_cases", "value": reviewed_df["correct_use_case"].nunique() if not reviewed_df.empty else 0},
    ])
    summary.to_excel(output_dir / "training_summary.xlsx", index=False)

    print(f"Wrote {reviewed_path} rows={len(reviewed_df)}")
    print(f"Wrote {transaction_path} rows={len(reviewed_df)}")
    print(f"Wrote {object_path} rows={len(object_df)}")
    print(f"Wrote {exception_path} rows={len(exception_df)}")
    print(f"Wrote {output_dir / 'training_summary.xlsx'}")
    return 0


def _load_records(summary_path: str, tracking_path: str = "") -> list[dict[str, Any]]:
    if tracking_path:
        legacy_path = Path(tracking_path)
        if not legacy_path.exists():
            raise SystemExit(f"Tracking file not found: {legacy_path}")
        return json.loads(legacy_path.read_text(encoding="utf-8"))

    path = Path(summary_path)
    if not path.exists():
        raise SystemExit(f"Summary file not found: {path}")
    try:
        df = pd.read_excel(path, sheet_name=SUMMARY_SHEET_NAME, dtype=object)
    except ValueError:
        df = pd.read_excel(path, sheet_name=0, dtype=object)
    df = df.where(pd.notna(df), "")
    return [_summary_row_to_training_record(row) for row in df.to_dict("records")]


def _summary_row_to_training_record(row: dict[str, Any]) -> dict[str, Any]:
    object_code = row.get("object_code", "")
    return {
        "transaction_uid": row.get("transaction_uid", ""),
        "source_file": row.get("source_file", ""),
        "original_row_index": row.get("source_row") or row.get("source_row_index", ""),
        "bank": row.get("bank") or row.get("bank_code", ""),
        "flow": row.get("flow") or row.get("direction", ""),
        "transaction_date": row.get("transaction_date", ""),
        "doc_no": row.get("doc_no", ""),
        "original_content": row.get("original_content", ""),
        "counterparty_raw": row.get("counterparty_raw", ""),
        "matched_object_code": object_code,
        "matched_object_name": row.get("object_name", ""),
        "reason": row.get("reason", ""),
        "debit_account": row.get("debit_account", ""),
        "credit_account": row.get("credit_account", ""),
        "amount": row.get("amount", ""),
        "use_case": row.get("use_case", ""),
        "object_match_source": row.get("object_match_source", ""),
        "confidence": row.get("confidence", 0),
        "processing_status": row.get("processing_status", "OK" if object_code != "ERROR" else "ERROR"),
        "status": row.get("processing_status", "OK" if object_code != "ERROR" else "ERROR"),
        "error_note": row.get("rpa_message", ""),
        "entities": {},
        "matched_candidates": [],
    }


def build_training_frames(records: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    reviewed_rows = [_reviewed_transaction_row(item) for item in records if _has_training_label(item)]
    object_rows = [row for item in records for row in _object_training_rows(item)]
    exception_rows = [_exception_review_row(item) for item in records if _processing_status(item) != "OK"]
    return {
        "reviewed": pd.DataFrame(reviewed_rows),
        "object": pd.DataFrame(object_rows),
        "exception": pd.DataFrame(exception_rows),
    }


def _has_training_label(item: dict[str, Any]) -> bool:
    if item.get("flow") not in FLOW_ACCOUNT_SIDE:
        return False
    if not item.get("use_case"):
        return False
    if item.get("matched_rule") == "ML":
        return False
    return bool(_correct_account(item))


def _has_object_label(item: dict[str, Any]) -> bool:
    code = str(item.get("matched_object_code") or "")
    if _processing_status(item) != "OK":
        return False
    if not code or code == "ERROR":
        return False
    if code.upper() == "LE PHAM":
        return False
    return item.get("flow") in FLOW_ACCOUNT_SIDE


def _has_safe_object_label(item: dict[str, Any]) -> bool:
    if not _has_object_label(item):
        return False
    review_status = str(item.get("review_status") or "").upper()
    if review_status in {"OK", "APPROVED", "REVIEWED"}:
        return True
    return str(item.get("object_match_source") or "") in {"tax_code", "alias_match", "catalog_phrase"}


def _reviewed_transaction_row(item: dict[str, Any]) -> dict[str, Any]:
    entities = item.get("entities") or {}
    object_code = item.get("matched_object_code") or ""
    return {
        "source_file": item.get("source_file", ""),
        "row_index": item.get("original_row_index", ""),
        "bank": item.get("bank", ""),
        "flow": item.get("flow", ""),
        "transaction_date": item.get("transaction_date", ""),
        "description": item.get("original_content", ""),
        "normalized_content": item.get("normalized_content", ""),
        "counterparty_raw": item.get("counterparty_raw", ""),
        "counterparty_hint": entities.get("counterparty_hint", ""),
        "counterparty_source": entities.get("counterparty_source", ""),
        "cleaned_description": entities.get("cleaned_description", ""),
        "intent": entities.get("intent", ""),
        "invoice_no": entities.get("invoice_no", ""),
        "bill_no": entities.get("bill_no", ""),
        "tax_code": entities.get("tax_code", ""),
        "bank_account_hint": entities.get("bank_account_hint", ""),
        "service_hint": entities.get("service_hint", ""),
        "correct_use_case": item.get("use_case", ""),
        "correct_account": _correct_account(item),
        "correct_object_code": "" if object_code == "ERROR" else object_code,
        "correct_object_name": item.get("matched_object_name", "") if object_code != "ERROR" else "",
        "review_status": "OK",
        "training_source": "AUTO_RULE_VERIFIER" if item.get("status") == "OK" else "AUTO_RULE_OBJECT_PENDING",
        "original_status": item.get("status", ""),
        "error_note": item.get("error_note", ""),
        "confidence": item.get("confidence", 0),
        "object_match_source": item.get("object_match_source", ""),
        "note": "Auto-labeled from deterministic accounting rules; review object fields when blank.",
    }


def _object_training_rows(item: dict[str, Any]) -> list[dict[str, Any]]:
    if not _has_safe_object_label(item):
        return []
    correct_code = str(item.get("matched_object_code") or "")
    candidates = list(item.get("matched_candidates") or [])
    if not any(str(candidate.get("code") or "") == correct_code for candidate in candidates):
        candidates.insert(
            0,
            {
                "code": correct_code,
                "name": item.get("matched_object_name", ""),
                "score": item.get("confidence", 0),
                "source": item.get("object_match_source", ""),
                "matched_on": "",
            },
        )
    rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for candidate in candidates:
        code = str(candidate.get("code") or "")
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        rows.append(_object_training_row(item, candidate, label=1 if code == correct_code else 0))
    return rows


def _object_training_row(item: dict[str, Any], candidate: dict[str, Any], label: int) -> dict[str, Any]:
    entities = item.get("entities") or {}
    return {
        "source_file": item.get("source_file", ""),
        "row_index": item.get("original_row_index", ""),
        "bank": item.get("bank", ""),
        "flow": item.get("flow", ""),
        "catalog": "payable" if item.get("flow") == "bao_no" else "receivable",
        "description": item.get("original_content", ""),
        "counterparty_raw": item.get("counterparty_raw", ""),
        "counterparty_hint": entities.get("counterparty_hint", ""),
        "cleaned_description": entities.get("cleaned_description", ""),
        "intent": entities.get("intent", ""),
        "service_hint": entities.get("service_hint", ""),
        "tax_code": entities.get("tax_code", ""),
        "object_match_source": item.get("object_match_source", ""),
        "correct_object_code": item.get("matched_object_code", ""),
        "correct_object_name": item.get("matched_object_name", ""),
        "correct_use_case": item.get("use_case", ""),
        "correct_account": _correct_account(item),
        "candidate_code": candidate.get("code", ""),
        "candidate_name": candidate.get("name", ""),
        "candidate_score": candidate.get("score", 0),
        "candidate_source": candidate.get("source", ""),
        "candidate_matched_on": candidate.get("matched_on", ""),
        "candidate_tax_code": candidate.get("tax_code", ""),
        "candidate_group_name": candidate.get("group_name", ""),
        "candidate_group_code": candidate.get("group_code", ""),
        "confidence": item.get("confidence", 0),
        "label": int(label),
        "training_source": "SAFE_OBJECT_MATCH",
    }


def _exception_review_row(item: dict[str, Any]) -> dict[str, Any]:
    row = _reviewed_transaction_row(item) if _has_training_label(item) else {
        "source_file": item.get("source_file", ""),
        "row_index": item.get("original_row_index", ""),
        "bank": item.get("bank", ""),
        "flow": item.get("flow", ""),
        "transaction_date": item.get("transaction_date", ""),
        "description": item.get("original_content", ""),
        "counterparty_raw": item.get("counterparty_raw", ""),
        "correct_use_case": "",
        "correct_account": "",
        "correct_object_code": "",
        "correct_object_name": "",
        "review_status": "NEEDS_REVIEW",
        "note": "Fill correct labels if this row should become training data.",
    }
    row["review_status"] = "NEEDS_REVIEW"
    row["original_status"] = item.get("status", "")
    row["error_note"] = item.get("error_note", "")
    return row


def _correct_account(item: dict[str, Any]) -> str:
    side = FLOW_ACCOUNT_SIDE.get(item.get("flow"), "")
    return str(item.get(side) or "") if side else ""


def _processing_status(item: dict[str, Any]) -> str:
    return str(item.get("processing_status") or item.get("original_status") or item.get("status") or "")


if __name__ == "__main__":
    raise SystemExit(main())

