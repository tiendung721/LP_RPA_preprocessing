from __future__ import annotations

from .base_parser import BaseBankParser


class MSBParser(BaseBankParser):
    bank = "MSB"
    preferred_sheets = ("Sheet1",)
    field_aliases = {
        "transaction_date": ["NGAY GIAO DICH TRANSACTION DATE", "TRANSACTION DATE"],
        "doc_no": ["SO BUT TOAN REFERENCE NO", "REFERENCE NO"],
        "counterparty_raw": [
            "NGUOI HUONG NGUOI CHUYEN PAYEE PAYER",
            "NGUOI HUONG NGUOI CHUYEN",
            "PAYEE PAYER",
        ],
        "description": ["DIEN GIAI TRANSACTION DESCRIPTION", "TRANSACTION DESCRIPTION"],
        "debit_amount": ["NO DEBIT"],
        "credit_amount": ["CO CREDIT"],
    }
