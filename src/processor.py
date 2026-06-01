from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .accounting_verifier import AccountingVerifier
from .bank_detector import detect_bank
from .config_loader import load_rules
from .entity_extractor import EntityExtractor, OwnCompanyConfig
from .file_utils import list_statement_files
from .models import ClassificationResult, ObjectMatchResult, ProcessedTransaction, Rule, Transaction
from .normalizer import normalize_text
from .object_aliases import load_object_aliases
from .object_matcher import ObjectMatcher
from .parsers.acb_parser import ACBParser
from .parsers.msb_parser import MSBParser
from .parsers.vcb_parser import VCBParser
from .reason_generator import generate_reason
from .rule_engine import RuleEngine
from .ml.transaction_classifier import TransactionClassifier
from .transaction_identity import assign_transaction_uids, build_transaction_uid


PARSERS = {
    "ACB": ACBParser,
    "MSB": MSBParser,
    "VCB": VCBParser,
}


def process_all(
    statements_dir: str | Path,
    receivable_path: str | Path,
    payable_path: str | Path,
    rules_path: str | Path | None,
    default_rules_path: str | Path,
    config: dict[str, Any],
    logger: logging.Logger,
) -> list[ProcessedTransaction]:
    logger.info("Bắt đầu chạy bank statement processor")
    logger.info("Statements dir: %s", statements_dir)
    logger.info("Receivable catalog: %s", receivable_path)
    logger.info("Payable catalog: %s", payable_path)

    project_root = Path(default_rules_path).resolve().parents[1]
    matching_cfg = config.get("matching", {})
    min_score = float(matching_cfg.get("min_score", 80))
    min_gap = float(matching_cfg.get("min_gap", 8))

    own_company_path = _resolve_config_path(config.get("own_company_file", "config/own_company.yaml"), project_root)
    aliases_path = _resolve_config_path(config.get("object_aliases_file", "config/object_aliases.yaml"), project_root)
    own_company = OwnCompanyConfig.from_yaml(own_company_path)
    object_aliases = load_object_aliases(aliases_path)
    entity_extractor = EntityExtractor(own_company)
    verifier = AccountingVerifier(config.get("bank_accounts", {}), own_company)

    receivable_matcher = _load_matcher(
        receivable_path,
        min_score,
        min_gap,
        "phải thu",
        logger,
        aliases=object_aliases.get("receivable", {}),
        own_company=own_company,
    )
    payable_matcher = _load_matcher(
        payable_path,
        min_score,
        min_gap,
        "phải trả",
        logger,
        aliases=object_aliases.get("payable", {}),
        own_company=own_company,
    )

    rules, rule_source = load_rules(rules_path, default_rules_path, logger=logger)
    logger.info("Rule source: %s", rule_source)
    rule_engine = RuleEngine(rules)

    ml_cfg = config.get("ml", {})
    classifier = TransactionClassifier(
        model_path=_resolve_config_path(ml_cfg.get("transaction_classifier_model", "models/transaction_classifier.joblib"), project_root),
        enabled=bool(ml_cfg.get("enabled", True)),
    )
    if classifier.available:
        logger.info("ML transaction classifier loaded")
    else:
        logger.info("ML transaction classifier not found; using rule/entity/fuzzy fallback")

    statement_files = list_statement_files(statements_dir)
    logger.info("Đọc được %s file sao kê", len(statement_files))

    processed: list[ProcessedTransaction] = []
    for statement_file in statement_files:
        try:
            bank = detect_bank(statement_file, logger=logger)
            if not bank:
                logger.error("Không nhận diện được ngân hàng: %s", statement_file)
                continue
            logger.info("File %s được nhận diện là %s", statement_file.name, bank)
            parser = PARSERS[bank]()
            transactions = parser.parse(statement_file)
            logger.info("Parse được %s dòng giao dịch từ %s", len(transactions), statement_file.name)
        except Exception as exc:  # noqa: BLE001 - continue next file
            logger.exception("Lỗi đọc/parse file %s: %s", statement_file, exc)
            continue

        for transaction in transactions:
            item = process_transaction(
                transaction=transaction,
                config=config,
                rule_engine=rule_engine,
                receivable_matcher=receivable_matcher,
                payable_matcher=payable_matcher,
                entity_extractor=entity_extractor,
                verifier=verifier,
                classifier=classifier,
                rules=rules,
            )
            processed.append(item)

    assign_transaction_uids(processed)
    logger.info("Số dòng báo nợ: %s", sum(1 for item in processed if item.flow == "bao_no"))
    logger.info("Số dòng báo có: %s", sum(1 for item in processed if item.flow == "bao_co"))
    logger.info("Số dòng OK: %s", sum(1 for item in processed if item.status == "OK"))
    logger.info("Số dòng EXCEPTION: %s", sum(1 for item in processed if item.status != "OK"))
    logger.info("Kết thúc chạy")
    return processed


def process_transaction(
    transaction: Transaction,
    config: dict[str, Any],
    rule_engine: RuleEngine,
    receivable_matcher: ObjectMatcher,
    payable_matcher: ObjectMatcher,
    entity_extractor: EntityExtractor | None = None,
    verifier: AccountingVerifier | None = None,
    classifier: TransactionClassifier | None = None,
    rules: list[Rule] | None = None,
) -> ProcessedTransaction:
    errors: list[str] = []
    flow = ""
    amount = 0.0
    if transaction.debit_amount > 0 and transaction.credit_amount > 0:
        flow = "unknown"
        amount = max(transaction.debit_amount, transaction.credit_amount)
        errors.append("Dòng có cả ghi nợ và ghi có")
    elif transaction.debit_amount > 0:
        flow = "bao_no"
        amount = transaction.debit_amount
    elif transaction.credit_amount > 0:
        flow = "bao_co"
        amount = transaction.credit_amount
    else:
        flow = "unknown"
        errors.append("Dòng không có số tiền hợp lệ")

    if transaction.transaction_date is None:
        errors.append("Không parse được ngày chứng từ")

    bank_account = config.get("bank_accounts", {}).get(transaction.bank, "")
    if not bank_account:
        errors.append("Không tìm thấy tài khoản ngân hàng cấu hình")

    if entity_extractor is None:
        entity_extractor = EntityExtractor(OwnCompanyConfig([], [], []))
    entities = entity_extractor.extract(transaction.bank, transaction.description, transaction.counterparty_raw)

    rule_match = None
    ml_result = ClassificationResult()
    if flow in {"bao_no", "bao_co"}:
        search_text = f"{transaction.counterparty_raw} {transaction.description}".strip()
        rule_match = rule_engine.match(flow, transaction.bank, search_text)
        if classifier:
            ml_result = classifier.predict(flow, transaction.bank, transaction.description, entities)
        if not rule_match and ml_result.status != "OK":
            errors.append("Không nhận diện được use case")
    else:
        errors.append("Không xác định được luồng báo nợ/báo có")

    use_case = ""
    debit_account = ""
    credit_account = ""
    object_code = ""
    object_name = ""
    match_result = ObjectMatchResult()
    confidence = 0.0
    matched_rule = ""
    active_rule: Rule | None = None

    if rule_match:
        active_rule = rule_match.rule
        matched_rule = active_rule.use_case
        use_case = active_rule.use_case
        confidence = rule_match.confidence
    elif ml_result.status == "OK":
        use_case = ml_result.use_case
        confidence = ml_result.confidence
        active_rule = _rule_for_ml_result(flow, ml_result, rules or [])
        matched_rule = "ML"

    if active_rule:
        if flow == "bao_no":
            debit_account = active_rule.account
            credit_account = bank_account
        elif flow == "bao_co":
            debit_account = bank_account
            credit_account = active_rule.account

        if not active_rule.auto_process:
            errors.append(active_rule.error_note or "Rule không xử lý tự động")

        if active_rule.requires_object:
            matcher = payable_matcher if active_rule.object_catalog == "payable" else receivable_matcher
            match_result = matcher.match(
                transaction.counterparty_raw,
                transaction.description,
                counterparty_hint=entities.counterparty_hint,
                cleaned_description=entities.cleaned_description,
            )
            if match_result.status == "OK":
                object_code = match_result.code
                object_name = match_result.name
                confidence = min(confidence or 1.0, match_result.score / 100)
            else:
                object_code = "ERROR"
                errors.append(match_result.error_note or "Không tìm thấy mã đối tượng")
    elif ml_result.status == "OK":
        if flow == "bao_no":
            debit_account = ml_result.account
            credit_account = bank_account
        elif flow == "bao_co":
            debit_account = bank_account
            credit_account = ml_result.account

    reason = generate_reason(use_case, object_name)
    item = ProcessedTransaction(
        source_file=transaction.source_file,
        original_row_index=transaction.original_row_index,
        bank=transaction.bank,
        flow=flow,
        transaction_date=transaction.transaction_date,
        object_code=object_code,
        object_name=object_name,
        reason=reason,
        debit_account=debit_account,
        credit_account=credit_account,
        amount=amount,
        use_case=use_case,
        original_content=transaction.description,
        counterparty_raw=transaction.counterparty_raw,
        doc_no=transaction.doc_no,
        status="OK",
        error_note="",
        confidence=round(confidence, 4),
        matched_candidates=match_result.candidates,
        normalized_content=normalize_text(transaction.description),
        normalized_counterparty=normalize_text(transaction.counterparty_raw),
        matched_rule=matched_rule,
        raw_data=transaction.raw_data,
        entities=entities,
        ml_result=ml_result,
        object_match_source=match_result.source,
        source_sheet=transaction.source_sheet,
    )

    if verifier:
        verification = verifier.verify(item, active_rule)
        item.verification_result = verification
        if verification.status != "OK":
            errors.append(verification.error_note)

    status = "OK" if not errors else "ERROR"
    if status == "OK" and not _has_required_rpa_fields(transaction, object_code, reason, debit_account, credit_account, amount):
        status = "ERROR"
        errors.append("Thiếu trường bắt buộc để ghi RPA input")

    item.status = status
    item.error_note = "; ".join(dict.fromkeys(error for error in errors if error))
    item.transaction_uid = build_transaction_uid(item)
    return item


def _load_matcher(
    path: str | Path,
    min_score: float,
    min_gap: float,
    label: str,
    logger: logging.Logger,
    aliases: dict[str, list[str]] | None = None,
    own_company: OwnCompanyConfig | None = None,
) -> ObjectMatcher:
    try:
        matcher = ObjectMatcher.from_excel(path, min_score=min_score, min_gap=min_gap, aliases=aliases or {}, own_company=own_company)
        logger.info("Load danh mục %s: %s dòng", label, len(matcher.objects))
        return matcher
    except Exception as exc:  # noqa: BLE001
        logger.error("Không load được danh mục %s từ %s: %s", label, path, exc)
        return ObjectMatcher([], min_score=min_score, min_gap=min_gap, aliases=aliases or {}, own_company=own_company or OwnCompanyConfig([], [], []))


def _has_required_rpa_fields(
    transaction: Transaction,
    object_code: str,
    reason: str,
    debit_account: str,
    credit_account: str,
    amount: float,
) -> bool:
    return bool(transaction.transaction_date and reason and debit_account and credit_account and amount > 0 and object_code != "ERROR")


def _resolve_config_path(value: str | Path, project_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _rule_for_ml_result(flow: str, ml_result: ClassificationResult, rules: list[Rule]) -> Rule | None:
    for rule in rules:
        if rule.flow == flow and rule.account == ml_result.account:
            return rule
    if not ml_result.account:
        return None
    requires_object = ml_result.account in {"331", "131", "141"}
    return Rule(
        flow=flow,
        use_case=ml_result.use_case,
        account=ml_result.account,
        bank_scope=[],
        include_keywords=[],
        context_keywords=[],
        exclude_keywords=[],
        auto_process=True,
        priority=999,
        requires_object=requires_object,
        object_catalog="payable" if flow == "bao_no" and requires_object else "receivable" if flow == "bao_co" and requires_object else "none",
    )
