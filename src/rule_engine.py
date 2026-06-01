from __future__ import annotations

import re

from .models import Rule, RuleMatch
from .normalizer import normalize_text


class RuleEngine:
    def __init__(self, rules: list[Rule]):
        self.rules = sorted(rules, key=lambda rule: (rule.flow, rule.priority))

    def match(self, flow: str, bank: str, description: str) -> RuleMatch | None:
        normalized = normalize_text(description)
        for rule in self.rules:
            if rule.flow != flow:
                continue
            if rule.bank_scope and bank.upper() not in {item.upper() for item in rule.bank_scope}:
                continue
            if any(contains_keyword(normalized, keyword) for keyword in rule.exclude_keywords):
                continue

            include_hits = [
                normalize_text(keyword)
                for keyword in rule.include_keywords
                if contains_keyword(normalized, keyword)
            ]
            if not include_hits:
                continue

            context_hits = [
                normalize_text(keyword)
                for keyword in rule.context_keywords
                if contains_keyword(normalized, keyword)
            ]
            if rule.context_required and not context_hits and not any(_is_strong_keyword(hit) for hit in include_hits):
                continue

            confidence = 0.92
            if context_hits:
                confidence += 0.04
            if not rule.auto_process:
                confidence = 0.99
            return RuleMatch(rule=rule, confidence=min(confidence, 0.99), matched_keywords=include_hits)
        return None


def contains_keyword(normalized_text: str, keyword: str) -> bool:
    keyword_norm = normalize_text(keyword)
    if not normalized_text or not keyword_norm:
        return False
    tokens = keyword_norm.split()
    pattern = r"(?<![A-Z0-9])" + r"\s+".join(re.escape(token) for token in tokens) + r"(?![A-Z0-9])"
    return re.search(pattern, normalized_text) is not None


def _is_strong_keyword(keyword_norm: str) -> bool:
    if keyword_norm.startswith("THUE ") or " THUE " in f" {keyword_norm} ":
        return True
    return keyword_norm in {"VAT", "TCHQ", "BHXH", "BHTN", "BHYT"}
