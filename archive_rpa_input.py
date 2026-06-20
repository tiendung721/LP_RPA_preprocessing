from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive an edited rpa_input.xlsx workbook")
    parser.add_argument("--input-file", required=True, help="Path to the edited rpa_input.xlsx")
    parser.add_argument("--history-dir", required=True, help="Directory for archived input workbooks")
    return parser.parse_args()


def archive_rpa_input(input_file: str | Path, history_dir: str | Path) -> Path:
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"RPA input file not found: {input_path}")

    history_path = Path(history_dir)
    history_path.mkdir(parents=True, exist_ok=True)
    destination = _archive_destination(history_path, datetime.now().strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(input_path, destination)
    return destination


def _archive_destination(history_dir: Path, timestamp: str) -> Path:
    base = history_dir / f"rpa_input_{timestamp}.xlsx"
    if not base.exists():
        return base
    for suffix in range(1, 1000):
        candidate = history_dir / f"rpa_input_{timestamp}_{suffix:03d}.xlsx"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Cannot create a unique archive name in {history_dir}")


def main() -> int:
    args = parse_args()
    try:
        archived_path = archive_rpa_input(args.input_file, args.history_dir)
    except OSError as exc:
        print(str(exc))
        return 1
    print(archived_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
