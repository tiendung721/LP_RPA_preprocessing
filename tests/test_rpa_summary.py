from __future__ import annotations

from datetime import date

import pandas as pd
from openpyxl import load_workbook

from src.models import ProcessedTransaction
from src.output_writer import write_outputs
from src.rpa_summary import (
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    SUMMARY_COLUMNS,
    SUMMARY_SHEET_NAME,
    mark_rpa_done,
    mark_rpa_started,
    write_summary,
)


def _processed(uid: str, row_index: int, amount: int = 1000) -> ProcessedTransaction:
    return ProcessedTransaction(
        source_file="sample.xlsx",
        original_row_index=row_index,
        bank="ACB",
        flow="bao_no",
        transaction_date=date(2026, 4, 1),
        object_code="ABC",
        object_name="ABC",
        reason="Thanh toán ABC",
        debit_account="331",
        credit_account="1121CT",
        amount=amount,
        use_case="Chi phí thanh toán",
        original_content=f"TT CHO ABC {row_index}",
        counterparty_raw="ABC",
        doc_no=str(row_index),
        status="OK",
        error_note="",
        confidence=0.95,
        transaction_uid=uid,
        source_sheet="Statement",
    )


def test_write_outputs_filters_completed_summary_rows(tmp_path):
    summary_path = tmp_path / "rpa_summary.xlsx"
    existing_summary = pd.DataFrame(
        [
            {
                "transaction_uid": "uid_done",
                "source_file": "sample.xlsx",
                "source_sheet": "Statement",
                "source_row_index": 2,
                "bank": "ACB",
                "flow": "bao_no",
                "transaction_date": date(2026, 4, 1),
                "doc_no": "2",
                "original_content": "TT CHO ABC 2",
                "counterparty_raw": "ABC",
                "amount": 1000,
                "object_code": "ABC",
                "object_name": "ABC",
                "debit_account": "331",
                "credit_account": "1121CT",
                "reason": "Thanh toán ABC",
                "status": STATUS_DONE,
                "last_run_id": "old_run",
                "rpa_started_at": "2026-04-01T08:00:00",
                "rpa_finished_at": "2026-04-01T08:01:00",
                "rpa_message": "",
                "voucher_no": "BN001",
                "created_at": "2026-04-01T08:00:00",
                "updated_at": "2026-04-01T08:01:00",
            }
        ],
        columns=SUMMARY_COLUMNS,
    )
    write_summary(existing_summary, summary_path)

    config = {
        "output": {
            "excel_file": "rpa_input.xlsx",
            "tracking_file": "rpa_tracking.json",
            "summary_file": "rpa_summary.xlsx",
        }
    }
    write_outputs([_processed("uid_done", 2), _processed("uid_new", 3)], tmp_path, config)

    wb = load_workbook(tmp_path / "rpa_input.xlsx", data_only=True)
    assert wb["BAO_NO_INPUT"].max_row == 2
    assert wb["BAO_NO_INPUT"]["F2"].value == 1000
    assert wb["RPA_TASKS"].max_row == 2
    task_headers = [cell.value for cell in wb["RPA_TASKS"][1]]
    task_values = dict(zip(task_headers, [cell.value for cell in wb["RPA_TASKS"][2]]))
    assert task_values["transaction_uid"] == "uid_new"
    assert task_values["source_row_index"] == 3

    summary_df = pd.read_excel(summary_path, sheet_name=SUMMARY_SHEET_NAME, dtype=object)
    statuses = dict(zip(summary_df["transaction_uid"], summary_df["status"]))
    assert statuses["uid_done"] == STATUS_DONE
    assert statuses["uid_new"] == STATUS_PENDING


def test_rpa_status_helpers_update_summary_after_each_row(tmp_path):
    summary_path = tmp_path / "rpa_summary.xlsx"
    row = {
        column: ""
        for column in SUMMARY_COLUMNS
    }
    row.update(
        {
            "transaction_uid": "uid_pending",
            "source_file": "sample.xlsx",
            "source_sheet": "Statement",
            "source_row_index": 5,
            "status": STATUS_PENDING,
        }
    )
    write_summary(pd.DataFrame([row], columns=SUMMARY_COLUMNS), summary_path)

    mark_rpa_started(summary_path, "uid_pending", "run_1")
    df = pd.read_excel(summary_path, sheet_name=SUMMARY_SHEET_NAME, dtype=object)
    df = df.where(pd.notna(df), "")
    started_row = df[df["transaction_uid"] == "uid_pending"].iloc[0]
    assert started_row["status"] == STATUS_IN_PROGRESS
    assert started_row["rpa_started_at"]

    mark_rpa_done(summary_path, "uid_pending", "run_1", voucher_no="BN001")
    df = pd.read_excel(summary_path, sheet_name=SUMMARY_SHEET_NAME, dtype=object)
    df = df.where(pd.notna(df), "")
    done_row = df[df["transaction_uid"] == "uid_pending"].iloc[0]
    assert done_row["status"] == STATUS_DONE
    assert done_row["voucher_no"] == "BN001"
    assert done_row["rpa_finished_at"]
