"""Persistent task registry shared by the API and the Celery worker.

The Celery result backend stores task state, but it cannot list tasks. The UI
needs a durable list with progress, filenames, and timestamps, so every task is
also written as a small JSON document under ``storage/tasks``. Writes are
atomic and safe across the two local processes.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.config import settings

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"PENDING", "STARTED", "PROGRESS"}
TERMINAL_STATUSES = {"SUCCESS", "FAILURE", "REVOKED"}
HISTORY_LIMIT = 200
PRUNE_INTERVAL_SECONDS = 300.0
MAX_FILENAME_LENGTH = 200

_last_prune = 0.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_timestamp(value: datetime | None = None) -> str:
    moment = utc_now() if value is None else value.astimezone(timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_task_id(task_id: str) -> str:
    return str(UUID(str(task_id)))


def tasks_dir() -> Path:
    return settings.tasks_dir


def task_path(task_id: str) -> Path:
    return tasks_dir() / f"{normalize_task_id(task_id)}.json"


def clean_filename(filename: str | None, task_id: str) -> str:
    """Keep only a display name; never trust a client path for storage."""
    name = str(filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        name = f"{task_id}.mp4"
    return name[:MAX_FILENAME_LENGTH]


def _write(record: dict) -> None:
    directory = tasks_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = task_path(record["task_id"])
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_path(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    task_id = payload.get("task_id")
    if not isinstance(task_id, str):
        return None
    try:
        normalize_task_id(task_id)
    except ValueError:
        return None
    return payload


def get_task(task_id: str) -> dict | None:
    try:
        path = task_path(task_id)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return _read_path(path)


def create_task(task_id: str, filename: str | None, size_bytes: int) -> dict:
    identifier = normalize_task_id(task_id)
    now = iso_timestamp()
    record = {
        "task_id": identifier,
        "filename": clean_filename(filename, identifier),
        "size_bytes": max(0, int(size_bytes)),
        "created_at": now,
        "updated_at": now,
        "status": "PENDING",
        "progress": 0,
        "stage": "queued",
        "download_url": None,
        "error": None,
    }
    _write(record)
    return record


def update_task(task_id: str, **changes: object) -> dict | None:
    """Merge supported fields into an existing record, creating it if needed."""
    try:
        identifier = normalize_task_id(task_id)
    except ValueError:
        return None
    record = get_task(identifier)
    if record is None:
        record = create_task(identifier, None, 0)
    allowed = {
        "filename",
        "size_bytes",
        "status",
        "progress",
        "stage",
        "download_url",
        "error",
    }
    for key, value in changes.items():
        if key not in allowed:
            continue
        if key == "filename":
            value = clean_filename(str(value), identifier)
        elif key == "progress":
            value = max(0, min(100, int(value)))
        elif key == "size_bytes":
            value = max(0, int(value))
        record[key] = value
    record["updated_at"] = iso_timestamp()
    try:
        _write(record)
    except OSError:
        logger.warning("Could not persist task metadata for %s", identifier, exc_info=True)
        return None
    return record


def delete_task(task_id: str) -> None:
    try:
        task_path(task_id).unlink(missing_ok=True)
    except (OSError, ValueError):
        pass


def all_tasks() -> list[dict]:
    directory = tasks_dir()
    try:
        paths = list(directory.glob("*.json"))
    except OSError:
        return []
    tasks = [record for path in paths if (record := _read_path(path)) is not None]
    return tasks


def _timestamp(record: dict) -> float:
    value = record.get("updated_at") or record.get("created_at")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _is_active(record: dict) -> bool:
    return record.get("status") in ACTIVE_STATUSES


def sort_tasks(tasks: list[dict]) -> list[dict]:
    """Queue order for active tasks, newest first for finished work."""
    active = sorted(
        (task for task in tasks if _is_active(task)),
        key=lambda task: (_timestamp(task), task.get("task_id", "")),
    )
    terminal = sorted(
        (task for task in tasks if not _is_active(task)),
        key=lambda task: (_timestamp(task), task.get("task_id", "")),
        reverse=True,
    )
    return [*active, *terminal]


def list_tasks(limit: int = 50) -> list[dict]:
    return sort_tasks(all_tasks())[: max(1, int(limit))]


def snapshot() -> dict:
    maybe_prune()
    tasks = list_tasks(limit=HISTORY_LIMIT)
    return {"tasks": tasks, "active": sum(1 for task in tasks if _is_active(task))}


def _has_local_artifacts(record: dict) -> bool:
    identifier = record["task_id"]
    return any(
        path.exists()
        for path in (
            settings.uploads_dir / f"{identifier}.mp4",
            settings.temp_dir / identifier,
            settings.outputs_dir / f"{identifier}.mp4",
        )
    )


def prune_tasks(
    max_age_seconds: float | None = None,
    history_limit: int = HISTORY_LIMIT,
) -> None:
    """Remove expired and orphaned metadata without touching result files."""
    max_age = settings.result_expires if max_age_seconds is None else max_age_seconds
    cutoff = time.time() - max_age
    kept_terminal: list[dict] = []
    for record in all_tasks():
        identifier = record["task_id"]
        age = _timestamp(record)
        if _is_active(record):
            # A crashed worker leaves an active record behind. Keep it while the
            # upload or checkpoints still exist, otherwise drop it after expiry.
            if age >= cutoff or _has_local_artifacts(record):
                continue
            delete_task(identifier)
            continue
        output_exists = (
            record.get("status") == "SUCCESS"
            and (settings.outputs_dir / f"{identifier}.mp4").is_file()
        )
        if output_exists or age >= cutoff:
            kept_terminal.append(record)
        else:
            delete_task(identifier)
    kept_terminal.sort(key=_timestamp, reverse=True)
    for record in kept_terminal[history_limit:]:
        delete_task(record["task_id"])


def maybe_prune() -> None:
    global _last_prune
    now = time.monotonic()
    if now - _last_prune < PRUNE_INTERVAL_SECONDS:
        return
    _last_prune = now
    try:
        prune_tasks()
    except OSError:
        logger.warning("Could not prune task metadata", exc_info=True)
