from __future__ import annotations

from .typing_compat import EntityLike


def build_transaction_text(flow: str, bank: str, normalized_content: str, entities: EntityLike | None = None) -> str:
    parts = [flow, bank, normalized_content]
    if entities:
        parts.extend([
            getattr(entities, "counterparty_hint", ""),
            getattr(entities, "intent", ""),
            getattr(entities, "service_hint", ""),
        ])
    return " ".join(part for part in parts if part)
