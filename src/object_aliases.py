from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .normalizer import normalize_text


def load_object_aliases(path: str | Path | None) -> dict[str, dict[str, list[str]]]:
    if not path:
        return {"payable": {}, "receivable": {}}
    path = Path(path)
    if not path.exists():
        return {"payable": {}, "receivable": {}}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return {
        "payable": _normalize_alias_section(data.get("payable", {})),
        "receivable": _normalize_alias_section(data.get("receivable", {})),
    }


def _normalize_alias_section(section: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for code, aliases in section.items():
        if isinstance(aliases, str):
            alias_list = [aliases]
        else:
            alias_list = list(aliases or [])
        normalized = [normalize_text(alias) for alias in alias_list if normalize_text(alias)]
        normalized.append(normalize_text(code))
        result[str(code)] = list(dict.fromkeys(normalized))
    return result
