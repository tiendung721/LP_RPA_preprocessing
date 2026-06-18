from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None

from ..models import Transaction
from ..normalizer import clean_string, is_empty, normalize_text, parse_amount, parse_date


class BaseBankParser:
    bank: str = ""
    preferred_sheets: tuple[str, ...] = ()
    field_aliases: dict[str, list[str]] = {}
    required_fields: tuple[str, ...] = (
        "transaction_date",
        "description",
        "debit_amount",
        "credit_amount",
    )

    def parse(self, path: str | Path) -> list[Transaction]:
        path = Path(path)
        self.skipped_row_count = 0
        self.warnings: list[dict[str, Any]] = []
        sheet_name, header_row, column_map = self._find_header(path)
        df = pd.read_excel(path, sheet_name=sheet_name, header=header_row, dtype=object)
        transactions: list[Transaction] = []

        for idx, row in df.iterrows():
            if self._is_blank_row(row):
                self.skipped_row_count += 1
                continue
            transaction = self._row_to_transaction(
                path=path,
                source_sheet=sheet_name,
                row=row,
                row_index=int(idx) + header_row + 2,
                column_map=column_map,
                columns=list(df.columns),
            )
            if self._should_keep(transaction):
                transactions.append(transaction)
            else:
                self.skipped_row_count += 1
        return transactions

    def _row_to_transaction(
        self,
        path: Path,
        source_sheet: str,
        row: pd.Series,
        row_index: int,
        column_map: dict[str, int],
        columns: list[Any],
    ) -> Transaction:
        raw_data = {
            clean_string(columns[col_idx]): _jsonable_cell(row.iloc[col_idx])
            for col_idx in range(len(columns))
            if not is_empty(row.iloc[col_idx])
        }
        description = self._value(row, column_map, "description")
        counterparty = self._value(row, column_map, "counterparty_raw")
        return Transaction(
            source_file=path.name,
            bank=self.bank,
            transaction_date=parse_date(self._value(row, column_map, "transaction_date")),
            doc_no=clean_string(self._value(row, column_map, "doc_no")),
            description=clean_string(description),
            counterparty_raw=clean_string(counterparty),
            debit_amount=parse_amount(self._value(row, column_map, "debit_amount")),
            credit_amount=parse_amount(self._value(row, column_map, "credit_amount")),
            original_row_index=row_index,
            raw_data=raw_data,
            source_sheet=source_sheet,
        )

    def _value(self, row: pd.Series, column_map: dict[str, int], field: str) -> Any:
        col_idx = column_map.get(field)
        if col_idx is None or col_idx >= len(row):
            return ""
        return row.iloc[col_idx]

    def _should_keep(self, transaction: Transaction) -> bool:
        if transaction.debit_amount or transaction.credit_amount:
            return True
        if transaction.description or transaction.counterparty_raw or transaction.doc_no:
            return transaction.transaction_date is not None
        return False

    def _find_header(self, path: Path) -> tuple[str, int, dict[str, int]]:
        excel = pd.ExcelFile(path)
        sheet_names = _ordered_sheets(excel.sheet_names, self.preferred_sheets)
        best: tuple[str, int, dict[str, int], int] | None = None

        for sheet_name in sheet_names:
            sample = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=30, dtype=object)
            for row_idx, row in sample.iterrows():
                column_map = self._match_header(row.tolist())
                score = sum(1 for field in self.required_fields if field in column_map)
                score += sum(1 for field in ("doc_no", "counterparty_raw") if field in column_map)
                if all(field in column_map for field in self.required_fields):
                    if best is None or score > best[3]:
                        best = (sheet_name, int(row_idx), column_map, score)
        if not best:
            raise ValueError(f"Cannot find required header columns for {self.bank} in {path.name}")
        return best[0], best[1], best[2]

    def _match_header(self, values: list[Any]) -> dict[str, int]:
        normalized_values = [normalize_text(value) for value in values]
        column_map: dict[str, int] = {}
        used: set[int] = set()
        for field, aliases in self.field_aliases.items():
            best_idx = -1
            best_score = 0.0
            for idx, column in enumerate(normalized_values):
                if idx in used or not column:
                    continue
                score = max(_score(column, normalize_text(alias)) for alias in aliases)
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx >= 0 and best_score >= 86:
                column_map[field] = best_idx
                used.add(best_idx)
        return column_map

    def _is_blank_row(self, row: pd.Series) -> bool:
        return all(is_empty(value) for value in row.tolist())


def _ordered_sheets(sheet_names: list[str], preferred: tuple[str, ...]) -> list[str]:
    ordered: list[str] = []
    for preferred_name in preferred:
        for sheet_name in sheet_names:
            if normalize_text(sheet_name) == normalize_text(preferred_name) and sheet_name not in ordered:
                ordered.append(sheet_name)
    ordered.extend(sheet for sheet in sheet_names if sheet not in ordered)
    return ordered


def _score(column: str, alias: str) -> float:
    if not column or not alias:
        return 0.0
    if column == alias or alias in column:
        return 100.0
    if fuzz:
        return float(fuzz.token_set_ratio(alias, column))
    left = set(alias.split())
    right = set(column.split())
    return len(left & right) / max(len(left | right), 1) * 100


def _jsonable_cell(value: Any) -> Any:
    if is_empty(value):
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
