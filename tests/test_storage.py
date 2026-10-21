from datetime import date

from app.config import get_settings
from app.schemas import DateConfidence, ExtractionStatus, TaskRecord, TaskType
from app.storage import (
    create_upload,
    ensure_storage,
    get_text,
    read_state,
    replace_tasks,
    set_extraction,
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
