from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

FLOW_ACCOUNT_SIDE = {
    "bao_no": "debit_account",
    "bao_co": "credit_account",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build weakly supervised ML training files from RPA tracking JSON")
    parser.add_argument("--tracking", default="output/rpa_tracking.json")
    parser.add_argument("--output-dir", default="data/training")
    args = parser.parse_args()

    tracking_path = Path(args.tracking)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not tracking_path.exists():
        raise SystemExit(f"Tracking file not found: {tracking_path}")

    records = json.loads(tracking_path.read_text(encoding="utf-8"))
    reviewed_rows = [_reviewed_transaction_row(item) for item in records if _has_training_label(item)]
    object_rows = [_object_training_row(item) for item in records if _has_object_label(item)]
    exception_rows = [_exception_review_row(item) for item in records if item.get("status") != "OK"]

    reviewed_df = pd.DataFrame(reviewed_rows)
    object_df = pd.DataFrame(object_rows)
    exception_df = pd.DataFrame(exception_rows)

    reviewed_path = output_dir / "reviewed_transactions.xlsx"
    transaction_path = output_dir / "transaction_classifier_training.xlsx"
    object_path = output_dir / "object_ranker_training.xlsx"
    exception_path = output_dir / "exception_review_queue.xlsx"

    reviewed_df.to_excel(reviewed_path, index=False)
    reviewed_df.to_excel(transaction_path, index=False)
    object_df.to_excel(object_path, index=False)
    exception_df.to_excel(exception_path, index=False)

    summary = pd.DataFrame([
        {"metric": "tracking_rows", "value": len(records)},
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
    if item.get("status") != "OK":
        return False
    if not code or code == "ERROR":
        return False
    if code.upper() == "LE PHAM":
        return False
    return item.get("flow") in FLOW_ACCOUNT_SIDE


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


def _object_training_row(item: dict[str, Any]) -> dict[str, Any]:
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
        "object_match_source": item.get("object_match_source", ""),
        "correct_object_code": item.get("matched_object_code", ""),
        "correct_object_name": item.get("matched_object_name", ""),
        "correct_use_case": item.get("use_case", ""),
        "correct_account": _correct_account(item),
        "confidence": item.get("confidence", 0),
        "label": 1,
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


if __name__ == "__main__":
    raise SystemExit(main())

