from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .models import ProcessedTransaction
from .normalizer import normalize_text


def assign_transaction_uids(items: list[ProcessedTransaction]) -> None:
    fingerprints = [transaction_fingerprint(item) for item in items]
    counts = Counter(fingerprints)
    seen: dict[str, int] = defaultdict(int)

    for item, fingerprint in zip(items, fingerprints):
        suffix = ""
        if counts[fingerprint] > 1:
            seen[fingerprint] += 1
            suffix = _source_suffix(item, seen[fingerprint])
        item.transaction_uid = _digest(f"{fingerprint}|{suffix}" if suffix else fingerprint)


def build_transaction_uid(item: Any) -> str:
    return _digest(transaction_fingerprint(item))


def transaction_fingerprint(item: Any) -> str:
    flow = _flow_key(item)
    amount = _amount_key(item, flow)
    content = getattr(item, "normalized_content", "") or normalize_text(
        getattr(item, "original_content", "") or getattr(item, "description", "")
    )
    counterparty = getattr(item, "normalized_counterparty", "") or normalize_text(getattr(item, "counterparty_raw", ""))
    parts = [
        normalize_text(getattr(item, "bank", "")),
        _date_key(getattr(item, "transaction_date", None)),
        normalize_text(getattr(item, "doc_no", "")),
        flow,
        amount,
        content,
        counterparty,
    ]
    return "|".join(parts)


def _flow_key(item: Any) -> str:
    flow = getattr(item, "flow", "")
    if flow:
        return normalize_text(flow)
    debit_amount = float(getattr(item, "debit_amount", 0) or 0)
    credit_amount = float(getattr(item, "credit_amount", 0) or 0)
    if debit_amount > 0 and credit_amount <= 0:
        return "bao_no"
    if credit_amount > 0 and debit_amount <= 0:
        return "bao_co"
    return "unknown"


def _amount_key(item: Any, flow: str) -> str:
    amount = getattr(item, "amount", None)
    if amount is None:
        debit_amount = float(getattr(item, "debit_amount", 0) or 0)
        credit_amount = float(getattr(item, "credit_amount", 0) or 0)
        amount = debit_amount if flow == "bao_no" else credit_amount if flow == "bao_co" else max(debit_amount, credit_amount)
    try:
        value = Decimal(str(amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal("0.00")
    return format(value, "f")


def _date_key(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "").strip()


def _source_suffix(item: ProcessedTransaction, ordinal: int) -> str:
    parts = [
        normalize_text(item.source_file),
        normalize_text(item.source_sheet),
        str(item.original_row_index),
        str(ordinal),
    ]
    return "|".join(parts)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
