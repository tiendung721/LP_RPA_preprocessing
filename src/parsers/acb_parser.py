from __future__ import annotations

from .base_parser import BaseBankParser


class ACBParser(BaseBankParser):
    bank = "ACB"
    preferred_sheets = ("Statement",)
    field_aliases = {
        "transaction_date": ["NGAY HIEU LUC"],
        "doc_no": ["SO GD", "SO GIAO DICH"],
        "description": ["NOI DUNG GIAO DICH"],
        "debit_amount": ["SO TIEN RUT RA"],
        "credit_amount": ["SO TIEN GUI VAO"],
    }
