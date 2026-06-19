from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.rpa_summary import abort_rpa_run, finalize_rpa_run, load_summary, reset_all_rpa_status, update_rpa_status as update_summary_status
from src.rpa_tracking import abort_tracking_run, finalize_tracking_run, reset_all_tracking, update_tracking_status, validate_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update RPA status by transaction_uid")
    parser.add_argument("--output-dir", default="output", help="Output directory containing RPA tracking files")
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
    args = parse_args()
    output_dir = Path(args.output_dir)
    summary_path = output_dir / "rpa_summary.xlsx"
    tracking_path = output_dir / "rpa_tracking.json"

    if args.reset_all:
        if args.uid or args.finalize_run or args.abort_run:
            print("Use --reset-all without --uid, --finalize-run, or --abort-run")
            return 1
        updated_targets = []
        if summary_path.exists():
            reset_all_rpa_status(summary_path, message=args.message)
            updated_targets.append(str(summary_path))
        if tracking_path.exists():
            reset_all_tracking(tracking_path, message=args.message)
            updated_targets.append(str(tracking_path))
        if not updated_targets:
            print(f"No RPA status files found in {output_dir}")
            return 1
        print(f"Reset all rows -> chua_nhap in {', '.join(updated_targets)}")
        return 0

    if args.finalize_run or args.abort_run:
        if args.finalize_run and args.abort_run:
            print("Use only one of --finalize-run or --abort-run")
            return 1
        if not args.run_id:
            print("--run-id is required for run-level updates")
            return 1
        if args.finalize_run:
            if summary_path.exists():
                finalize_rpa_run(summary_path, args.run_id)
            if tracking_path.exists():
                finalize_tracking_run(tracking_path, args.run_id)
            print(f"Finalized run {args.run_id}")
        else:
            if summary_path.exists():
                abort_rpa_run(summary_path, args.run_id, message=args.message)
            if tracking_path.exists():
                abort_tracking_run(tracking_path, args.run_id, message=args.message)
            print(f"Aborted run {args.run_id}")
        return 0

    if not args.uid:
        print("--uid is required for row-level updates")
        return 1

    status = validate_status(args.status)

    base_record = _summary_record(summary_path, args.uid)
    summary_updated = False
    tracking_updated = False
    errors: list[str] = []

    if summary_path.exists():
        try:
            base_record = update_summary_status(
                summary_path,
                args.uid,
                status,
                run_id=args.run_id,
                message=args.message,
                voucher_no=args.voucher_no,
            )
            summary_updated = True
        except KeyError as exc:
            errors.append(str(exc))

    try:
        update_tracking_status(
            tracking_path,
            args.uid,
            status,
            message=args.message,
            voucher_no=args.voucher_no,
            run_id=args.run_id,
            base_record=base_record,
        )
        tracking_updated = True
    except KeyError as exc:
        errors.append(str(exc))

    if not summary_updated and not tracking_updated:
        print("; ".join(errors) or f"transaction_uid not found: {args.uid}")
        return 1

    targets = []
    if tracking_updated:
        targets.append(str(tracking_path))
    if summary_updated:
        targets.append(str(summary_path))
    print(f"Updated {args.uid} -> {status} in {', '.join(targets)}")
    return 0


def _summary_record(summary_path: Path, uid: str) -> dict[str, Any] | None:
    if not summary_path.exists():
        return None
    df = load_summary(summary_path)
    matches = df[df["transaction_uid"].astype(str) == str(uid)]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


if __name__ == "__main__":
    raise SystemExit(main())
