from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .models import ProcessedTransaction
from .transaction_identity import assign_transaction_uids


SUMMARY_SHEET_NAME = "RPA_SUMMARY"
STATUS_PENDING = "chưa nhập"
STATUS_IN_PROGRESS = "đang nhập"
STATUS_DONE = "hoàn thành"
STATUS_ERROR = "lỗi"
STATUS_SKIPPED = "bỏ qua"
STATUS_REVIEW = "cần kiểm tra"

ELIGIBLE_RPA_STATUSES = {STATUS_PENDING, STATUS_ERROR}

SUMMARY_COLUMNS = [
    "transaction_uid",
    "source_file",
    "source_sheet",
    "source_row_index",
    "bank",
    "flow",
    "transaction_date",
    "doc_no",
    "original_content",
    "counterparty_raw",
    "amount",
    "object_code",
    "object_name",
    "debit_account",
    "credit_account",
    "reason",
    "status",
    "last_run_id",
    "rpa_started_at",
    "rpa_finished_at",
    "rpa_message",
    "voucher_no",
    "created_at",
    "updated_at",
]


@dataclass
class RpaRunState:
    run_id: str
    summary_df: pd.DataFrame
    rpa_items: list[ProcessedTransaction]


def make_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def prepare_rpa_run(
    processed: list[ProcessedTransaction],
    summary_path: str | Path,
    run_id: str | None = None,
) -> RpaRunState:
    run_id = run_id or make_run_id()
    if any(not item.transaction_uid for item in processed):
        assign_transaction_uids(processed)

    existing_df = load_summary(summary_path)
    existing_by_uid = {
        str(row.get("transaction_uid", "")).strip(): _clean_record(row)
        for row in existing_df.to_dict("records")
        if str(row.get("transaction_uid", "")).strip()
    }

    now = _now()
    records_by_uid: dict[str, dict[str, Any]] = {}
    rpa_items: list[ProcessedTransaction] = []
    seen: set[str] = set()

    for item in processed:
        uid = item.transaction_uid
        if not uid:
            continue
        previous = existing_by_uid.get(uid)
        record = _merge_record(previous, item, run_id, now)
        records_by_uid[uid] = record
        seen.add(uid)

        item.rpa_status = str(record.get("status", "")).strip()
        if item.status == "OK" and item.rpa_status in ELIGIBLE_RPA_STATUSES:
            rpa_items.append(item)

    for row in existing_df.to_dict("records"):
        uid = str(row.get("transaction_uid", "")).strip()
        if uid and uid not in seen:
            records_by_uid[uid] = _ensure_summary_record(_clean_record(row))

    summary_df = pd.DataFrame(list(records_by_uid.values()), columns=SUMMARY_COLUMNS)
    return RpaRunState(run_id=run_id, summary_df=summary_df, rpa_items=rpa_items)


def load_summary(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    try:
        df = pd.read_excel(path, sheet_name=SUMMARY_SHEET_NAME, dtype=object)
    except ValueError:
        df = pd.read_excel(path, sheet_name=0, dtype=object)
    return _ensure_columns(df)


def write_summary(summary_df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _ensure_columns(summary_df)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=SUMMARY_SHEET_NAME, index=False)
        status_df = _status_counts(df)
        status_df.to_excel(writer, sheet_name="STATUS_COUNTS", index=False)
        for sheet_name in (SUMMARY_SHEET_NAME, "STATUS_COUNTS"):
            _format_sheet(writer.book[sheet_name])


def update_rpa_status(
    summary_path: str | Path,
    transaction_uid: str,
    status: str,
    run_id: str = "",
    message: str = "",
    voucher_no: str = "",
) -> None:
    if status not in {STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_ERROR, STATUS_SKIPPED, STATUS_REVIEW}:
        raise ValueError(f"Unsupported RPA status: {status}")

    df = load_summary(summary_path)
    matches = df.index[df["transaction_uid"].astype(str) == str(transaction_uid)].tolist()
    if not matches:
        raise KeyError(f"transaction_uid not found in RPA summary: {transaction_uid}")

    row_idx = matches[0]
    now = _now()
    df.at[row_idx, "status"] = status
    df.at[row_idx, "updated_at"] = now
    if run_id:
        df.at[row_idx, "last_run_id"] = run_id
    if message or status in {STATUS_DONE, STATUS_ERROR, STATUS_REVIEW}:
        df.at[row_idx, "rpa_message"] = message
    if voucher_no:
        df.at[row_idx, "voucher_no"] = voucher_no
    if status == STATUS_IN_PROGRESS:
        df.at[row_idx, "rpa_started_at"] = now
        df.at[row_idx, "rpa_finished_at"] = ""
    elif status in {STATUS_DONE, STATUS_ERROR, STATUS_REVIEW, STATUS_SKIPPED}:
        df.at[row_idx, "rpa_finished_at"] = now

    write_summary(df, summary_path)


def mark_rpa_started(summary_path: str | Path, transaction_uid: str, run_id: str) -> None:
    update_rpa_status(summary_path, transaction_uid, STATUS_IN_PROGRESS, run_id=run_id)


def mark_rpa_done(
    summary_path: str | Path,
    transaction_uid: str,
    run_id: str,
    voucher_no: str = "",
    message: str = "",
) -> None:
    update_rpa_status(summary_path, transaction_uid, STATUS_DONE, run_id=run_id, message=message, voucher_no=voucher_no)


def mark_rpa_error(summary_path: str | Path, transaction_uid: str, run_id: str, message: str) -> None:
    update_rpa_status(summary_path, transaction_uid, STATUS_ERROR, run_id=run_id, message=message)


def _merge_record(
    previous: dict[str, Any] | None,
    item: ProcessedTransaction,
    run_id: str,
    now: str,
) -> dict[str, Any]:
    current = _record_from_item(item, run_id, now)
    if not previous:
        current["status"] = STATUS_PENDING if item.status == "OK" else STATUS_REVIEW
        current["rpa_message"] = "" if item.status == "OK" else item.error_note
        return current

    previous = _ensure_summary_record(previous)
    previous_status = str(previous.get("status", "")).strip()

    if previous_status in {STATUS_DONE, STATUS_SKIPPED}:
        return previous

    record = {**current, "created_at": previous.get("created_at") or now}
    _preserve_rpa_fields(record, previous)

    if previous_status == STATUS_IN_PROGRESS:
        record["status"] = STATUS_REVIEW
        record["rpa_message"] = previous.get("rpa_message") or "Dòng đang nhập từ run trước; cần kiểm tra trước khi chạy lại"
        return record

    if item.status == "OK":
        record["status"] = previous_status if previous_status in ELIGIBLE_RPA_STATUSES else STATUS_PENDING
        if record["status"] == STATUS_PENDING and previous_status != STATUS_ERROR:
            record["rpa_message"] = ""
        return record

    record["status"] = STATUS_REVIEW
    record["rpa_message"] = item.error_note
    return record


def _record_from_item(item: ProcessedTransaction, run_id: str, now: str) -> dict[str, Any]:
    return {
        "transaction_uid": item.transaction_uid,
        "source_file": item.source_file,
        "source_sheet": item.source_sheet,
        "source_row_index": item.original_row_index,
        "bank": item.bank,
        "flow": item.flow,
        "transaction_date": item.transaction_date,
        "doc_no": item.doc_no,
        "original_content": item.original_content,
        "counterparty_raw": item.counterparty_raw,
        "amount": item.amount,
        "object_code": item.object_code,
        "object_name": item.object_name,
        "debit_account": item.debit_account,
        "credit_account": item.credit_account,
        "reason": item.reason,
        "status": "",
        "last_run_id": run_id,
        "rpa_started_at": "",
        "rpa_finished_at": "",
        "rpa_message": "",
        "voucher_no": "",
        "created_at": now,
        "updated_at": now,
    }


def _preserve_rpa_fields(record: dict[str, Any], previous: dict[str, Any]) -> None:
    for field in ("rpa_started_at", "rpa_finished_at", "rpa_message", "voucher_no"):
        record[field] = previous.get(field, "")


def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in SUMMARY_COLUMNS:
        if column not in result.columns:
            result[column] = ""
    return result[SUMMARY_COLUMNS]


def _ensure_summary_record(row: dict[str, Any]) -> dict[str, Any]:
    return {column: _clean_cell(row.get(column, "")) for column in SUMMARY_COLUMNS}


def _clean_record(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _clean_cell(value) for key, value in row.items()}


def _clean_cell(value: Any) -> Any:
    if pd.isna(value):
        return ""
    return value


def _status_counts(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["status", "count"])
    counts = df["status"].fillna("").astype(str).value_counts().reset_index()
    counts.columns = ["status", "count"]
    return counts


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _format_sheet(ws) -> None:
    for cell in ws[1]:
        cell.font = Font(bold=True)
    header_names = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
    for name, idx in header_names.items():
        if name and ("date" in str(name).lower() or str(name) in {"created_at", "updated_at"}):
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=idx).number_format = "DD/MM/YYYY"
        if name in {"amount", "count"}:
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=idx).number_format = "#,##0"

    for col_idx in range(1, ws.max_column + 1):
        letter = get_column_letter(col_idx)
        max_len = 0
        for cell in ws[letter]:
            if cell.value is None:
                continue
            max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 60)
