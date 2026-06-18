from src.ml.object_ranker import ObjectRanker
from src.models import ObjectCandidate


class FakeObjectModel:
    classes_ = [0, 1]

    def predict_proba(self, texts):
        rows = []
        for text in texts:
            if "RIGHT" in text:
                rows.append([0.05, 0.95])
            elif "CLOSE" in text:
                rows.append([0.18, 0.82])
            else:
                rows.append([0.9, 0.1])
        return rows


class BrokenObjectModel:
    classes_ = [0, 1]

    def predict_proba(self, texts):
        raise RuntimeError("broken model")


def _ranker(min_confidence=0.85, min_gap=0.15):
    ranker = ObjectRanker(enabled=False, min_confidence=min_confidence, min_gap=min_gap)
    ranker.model = FakeObjectModel()
    return ranker


def test_object_ranker_no_candidates():
    result = _ranker().rank({}, [])
    assert result.status == "NO_CANDIDATES"
    assert result.decision == "FALLBACK"


def test_object_ranker_no_model_falls_back():
    result = ObjectRanker(enabled=False).rank({}, [ObjectCandidate(code="A", name="A", score=90)])
    assert result.status == "NO_MODEL"
    assert result.ranked_candidates[0].code == "A"


def test_object_ranker_prediction_error_falls_back():
    ranker = ObjectRanker(enabled=False)
    ranker.model = BrokenObjectModel()

    result = ranker.rank({}, [ObjectCandidate(code="A", name="A", score=90)])

    assert result.status == "MODEL_ERROR"
    assert result.decision == "FALLBACK"
    assert result.ranked_candidates[0].code == "A"


def test_object_ranker_selects_high_confidence_candidate():
    result = _ranker().rank(
        {"description": "TT CHO TARGET", "flow": "bao_no", "catalog": "payable"},
        [
            ObjectCandidate(code="WRONG", name="WRONG TARGET", score=100),
            ObjectCandidate(code="RIGHT", name="RIGHT TARGET", score=100),
        ],
    )
    assert result.status == "OK"
    assert result.decision == "AUTO_SELECT"
    assert result.best_code == "RIGHT"
    assert result.confidence >= 0.85
    assert result.gap >= 0.15


def test_object_ranker_low_gap_stays_review():
    result = _ranker(min_gap=0.2).rank(
        {"description": "TT CHO TARGET", "flow": "bao_no", "catalog": "payable"},
        [
            ObjectCandidate(code="RIGHT", name="RIGHT TARGET", score=100),
            ObjectCandidate(code="CLOSE", name="CLOSE TARGET", score=100),
        ],
    )
    assert result.status == "LOW_CONFIDENCE"
    assert result.decision == "REVIEW"
