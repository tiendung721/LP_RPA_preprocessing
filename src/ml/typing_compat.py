from __future__ import annotations

from typing import Protocol


class EntityLike(Protocol):
    counterparty_hint: str
    intent: str
    service_hint: str
