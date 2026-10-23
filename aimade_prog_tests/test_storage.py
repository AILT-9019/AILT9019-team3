from datetime import date

import pytest

from app import storage
from app.config import get_settings
from app.schemas import DateConfidence, ExtractionStatus, TaskRecord, TaskType
from app.storage import (
    create_upload,
    ensure_storage,
    get_text,
    read_state,
    replace_tasks,
    set_extraction,
    write_state,
)


def test_create_upload_and_replace_tasks():
    ensure_storage()
    upload_id, record = create_upload(
        "Assignment 1 is due on 24 October 2026.",
        "paste",
        course_hint="COMP3230",
    )

    assert upload_id == record.uploaded_at.strftime("%Y-%m-%d_%H%M%S")
    assert record.text_file == f"texts/{upload_id}.txt"
    assert get_text(upload_id) == "Assignment 1 is due on 24 October 2026."

    task = TaskRecord(
        id=f"{upload_id}_01",
        upload_id=upload_id,
        course_name="COMP3230",
        title="Assignment 1",
        description="Implement a simple shell.",
        task_type=TaskType.assignment,
        due_date=date(2026, 10, 24),
        date_confidence=DateConfidence.exact,
        source_quote="Assignment 1 is due on 24 October 2026.",
    )
    replace_tasks(upload_id, [task])
    set_extraction(upload_id, ExtractionStatus.succeeded, model="mock")

    state = read_state()
    assert len(state.tasks) == 1
    assert state.tasks[0].title == "Assignment 1"
    assert state.uploads[upload_id].extraction.status == ExtractionStatus.succeeded

    data_dir = get_settings().data_dir
    assert (data_dir / "db.json").exists()
    assert (data_dir / "db.json.bak").exists()


@pytest.mark.parametrize("damage", ["missing", "invalid-json", "invalid-utf8"])
def test_storage_recovers_backup_without_losing_upload(damage):
    upload_id, _ = create_upload("Keep this source.", "paste")
    expected = read_state()
    write_state(expected)
    path = get_settings().data_dir / "db.json"
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b'{"uploads":' if damage == "invalid-json" else b'\xff\xfe')
    assert read_state() == expected
    assert get_text(upload_id) == "Keep this source."


def test_failed_atomic_replace_preserves_current_database(monkeypatch):
    create_upload("Keep this source.", "paste")
    expected = read_state()
    path = get_settings().data_dir / "db.json"
    before = path.read_bytes()

    def fail_replace(source, destination):
        raise PermissionError("File is locked")

    monkeypatch.setattr(storage.os, "replace", fail_replace)
    with pytest.raises(storage.StorageError, match="Could not save"):
        write_state(expected)
    assert path.read_bytes() == before


def test_status_only_update_preserves_extraction_metadata():
    uid, _ = create_upload("Source.", "paste")
    set_extraction(uid, ExtractionStatus.succeeded, model="mock", prompt_version="v2")
    set_extraction(uid, ExtractionStatus.running)
    metadata = read_state().uploads[uid].extraction
    assert metadata.model == "mock"
    assert metadata.prompt_version == "v2"


def test_concurrent_claims_schedule_upload_once():
    from concurrent.futures import ThreadPoolExecutor

    uid, _ = create_upload("Source.", "paste")
    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(storage.claim_extractions, [[uid, uid], [uid]]))
    assert sum(len(ids) for ids in claims) == 1
    assert read_state().uploads[uid].extraction.status == ExtractionStatus.running


def test_storage_check_cannot_remove_an_active_write(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    create_upload("Source.", "paste")
    state = read_state()
    replacing = Event()
    release = Event()
    checking = Event()
    checked = Event()
    original_replace = storage.os.replace

    def paused_replace(source, destination):
        replacing.set()
        assert release.wait(3)
        original_replace(source, destination)

    def checker():
        checking.set()
        try:
            ensure_storage()
        finally:
            checked.set()

    monkeypatch.setattr(storage.os, "replace", paused_replace)
    with ThreadPoolExecutor(max_workers=2) as executor:
        writer = executor.submit(write_state, state)
        try:
            assert replacing.wait(3)
            check = executor.submit(checker)
            assert checking.wait(3)
            assert not checked.wait(0.1)
        finally:
            release.set()
        writer.result(timeout=3)
        check.result(timeout=3)
    assert read_state() == state
