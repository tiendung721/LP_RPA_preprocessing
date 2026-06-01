from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .models import Rule
from .normalizer import normalize_text


DEFAULT_CONFIG: dict[str, Any] = {
    "bank_accounts": {"VCB": "1121VCB", "ACB": "1121CT", "MSB": "1121HB"},
    "matching": {"min_score": 80, "min_gap": 8},
    "output": {
        "date_format": "%d/%m/%Y",
        "excel_file": "rpa_input.xlsx",
        "tracking_file": "rpa_tracking.json",
        "log_file": "agent_run.log",
    },
    "rules": {"default_rules_file": "config/default_rules.yaml"},
    "own_company_file": "config/own_company.yaml",
    "object_aliases_file": "config/object_aliases.yaml",
    "ml": {
        "enabled": True,
        "transaction_classifier_model": "models/transaction_classifier.joblib",
        "object_ranker_model": "models/object_ranker.joblib",
        "min_classification_confidence": 0.75,
        "min_object_confidence": 0.80,
    },
}


def load_config(path: str | Path) -> dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    path = Path(path)
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        config = _deep_merge(config, loaded)
    return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_rules(
    rules_path: str | Path | None,
    default_rules_path: str | Path,
    logger: logging.Logger | None = None,
) -> tuple[list[Rule], str]:
    logger = logger or logging.getLogger(__name__)
    if rules_path:
        rules_path = Path(rules_path)
        if rules_path.exists():
            try:
                rules = _load_rules_from_excel(rules_path)
                if len(rules) >= 6:
                    logger.info("Using rules from Excel: %s", rules_path)
                    return rules, str(rules_path)
                logger.warning("Excel rule file parsed but did not contain enough valid rules: %s", rules_path)
            except Exception as exc:  # noqa: BLE001 - log and fallback by design
                logger.warning("Cannot parse Excel rule file %s: %s", rules_path, exc)
        else:
            logger.warning("Excel rule file does not exist: %s", rules_path)

    default_rules_path = Path(default_rules_path)
    rules = _load_rules_from_yaml(default_rules_path)
    logger.info("Using default YAML rules: %s", default_rules_path)
    return rules, str(default_rules_path)


def _load_rules_from_yaml(path: Path) -> list[Rule]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return [_rule_from_dict(item) for item in data.get("rules", [])]


def _load_rules_from_excel(path: Path) -> list[Rule]:
    df = pd.read_excel(path, sheet_name=0, dtype=object)
    col_map = {normalize_text(col): col for col in df.columns}

    use_case_col = _find_col(col_map, ["USE CASE", "NGHIEP VU"])
    account_col = _find_col(col_map, ["TK", "TAI KHOAN"])
    flow_col = _find_col(col_map, ["LUONG"])
    entry_col = _find_col(col_map, ["NHAP TK"])
    bank_col = _find_col(col_map, ["NGUON SAO KE NGAN HANG", "NGAN HANG"])
    keyword_col = _find_col(col_map, ["DAU HIEU NHAN BIET", "TU KHOA"])
    note_col = _find_col(col_map, ["GHI CHU"])

    if not all([use_case_col, account_col, flow_col, entry_col, bank_col, keyword_col]):
        return []

    rules: list[Rule] = []
    last_flow = ""
    for idx, row in df.iterrows():
        flow_text = normalize_text(row.get(flow_col))
        if "BAO NO" in flow_text:
            last_flow = "bao_no"
        elif "BAO CO" in flow_text:
            last_flow = "bao_co"

        flow = last_flow
        use_case = str(row.get(use_case_col) or "").strip()
        account = str(row.get(account_col) or "").strip()
        banks = _split_banks(str(row.get(bank_col) or ""))
        keywords = _split_keywords(str(row.get(keyword_col) or ""))
        note = str(row.get(note_col) or "").strip() if note_col else ""
        if not flow or not use_case or not account or not banks or not keywords:
            continue

        norm_use_case = normalize_text(use_case)
        insurance = any(token in norm_use_case for token in ["BHXH", "BHTN", "BHYT", "BAO HIEM"])
        requires_object = account in {"331", "131"} or "TAM UNG" in norm_use_case
        catalog = "none"
        if requires_object:
            catalog = "payable" if flow == "bao_no" else "receivable"

        rules.append(
            Rule(
                flow=flow,
                use_case=use_case,
                account=account,
                bank_scope=banks,
                include_keywords=keywords,
                context_keywords=[],
                exclude_keywords=["TNDN", "THUE TNDN"] if account == "3335" else [],
                auto_process=not insurance,
                priority=(idx + 1) * 10,
                requires_object=requires_object,
                object_catalog=catalog,
                error_note="Luá»“ng báº£o hiá»ƒm khÃ´ng xá»­ lÃ½ tá»± Ä‘á»™ng" if insurance else "",
            )
        )
    return rules


def _find_col(col_map: dict[str, Any], candidates: list[str]) -> Any | None:
    normalized_candidates = [normalize_text(candidate) for candidate in candidates]
    for norm_col, original in col_map.items():
        if any(candidate in norm_col for candidate in normalized_candidates):
            return original
    return None


def _split_banks(value: str) -> list[str]:
    banks = []
    for item in re.split(r"[,;/\n]+", value.upper()):
        item = item.strip()
        if item in {"VCB", "ACB", "MSB"}:
            banks.append(item)
    return banks


def _split_keywords(value: str) -> list[str]:
    parts = re.split(r"[,;\n]+", value)
    keywords: list[str] = []
    for part in parts:
        part = re.sub(r"^[-â€¢\s]+", "", part).strip()
        if not part:
            continue
        normalized = normalize_text(part)
        if ":" in part or "DAU HIEU" in normalized or "TU KHOA" in normalized:
            tail = part.split(":", 1)[-1]
            keywords.extend(_split_keywords(tail))
            continue
        if normalized and len(normalized) <= 60:
            keywords.append(normalized)
    return list(dict.fromkeys(keywords))


def _rule_from_dict(item: dict[str, Any]) -> Rule:
    return Rule(
        flow=str(item.get("flow", "")).strip(),
        use_case=str(item.get("use_case", "")).strip(),
        account=str(item.get("account", "")).strip(),
        bank_scope=[str(bank).upper() for bank in item.get("bank_scope", [])],
        include_keywords=[str(keyword) for keyword in item.get("include_keywords", [])],
        context_keywords=[str(keyword) for keyword in item.get("context_keywords", [])],
        exclude_keywords=[str(keyword) for keyword in item.get("exclude_keywords", [])],
        auto_process=bool(item.get("auto_process", True)),
        priority=int(item.get("priority", 999)),
        requires_object=bool(item.get("requires_object", False)),
        object_catalog=str(item.get("object_catalog", "none") or "none"),
        error_note=str(item.get("error_note", "") or ""),
        context_required=bool(item.get("context_required", False)),
    )

