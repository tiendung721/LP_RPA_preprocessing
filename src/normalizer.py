from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
from dateutil import parser as date_parser
from unidecode import unidecode


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and not value.strip():
        return True
    return False


def normalize_text(text: Any) -> str:
    if is_empty(text):
        return ""
    value = unicodedata.normalize("NFKC", str(text)).strip()
    value = unidecode(value)
    value = value.upper()
    value = re.sub(r"[^A-Z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_amount(value: Any) -> float:
    if is_empty(value):
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return 0.0
        return float(value)

    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return 0.0
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[^\d,.\-]", "", text)
    if text in {"", "-", ".", ",", "-.", "-,"}:
        return 0.0

    negative = text.startswith("-")
    text = text.lstrip("-")

    if "," in text and "." in text:
        if text.rfind(".") > text.rfind(","):
            text = text.replace(",", "")
        else:
            text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        parts = text.split(",")
        if len(parts) > 2 or len(parts[-1]) == 3:
            text = "".join(parts)
        else:
            text = text.replace(",", ".")
    elif "." in text:
        parts = text.split(".")
        if len(parts) > 2 or len(parts[-1]) == 3:
            text = "".join(parts)

    try:
        amount = float(text)
    except ValueError:
        return 0.0
    return -amount if negative else amount


def parse_date(value: Any) -> date | None:
    if is_empty(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(float(value)):
            return None
        if 20000 <= float(value) <= 80000:
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()

    text = str(value).strip()
    if not text:
        return None

    match = re.search(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text)
    if match:
        text = match.group(1)

    try:
        return date_parser.parse(text, dayfirst=True, fuzzy=True).date()
    except (ValueError, OverflowError, TypeError):
        return None


def clean_string(value: Any) -> str:
    if is_empty(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return re.sub(r"\s+", " ", text)
