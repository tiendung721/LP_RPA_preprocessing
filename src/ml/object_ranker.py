from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None


class ObjectRanker:
    def __init__(self, model_path: str | Path | None = None, enabled: bool = True):
        self.model_path = Path(model_path) if model_path else None
        self.enabled = enabled
        self.model: Any | None = None
        if self.enabled and self.model_path and self.model_path.exists() and joblib:
            self.model = joblib.load(self.model_path)

    @property
    def available(self) -> bool:
        return self.model is not None

    def rank(self, candidates: list[Any]) -> list[Any]:
        # Deterministic fallback: ObjectMatcher already ranks candidates by score/source.
        return candidates
