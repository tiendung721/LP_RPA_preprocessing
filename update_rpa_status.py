from __future__ import annotations

import argparse
from pathlib import Path

from src.rpa_summary import abort_rpa_run, finalize_rpa_run, reset_all_rpa_status, update_rpa_status as update_summary_status
from src.rpa_tracking import validate_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update RPA status by transaction_uid")
    parser.add_argument("--output-dir", default="output", help="Output directory containing rpa_summary.xlsx")
    parser.add_argument("--uid", help="transaction_uid to update")
    parser.add_argument("--status", default="chua_nhap", help="chua_nhap or hoan_thanh; legacy statuses are normalized to chua_nhap")
    parser.add_argument("--message", default="", help="Optional RPA message")
    parser.add_argument("--voucher-no", default="", help="Optional VACOM voucher number")
    parser.add_argument("--run-id", default="", help="Optional run id")
    parser.add_argument("--finalize-run", action="store_true", help="Finalize successful rows from this run as hoan_thanh")
    parser.add_argument("--abort-run", action="store_true", help="Reset rows touched in this run back to chua_nhap")
    parser.add_argument("--reset-all", action="store_true", help="Reset all rows back to chua_nhap")
    return parser.parse_args()


def main() -> int:
    try:
        return _main()
    except PermissionError:
        print("Không ghi được rpa_summary.xlsx. Vui lòng đóng file Excel rồi chạy lại.")
        return 1


def _main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    summary_path = output_dir / "rpa_summary.xlsx"

    if args.reset_all:
        if args.uid or args.finalize_run or args.abort_run:
            print("Use --reset-all without --uid, --finalize-run, or --abort-run")
            return 1
        if not summary_path.exists():
            print(f"RPA summary file not found: {summary_path}")
            return 1
        reset_all_rpa_status(summary_path, message=args.message)
        print(f"Reset all rows -> chua_nhap in {summary_path}")
        return 0

    if args.finalize_run or args.abort_run:
        if args.finalize_run and args.abort_run:
            print("Use only one of --finalize-run or --abort-run")
            return 1
        if not args.run_id:
            print("--run-id is required for run-level updates")
            return 1
        if not summary_path.exists():
            print(f"RPA summary file not found: {summary_path}")
            return 1
        if args.finalize_run:
            finalize_rpa_run(summary_path, args.run_id)
            print(f"Finalized run {args.run_id}")
        else:
            abort_rpa_run(summary_path, args.run_id, message=args.message)
            print(f"Aborted run {args.run_id}")
        return 0

    if not args.uid:
        print("--uid is required for row-level updates")
        return 1

    status = validate_status(args.status)

    if not summary_path.exists():
        print(f"RPA summary file not found: {summary_path}")
        return 1
    try:
        update_summary_status(
            summary_path,
            args.uid,
            status,
            run_id=args.run_id,
            message=args.message,
            voucher_no=args.voucher_no,
        )
    except KeyError as exc:
        print(str(exc))
        return 1

    print(f"Updated {args.uid} -> {status} in {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
