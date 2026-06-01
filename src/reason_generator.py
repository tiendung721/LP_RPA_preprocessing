from __future__ import annotations

from .normalizer import normalize_text


TEMPLATES: dict[str, str] = {
    "Chi phí thanh toán": "Thanh toán {object}",
    "Tạm ứng tiền hàng": "Tạm ứng tiền hàng",
    "Trả lương nhân viên": "Trả lương nhân viên",
    "Trả thuế GTGT": "Nộp thuế GTGT",
    "Trả thuế TNDN": "Nộp thuế TNDN",
    "Trả thuế TNCN": "Nộp thuế TNCN",
    "Trả thuế XNK": "Nộp thuế XNK",
    "Trả phí hải quan": "Trả phí hải quan",
    "Chi phí tài chính": "Chi phí tài chính",
    "Công nợ của khách": "Thu công nợ {object}",
    "Doanh thu tài chính": "Lãi tiền gửi",
    "Nhận tiền tạm ứng": "Nhận tiền tạm ứng",
}


def generate_reason(use_case: str, object_name: str = "") -> str:
    template = TEMPLATES.get(use_case, use_case or "")
    if "{object}" not in template:
        return template
    short_name = shorten_object_name(object_name)
    if not short_name:
        return template.replace(" {object}", "").replace("{object}", "").strip()
    return template.format(object=short_name)


def shorten_object_name(object_name: str) -> str:
    text = normalize_text(object_name)
    if not text:
        return ""
    phrase_stops = [
        "CONG TY CO PHAN",
        "CONG TY TNHH",
        "CONG TY",
        "C NG TY",
        "CTY",
        "TNHH",
        "CO PHAN",
        "CHI NHANH",
        "VIET NAM",
        "VIETNAM",
    ]
    for phrase in phrase_stops:
        text = " ".join(text.replace(phrase, " ").split())
    word_stops = {
        "CP",
        "MTV",
        "TRACH",
        "NHIEM",
        "HUU",
        "HAN",
        "VAN",
        "TAI",
        "BIEN",
        "THUONG",
        "MAI",
        "DICH",
        "VU",
        "XUAT",
        "NHAP",
        "KHAU",
    }
    tokens = [token for token in text.split() if token not in word_stops]
    if not tokens:
        return ""
    if len(tokens) > 4:
        tokens = tokens[-3:]
    return " ".join(token.capitalize() for token in tokens)
