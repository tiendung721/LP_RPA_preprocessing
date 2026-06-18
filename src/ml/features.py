from __future__ import annotations

from typing import Any

from ..normalizer import normalize_text
from .typing_compat import EntityLike


def build_transaction_text(flow: str, bank: str, normalized_content: str, entities: EntityLike | None = None) -> str:
    parts = [flow, bank, normalized_content]
    if entities:
        parts.extend(
            [
                getattr(entities, "counterparty_hint", ""),
                getattr(entities, "intent", ""),
                getattr(entities, "service_hint", ""),
            ]
        )
    return " ".join(part for part in parts if part)


def build_object_candidate_text(context: Any, candidate: Any) -> str:
    parts = [
        _get(context, "bank"),
        _get(context, "flow"),
        _get(context, "catalog"),
        _get(context, "use_case"),
        _get(context, "account"),
        normalize_text(_get(context, "description") or _get(context, "normalized_content")),
        normalize_text(_get(context, "counterparty_raw")),
        normalize_text(_get(context, "counterparty_hint")),
        normalize_text(_get(context, "service_hint")),
        normalize_text(_get(context, "tax_code")),
        normalize_text(_get(candidate, "code")),
        normalize_text(_get(candidate, "name")),
        normalize_text(_get(candidate, "tax_code")),
        normalize_text(_get(candidate, "group_name")),
        normalize_text(_get(candidate, "group_code")),
        normalize_text(_get(candidate, "source")),
        normalize_text(_get(candidate, "matched_on")),
        str(_get(candidate, "score") or ""),
    ]
    return " ".join(part for part in parts if part)


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key, "")
    return getattr(value, key, "")
