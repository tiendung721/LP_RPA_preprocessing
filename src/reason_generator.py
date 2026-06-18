from __future__ import annotations

import re

from .flows import FLOW_CHI_TIEN_MAT, FLOW_THU_TIEN_MAT


OBJECT_CODE_PLACEHOLDER = "{object_code}"

TEMPLATES: dict[tuple[str, str], str] = {
    ("bao_no", "331"): "Thanh toán công nợ {object_code}",
    ("bao_no", "141"): "Tạm ứng cá nhân {object_code}",
    ("bao_no", "334"): "Trả lương nhân viên",
    ("bao_no", "3331"): "Nộp thuế GTGT",
    ("bao_no", "3333"): "Nộp thuế XNK",
    ("bao_no", "3335"): "Nộp thuế TNCN",
    ("bao_no", "6421"): "Phí hải quan",
    ("bao_no", "635"): "Chi phí tài chính",
    ("bao_no", "1122"): "Mua ngoại tệ",
    ("bao_no", "341"): "Trả nợ vay ngân hàng",
    ("bao_co", "131"): "Thu tiền công nợ {object_code}",
    ("bao_co", "141"): "Nhận tiền tạm ứng {object_code}",
    ("bao_co", "515"): "Lãi tiền gửi ngân hàng",
    ("bao_co", "1122"): "Bán ngoại tệ",
    ("bao_co", "341"): "Nhận tiền vay ngân hàng",
    (FLOW_THU_TIEN_MAT, "1111"): "Rút tiền mặt nhập quỹ",
    (FLOW_CHI_TIEN_MAT, "1111"): "Nộp tiền mặt vào tài khoản",
}


def generate_reason(flow: str, debit_account: str = "", credit_account: str = "", object_code: str = "") -> str:
    account = _business_account(flow, debit_account, credit_account)
    template = TEMPLATES.get((flow, account), "")
    if not template:
        return ""
    if OBJECT_CODE_PLACEHOLDER not in template:
        return template

    cleaned_object_code = clean_reason_value(object_code)
    if not cleaned_object_code or cleaned_object_code == "ERROR":
        return ""
    return template.format(object_code=cleaned_object_code)


def reason_requires_object_code(flow: str, debit_account: str = "", credit_account: str = "") -> bool:
    account = _business_account(flow, debit_account, credit_account)
    template = TEMPLATES.get((flow, account), "")
    return OBJECT_CODE_PLACEHOLDER in template


def has_usable_object_code(object_code: str) -> bool:
    cleaned_object_code = clean_reason_value(object_code)
    return bool(cleaned_object_code and cleaned_object_code != "ERROR")


def clean_reason_value(value: str) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def _business_account(flow: str, debit_account: str, credit_account: str) -> str:
    if flow == "bao_no":
        return str(debit_account or "").strip()
    if flow == "bao_co":
        return str(credit_account or "").strip()
    if flow == FLOW_THU_TIEN_MAT:
        return str(debit_account or "").strip()
    if flow == FLOW_CHI_TIEN_MAT:
        return str(credit_account or "").strip()
    return ""
