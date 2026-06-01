from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None

from ..models import ClassificationResult, ExtractedEntities
from ..normalizer import normalize_text
from .features import build_transaction_text


class TransactionClassifier:
    def __init__(self, model_path: str | Path | None = None, enabled: bool = True):
        self.model_path = Path(model_path) if model_path else None
        self.enabled = enabled
        self.model: Any | None = None
        self.load_error = ""
        if self.enabled and self.model_path and self.model_path.exists() and joblib:
            try:
                self.model = joblib.load(self.model_path)
            except Exception as exc:  # noqa: BLE001 - fall back to rules if model cannot load
                self.load_error = str(exc)

    @property
    def available(self) -> bool:
        return self.model is not None

    def predict(self, flow: str, bank: str, description: str, entities: ExtractedEntities) -> ClassificationResult:
        if not self.available:
            note = self.load_error or "ML classifier model not found"
            return ClassificationResult(source="ml", status="NO_MODEL", note=note)
        text = build_transaction_text(flow, bank, normalize_text(description), entities)
        try:
            label = self.model.predict([text])[0]
        except Exception as exc:  # noqa: BLE001 - keep deterministic rule fallback alive
            return ClassificationResult(source="ml", status="ERROR", note=f"ML classifier predict failed: {exc}")
        confidence = 0.0
        if hasattr(self.model, "predict_proba"):
            try:
                confidence = float(max(self.model.predict_proba([text])[0]))
            except Exception:  # noqa: BLE001 - prediction label is still usable without probability
                confidence = 0.0
        use_case, account = _split_label(str(label))
        return ClassificationResult(use_case=use_case, account=account, confidence=confidence, source="ml", status="OK")


def _split_label(label: str) -> tuple[str, str]:
    if "|" not in label:
        return label, ""
    use_case, account = label.split("|", 1)
    return use_case, account
