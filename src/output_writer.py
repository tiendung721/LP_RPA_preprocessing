from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .models import ProcessedTransaction
from .rpa_summary import STATUS_PENDING, prepare_rpa_run, write_summary


RPA_COLUMNS = ["Ngày CT", "Mã ĐT", "Lí do", "TK nợ", "TK có", "Thành tiền"]
RPA_TASK_COLUMNS = [
    "run_id",
    "task_id",
    "transaction_uid",
    "flow",
    "input_sheet",
    "input_excel_row",
    "summary_status",
    "source_file",
    "source_sheet",
    "source_row_index",
]


def write_outputs(processed: list[ProcessedTransaction], output_dir: str | Path, config: dict[str, Any]) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_cfg = config.get("output", {})
    excel_path = output_dir / output_cfg.get("excel_file", "rpa_input.xlsx")
    tracking_path = output_dir / output_cfg.get("tracking_file", "rpa_tracking.json")
    summary_path = output_dir / output_cfg.get("summary_file", "rpa_summary.xlsx")
    run_state = prepare_rpa_run(processed, summary_path)
    write_summary(run_state.summary_df, summary_path)
    write_excel(processed, excel_path, run_id=run_state.run_id, rpa_items=run_state.rpa_items)
    write_tracking(processed, tracking_path)


def write_excel(
    processed: list[ProcessedTransaction],
    path: str | Path,
    run_id: str | None = None,
    rpa_items: list[ProcessedTransaction] | None = None,
) -> None:
    path = Path(path)
    input_items = rpa_items if rpa_items is not None else processed
    bao_no_items = [item for item in input_items if item.status == "OK" and item.flow == "bao_no"]
    bao_co_items = [item for item in input_items if item.status == "OK" and item.flow == "bao_co"]
    bao_no_df = pd.DataFrame(
        [_rpa_record(item) for item in bao_no_items],
        columns=RPA_COLUMNS,
    )
    bao_co_df = pd.DataFrame(
        [_rpa_record(item) for item in bao_co_items],
        columns=RPA_COLUMNS,
    )
    exception_df = pd.DataFrame([_exception_record(item) for item in processed if item.status != "OK"])
    summary_df = pd.DataFrame(_summary_records(processed))
    task_df = pd.DataFrame(_task_records(bao_no_items, bao_co_items, run_id), columns=RPA_TASK_COLUMNS)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        bao_no_df.to_excel(writer, sheet_name="BAO_NO_INPUT", index=False)
        bao_co_df.to_excel(writer, sheet_name="BAO_CO_INPUT", index=False)
        exception_df.to_excel(writer, sheet_name="EXCEPTION", index=False)
        summary_df.to_excel(writer, sheet_name="SUMMARY", index=False)
        if run_id:
            task_df.to_excel(writer, sheet_name="RPA_TASKS", index=False)
        sheet_names = ["BAO_NO_INPUT", "BAO_CO_INPUT", "EXCEPTION", "SUMMARY"]
        if run_id:
            sheet_names.append("RPA_TASKS")
        for sheet_name in sheet_names:
            _format_sheet(writer.book[sheet_name])


def write_tracking(processed: list[ProcessedTransaction], path: str | Path) -> None:
    records = [_tracking_record(item) for item in processed]
    Path(path).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def _rpa_record(item: ProcessedTransaction) -> dict[str, Any]:
    return {
        "Ngày CT": item.transaction_date,
        "Mã ĐT": item.object_code,
        "Lí do": item.reason,
        "TK nợ": item.debit_account,
        "TK có": item.credit_account,
        "Thành tiền": item.amount,
    }


def _exception_record(item: ProcessedTransaction) -> dict[str, Any]:
    return {
        "Mã định danh": item.transaction_uid,
        "File gốc": item.source_file,
        "Sheet gốc": item.source_sheet,
        "Dòng gốc": item.original_row_index,
        "Ngân hàng": item.bank,
        "Luồng": item.flow,
        "Ngày CT": item.transaction_date,
        "Nội dung giao dịch gốc": item.original_content,
        "Người hưởng/Người chuyển": item.counterparty_raw,
        "Mã ĐT": item.object_code,
        "Tên ĐT suy luận": item.object_name,
        "TK nợ": item.debit_account,
        "TK có": item.credit_account,
        "Thành tiền": item.amount,
        "Use case dự đoán": item.use_case,
        "Trạng thái": item.status,
        "Ghi chú lỗi": item.error_note,
        "Độ tin cậy": item.confidence,
        "Nguồn match ĐT": item.object_match_source,
        "Counterparty hint": item.entities.counterparty_hint,
    }


def _task_records(
    bao_no_items: list[ProcessedTransaction],
    bao_co_items: list[ProcessedTransaction],
    run_id: str | None,
) -> list[dict[str, Any]]:
    if not run_id:
        return []
    rows: list[dict[str, Any]] = []
    for input_sheet, items in (("BAO_NO_INPUT", bao_no_items), ("BAO_CO_INPUT", bao_co_items)):
        for excel_row, item in enumerate(items, start=2):
            rows.append(
                {
                    "run_id": run_id,
                    "task_id": f"{run_id}:{input_sheet}:{excel_row}",
                    "transaction_uid": item.transaction_uid,
                    "flow": item.flow,
                    "input_sheet": input_sheet,
                    "input_excel_row": excel_row,
                    "summary_status": item.rpa_status or STATUS_PENDING,
                    "source_file": item.source_file,
                    "source_sheet": item.source_sheet,
                    "source_row_index": item.original_row_index,
                }
            )
    return rows


def _summary_records(processed: list[ProcessedTransaction]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(group: str, metric: str, value: Any) -> None:
        rows.append({"Nhóm": group, "Chỉ tiêu": metric, "Giá trị": value})

    add("Tổng quan", "Tổng số giao dịch đọc vào", len(processed))
    add("Tổng quan", "Số dòng báo nợ", sum(1 for item in processed if item.flow == "bao_no"))
    add("Tổng quan", "Số dòng báo có", sum(1 for item in processed if item.flow == "bao_co"))
    add("Tổng quan", "Số dòng BAO_NO_INPUT", sum(1 for item in processed if item.flow == "bao_no" and item.status == "OK"))
    add("Tổng quan", "Số dòng BAO_CO_INPUT", sum(1 for item in processed if item.flow == "bao_co" and item.status == "OK"))
    add("Tổng quan", "Số dòng OK", sum(1 for item in processed if item.status == "OK"))
    add("Tổng quan", "Số dòng EXCEPTION", sum(1 for item in processed if item.status != "OK"))

    for bank in sorted({item.bank for item in processed if item.bank}):
        add(
            "Tổng tiền OK theo ngân hàng",
            bank,
            sum(item.amount for item in processed if item.bank == bank and item.status == "OK"),
        )
        add(
            "Tổng tiền EXCEPTION theo ngân hàng",
            bank,
            sum(item.amount for item in processed if item.bank == bank and item.status != "OK"),
        )

    for use_case in sorted({item.use_case for item in processed if item.use_case}):
        add("Số dòng theo use case", use_case, sum(1 for item in processed if item.use_case == use_case))

    for status in sorted({item.status for item in processed if item.status}):
        add("Số dòng theo trạng thái", status, sum(1 for item in processed if item.status == status))

    for flow in sorted({item.flow for item in processed if item.flow}):
        add("Tổng tiền theo luồng", flow, sum(item.amount for item in processed if item.flow == flow))
    return rows


def _tracking_record(item: ProcessedTransaction) -> dict[str, Any]:
    return {
        "transaction_uid": item.transaction_uid,
        "source_file": item.source_file,
        "source_sheet": item.source_sheet,
        "original_row_index": item.original_row_index,
        "rpa_status": item.rpa_status,
        "bank": item.bank,
        "flow": item.flow,
        "transaction_date": _serialize_date(item.transaction_date),
        "doc_no": item.doc_no,
        "original_content": item.original_content,
        "normalized_content": item.normalized_content,
        "counterparty_raw": item.counterparty_raw,
        "normalized_counterparty": item.normalized_counterparty,
        "entities": asdict(item.entities),
        "matched_object_code": item.object_code,
        "matched_object_name": item.object_name,
        "matched_candidates": [asdict(candidate) for candidate in item.matched_candidates],
        "object_match_source": item.object_match_source,
        "reason": item.reason,
        "debit_account": item.debit_account,
        "credit_account": item.credit_account,
        "amount": item.amount,
        "use_case": item.use_case,
        "matched_rule": item.matched_rule,
        "ml_result": asdict(item.ml_result),
        "verification_result": asdict(item.verification_result),
        "status": item.status,
        "error_note": item.error_note,
        "confidence": item.confidence,
        "raw_data": item.raw_data,
    }


def _serialize_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def _format_sheet(ws) -> None:
    for cell in ws[1]:
        cell.font = Font(bold=True)
    header_names = {cell.value: idx for idx, cell in enumerate(ws[1], start=1)}
    for name, idx in header_names.items():
        if name and "Ngày" in str(name):
            for row in range(2, ws.max_row + 1):
                ws.cell(row=row, column=idx).number_format = "DD/MM/YYYY"
        if name in {"Thành tiền", "Giá trị"}:
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
