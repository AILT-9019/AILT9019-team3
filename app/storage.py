from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from app.config import get_settings
from app.schemas import (
    SCHEMA_VERSION,
    DbState,
    DuplicateGroup,
    ExtractionStatus,
    SourceType,
    TaskRecord,
    UploadRecord,
)

_LOCK = threading.RLock()


class StorageError(RuntimeError):
    pass


def _db_path() -> Path:
    return get_settings().data_dir / "db.json"


def _backup_path() -> Path:
    return get_settings().data_dir / "db.json.bak"


def _texts_dir() -> Path:
    return get_settings().data_dir / "texts"


def _originals_dir() -> Path:
    return get_settings().data_dir / "originals"


def _read_state_from(path: Path) -> DbState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StorageError(f"Storage file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StorageError(f"Invalid JSON in {path}: {exc}") from exc

    try:
        state = DbState.model_validate(payload)
    except Exception as exc:
        raise StorageError(f"Invalid storage schema in {path}: {exc}") from exc

    if state.schema_version != SCHEMA_VERSION:
        raise StorageError(
            f"Unsupported schema_version {state.schema_version} in {path}; "
            f"expected {SCHEMA_VERSION}"
        )
    return state


def _read_state_unlocked() -> DbState:
    return _read_state_from(_db_path())


def _atomic_write_state(state: DbState, *, backup_current: bool = True) -> None:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    payload = state.model_dump(mode="json")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if backup_current and db_path.exists():
        shutil.copyfile(db_path, _backup_path())
    os.replace(tmp_path, db_path)


def ensure_storage() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    _texts_dir().mkdir(parents=True, exist_ok=True)
    _originals_dir().mkdir(parents=True, exist_ok=True)

    tmp_path = _db_path().with_name(_db_path().name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    if not _db_path().exists():
        _atomic_write_state(DbState(), backup_current=False)
        return

    try:
        _read_state_unlocked()
    except StorageError:
        if not _backup_path().exists():
            raise
        recovered = _read_state_from(_backup_path())
        _atomic_write_state(recovered, backup_current=False)


def read_state() -> DbState:
    with _LOCK:
        ensure_storage()
        return _read_state_unlocked()


def write_state(state: DbState) -> None:
    with _LOCK:
        ensure_storage()
        _atomic_write_state(state)


def _next_upload_id(state: DbState, now: datetime) -> str:
    base = now.strftime("%Y-%m-%d_%H%M%S")
    candidate = base
    suffix = 2
    while candidate in state.uploads or (_texts_dir() / f"{candidate}.txt").exists():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def create_upload(
    text: str,
    source_type: SourceType | str,
    *,
    original_filename: str | None = None,
    course_hint: str | None = None,
    original_bytes: bytes | None = None,
    original_ext: str | None = None,
) -> tuple[str, UploadRecord]:
    settings = get_settings()
    now = datetime.now(settings.timezone)

    with _LOCK:
        ensure_storage()
        state = _read_state_unlocked()
        upload_id = _next_upload_id(state, now)

        text_rel = f"texts/{upload_id}.txt"
        (_texts_dir() / f"{upload_id}.txt").write_text(text, encoding="utf-8")

        original_rel: str | None = None
        if original_bytes is not None and original_ext:
            ext = original_ext if original_ext.startswith(".") else f".{original_ext}"
            original_rel = f"originals/{upload_id}{ext.lower()}"
            (_originals_dir() / f"{upload_id}{ext.lower()}").write_bytes(original_bytes)

        record = UploadRecord(
            uploaded_at=now,
            source_type=SourceType(source_type),
            original_filename=original_filename,
            text_file=text_rel,
            original_file=original_rel,
            course_hint=(course_hint.strip() or None) if course_hint else None,
        )
        state.uploads[upload_id] = record
        _atomic_write_state(state)
        return upload_id, record


def get_upload(upload_id: str) -> UploadRecord | None:
    return read_state().uploads.get(upload_id)


def get_text(upload_id: str) -> str:
    state = read_state()
    record = state.uploads.get(upload_id)
    if record is None:
        raise StorageError(f"Upload not found: {upload_id}")
    path = get_settings().data_dir / record.text_file
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StorageError(f"Text file missing for upload {upload_id}: {path}") from exc


def set_extraction(
    upload_id: str,
    status: ExtractionStatus,
    *,
    error: str | None = None,
    model: str | None = None,
    prompt_version: str = "v1",
) -> None:
    with _LOCK:
        ensure_storage()
        state = _read_state_unlocked()
        record = state.uploads.get(upload_id)
        if record is None:
            raise StorageError(f"Upload not found: {upload_id}")
        record.extraction.status = status
        record.extraction.error = error
        if model is not None:
            record.extraction.model = model
        record.extraction.prompt_version = prompt_version
        _atomic_write_state(state)


def replace_tasks(upload_id: str, tasks: list[TaskRecord]) -> None:
    for task in tasks:
        if task.upload_id != upload_id:
            raise StorageError(
                f"Task {task.id} belongs to {task.upload_id}, not {upload_id}"
            )
    with _LOCK:
        ensure_storage()
        state = _read_state_unlocked()
        if upload_id not in state.uploads:
            raise StorageError(f"Upload not found: {upload_id}")
        state.tasks = [task for task in state.tasks if task.upload_id != upload_id]
        state.tasks.extend(tasks)
        state.duplicate_groups = {}
        _atomic_write_state(state)


def set_duplicate_groups(groups: dict[str, DuplicateGroup]) -> None:
    with _LOCK:
        ensure_storage()
        state = _read_state_unlocked()
        state.duplicate_groups = groups
        _atomic_write_state(state)


def get_task(task_id: str) -> TaskRecord | None:
    for task in read_state().tasks:
        if task.id == task_id:
            return task
    return None


def reset_interrupted_extractions() -> None:
    with _LOCK:
        ensure_storage()
        state = _read_state_unlocked()
        changed = False
        for record in state.uploads.values():
            if record.extraction.status == ExtractionStatus.running:
                record.extraction.status = ExtractionStatus.failed
                record.extraction.error = "Interrupted by app restart"
                changed = True
        if changed:
            _atomic_write_state(state)
