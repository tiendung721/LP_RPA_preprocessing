from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class Transaction:
    source_file: str
    bank: str
    transaction_date: date | None
    doc_no: str
    description: str
    counterparty_raw: str
    debit_amount: float
    credit_amount: float
    original_row_index: int
    raw_data: dict[str, Any] = field(default_factory=dict)
    source_sheet: str = ""


@dataclass
class Rule:
    flow: str
    use_case: str
    account: str
    bank_scope: list[str]
    include_keywords: list[str]
    context_keywords: list[str]
    exclude_keywords: list[str]
    auto_process: bool
    priority: int
    requires_object: bool
    object_catalog: str = "none"
    error_note: str = ""
    context_required: bool = False


@dataclass
class ObjectCandidate:
    code: str
    name: str
    score: float
    source: str = "fuzzy_name"
    matched_on: str = ""


@dataclass
class CatalogObject:
    code: str
    name: str
    group_name: str = ""
    address: str = ""
    tax_code: str = ""
    group_code: str = ""


@dataclass
class ObjectMatchResult:
    code: str = ""
    name: str = ""
    status: str = "NOT_FOUND"
    error_note: str = ""
    score: float = 0.0
    source: str = ""
    candidates: list[ObjectCandidate] = field(default_factory=list)


@dataclass
class RuleMatch:
    rule: Rule
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class ExtractedEntities:
    counterparty_hint: str = ""
    counterparty_source: str = ""
    cleaned_description: str = ""
    intent: str = ""
    invoice_no: str = ""
    bill_no: str = ""
    tax_code: str = ""
    bank_account_hint: str = ""
    service_hint: str = ""
    own_company_hits: list[str] = field(default_factory=list)


@dataclass
class ClassificationResult:
    use_case: str = ""
    account: str = ""
    confidence: float = 0.0
    source: str = "none"
    status: str = "NO_MODEL"
    note: str = ""


@dataclass
class VerificationResult:
    status: str = "OK"
    error_note: str = ""
    checks: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedTransaction:
    source_file: str
    original_row_index: int
    bank: str
    flow: str
    transaction_date: date | None
    object_code: str
    object_name: str
    reason: str
    debit_account: str
    credit_account: str
    amount: float
    use_case: str
    original_content: str
    counterparty_raw: str
    doc_no: str
    status: str
    error_note: str
    confidence: float
    matched_candidates: list[ObjectCandidate] = field(default_factory=list)
    normalized_content: str = ""
    normalized_counterparty: str = ""
    matched_rule: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)
    entities: ExtractedEntities = field(default_factory=ExtractedEntities)
    ml_result: ClassificationResult = field(default_factory=ClassificationResult)
    verification_result: VerificationResult = field(default_factory=VerificationResult)
    object_match_source: str = ""
    transaction_uid: str = ""
    source_sheet: str = ""
    rpa_status: str = ""
