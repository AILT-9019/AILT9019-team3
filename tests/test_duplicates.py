from datetime import date

from app.schemas import DateConfidence, DuplicateGroup, TaskRecord, TaskType
from app.services import deduplicator
from app.services.deduplicator import build_duplicate_groups
from app.storage import (
    create_upload,
    ensure_storage,
    read_state,
    replace_tasks,
    set_duplicate_groups,
)


def make_task(
    task_id: str,
    upload_id: str,
    *,
    title: str = "Assignment 1",
    description: str = "Implement a simple shell.",
    due: date = date(2026, 10, 24),
) -> TaskRecord:
    return TaskRecord(
        id=task_id,
        upload_id=upload_id,
        course_name="COMP3230",
        title=title,
        description=description,
        task_type=TaskType.assignment,
        due_date=due,
        date_confidence=DateConfidence.exact,
        source_quote=f"{title} is due on {due.isoformat()}.",
    )


def test_exact_duplicates_are_grouped_without_ai():
    tasks = [
        make_task("t1", "u1"),
        make_task("t2", "u2"),
    ]
    groups, warning = build_duplicate_groups(tasks)
    assert warning is None
    assert len(groups) == 1
    group = next(iter(groups.values()))
    assert group.source == "exact"
    assert set(group.task_ids) == {"t1", "t2"}


def test_distinct_content_is_not_grouped():
    tasks = [
        make_task("t1", "u1"),
        make_task("t2", "u2", description="Write a different essay.", due=date(2026, 11, 1)),
    ]
    groups, _ = build_duplicate_groups(tasks)
    assert groups == {}


def test_duplicate_groups_are_persisted_separately():
    ensure_storage()
    upload_a, _ = create_upload("Assignment 1 is due on 2026-10-24.", "paste")
    upload_b, _ = create_upload("Assignment 1 is due on 2026-10-24.", "paste")
    task_a = make_task(f"{upload_a}_01", upload_a)
    task_b = make_task(f"{upload_b}_01", upload_b)
    replace_tasks(upload_a, [task_a])
    replace_tasks(upload_b, [task_b])

    group = DuplicateGroup(task_ids=[task_a.id, task_b.id], source="exact")
    set_duplicate_groups({task_a.id: group})

    state = read_state()
    assert len(state.tasks) == 2
    assert task_a.id in state.duplicate_groups
    assert state.duplicate_groups[task_a.id].task_ids == [task_a.id, task_b.id]


def test_live_candidates_allow_title_and_course_name_variations(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_MODE", "live")
    deduplicator._CACHE.clear()
    tasks = [make_task("t1", "u1"), make_task("t2", "u2", title="Shell programming project")]
    tasks[1].course_name = "COMP3230 Operating Systems"
    prompts = []

    def respond(system, user):
        prompts.append(user)
        return '{"duplicate_groups": [["t1", "t2"]]}'

    monkeypatch.setattr(deduplicator, "chat_completion", respond)
    groups, warning = build_duplicate_groups(tasks)
    assert warning is None
    assert len(groups) == 1
    assert "Shell programming project" in prompts[0]


def test_fallback_does_not_merge_different_titles_or_courses():
    tasks = [make_task("t1", "u1"), make_task("t2", "u2", title="Assignment 2")]
    assert build_duplicate_groups(tasks)[0] == {}
    tasks[1].title = tasks[0].title
    tasks[1].course_name = "COMP3234"
    assert build_duplicate_groups(tasks)[0] == {}


def test_failed_ai_grouping_is_not_cached(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_MODE", "live")
    deduplicator._CACHE.clear()
    calls = []

    def respond(system, user):
        calls.append(user)
        if len(calls) == 1:
            raise deduplicator.LLMError("offline")
        return '{"duplicate_groups": [["t1", "t2"]]}'

    monkeypatch.setattr(deduplicator, "chat_completion", respond)
    tasks = [make_task("t1", "u1"), make_task("t2", "u2")]
    assert build_duplicate_groups(tasks)[1] is not None
    assert build_duplicate_groups(tasks)[1] is None
    assert len(calls) == 2
