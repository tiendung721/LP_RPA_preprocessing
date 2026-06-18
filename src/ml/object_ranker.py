from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import ObjectCandidate, ObjectRankResult
from .features import build_object_candidate_text

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None


class ObjectRanker:
    def __init__(
        self,
        model_path: str | Path | None = None,
        enabled: bool = True,
        min_confidence: float = 0.85,
        min_gap: float = 0.15,
    ):
        self.model_path = Path(model_path) if model_path else None
        self.enabled = enabled
        self.min_confidence = float(min_confidence)
        self.min_gap = float(min_gap)
        self.model: Any | None = None
        self.load_error = ""
        self._load_attempted = False

    @property
    def available(self) -> bool:
        return self.model is not None

    def rank(self, context: dict[str, Any], candidates: list[ObjectCandidate]) -> ObjectRankResult:
        if not candidates:
            return ObjectRankResult(status="NO_CANDIDATES", decision="FALLBACK", note="No candidates to rank")
        self._ensure_loaded()
        if not self.available:
            note = self.load_error or "Object ranker model not found"
            return ObjectRankResult(
                status="NO_MODEL",
                decision="FALLBACK",
                note=note,
                ranked_candidates=[_copy_candidate(candidate, 0.0) for candidate in candidates],
            )

        texts = [build_object_candidate_text(context, candidate) for candidate in candidates]
        try:
            scores = self._predict_scores(texts)
        except Exception as exc:  # noqa: BLE001 - model files can be stale/incompatible
            return ObjectRankResult(
                status="MODEL_ERROR",
                decision="FALLBACK",
                note=f"Object ranker prediction failed: {exc}",
                ranked_candidates=[_copy_candidate(candidate, 0.0) for candidate in candidates],
            )
        ranked = [
            _copy_candidate(candidate, score)
            for candidate, score in sorted(zip(candidates, scores, strict=False), key=lambda item: item[1], reverse=True)
        ]
        best = ranked[0]
        second_score = ranked[1].ml_score if len(ranked) > 1 else 0.0
        confidence = float(best.ml_score)
        gap = confidence - float(second_score)
        ok = confidence >= self.min_confidence and gap >= self.min_gap
        return ObjectRankResult(
            status="OK" if ok else "LOW_CONFIDENCE",
            best_code=best.code,
            best_name=best.name,
            confidence=round(confidence, 4),
            gap=round(gap, 4),
            decision="AUTO_SELECT" if ok else "REVIEW",
            note="" if ok else "Object ranker confidence/gap below threshold",
            ranked_candidates=ranked,
        )

    def _predict_scores(self, texts: list[str]) -> list[float]:
        if not texts:
            return []
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(texts)
            classes = list(getattr(self.model, "classes_", []))
            positive_idx = _positive_class_index(classes)
            return [float(row[positive_idx]) for row in probabilities]
        predictions = self.model.predict(texts)
        return [1.0 if str(value) == "1" else 0.0 for value in predictions]

    def _ensure_loaded(self) -> None:
        if self._load_attempted or self.model is not None:
            return
        self._load_attempted = True
        if not self.enabled:
            self.load_error = "Object ranker disabled"
            return
        if not self.model_path or not self.model_path.exists():
            self.load_error = "Object ranker model not found"
            return
        if not joblib:
            self.load_error = "joblib is not installed"
            return
        try:
            self.model = joblib.load(self.model_path)
        except Exception as exc:  # noqa: BLE001 - keep deterministic fallback
            self.load_error = str(exc)


def _positive_class_index(classes: list[Any]) -> int:
    for idx, value in enumerate(classes):
        if value == 1 or str(value) == "1":
            return idx
    return len(classes) - 1 if classes else 0


def _copy_candidate(candidate: ObjectCandidate, ml_score: float) -> ObjectCandidate:
    return ObjectCandidate(
        code=candidate.code,
        name=candidate.name,
        score=candidate.score,
        source=candidate.source,
        matched_on=candidate.matched_on,
        tax_code=candidate.tax_code,
        group_name=candidate.group_name,
        group_code=candidate.group_code,
        ml_score=round(float(ml_score), 4),
    )
