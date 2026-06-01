from __future__ import annotations

from src.ml.transaction_classifier import TransactionClassifier
from src.models import ExtractedEntities


class _BrokenModel:
    def predict(self, values):
        raise RuntimeError("not fitted")


def test_classifier_predict_error_falls_back_without_crashing():
    classifier = TransactionClassifier(enabled=False)
    classifier.model = _BrokenModel()

    result = classifier.predict("bao_no", "ACB", "Thanh toán ABC", ExtractedEntities())

    assert result.status == "ERROR"
    assert "ML classifier predict failed" in result.note
