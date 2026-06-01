from __future__ import annotations

import argparse
from pathlib import Path

from src.config_loader import load_config
from src.logger_setup import setup_logger
from src.output_writer import write_outputs
from src.processor import process_all


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline bank statement RPA input generator")
    parser.add_argument("--input-dir", default="input", help="Thư mục input tổng")
    parser.add_argument("--statements", help="Thư mục chứa sao kê ngân hàng")
    parser.add_argument("--receivable", help="File danh mục đối tượng phải thu")
    parser.add_argument("--payable", help="File danh mục đối tượng phải trả")
    parser.add_argument("--rules", help="File Excel quy luật")
    parser.add_argument("--output-dir", default="output", help="Thư mục output")
    parser.add_argument("--config", default="config/config.yaml", help="File config YAML")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent

    config_path = _resolve_path(args.config, project_root)
    config = load_config(config_path)
    output_dir = _resolve_path(args.output_dir, project_root)
    log_file = config.get("output", {}).get("log_file", "agent_run.log")
    logger = setup_logger(output_dir, log_file)

    input_dir = _resolve_path(args.input_dir, project_root)
    statements_dir = _resolve_path(args.statements, project_root) if args.statements else input_dir / "statements"
    receivable_path = _resolve_path(args.receivable, project_root) if args.receivable else input_dir / "DS mã đối tượng phải thu.xlsx"
    payable_path = _resolve_path(args.payable, project_root) if args.payable else input_dir / "DS mã đối tượng phải trả.xlsx"
    rules_path = _resolve_path(args.rules, project_root) if args.rules else input_dir / "quy_luat_da_bo_TNDN_o_TNCN.xlsx"
    default_rules_path = _resolve_path(config.get("rules", {}).get("default_rules_file", "config/default_rules.yaml"), project_root)

    processed = process_all(
        statements_dir=statements_dir,
        receivable_path=receivable_path,
        payable_path=payable_path,
        rules_path=rules_path,
        default_rules_path=default_rules_path,
        config=config,
        logger=logger,
    )
    write_outputs(processed, output_dir, config)
    logger.info("Đã ghi output vào: %s", output_dir)
    return 0


def _resolve_path(value: str | Path | None, project_root: Path) -> Path:
    if value is None:
        return project_root
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = project_root / path
    return candidate if candidate.exists() or not path.exists() else path.resolve()


if __name__ == "__main__":
    raise SystemExit(main())
