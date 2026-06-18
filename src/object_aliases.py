from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .normalizer import normalize_text


def load_object_aliases(path: str | Path | None) -> dict[str, dict[str, list[str]]]:
    if not path:
        return {"payable": {}, "receivable": {}, "internal": {}}
    path = Path(path)
    if not path.exists():
        return {"payable": {}, "receivable": {}, "internal": {}}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return {
        "payable": _normalize_alias_section(data.get("payable", {})),
        "receivable": _normalize_alias_section(data.get("receivable", {})),
        "internal": _normalize_alias_section(data.get("internal", {})),
    }


def _normalize_alias_section(section: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for code, aliases in section.items():
        if isinstance(aliases, str):
            alias_list = [aliases]
        else:
            alias_list = list(aliases or [])
        normalized = [normalize_text(alias) for alias in alias_list if normalize_text(alias)]
        code_alias = normalize_text(code)
        if _should_include_code_alias(code_alias):
            normalized.append(code_alias)
        result[str(code)] = list(dict.fromkeys(normalized))
    return result


def _should_include_code_alias(code: str) -> bool:
    if not code:
        return False
    compact = code.replace(" ", "")
    if compact.isdigit():
        return len(compact) >= 5
    if any(char.isdigit() for char in compact):
        return len(compact) >= 4
    return len(compact) >= 4
