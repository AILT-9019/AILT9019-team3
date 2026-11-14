from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

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
    except UnicodeDecodeError as exc:
        raise StorageError(f"Invalid UTF-8 in {path}") from exc
    except OSError as exc:
        raise StorageError(f"Could not read storage file: {path}") from exc

    try:
        state = DbState.model_validate(payload)
    except ValidationError as exc:
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
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    payload = state.model_dump(mode="json")
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if backup_current and db_path.exists():
            shutil.copyfile(db_path, _backup_path())
        os.replace(tmp_path, db_path)
    except OSError as exc:
        raise StorageError(f"Could not save storage file: {db_path}") from exc


def ensure_storage() -> None:
    # 启动自检也可能与读写交错，须与原子写共用同一把锁。
    with _LOCK:
        _ensure_storage_unlocked()


def _ensure_storage_unlocked() -> None:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    _texts_dir().mkdir(parents=True, exist_ok=True)
    _originals_dir().mkdir(parents=True, exist_ok=True)

    tmp_path = _db_path().with_name(_db_path().name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    if not _db_path().exists():
        recovered = _read_state_from(_backup_path()) if _backup_path().exists() else DbState()
        _atomic_write_state(recovered, backup_current=False)
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
    prompt_version: str | None = None,
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
        if prompt_version is not None:
            record.extraction.prompt_version = prompt_version
        _atomic_write_state(state)


def claim_extractions(upload_ids: list[str]) -> list[str]:
    """原子占用待抽取记录，避免重复请求同时调度同一上传。"""
    with _LOCK:
        ensure_storage()
        state = _read_state_unlocked()
        unique_ids = list(dict.fromkeys(upload_ids))
        for upload_id in unique_ids:
            if upload_id not in state.uploads:
                raise StorageError(f"Upload not found: {upload_id}")
        claimed: list[str] = []
        for upload_id in unique_ids:
            record = state.uploads[upload_id]
            if record.extraction.status == ExtractionStatus.running:
                continue
            record.extraction.status = ExtractionStatus.running
            record.extraction.error = None
            claimed.append(upload_id)
        if claimed:
            _atomic_write_state(state)
        return claimed


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


def delete_task(task_id: str) -> bool:
    """删除一条抽取任务；上传原文和原文件保留，重复分组同步调整。"""
    with _LOCK:
        ensure_storage()
        state = _read_state_unlocked()
        if not any(task.id == task_id for task in state.tasks):
            return False
        state.tasks = [task for task in state.tasks if task.id != task_id]

        groups: dict[str, DuplicateGroup] = {}
        for primary, group in state.duplicate_groups.items():
            if task_id not in group.task_ids:
                groups[primary] = group
                continue
            remaining = [item for item in group.task_ids if item != task_id]
            if len(remaining) < 2:
                continue
            new_primary = primary if primary in remaining else remaining[0]
            groups[new_primary] = DuplicateGroup(
                task_ids=remaining,
                source=group.source,
            )
        state.duplicate_groups = groups
        _atomic_write_state(state)
        return True


def set_duplicate_groups(
    groups: dict[str, DuplicateGroup], *, expected_tasks: list[TaskRecord] | None = None
) -> bool:
    with _LOCK:
        ensure_storage()
        state = _read_state_unlocked()
        # LLM 调用在锁外；仅保存仍匹配当前任务快照的结果。
        if expected_tasks is not None and state.tasks != expected_tasks:
            return False
        state.duplicate_groups = groups
        _atomic_write_state(state)
        return True


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
