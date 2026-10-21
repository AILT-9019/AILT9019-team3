from datetime import date

from app.schemas import DateConfidence, ExtractedTask, TaskType
from app.services.normalizer import coerce_payload, normalize_tasks


def make_task(**overrides) -> ExtractedTask:
    data = {
        "course_name": "COMP3230",
        "title": "Assignment 1",
        "task_type": TaskType.assignment,
        "due_date": date(2026, 10, 24),
        "date_confidence": DateConfidence.exact,
        "source_quote": "Due 24 October 2026",
    }
    data.update(overrides)
    return ExtractedTask(**data)


def test_exact_with_explicit_quote_stays_exact():
    result = normalize_tasks([make_task()], course_hint=None)
    assert result[0].date_confidence == DateConfidence.exact
    assert result[0].due_date == date(2026, 10, 24)


def test_exact_with_vague_quote_is_demoted():
    result = normalize_tasks([make_task(source_quote="Week 10")], course_hint=None)
    assert result[0].date_confidence == DateConfidence.unknown
    assert result[0].due_date is None


def test_range_is_preserved():
    task = make_task(
        due_date=None,
        due_range_start=date(2026, 10, 26),
        due_range_end=date(2026, 11, 1),
        date_confidence=DateConfidence.range,
        source_quote="Week 10",
    )
    result = normalize_tasks([task], course_hint=None)
    assert result[0].date_confidence == DateConfidence.range
    assert result[0].due_range_start == date(2026, 10, 26)


def test_out_of_semester_exact_is_demoted():
    task = make_task(due_date=date(2027, 3, 1), source_quote="Due 1 March 2027")
    result = normalize_tasks([task], course_hint=None)
    assert result[0].date_confidence == DateConfidence.unknown


def test_coerce_payload_dates_and_fallbacks():
    payload = {
        "tasks": [
            {
                "title": "Essay",
                "course_name": "",
                "task_type": "weird",
                "due_date": "5 November 2026",
                "date_confidence": "exact",
                "source_quote": "Due 5 November 2026",
            }
        ]
    }
    tasks = coerce_payload(payload, "HIST1001")
    assert tasks[0]["course_name"] == "HIST1001"
    assert tasks[0]["task_type"] == "other"
    assert tasks[0]["due_date"] == date(2026, 11, 5)
