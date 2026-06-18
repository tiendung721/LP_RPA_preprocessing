from __future__ import annotations

import json
import logging
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .normalizer import normalize_text


STATUS_PENDING = "chua_nhap"
STATUS_DONE = "hoan_thanh"
ATTEMPT_SUCCESS = "success"
ATTEMPT_ERROR = "error"

VALID_RPA_STATUSES = {
    STATUS_PENDING,
    STATUS_DONE,
}

ELIGIBLE_RPA_STATUSES = {STATUS_PENDING}

TRACKING_REQUIRED_FIELDS = [
    "transaction_uid",
    "bank_code",
    "source_file",
    "source_sheet",
    "source_row",
    "direction",
    "rpa_status",
    "rpa_message",
    "created_at",
    "updated_at",
    "completed_at",
]


def normalize_status(value: Any, default: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return default
    if raw in VALID_RPA_STATUSES:
        return raw

    normalized = normalize_text(raw)
    aliases = {
        "CHUA NHAP": STATUS_PENDING,
        "DANG NHAP": STATUS_PENDING,
        "HOAN THANH": STATUS_DONE,
        "LOI": STATUS_PENDING,
        "BO QUA": STATUS_PENDING,
        "CAN KIEM TRA": STATUS_PENDING,
        "PENDING": STATUS_PENDING,
        "IN PROGRESS": STATUS_PENDING,
        "DONE": STATUS_DONE,
        "COMPLETED": STATUS_DONE,
        "ERROR": STATUS_PENDING,
        "SKIPPED": STATUS_PENDING,
        "REVIEW": STATUS_PENDING,
    }
    return aliases.get(normalized, default)


def validate_status(status: str) -> str:
    normalized = normalize_status(status)
    if normalized not in VALID_RPA_STATUSES:
        raise ValueError(f"Unsupported RPA status: {status}")
    return normalized


def load_tracking(path: str | Path, logger: logging.Logger | None = None) -> dict[str, dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _backup_invalid_json(path, exc, logger)
        return {}
    except OSError as exc:
        if logger:
            logger.warning("Cannot read RPA tracking file %s: %s", path, exc)
        return {}

    records: dict[str, dict[str, Any]] = {}
    for record in _iter_records(data):
        explicit_status = normalize_status(record.get("rpa_status") or record.get("status"), default="")
        normalized = normalize_tracking_record(record)
        if not explicit_status:
            normalized["rpa_status"] = ""
            normalized["status"] = ""
        uid = str(normalized.get("transaction_uid", "")).strip()
        if uid:
            records[uid] = normalized
    return records


def write_tracking_records(records: Iterable[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean_records = [normalize_tracking_record(record) for record in records]
    clean_records.sort(
        key=lambda item: (
            str(item.get("source_file", "")),
            str(item.get("source_sheet", "")),
            _safe_int(item.get("source_row")),
            str(item.get("transaction_uid", "")),
        )
    )
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(clean_records, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    tmp_path.replace(path)


def update_tracking_status(
    path: str | Path,
    transaction_uid: str,
    status: str,
    message: str = "",
    voucher_no: str = "",
    run_id: str = "",
    base_record: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    path = Path(path)
    records = load_tracking(path, logger=logger)
    uid = str(transaction_uid).strip()
    if not uid:
        raise ValueError("transaction_uid is required")
    if uid not in records:
        if base_record is None:
            raise KeyError(f"transaction_uid not found in RPA tracking: {uid}")
        records[uid] = normalize_tracking_record({**base_record, "transaction_uid": uid})

    record = apply_status_update(records[uid], status, message=message, voucher_no=voucher_no, run_id=run_id)
    records[uid] = record
    write_tracking_records(records.values(), path)
    return record


def apply_status_update(
    record: dict[str, Any],
    status: str,
    message: str = "",
    voucher_no: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    status = validate_status(status)
    now = _now()
    result = normalize_tracking_record(record)
    if status == STATUS_DONE:
        result["last_attempt_result"] = ""
        result["rpa_status"] = STATUS_DONE
        result["status"] = STATUS_DONE
        result["completed_at"] = now
    else:
        result["last_attempt_result"] = ATTEMPT_ERROR if message else result.get("last_attempt_result", "")
        result["rpa_status"] = STATUS_PENDING
        result["status"] = STATUS_PENDING
        if result["last_attempt_result"] == ATTEMPT_ERROR:
            result["completed_at"] = ""
    result["updated_at"] = now
    if run_id:
        result["last_run_id"] = run_id
    if message or status == STATUS_DONE:
        result["rpa_message"] = message
    if voucher_no:
        result["voucher_no"] = voucher_no

    if status == STATUS_PENDING and not message and not voucher_no:
        result["rpa_started_at"] = now
        result["rpa_finished_at"] = ""
        result["last_attempt_result"] = ""
    else:
        result["rpa_finished_at"] = now
    return result


def finalize_run_records(records: Iterable[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    run_id = str(run_id).strip()
    now = _now()
    updated: list[dict[str, Any]] = []
    for record in records:
        item = normalize_tracking_record(record)
        if run_id and str(item.get("last_run_id", "")).strip() == run_id and item.get("last_attempt_result") == ATTEMPT_SUCCESS:
            item["rpa_status"] = STATUS_DONE
            item["status"] = STATUS_DONE
            item["completed_at"] = now
            item["rpa_finished_at"] = now
            item["updated_at"] = now
            item["last_attempt_result"] = ""
        updated.append(item)
    return updated


def abort_run_records(records: Iterable[dict[str, Any]], run_id: str, message: str = "") -> list[dict[str, Any]]:
    run_id = str(run_id).strip()
    now = _now()
    updated: list[dict[str, Any]] = []
    for record in records:
        item = normalize_tracking_record(record)
        touched_in_run = run_id and str(item.get("last_run_id", "")).strip() == run_id and bool(item.get("last_attempt_result"))
        if touched_in_run:
            item["rpa_status"] = STATUS_PENDING
            item["status"] = STATUS_PENDING
            item["completed_at"] = ""
            item["voucher_no"] = ""
            item["rpa_message"] = message
            item["rpa_finished_at"] = now
            item["updated_at"] = now
            item["last_attempt_result"] = ""
        updated.append(item)
    return updated


def finalize_tracking_run(path: str | Path, run_id: str, logger: logging.Logger | None = None) -> None:
    records = load_tracking(path, logger=logger)
    write_tracking_records(finalize_run_records(records.values(), run_id), path)


def abort_tracking_run(path: str | Path, run_id: str, message: str = "", logger: logging.Logger | None = None) -> None:
    records = load_tracking(path, logger=logger)
    write_tracking_records(abort_run_records(records.values(), run_id, message=message), path)


def normalize_tracking_record(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    rpa_status = normalize_status(result.get("rpa_status") or result.get("status"), default=STATUS_PENDING)
    last_attempt_result = result.get("last_attempt_result") or ""
    if rpa_status != STATUS_DONE and last_attempt_result == ATTEMPT_SUCCESS:
        rpa_status = STATUS_DONE
        last_attempt_result = ""
    result["transaction_uid"] = str(result.get("transaction_uid", "") or "").strip()
    result["bank_code"] = result.get("bank_code") or result.get("bank") or ""
    result["source_file"] = result.get("source_file") or ""
    result["source_sheet"] = result.get("source_sheet") or ""
    result["source_row"] = result.get("source_row") or result.get("source_row_index") or result.get("original_row_index") or ""
    result["direction"] = result.get("direction") or result.get("flow") or ""
    result["rpa_status"] = rpa_status
    result["status"] = rpa_status
    result["rpa_message"] = result.get("rpa_message") or ""
    result["last_attempt_result"] = last_attempt_result
    result["created_at"] = result.get("created_at") or _now()
    result["updated_at"] = result.get("updated_at") or result["created_at"]
    completed_at = result.get("completed_at") or ""
    if not completed_at and rpa_status == STATUS_DONE:
        completed_at = result.get("rpa_finished_at") or result.get("updated_at") or _now()
    result["completed_at"] = completed_at
    result["bank"] = result.get("bank") or result["bank_code"]
    result["flow"] = result.get("flow") or result["direction"]
    result["source_row_index"] = result.get("source_row_index") or result["source_row"]
    for field in TRACKING_REQUIRED_FIELDS:
        result.setdefault(field, "")
    return result


def _iter_records(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
        return

    if isinstance(data, dict):
        if isinstance(data.get("transactions"), list):
            for item in data["transactions"]:
                if isinstance(item, dict):
                    yield item
            return
        for key, value in data.items():
            if isinstance(value, dict):
                record = dict(value)
                record.setdefault("transaction_uid", key)
                yield record


def _backup_invalid_json(path: Path, exc: json.JSONDecodeError, logger: logging.Logger | None) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.stem}.corrupt.{timestamp}{path.suffix}")
    try:
        shutil.copy2(path, backup_path)
        if logger:
            logger.warning("Invalid JSON in %s: %s. Backed up to %s", path, exc, backup_path)
    except OSError as backup_exc:
        if logger:
            logger.warning("Invalid JSON in %s: %s. Backup failed: %s", path, exc, backup_exc)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
