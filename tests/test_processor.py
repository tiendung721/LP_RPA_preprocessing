from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from src.config_loader import load_config, load_rules
from src.models import ProcessedTransaction, Transaction
from src.object_matcher import ObjectMatcher
from src.output_writer import RPA_COLUMNS, write_excel
from src.processor import process_transaction
from src.rule_engine import RuleEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _config():
    return load_config(PROJECT_ROOT / "config/config.yaml")


def _engine():
    rules, _ = load_rules(None, PROJECT_ROOT / "config/default_rules.yaml")
    return RuleEngine(rules)


def test_both_debit_credit_goes_exception():
    txn = Transaction(
        source_file="sample.xlsx",
        bank="ACB",
        transaction_date=date(2026, 4, 1),
        doc_no="1",
        description="THANH TOAN ABC",
        counterparty_raw="",
        debit_amount=100,
        credit_amount=100,
        original_row_index=2,
    )
    result = process_transaction(txn, _config(), _engine(), ObjectMatcher([]), ObjectMatcher([]))
    assert result.status == "ERROR"
    assert "Dòng có cả ghi nợ và ghi có" in result.error_note


def test_output_has_separate_flow_sheets_and_excludes_error(tmp_path):
    bao_no = ProcessedTransaction(
        source_file="sample.xlsx",
        original_row_index=2,
        bank="ACB",
        flow="bao_no",
        transaction_date=date(2026, 4, 1),
        object_code="ABC",
        object_name="ABC",
        reason="Thanh toán ABC",
        debit_account="331",
        credit_account="1121CT",
        amount=1000,
        use_case="Chi phí thanh toán",
        original_content="TT CHO ABC",
        counterparty_raw="",
        doc_no="1",
        status="OK",
        error_note="",
        confidence=0.95,
    )
    bao_co = ProcessedTransaction(
        source_file="sample.xlsx",
        original_row_index=3,
        bank="VCB",
        flow="bao_co",
        transaction_date=date(2026, 4, 1),
        object_code="",
        object_name="",
        reason="Lãi tiền gửi",
        debit_account="1121VCB",
        credit_account="515",
        amount=1000,
        use_case="Doanh thu tài chính",
        original_content="LAI NHAP VON",
        counterparty_raw="",
        doc_no="2",
        status="OK",
        error_note="",
        confidence=0.95,
    )
    err = ProcessedTransaction(
        source_file="sample.xlsx",
        original_row_index=4,
        bank="VCB",
        flow="bao_no",
        transaction_date=date(2026, 4, 2),
        object_code="ERROR",
        object_name="",
        reason="",
        debit_account="",
        credit_account="1121VCB",
        amount=2000,
        use_case="",
        original_content="BHXH",
        counterparty_raw="",
        doc_no="3",
        status="ERROR",
        error_note="Luồng bảo hiểm không xử lý tự động",
        confidence=0.99,
    )
    output_file = tmp_path / "rpa_input.xlsx"
    write_excel([bao_no, bao_co, err], output_file)
    wb = load_workbook(output_file)
    assert "BAO_NO_INPUT" in wb.sheetnames
    assert "BAO_CO_INPUT" in wb.sheetnames
    assert "RPA_INPUT" not in wb.sheetnames
    assert [cell.value for cell in wb["BAO_NO_INPUT"][1]] == RPA_COLUMNS
    assert [cell.value for cell in wb["BAO_CO_INPUT"][1]] == RPA_COLUMNS
    assert wb["BAO_NO_INPUT"].max_row == 2
    assert wb["BAO_CO_INPUT"].max_row == 2
