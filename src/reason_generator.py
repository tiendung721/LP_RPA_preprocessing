from __future__ import annotations

import re

from .flows import FLOW_CHI_TIEN_MAT, FLOW_THU_TIEN_MAT
from .normalizer import clean_display_text
from .reason_aliases import ReasonPurpose, match_reason_purpose


OBJECT_CODE_PLACEHOLDER = "{object_code}"

TEMPLATES: dict[tuple[str, str], str] = {
    ("bao_no", "331"): "Thanh toán {object_code}",
    ("bao_no", "141"): "Tạm ứng cá nhân {object_code}",
    ("bao_no", "334"): "Trả lương nhân viên",
    ("bao_no", "3331"): "Nộp thuế GTGT",
    ("bao_no", "3333"): "Nộp thuế XNK",
    ("bao_no", "3335"): "Nộp thuế TNCN",
    ("bao_no", "6421"): "Phí hải quan",
    ("bao_no", "635"): "Chi phí tài chính",
    ("bao_no", "1122"): "Mua ngoại tệ",
    ("bao_no", "341"): "Trả nợ vay ngân hàng",
    ("bao_co", "131"): "Thu tiền {object_code}",
    ("bao_co", "141"): "Nhận tiền tạm ứng {object_code}",
    ("bao_co", "515"): "Lãi tiền gửi ngân hàng",
    ("bao_co", "1122"): "Bán ngoại tệ",
    ("bao_co", "341"): "Nhận tiền vay ngân hàng",
    (FLOW_THU_TIEN_MAT, "1111"): "Rút tiền mặt nhập quỹ",
    (FLOW_CHI_TIEN_MAT, "1111"): "Nộp tiền mặt vào tài khoản",
}


def generate_reason(
    flow: str,
    debit_account: str = "",
    credit_account: str = "",
    object_code: str = "",
    object_name: str = "",
    description: str = "",
    purposes: list[ReasonPurpose] | tuple[ReasonPurpose, ...] | None = None,
) -> str:
    account = _business_account(flow, debit_account, credit_account)
    if (flow, account) == ("bao_no", "331"):
        return _payable_reason(object_code, object_name, description, purposes)
    if (flow, account) == ("bao_co", "131"):
        return _receivable_reason(object_code, object_name, description, purposes)

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
    text = clean_display_text(value)
    return re.sub(r"\s+", " ", text)


def _payable_reason(
    object_code: str,
    object_name: str,
    description: str,
    purposes: list[ReasonPurpose] | tuple[ReasonPurpose, ...] | None,
) -> str:
    party = _reason_party(object_code, object_name)
    if not party:
        return ""
    purpose = match_reason_purpose(description, purposes)
    if not purpose:
        return f"Thanh toán {party}"
    return f"Thanh toán {clean_reason_value(purpose.label)} {party}"


def _receivable_reason(
    object_code: str,
    object_name: str,
    description: str,
    purposes: list[ReasonPurpose] | tuple[ReasonPurpose, ...] | None,
) -> str:
    party = _reason_party(object_code, object_name)
    if not party:
        return ""
    purpose = match_reason_purpose(description, purposes)
    if not purpose:
        return f"Thu tiền {party}"
    label = clean_reason_value(purpose.label)
    prefix = "Thu" if label.lower().startswith("tiền ") else "Thu tiền"
    return f"{prefix} {label} {party}"


def _reason_party(object_code: str, object_name: str) -> str:
    cleaned_object_name = clean_reason_value(object_name)
    if cleaned_object_name:
        return cleaned_object_name
    cleaned_object_code = clean_reason_value(object_code)
    if not cleaned_object_code or cleaned_object_code == "ERROR":
        return ""
    return cleaned_object_code


def _business_account(flow: str, debit_account: str, credit_account: str) -> str:
    if flow == "bao_no":
        return _reason_account_key(debit_account)
    if flow == "bao_co":
        return _reason_account_key(credit_account)
    if flow == FLOW_THU_TIEN_MAT:
        return _reason_account_key(debit_account)
    if flow == FLOW_CHI_TIEN_MAT:
        return _reason_account_key(credit_account)
    return ""


def _reason_account_key(account: str) -> str:
    value = str(account or "").strip().upper()
    if value.startswith("1122"):
        return "1122"
    return value
