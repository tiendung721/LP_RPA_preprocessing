from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz

from .entity_extractor import OwnCompanyConfig
from .models import CatalogObject, ObjectCandidate, ObjectMatchResult
from .normalizer import clean_string, is_empty, normalize_text


@dataclass
class ObjectMatcher:
    objects: list[CatalogObject]
    min_score: float = 80
    min_gap: float = 8
    aliases: dict[str, list[str]] = field(default_factory=dict)
    own_company: OwnCompanyConfig = field(default_factory=lambda: OwnCompanyConfig([], [], []))

    def __post_init__(self) -> None:
        self._prepared_objects = [
            (obj, _object_variants(obj), _variant_tokens(_object_variants(obj)))
            for obj in self.objects
            if not self._is_own_company_object(obj)
        ]
        self._objects_by_norm_code = {normalize_text(obj.code): obj for obj, _, _ in self._prepared_objects}

    @classmethod
    def from_excel(
        cls,
        path: str | Path,
        min_score: float = 80,
        min_gap: float = 8,
        aliases: dict[str, list[str]] | None = None,
        own_company: OwnCompanyConfig | None = None,
    ) -> "ObjectMatcher":
        return cls(
            load_catalog(path),
            min_score=min_score,
            min_gap=min_gap,
            aliases=aliases or {},
            own_company=own_company or OwnCompanyConfig([], [], []),
        )

    @classmethod
    def from_records(
        cls,
        records: list[dict[str, Any]],
        min_score: float = 80,
        min_gap: float = 8,
        aliases: dict[str, list[str]] | None = None,
        own_company: OwnCompanyConfig | None = None,
    ) -> "ObjectMatcher":
        objects = [
            CatalogObject(
                code=clean_string(record.get("code", "")),
                name=clean_string(record.get("name", "")),
                group_name=clean_string(record.get("group_name", "")),
                address=clean_string(record.get("address", "")),
                tax_code=clean_string(record.get("tax_code", "")),
                group_code=clean_string(record.get("group_code", "")),
            )
            for record in records
            if clean_string(record.get("code", "")) and clean_string(record.get("name", ""))
        ]
        return cls(objects, min_score=min_score, min_gap=min_gap, aliases=aliases or {}, own_company=own_company or OwnCompanyConfig([], [], []))

    def match(
        self,
        counterparty_raw: str = "",
        description: str = "",
        counterparty_hint: str = "",
        cleaned_description: str = "",
    ) -> ObjectMatchResult:
        search_parts = _dedupe(
            [
                normalize_text(counterparty_hint),
                normalize_text(counterparty_raw),
                normalize_text(cleaned_description),
                self.own_company.strip_from_text(description),
            ]
        )
        search_parts = [part for part in search_parts if part]
        if not search_parts or not self._prepared_objects:
            return ObjectMatchResult(error_note="Không tìm thấy mã đối tượng")

        alias_candidates = self._alias_candidates(search_parts)
        fuzzy_candidates = self._fuzzy_candidates(search_parts, bool(counterparty_hint))
        scored = _merge_candidates(alias_candidates + fuzzy_candidates)
        top_candidates = scored[:5]
        if not top_candidates:
            return ObjectMatchResult(error_note="Không tìm thấy mã đối tượng", candidates=[])

        best = top_candidates[0]
        second_score = top_candidates[1].score if len(top_candidates) > 1 else 0.0
        gap = best.score - second_score

        if best.score < self.min_score:
            return ObjectMatchResult(
                status="NOT_FOUND",
                error_note="Không tìm thấy mã đối tượng",
                score=best.score,
                source=best.source,
                candidates=top_candidates,
            )

        strong_source = best.source in {"alias_match", "entity_match", "tax_code"}
        if len(top_candidates) > 1 and gap < self.min_gap and not (strong_source and best.score >= 95):
            return ObjectMatchResult(
                code="ERROR",
                status="AMBIGUOUS",
                error_note="Nhiều mã đối tượng khớp gần bằng nhau",
                score=best.score,
                source=best.source,
                candidates=top_candidates,
            )
        return ObjectMatchResult(
            code=best.code,
            name=best.name,
            status="OK",
            score=best.score,
            source=best.source,
            candidates=top_candidates,
        )

    def _alias_candidates(self, search_parts: list[str]) -> list[ObjectCandidate]:
        search_text = " ".join(search_parts)
        candidates: list[ObjectCandidate] = []
        for code, aliases in self.aliases.items():
            obj = self._objects_by_norm_code.get(normalize_text(code))
            if not obj or self._is_own_company_object(obj):
                continue
            for alias in aliases:
                if alias and _contains_phrase(search_text, alias):
                    candidates.append(ObjectCandidate(code=obj.code, name=obj.name, score=100.0, source="alias_match", matched_on=alias))
                    break
        return candidates

    def _fuzzy_candidates(self, search_parts: list[str], has_hint: bool) -> list[ObjectCandidate]:
        search_tokens = _search_tokens(search_parts)
        scored: list[ObjectCandidate] = []
        for obj, variants, variant_tokens in self._prepared_objects:
            if search_tokens and variant_tokens and not (search_tokens & variant_tokens):
                continue
            score, source, matched_on = self._score_object(variants, search_parts, has_hint)
            if score > 0:
                scored.append(ObjectCandidate(code=obj.code, name=obj.name, score=round(score, 2), source=source, matched_on=matched_on))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored

    def _score_object(self, variants: list[str], search_parts: list[str], has_hint: bool) -> tuple[float, str, str]:
        best = 0.0
        best_source = "fuzzy_name"
        best_variant = ""
        for idx, part in enumerate(search_parts):
            if not part:
                continue
            is_hint_part = has_hint and idx == 0
            for variant in variants:
                if not variant:
                    continue
                if _is_exact_identifier(variant) and _contains_identifier(part, variant):
                    return 100.0, "tax_code", variant
                if is_hint_part and (_contains_phrase(part, variant) or _contains_phrase(variant, part)):
                    return 100.0, "entity_match", variant
                token_score = fuzz.token_set_ratio(part, variant)
                partial_score = fuzz.partial_ratio(part, variant)
                score = token_score * 0.65 + partial_score * 0.35
                if is_hint_part:
                    score = min(100.0, score + 8)
                if score > best:
                    best = score
                    best_source = "entity_match" if is_hint_part else "fuzzy_name"
                    best_variant = variant
        return best, best_source, best_variant

    def _is_own_company_object(self, obj: CatalogObject) -> bool:
        return self.own_company.is_own_code(obj.code) or self.own_company.is_own_name(obj.name) or self.own_company.is_own_tax_code(obj.tax_code)


def load_catalog(path: str | Path) -> list[CatalogObject]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    excel = pd.ExcelFile(path)
    sheet_name = "r_dmdt" if "r_dmdt" in excel.sheet_names else excel.sheet_names[0]
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None, dtype=object)
    data_start, columns = _detect_catalog_columns(raw)

    objects: list[CatalogObject] = []
    for row_idx in range(data_start, len(raw)):
        row = raw.iloc[row_idx]
        code = clean_string(_safe_get(row, columns.get("code")))
        name = clean_string(_safe_get(row, columns.get("name")))
        if not code or not name or code.startswith("["):
            continue
        objects.append(
            CatalogObject(
                code=code,
                name=name,
                group_name=clean_string(_safe_get(row, columns.get("group_name"))),
                address=clean_string(_safe_get(row, columns.get("address"))),
                tax_code=clean_string(_safe_get(row, columns.get("tax_code"))),
                group_code=clean_string(_safe_get(row, columns.get("group_code"))),
            )
        )
    return objects


def _detect_catalog_columns(raw: pd.DataFrame) -> tuple[int, dict[str, int]]:
    for idx, row in raw.head(20).iterrows():
        normalized_cells = [normalize_text(value) for value in row.tolist()]
        code_idx = _find_cell_index(normalized_cells, ["MA DT", "MA DOI TUONG"])
        name_idx = _find_cell_index(normalized_cells, ["TEN DOI TUONG", "TEN DT"])
        if code_idx is not None and name_idx is not None:
            return int(idx) + 1, {
                "code": code_idx,
                "name": name_idx,
                "group_name": _find_cell_index(normalized_cells, ["TEN NHOM"]),
                "address": _find_cell_index(normalized_cells, ["DIA CHI"]),
                "tax_code": _find_cell_index(normalized_cells, ["MA SO THUE", "MS THUE"]),
                "group_code": _find_cell_index(normalized_cells, ["MA NHOM DT"]),
            }

    for idx, row in raw.head(30).iterrows():
        values = [clean_string(value) for value in row.tolist()]
        if sum(1 for value in values if value.startswith("[") and value.endswith("]")) >= 4:
            return int(idx) + 1, {
                "code": 1,
                "name": 3,
                "group_name": 4,
                "address": 5,
                "tax_code": 7,
                "group_code": 9,
            }
    raise ValueError("Không tìm thấy cấu trúc cột danh mục đối tượng")


def _find_cell_index(cells: list[str], aliases: list[str]) -> int | None:
    normalized_aliases = [normalize_text(alias) for alias in aliases]
    for idx, cell in enumerate(cells):
        if any(alias in cell for alias in normalized_aliases):
            return idx
    return None


def _safe_get(row: pd.Series, idx: int | None) -> Any:
    if idx is None or idx >= len(row):
        return ""
    value = row.iloc[idx]
    return "" if is_empty(value) else value


def _object_variants(obj: CatalogObject) -> list[str]:
    variants = [
        normalize_text(obj.name),
        _simplify_name_norm(obj.name),
        normalize_text(obj.code),
        normalize_text(obj.tax_code),
    ]
    return list(dict.fromkeys(variant for variant in variants if variant))


def _variant_tokens(variants: list[str]) -> set[str]:
    tokens: set[str] = set()
    for variant in variants:
        tokens.update(token for token in variant.split() if len(token) >= 3)
    return tokens


def _search_tokens(search_parts: list[str]) -> set[str]:
    tokens: set[str] = set()
    for part in search_parts:
        tokens.update(token for token in part.split() if len(token) >= 3)
    return tokens


def _simplify_name_norm(name: str) -> str:
    text = normalize_text(name)
    phrase_stops = [
        "CONG TY CO PHAN",
        "CONG TY TNHH",
        "CONG TY",
        "C NG TY",
        "CTY",
        "TNHH",
        "CO PHAN",
        "CHI NHANH",
        "VIET NAM",
        "VIETNAM",
    ]
    for phrase in phrase_stops:
        text = re_sub_phrase(text, phrase, " ")
    word_stops = {
        "CP",
        "MTV",
        "TRACH",
        "NHIEM",
        "HUU",
        "HAN",
        "VAN",
        "TAI",
        "BIEN",
        "THUONG",
        "MAI",
        "DICH",
        "VU",
        "XUAT",
        "NHAP",
        "KHAU",
    }
    tokens = [token for token in text.split() if token not in word_stops]
    return " ".join(tokens)


def re_sub_phrase(text: str, phrase: str, repl: str) -> str:
    return " ".join(text.replace(phrase, repl).split())


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    if len(phrase) <= 1:
        return False
    pattern = r"(?<![A-Z0-9])" + r"\s+".join(map(re.escape, phrase.split())) + r"(?![A-Z0-9])"
    return re.search(pattern, text) is not None


def _is_exact_identifier(value: str) -> bool:
    return value.isdigit() and len(value) >= 5


def _contains_identifier(text: str, identifier: str) -> bool:
    return re.search(rf"(?<!\d){re.escape(identifier)}(?!\d)", text) is not None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _merge_candidates(candidates: list[ObjectCandidate]) -> list[ObjectCandidate]:
    best_by_code: dict[str, ObjectCandidate] = {}
    for candidate in candidates:
        key = normalize_text(candidate.code)
        existing = best_by_code.get(key)
        if existing is None or candidate.score > existing.score:
            best_by_code[key] = candidate
    merged = list(best_by_code.values())
    merged.sort(key=lambda item: item.score, reverse=True)
    return merged
