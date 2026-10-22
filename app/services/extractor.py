from __future__ import annotations

import json
import re
from datetime import date, datetime

from dateutil import parser as date_parser
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import (
    DateConfidence,
    ExtractedTask,
    ExtractionResponse,
    ExtractionStatus,
    TaskRecord,
    TaskType,
)
from app.services import llm_client, prompts
from app.services.deduplicator import build_duplicate_groups
from app.services.normalizer import (
    MONTHS,
    coerce_payload,
    merge_subtasks,
    normalize_tasks,
)
from app.storage import (
    get_text,
    get_upload,
    read_state,
    replace_tasks,
    set_duplicate_groups,
    set_extraction,
)

# 常见作业说明尽量整体抽取，较长文档仍传递页眉和已有任务。
CHUNK_SIZE = 16000
MAX_CHUNKS = 30

_DATE_PATTERNS = (
    r"\b\d{4}-\d{2}-\d{2}\b",
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\s+\d{{4}}\b",
    rf"\b(?:{MONTHS})\s+\d{{1,2}},?\s+\d{{4}}\b",
    r"\b\d{1,2}/\d{1,2}/\d{4}\b",
)


class ExtractionError(RuntimeError):
    pass


def extract_upload(upload_id: str) -> None:
    upload = get_upload(upload_id)
    if upload is None:
        return

    settings = get_settings()
    model_name = "mock" if settings.extractor_mode == "mock" else settings.llm_model
    set_extraction(
        upload_id,
        ExtractionStatus.running,
        model=model_name,
        prompt_version=settings.prompt_version,
    )

    try:
        text = get_text(upload_id)
        if not text.strip():
            raise ExtractionError("No text to extract.")

        if settings.extractor_mode == "mock":
            extracted = _extract_mock(text, upload.course_hint)
        elif settings.extractor_mode == "live":
            extracted = _extract_live(text, upload)
        else:
            raise ExtractionError(f"Unknown EXTRACTOR_MODE: {settings.extractor_mode}")

        normalized = merge_subtasks(normalize_tasks(extracted, course_hint=upload.course_hint))
        records = [
            TaskRecord(
                id=f"{upload_id}_{index:02d}",
                upload_id=upload_id,
                **task.model_dump(),
            )
            for index, task in enumerate(normalized, start=1)
        ]
        replace_tasks(upload_id, records)
        try:
            groups, _ = build_duplicate_groups(read_state().tasks)
            set_duplicate_groups(groups)
        except Exception:  # noqa: BLE001 - display-only grouping must not fail extraction
            set_duplicate_groups({})
        set_extraction(
            upload_id,
            ExtractionStatus.succeeded,
            model=model_name,
            prompt_version=settings.prompt_version,
        )
    except Exception as exc:  # noqa: BLE001 - boundary: any extraction failure must be surfaced
        set_extraction(
            upload_id,
            ExtractionStatus.failed,
            error=str(exc),
            model=model_name,
            prompt_version=settings.prompt_version,
        )


def _extract_live(text: str, upload) -> list[ExtractedTask]:
    settings = get_settings()
    chunks = _chunk_text(text)
    today = datetime.now(settings.timezone).date().isoformat()
    tasks: list[ExtractedTask] = []

    for index, chunk in enumerate(chunks, start=1):
        user_prompt = prompts.build_user_prompt(
            document_title=upload.original_filename or "Untitled document",
            course_hint=upload.course_hint,
            uploaded_at=upload.uploaded_at.isoformat(),
            today=today,
            semester_start=settings.semester_start.isoformat(),
            semester_end=settings.semester_end.isoformat(),
            timezone=str(settings.timezone),
            chunk_index=index,
            chunk_count=len(chunks),
            chunk_text=chunk,
            document_header=text[:2000],
            known_tasks=[task.model_dump(mode="json") for task in tasks],
        )
        for task in _extract_chunk(user_prompt, upload.course_hint):
            _merge_continuation(tasks, task)
    return tasks


def _merge_continuation(tasks: list[ExtractedTask], incoming: ExtractedTask) -> None:
    """合并同名任务的续段；不同明确截止日期的任务仍然独立保留。"""
    for index, existing in enumerate(tasks):
        if (
            existing.course_name.casefold() != incoming.course_name.casefold()
            or existing.title.casefold() != incoming.title.casefold()
        ):
            continue
        existing_dates = (existing.due_date, existing.due_range_start, existing.due_range_end)
        incoming_dates = (incoming.due_date, incoming.due_range_start, incoming.due_range_end)
        if (
            existing.date_confidence != DateConfidence.unknown
            and incoming.date_confidence != DateConfidence.unknown
            and existing_dates != incoming_dates
        ):
            continue
        preferred = incoming if incoming.date_confidence != DateConfidence.unknown else existing
        data = preferred.model_dump()
        data["description"] = max(
            (existing.description or "", incoming.description or ""), key=len
        ) or None
        data["subtasks"] = [
            item.model_dump() for item in existing.subtasks + incoming.subtasks
        ]
        tasks[index] = ExtractedTask.model_validate(data)
        return
    tasks.append(incoming)


def _extract_chunk(user_prompt: str, course_hint: str | None) -> list[ExtractedTask]:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            content = llm_client.chat_completion(
                prompts.SYSTEM_PROMPT,
                user_prompt,
                repair=attempt == 1,
            )
            payload = _parse_json_content(content)
            raw_tasks = coerce_payload(payload, course_hint)
            response = ExtractionResponse.model_validate({"tasks": raw_tasks})
            return response.tasks
        except (ValueError, TypeError, ValidationError) as exc:
            last_error = exc
    raise ExtractionError(f"LLM returned invalid JSON: {last_error}")


def _parse_json_content(content: str) -> object:
    text = content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(text[start : end + 1])


def _chunk_text(text: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    length = 0

    for line in text.splitlines():
        if len(line) > max_chars:
            if current:
                chunks.append("\n".join(current))
                current = []
                length = 0
            for start in range(0, len(line), max_chars):
                chunks.append(line[start : start + max_chars])
            continue

        if current and length + len(line) + 1 > max_chars:
            chunks.append("\n".join(current))
            current = []
            length = 0

        current.append(line)
        length += len(line) + 1

    if current:
        chunks.append("\n".join(current))

    result = [chunk.strip() for chunk in chunks if chunk.strip()]
    if len(result) > MAX_CHUNKS:
        raise ExtractionError(
            f"Document is too long to extract in {MAX_CHUNKS} chunks; please split it."
        )
    return result


def _extract_mock(text: str, course_hint: str | None) -> list[ExtractedTask]:
    stripped = text.strip()
    if not stripped:
        raise ExtractionError("No text to extract.")

    title = "Mock task"
    for line in stripped.splitlines():
        candidate = line.strip()
        if candidate and not candidate.startswith("[["):
            title = candidate[:200]
            break

    due_date = _find_date(stripped)
    source_quote = _find_date_line(stripped, due_date) or stripped[:300]
    course_name = (course_hint or "TEST101").strip() or "TEST101"

    if due_date is not None:
        return [
            ExtractedTask(
                course_name=course_name,
                title=title,
                description=stripped[:300],
                task_type=TaskType.assignment,
                due_date=due_date,
                date_confidence=DateConfidence.exact,
                source_quote=source_quote[:1000],
            )
        ]

    return [
        ExtractedTask(
            course_name=course_name,
            title=title,
            description=stripped[:300],
            task_type=TaskType.assignment,
            date_confidence=DateConfidence.unknown,
            ambiguity_reason="No explicit deadline found by the mock extractor.",
            source_quote=source_quote[:1000],
        )
    ]


def _find_date(text: str) -> date | None:
    for pattern in _DATE_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            return date_parser.parse(match.group(0), fuzzy=False).date()
        except (ValueError, OverflowError, TypeError):
            continue
    return None


def _find_date_line(text: str, due_date: date | None) -> str | None:
    if due_date is None:
        return None
    for line in text.splitlines():
        for pattern in _DATE_PATTERNS:
            if re.search(pattern, line, flags=re.IGNORECASE):
                return line.strip()[:1000]
    return None
