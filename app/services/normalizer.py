from __future__ import annotations

import re
from datetime import date, timedelta

from dateutil import parser as date_parser

from app.config import get_settings
from app.schemas import DateConfidence, ExtractedTask, Subtask, TaskType

MONTHS = (
    "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|"
    "january|february|march|april|june|july|august|september|october|november|december"
)
_EXPLICIT_DATE_PATTERNS = (
    r"\d{4}-\d{2}-\d{2}",
    r"\d{4}/\d{1,2}/\d{1,2}",
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\b",
    rf"\b(?:{MONTHS})\s+\d{{1,2}}\b",
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b",
)


def coerce_payload(payload: object, course_hint: str | None) -> list[dict]:
    if isinstance(payload, list):
        payload = {"tasks": payload}
    if not isinstance(payload, dict):
        raise TypeError("LLM output must be a JSON object or list")
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list):
        raise TypeError("LLM output must contain a tasks array")

    tasks: list[dict] = []
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            continue
        task = _coerce_task(raw, course_hint)
        if task is not None:
            tasks.append(task)
    return tasks


def normalize_tasks(
    tasks: list[ExtractedTask],
    *,
    course_hint: str | None,
) -> list[ExtractedTask]:
    settings = get_settings()
    min_date = settings.semester_start - timedelta(days=30)
    max_date = settings.semester_end + timedelta(days=30)
    normalized: list[ExtractedTask] = []

    for task in tasks:
        data = task.model_dump()
        course_name = (task.course_name or "").strip() or course_hint or "Unknown course"
        data["course_name"] = course_name[:120]

        if task.date_confidence == DateConfidence.exact:
            if task.due_date is None or not (min_date <= task.due_date <= max_date):
                data.update(
                    {
                        "date_confidence": DateConfidence.unknown,
                        "due_date": None,
                        "due_range_start": None,
                        "due_range_end": None,
                        "ambiguity_reason": "Deadline is outside the semester window.",
                    }
                )
            elif _looks_ambiguous(task.source_quote):
                data.update(
                    {
                        "date_confidence": DateConfidence.unknown,
                        "due_date": None,
                        "due_range_start": None,
                        "due_range_end": None,
                        "ambiguity_reason": (
                            "The source quote does not contain an explicit date; "
                            "no specific date is assumed."
                        ),
                    }
                )
        elif task.date_confidence == DateConfidence.range:
            if (
                task.due_range_start is None
                or task.due_range_end is None
                or task.due_range_start < min_date
                or task.due_range_end > max_date
            ):
                data.update(
                    {
                        "date_confidence": DateConfidence.unknown,
                        "due_date": None,
                        "due_range_start": None,
                        "due_range_end": None,
                        "ambiguity_reason": "Deadline range is outside the semester window.",
                    }
                )
            elif (task.due_range_end - task.due_range_start).days > 21:
                data["ambiguity_reason"] = (
                    (task.ambiguity_reason or "Estimated deadline.")
                    + " The estimated window is wider than three weeks."
                )

        data["subtasks"] = [
            item.model_dump() for item in _filter_subtasks(task.subtasks)
        ]
        normalized.append(ExtractedTask.model_validate(data))

    return _dedupe(normalized)


_SUBTASK_TITLE_RE = re.compile(
    r"(?:^|[-–—:|]\s*|\b)(?:task|part|question|q|step|requirement|exercise)\s*(?:[A-Za-z]|[0-9]+)\b",
    flags=re.IGNORECASE,
)
_SUBTASK_KEY_RE = re.compile(
    r"\b(?:task|part|question|q|step|requirement|exercise)\s*([A-Za-z]|[0-9]+)\b",
    flags=re.IGNORECASE,
)
_NUMBERED_TITLE_RE = re.compile(r"^\s*(?:\(?[A-Za-z0-9]\)|[0-9]+[.)])\s+")


def merge_subtasks(tasks: list[ExtractedTask]) -> list[ExtractedTask]:
    """Attach undated part/same-parent tasks to a single dated parent assignment."""
    parents = [
        task
        for task in tasks
        if task.date_confidence != DateConfidence.unknown
        and not _looks_like_subtask_title(task.title)
    ]
    if len(parents) != 1:
        return tasks

    parent = parents[0]
    children = [
        task
        for task in tasks
        if task is not parent
        and (
            (
                task.date_confidence == DateConfidence.unknown
                and (
                    _looks_like_subtask_title(task.title)
                    or _title_matches_parent(task.title, parent.title)
                )
            )
            or (
                _looks_like_subtask_title(task.title)
                and _same_deadline(task, parent)
            )
        )
    ]

    seen: set[str] = set()
    subtasks: list[Subtask] = []

    def add_subtask(item: Subtask) -> None:
        key = _subtask_key(item.label)
        if not key or key in seen:
            return
        seen.add(key)
        subtasks.append(item)

    for item in _filter_subtasks(parent.subtasks):
        add_subtask(item)

    for child in children:
        if _looks_like_subtask_title(child.title):
            add_subtask(
                Subtask(
                    label=child.title.strip()[:120],
                    description=(child.description or child.source_quote)[:1000],
                )
            )
        else:
            for item in _filter_subtasks(child.subtasks):
                add_subtask(item)

    data = parent.model_dump()
    data["subtasks"] = [item.model_dump() for item in subtasks]
    merged_parent = ExtractedTask.model_validate(data)
    child_ids = {id(child) for child in children}
    return [merged_parent if task is parent else task for task in tasks if id(task) not in child_ids]


def _filter_subtasks(subtasks: list[Subtask]) -> list[Subtask]:
    """If the model returned Task A/B/C plus sub-steps, keep the top-level parts."""
    if any(_looks_like_subtask_title(item.label) for item in subtasks):
        subtasks = [item for item in subtasks if _looks_like_subtask_title(item.label)]
    unique: dict[str, Subtask] = {}
    for item in subtasks:
        unique.setdefault(_subtask_key(item.label), item)
    return list(unique.values())


def _looks_like_subtask_title(title: str) -> bool:
    return bool(_SUBTASK_TITLE_RE.search(title) or _NUMBERED_TITLE_RE.match(title))


def _subtask_key(label: str) -> str:
    match = _SUBTASK_KEY_RE.search(label)
    if match:
        return f"part:{match.group(1).casefold()}"
    return _normalize_label(label)


def _title_matches_parent(title: str, parent_title: str) -> bool:
    child_tokens = set(_title_tokens(title))
    parent_tokens = set(_title_tokens(parent_title))
    common = child_tokens & parent_tokens
    type_words = {"assignment", "exam", "quiz", "project"}
    return len(common) >= 3 and bool(common & type_words)


def _title_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _same_deadline(left: ExtractedTask, right: ExtractedTask) -> bool:
    if (
        left.date_confidence == DateConfidence.exact
        and right.date_confidence == DateConfidence.exact
    ):
        return left.due_date == right.due_date
    if (
        left.date_confidence == DateConfidence.range
        and right.date_confidence == DateConfidence.range
    ):
        return (
            left.due_range_start == right.due_range_start
            and left.due_range_end == right.due_range_end
        )
    return False


def _normalize_label(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def _coerce_task(raw: dict, course_hint: str | None) -> dict | None:
    title = _text(raw.get("title"))[:200]
    if not title:
        return None

    quote = _text(raw.get("source_quote"))[:1000] or title
    course_name = _text(raw.get("course_name"))[:120] or (course_hint or "Unknown course")
    description = _text(raw.get("description"))[:2000] or None

    task_type_raw = _text(raw.get("task_type")).lower()
    valid_types = {item.value for item in TaskType}
    task_type = task_type_raw if task_type_raw in valid_types else TaskType.other.value

    due_date = _coerce_date(raw.get("due_date"))
    range_start = _coerce_date(raw.get("due_range_start"))
    range_end = _coerce_date(raw.get("due_range_end"))
    confidence = _text(raw.get("date_confidence")).lower()

    if confidence not in {item.value for item in DateConfidence}:
        if due_date is not None:
            confidence = DateConfidence.exact.value
        elif range_start is not None and range_end is not None:
            confidence = DateConfidence.range.value
        else:
            confidence = DateConfidence.unknown.value

    if confidence == DateConfidence.exact.value:
        if due_date is None:
            confidence = (
                DateConfidence.range.value
                if range_start is not None and range_end is not None
                else DateConfidence.unknown.value
            )
        else:
            range_start = range_end = None
    if confidence == DateConfidence.range.value:
        if range_start is None or range_end is None or range_start > range_end:
            confidence = DateConfidence.unknown.value
        else:
            due_date = None
    if confidence == DateConfidence.unknown.value:
        due_date = range_start = range_end = None

    return {
        "course_name": course_name,
        "title": title,
        "description": description,
        "task_type": task_type,
        "due_date": due_date,
        "due_range_start": range_start,
        "due_range_end": range_end,
        "date_confidence": confidence,
        "ambiguity_reason": _text(raw.get("ambiguity_reason"))[:500] or None,
        "source_quote": quote,
        "subtasks": _coerce_subtasks(raw.get("subtasks")),
    }


def _coerce_subtasks(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    result: list[dict] = []
    for item in value[:20]:
        if isinstance(item, dict):
            label = _text(item.get("label") or item.get("title") or item.get("name"))[:120]
            description = _text(item.get("description") or item.get("summary"))[:1000] or None
        else:
            label = _text(item)[:120]
            description = None
        if label:
            result.append({"label": label, "description": description})
    return result


def _coerce_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return date_parser.parse(text, fuzzy=False).date()
    except (ValueError, OverflowError, TypeError):
        return None


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _looks_ambiguous(quote: str) -> bool:
    lower = quote.lower()
    for pattern in _EXPLICIT_DATE_PATTERNS:
        if re.search(pattern, lower, flags=re.IGNORECASE):
            return False
    return True


def _dedupe(tasks: list[ExtractedTask]) -> list[ExtractedTask]:
    seen: dict[tuple[str, str, str], ExtractedTask] = {}
    for task in tasks:
        key = (
            task.course_name.lower(),
            _normalize_title(task.title),
            _date_key(task),
        )
        existing = seen.get(key)
        if existing is None or len(task.description or "") > len(existing.description or ""):
            seen[key] = task
    return list(seen.values())


def _normalize_title(title: str) -> str:
    # 非拉丁标题不能被清空，否则同日的不同任务会共用去重键。
    return re.sub(r"[\W_]+", " ", title.lower()).strip()


def _date_key(task: ExtractedTask) -> str:
    if task.due_date is not None:
        return task.due_date.isoformat()
    if task.due_range_start is not None and task.due_range_end is not None:
        return f"{task.due_range_start.isoformat()}..{task.due_range_end.isoformat()}"
    return "unknown"
