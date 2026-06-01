from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


SUPPORTED_EXCEL_EXTENSIONS = {".xlsx", ".xls"}


def list_statement_files(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    if not directory.exists():
        return []
    files = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXCEL_EXTENSIONS
        and not path.name.startswith("~$")
    ]
    return sorted(files, key=lambda path: path.name.lower())


def ensure_paths_exist(paths: Iterable[str | Path]) -> list[Path]:
    missing = [Path(path) for path in paths if path and not Path(path).exists()]
    return missing


def get_sheet_names(path: str | Path) -> list[str]:
    excel = pd.ExcelFile(path)
    return excel.sheet_names


def read_excel_rows(
    path: str | Path,
    sheet_name: str,
    nrows: int = 30,
) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=nrows, dtype=object)
