from __future__ import annotations

import re
from dataclasses import dataclass

from .normalizer import normalize_text


@dataclass(frozen=True)
class ForeignExchangeInfo:
    currency: str = ""
    foreign_amount: float = 0.0
    exchange_rate: float = 0.0


def extract_foreign_exchange(description: str) -> ForeignExchangeInfo:
    normalized = normalize_text(description)
    if not normalized:
        return ForeignExchangeInfo()

    amount_match = re.search(r"\bSO TIEN\s+([0-9][0-9.,]*)\s+(USD|EUR|JPY|GBP)\b", str(description).upper())
    if not amount_match:
        amount_match = re.search(r"\bSO TIEN\s+([0-9][0-9 ]*)\s+(USD|EUR|JPY|GBP)\b", normalized)

    rate_match = re.search(r"\bTY GIA\s+([0-9][0-9.,]*)", str(description).upper())
    if not rate_match:
        rate_match = re.search(r"\bTY GIA\s+([0-9][0-9 ]*)", normalized)

    return ForeignExchangeInfo(
        currency=(amount_match.group(2).upper() if amount_match else ""),
        foreign_amount=_parse_vietnamese_number(amount_match.group(1)) if amount_match else 0.0,
        exchange_rate=_parse_exchange_rate(rate_match.group(1)) if rate_match else 0.0,
    )


def format_foreign_exchange_reason(base_reason: str, info: ForeignExchangeInfo) -> str:
    reason = base_reason or "Bán ngoại tệ"
    if not info.currency and not info.foreign_amount and not info.exchange_rate:
        return reason
    parts = [reason]
    if info.foreign_amount and info.currency:
        parts.append(f"{_format_number(info.foreign_amount)} {info.currency}")
    elif info.currency:
        parts.append(info.currency)
    if info.exchange_rate:
        parts.append(f"tỷ giá {_format_number(info.exchange_rate)}")
    return " ".join(parts)


def _parse_vietnamese_number(value: str) -> float:
    text = str(value or "").strip().replace(" ", "")
    if not text:
        return 0.0
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "." in text:
        parts = text.split(".")
        if len(parts[-1]) == 3:
            text = "".join(parts)
    elif "," in text:
        parts = text.split(",")
        if len(parts[-1]) == 3:
            text = "".join(parts)
        else:
            text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_exchange_rate(value: str) -> float:
    rate = _parse_vietnamese_number(value)
    if 20 <= rate < 100:
        return rate * 1000
    return rate


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
