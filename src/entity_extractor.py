from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import ExtractedEntities
from .normalizer import normalize_text


class OwnCompanyConfig:
    def __init__(self, aliases: list[str], tax_codes: list[str], object_codes: list[str]):
        self.aliases = list(dict.fromkeys(normalize_text(alias) for alias in aliases if normalize_text(alias)))
        self.tax_codes = list(dict.fromkeys(normalize_text(code) for code in tax_codes if normalize_text(code)))
        self.object_codes = list(dict.fromkeys(normalize_text(code) for code in object_codes if normalize_text(code)))

    @classmethod
    def from_yaml(cls, path: str | Path | None) -> "OwnCompanyConfig":
        if not path or not Path(path).exists():
            return cls([], [], [])
        with Path(path).open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        data = data.get("own_company", data)
        return cls(
            aliases=list(data.get("aliases", [])),
            tax_codes=list(data.get("tax_codes", [])),
            object_codes=list(data.get("object_codes", [])),
        )

    def is_own_code(self, code: str) -> bool:
        return normalize_text(code) in self.object_codes

    def is_own_tax_code(self, value: str) -> bool:
        return normalize_text(value) in self.tax_codes

    def is_own_name(self, value: str) -> bool:
        normalized = normalize_text(value)
        if not normalized:
            return False
        return any(_contains_phrase(normalized, alias) or alias in normalized for alias in self.aliases)

    def find_hits(self, value: str) -> list[str]:
        normalized = normalize_text(value)
        hits = [alias for alias in self.aliases if alias and (alias in normalized or _contains_phrase(normalized, alias))]
        hits.extend(code for code in self.tax_codes if code and code in normalized)
        return list(dict.fromkeys(hits))

    def strip_from_text(self, value: str) -> str:
        text = normalize_text(value)
        for alias in sorted(self.aliases, key=len, reverse=True):
            text = _remove_phrase(text, alias)
        for code in self.tax_codes:
            text = _remove_phrase(text, code)
        return re.sub(r"\s+", " ", text).strip()


class EntityExtractor:
    def __init__(self, own_company: OwnCompanyConfig):
        self.own_company = own_company

    def extract(self, bank: str, description: str, counterparty_raw: str = "") -> ExtractedEntities:
        normalized_description = normalize_text(description)
        normalized_counterparty = normalize_text(counterparty_raw)
        cleaned_description = self.own_company.strip_from_text(normalized_description)
        own_hits = self.own_company.find_hits(f"{description} {counterparty_raw}")

        intent = _detect_intent(cleaned_description)
        invoice_no = _extract_first(r"(?:HD|HOA DON|SO HD)\s*(?:SO)?\s*([A-Z0-9,\- ]{1,40})", cleaned_description)
        bill_no = _extract_first(r"(?:BILL|BL)\s*([A-Z0-9,\- ]{1,40})", cleaned_description)
        tax_code = _extract_first(r"(?:MST|MA SO THUE)\s*(\d{8,14})", normalized_description)
        bank_account_hint = _extract_first(r"(?:CK 24 7 CHO|CHO)\s*(\d{6,20})", cleaned_description)
        service_hint = _extract_service(cleaned_description)

        counterparty_hint = ""
        counterparty_source = ""
        if bank == "MSB" and normalized_counterparty and not self.own_company.is_own_name(normalized_counterparty):
            counterparty_hint = normalized_counterparty
            counterparty_source = "counterparty_raw"
        if not counterparty_hint:
            counterparty_hint, counterparty_source = _extract_counterparty_hint(cleaned_description)

        return ExtractedEntities(
            counterparty_hint=counterparty_hint,
            counterparty_source=counterparty_source,
            cleaned_description=cleaned_description,
            intent=intent,
            invoice_no=invoice_no,
            bill_no=bill_no,
            tax_code=tax_code,
            bank_account_hint=bank_account_hint,
            service_hint=service_hint,
            own_company_hits=own_hits,
        )


def _extract_counterparty_hint(text: str) -> tuple[str, str]:
    patterns = [
        ("ck_247_cho", r"CK 24 7 CHO\s+(?:\d{6,20}\s+)?(.+)"),
        ("tt_cho", r"TT\s+CHO\s+(.+)"),
        ("ct_cho", r"CT\s+CHO\s+(.+)"),
        ("thanh_toan_cho", r"THANH TOAN(?:\s+[A-Z0-9]+){0,8}\s+CHO\s+(.+)"),
        ("chuyen_tien_cho", r"CHUYEN TIEN(?:\s+[A-Z0-9]+){0,6}\s+CHO\s+(.+)"),
        ("thu_tien_tu", r"THU TIEN TU\s+(.+)"),
        ("cho", r"\bCHO\s+(.+)"),
    ]
    for source, pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        hint = _clean_counterparty_segment(match.group(1))
        if hint:
            return hint, source
    return "", ""


def _clean_counterparty_segment(segment: str) -> str:
    segment = re.sub(r"^\d{6,20}\s+", "", segment).strip()
    if " CHO " in segment:
        segment = segment.rsplit(" CHO ", 1)[-1].strip()
    stop_pattern = r"\b(THEO|HD|HOA DON|SO HD|BANG KE|BILL|BL|THANG|KY HOA DON|TAU|LAN|MST|MA SO THUE)\b"
    segment = re.split(stop_pattern, segment, maxsplit=1)[0]
    segment = re.sub(r"\b(CTY|CT|CONG TY|TNHH|CO PHAN|CP)\b", " ", segment)
    segment = re.sub(r"[^A-Z0-9]+", " ", segment)
    tokens = [token for token in segment.split() if token not in {"TIEN", "CUOC", "PHI", "DICH", "VU"}]
    return " ".join(tokens[:6]).strip()


def _detect_intent(text: str) -> str:
    for intent in ["NOP THUE", "THANH TOAN", "TT CHO", "CHUYEN TIEN", "TAM UNG", "TRA LUONG", "LAI NHAP VON"]:
        if intent in text:
            return intent
    return ""


def _extract_service(text: str) -> str:
    for pattern in [
        r"THANH TOAN\s+(.+?)\s+CHO\s+",
        r"TT\s+(.+?)\s+CHO\s+",
    ]:
        match = re.search(pattern, text)
        if match:
            return _clean_counterparty_segment(match.group(1))
    return ""


def _extract_first(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    pattern = r"(?<![A-Z0-9])" + r"\s+".join(re.escape(token) for token in phrase.split()) + r"(?![A-Z0-9])"
    return re.search(pattern, text) is not None


def _remove_phrase(text: str, phrase: str) -> str:
    if not phrase:
        return text
    pattern = r"(?<![A-Z0-9])" + r"\s+".join(re.escape(token) for token in phrase.split()) + r"(?![A-Z0-9])"
    text = re.sub(pattern, " ", text)
    text = text.replace(phrase, " ")
    return re.sub(r"\s+", " ", text).strip()

