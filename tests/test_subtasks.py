from datetime import date

from app.schemas import DateConfidence, ExtractedTask, Subtask, TaskType
from app.services.normalizer import coerce_payload, merge_subtasks, normalize_tasks


def task(
    title: str,
    *,
    due: date | None,
    description: str | None = None,
) -> ExtractedTask:
    return ExtractedTask(
        course_name="COMP3230",
        title=title,
        description=description,
        task_type=TaskType.assignment,
        due_date=due,
        date_confidence=DateConfidence.exact if due else DateConfidence.unknown,
        source_quote=f"{title} source quote.",
    )


def test_parts_are_merged_into_single_parent():
    parent = task(
        "Programming Assignment 1 - Course Selection Challenge",
        due=date(2026, 11, 4),
        description="Solve the course selection challenge.",
    )
    parts = [
        task("Task A: Lowest total difficulty", due=None),
        task("Task B: Count unreachable courses", due=None),
        task("Task C: Ordering number", due=None),
    ]

    merged = merge_subtasks([parent, *parts])

    assert len(merged) == 1
    assert merged[0].title == parent.title
    assert [item.label for item in merged[0].subtasks] == [
        "Task A: Lowest total difficulty",
        "Task B: Count unreachable courses",
        "Task C: Ordering number",
    ]


def test_dated_part_is_not_merged():
    parent = task("Programming Assignment 1", due=date(2026, 11, 4))
    part = task("Task A: Separate submission", due=date(2026, 11, 10))

    merged = merge_subtasks([parent, part])

    assert len(merged) == 2


def test_multiple_parents_are_left_alone():
    parent_a = task("Assignment 1", due=date(2026, 10, 24))
    parent_b = task("Assignment 2", due=date(2026, 11, 7))
    part = task("Task A: Extra", due=None)

    merged = merge_subtasks([parent_a, parent_b, part])

    assert len(merged) == 3


def test_same_parent_title_merges_and_dedupes_subtasks():
    parent = ExtractedTask(
        course_name="COMP3230",
        title="Programming Assignment 1 - Course Selection Challenge",
        task_type=TaskType.assignment,
        due_date=date(2026, 11, 4),
        date_confidence=DateConfidence.exact,
        source_quote="Due Date: Nov 4, 2026",
        subtasks=[
            Subtask(label="Task A", description="First part."),
            Subtask(label="Task B", description="Second part."),
            Subtask(label="Task C", description="Third part."),
        ],
    )
    child = ExtractedTask(
        course_name="COMP3230",
        title="Programming Assignment 1",
        task_type=TaskType.assignment,
        date_confidence=DateConfidence.unknown,
        source_quote="Programming Assignment 1",
        subtasks=[
            Subtask(label="Task A [40%]", description="First part duplicate."),
            Subtask(label="Task B [30%]", description="Second part duplicate."),
        ],
    )

    merged = merge_subtasks([parent, child])

    assert len(merged) == 1
    assert [item.label for item in merged[0].subtasks] == ["Task A", "Task B", "Task C"]


def test_normalize_keeps_only_named_parts_as_subtasks():
    parent = ExtractedTask(
        course_name="COMP2119",
        title="Programming Assignment 1 - Course Selection Challenge",
        task_type=TaskType.assignment,
        due_date=date(2026, 11, 4),
        date_confidence=DateConfidence.exact,
        source_quote="Due Date: Nov 4, 2026 7:00pm",
        subtasks=[
            Subtask(label="Task A", description="First part."),
            Subtask(label="Task B", description="Second part."),
            Subtask(label="Task C", description="Third part."),
            Subtask(label="Self Testing", description="Run the samples."),
            Subtask(label="Implementation", description="Write the program."),
            Subtask(label="Algorithm complexity", description="Use O(n log n)."),
            Subtask(label="Input constraints", description="Read n and m."),
        ],
    )

    normalized = normalize_tasks([parent], course_hint=None)

    assert [item.label for item in normalized[0].subtasks] == ["Task A", "Task B", "Task C"]


def test_coerce_payload_keeps_subtasks():
    payload = {
        "tasks": [
            {
                "course_name": "COMP3230",
                "title": "Programming Assignment 1",
                "task_type": "assignment",
                "due_date": "2026-11-04",
                "date_confidence": "exact",
                "source_quote": "Due Date: Nov 4, 2026",
                "subtasks": [
                    {"label": "Task A", "description": "First part."},
                    {"label": "Task B"},
                ],
            }
        ]
    }

    tasks = coerce_payload(payload, "COMP3230")

    assert len(tasks[0]["subtasks"]) == 2
    assert tasks[0]["subtasks"][0]["label"] == "Task A"
