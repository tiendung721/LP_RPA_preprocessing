from __future__ import annotations

from .base_parser import BaseBankParser


class VCBParser(BaseBankParser):
    bank = "VCB"
    preferred_sheets = ("Vietcombank_Account_Statement",)
    field_aliases = {
        "transaction_date": ["NGAY HIEU LUC EFFECTIVE DATE", "EFFECTIVE DATE"],
        "doc_no": ["NGAY TNX DATE SO CT DOC NO", "SO CT DOC NO", "DOC NO"],
        "description": ["NOI DUNG CHI TIET TRANSACTIONS IN DETAIL", "TRANSACTIONS IN DETAIL"],
        "debit_amount": ["SO TIEN GHI NO DEBIT"],
        "credit_amount": ["SO TIEN GHI CO CREDIT"],
    }
