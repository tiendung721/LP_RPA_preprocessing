from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - runtime fallback before dependencies are installed
    fuzz = None

from .file_utils import get_sheet_names, read_excel_rows
from .normalizer import normalize_text


BANK_COLUMN_REQUIREMENTS: dict[str, list[list[str]]] = {
    "ACB": [
        ["SO TIEN RUT RA"],
        ["SO TIEN GUI VAO"],
        ["NOI DUNG GIAO DICH"],
        ["NGAY HIEU LUC"],
    ],
    "MSB": [
        ["NO DEBIT", "DEBIT"],
        ["CO CREDIT", "CREDIT"],
        ["NGUOI HUONG NGUOI CHUYEN", "PAYEE PAYER"],
        ["DIEN GIAI TRANSACTION DESCRIPTION", "TRANSACTION DESCRIPTION"],
    ],
    "VCB": [
        ["SO TIEN GHI NO DEBIT"],
        ["SO TIEN GHI CO CREDIT"],
        ["NOI DUNG CHI TIET TRANSACTIONS IN DETAIL", "TRANSACTIONS IN DETAIL"],
        ["NGAY HIEU LUC EFFECTIVE DATE", "EFFECTIVE DATE"],
    ],
}


def detect_bank_from_columns(columns: Sequence[object]) -> str | None:
    normalized_columns = [normalize_text(col) for col in columns]
    scores = {
        bank: _count_requirement_matches(normalized_columns, requirements)
        for bank, requirements in BANK_COLUMN_REQUIREMENTS.items()
    }
    best_bank = max(scores, key=scores.get)
    if scores[best_bank] >= len(BANK_COLUMN_REQUIREMENTS[best_bank]):
        return best_bank
    return None


def detect_bank(path: str | Path, logger: logging.Logger | None = None) -> str | None:
    path = Path(path)
    logger = logger or logging.getLogger(__name__)
    try:
        for sheet_name in get_sheet_names(path):
            sample = read_excel_rows(path, sheet_name=sheet_name, nrows=30)
            for _, row in sample.iterrows():
                bank = detect_bank_from_columns(row.tolist())
                if bank:
                    return bank
    except Exception as exc:  # noqa: BLE001 - file-level validation logs and skips
        logger.warning("Cannot inspect workbook for bank detection %s: %s", path, exc)

    filename = normalize_text(path.name)
    if "VIETCOMBANK" in filename or "VCB" in filename:
        return "VCB"
    if "ACB" in filename:
        return "ACB"
    if "MSB" in filename or "REPORTIBS" in filename:
        return "MSB"
    return None


def _count_requirement_matches(columns: list[str], requirements: list[list[str]]) -> int:
    count = 0
    used_indexes: set[int] = set()
    for aliases in requirements:
        best_index = -1
        best_score = 0.0
        for idx, column in enumerate(columns):
            if idx in used_indexes or not column:
                continue
            score = max(_similarity(column, normalize_text(alias)) for alias in aliases)
            if score > best_score:
                best_score = score
                best_index = idx
        if best_score >= 86 and best_index >= 0:
            used_indexes.add(best_index)
            count += 1
    return count


def _similarity(column: str, alias: str) -> float:
    if not column or not alias:
        return 0.0
    if alias == column or alias in column:
        return 100.0
    if fuzz:
        return float(fuzz.token_set_ratio(alias, column))
    left = set(alias.split())
    right = set(column.split())
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right) * 100
