from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

TITLE_THRESHOLD = 0.8
PASS_PRECISION = 0.90
PASS_RECALL = 0.90
PASS_DATE_ACCURACY = 0.90
PASS_COURSE_ACCURACY = 0.95
SCORED_DOCUMENTS = 8
SCORED_TASKS = 32
OBSERVATION_DOCUMENTS = 3

_COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,}\s*[0-9]{4}[A-Za-z]?)\b")
_SECTION_SUFFIX_RE = re.compile(r"^([A-Z]{2,}[0-9]{4})[A-Z]$")


def _normalize_course_code(code: str) -> str:
    match = _SECTION_SUFFIX_RE.fullmatch(code)
    return match.group(1) if match else code


@dataclass(frozen=True)
class Match:
    gold_index: int
    system_index: int
    ratio: float


def field(task: Any, name: str, default: Any = None) -> Any:
    if isinstance(task, dict):
        return task.get(name, default)
    return getattr(task, name, default)


def normalize_title(value: Any) -> str:
    text = str(value or "").casefold()
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def course_key(value: Any) -> str:
    text = str(value or "")
    codes = sorted(
        {
            _normalize_course_code(re.sub(r"\s+", "", code).upper())
            for code in _COURSE_CODE_RE.findall(text)
        }
    )
    return "::".join(codes) if codes else normalize_title(text)


def as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def title_similarity(gold_title: str, system_title: str) -> float:
    if not gold_title or not system_title:
        return 0.0
    if gold_title == system_title:
        return 1.0
    shorter, longer = sorted((gold_title, system_title), key=len)
    if len(shorter.split()) >= 2 and longer.startswith(shorter + " "):
        return 1.0
    return SequenceMatcher(None, gold_title, system_title).ratio()


def match_tasks(
    gold_tasks: list[Any],
    system_tasks: list[Any],
    threshold: float = TITLE_THRESHOLD,
) -> tuple[list[Match], list[int], list[int]]:
    candidates: list[tuple[float, int, int]] = []
    for gold_index, gold in enumerate(gold_tasks):
        gold_title = normalize_title(field(gold, "title"))
        if not gold_title:
            continue
        for system_index, system in enumerate(system_tasks):
            system_title = normalize_title(field(system, "title"))
            if not system_title:
                continue
            ratio = title_similarity(gold_title, system_title)
            if ratio >= threshold:
                candidates.append((ratio, gold_index, system_index))

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_gold: set[int] = set()
    used_system: set[int] = set()
    matches: list[Match] = []
    for ratio, gold_index, system_index in candidates:
        if gold_index in used_gold or system_index in used_system:
            continue
        used_gold.add(gold_index)
        used_system.add(system_index)
        matches.append(Match(gold_index, system_index, ratio))

    false_positives = [
        index for index in range(len(system_tasks)) if index not in used_system
    ]
    false_negatives = [
        index for index in range(len(gold_tasks)) if index not in used_gold
    ]
    return matches, false_positives, false_negatives


def _task_brief(task: Any) -> dict[str, Any]:
    date_confidence = field(task, "date_confidence")
    task_type = field(task, "task_type")
    return {
        "id": field(task, "id"),
        "doc_id": field(task, "doc_id"),
        "title": field(task, "title"),
        "course_name": field(task, "course_name"),
        "date_confidence": getattr(date_confidence, "value", date_confidence),
        "due_date": _iso_date(field(task, "due_date")),
        "due_range_start": _iso_date(field(task, "due_range_start")),
        "due_range_end": _iso_date(field(task, "due_range_end")),
        "task_type": getattr(task_type, "value", task_type),
    }


def _iso_date(value: Any) -> str | None:
    parsed = as_date(value)
    return parsed.isoformat() if parsed else None


def compute_metrics(
    gold_tasks: list[Any],
    system_tasks: list[Any],
    matches: list[Match],
    false_positives: list[int],
    false_negatives: list[int],
) -> dict[str, Any]:
    matched = len(matches)
    total = len(gold_tasks)
    precision = matched / len(system_tasks) if system_tasks else 0.0
    recall = matched / total if total else 0.0

    date_correct: list[dict[str, Any]] = []
    near_miss: list[dict[str, Any]] = []
    date_wrong: list[dict[str, Any]] = []
    course_correct = 0
    course_mismatches: list[dict[str, Any]] = []
    fully_recovered = 0
    match_details: list[dict[str, Any]] = []

    for match in matches:
        gold = gold_tasks[match.gold_index]
        system = system_tasks[match.system_index]
        gold_date = as_date(field(gold, "due_date"))
        system_date = as_date(field(system, "due_date"))
        gold_course = field(gold, "course_name")
        system_course = field(system, "course_name")
        course_ok = bool(course_key(gold_course)) and course_key(
            gold_course
        ) == course_key(system_course)
        if course_ok:
            course_correct += 1
        else:
            course_mismatches.append(
                {
                    "gold": _task_brief(gold),
                    "system": _task_brief(system),
                    "ratio": round(match.ratio, 3),
                }
            )

        date_ok = gold_date is not None and system_date == gold_date
        detail = {
            "gold": _task_brief(gold),
            "system": _task_brief(system),
            "ratio": round(match.ratio, 3),
            "course_ok": course_ok,
            "date_ok": date_ok,
        }
        match_details.append(detail)
        if date_ok:
            date_correct.append(detail)
        elif (
            gold_date is not None
            and system_date is not None
            and 0 < abs((system_date - gold_date).days) <= 2
            and system_date.isocalendar()[:2] == gold_date.isocalendar()[:2]
        ):
            near_miss.append(detail)
        else:
            date_wrong.append(detail)

        if course_ok and date_ok:
            fully_recovered += 1

    return {
        "gold_tasks": total,
        "system_tasks": len(system_tasks),
        "matched": matched,
        "precision": precision,
        "recall": recall,
        "date_accuracy": len(date_correct) / total if total else 0.0,
        "course_accuracy": course_correct / matched if matched else 0.0,
        "fully_recovered": fully_recovered / total if total else 0.0,
        "date_correct": len(date_correct),
        "near_miss": len(near_miss),
        "date_wrong": len(date_wrong),
        "course_correct": course_correct,
        "matches": match_details,
        "near_miss_details": near_miss,
        "date_wrong_details": date_wrong,
        "course_mismatches": course_mismatches,
        "false_positives": [
            _task_brief(system_tasks[index]) for index in false_positives
        ],
        "false_negatives": [
            _task_brief(gold_tasks[index]) for index in false_negatives
        ],
    }


def passed(metrics: dict[str, Any]) -> bool:
    return (
        metrics["precision"] >= PASS_PRECISION
        and metrics["recall"] >= PASS_RECALL
        and metrics["date_accuracy"] >= PASS_DATE_ACCURACY
        and metrics["course_accuracy"] >= PASS_COURSE_ACCURACY
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_gold(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_date_fields(task: dict[str, Any]) -> str | None:
    confidence = task.get("date_confidence")
    due_date = task.get("due_date")
    range_start = task.get("due_range_start")
    range_end = task.get("due_range_end")
    if confidence == "exact":
        if not due_date or range_start or range_end:
            return "exact task must have due_date and no range"
        if as_date(due_date) is None:
            return "exact task has an invalid due_date"
    elif confidence == "range":
        if due_date or not range_start or not range_end:
            return "range task must have both bounds and no due_date"
        start = as_date(range_start)
        end = as_date(range_end)
        if start is None or end is None or start > end:
            return "range task has invalid bounds"
    elif confidence == "unknown":
        if due_date or range_start or range_end:
            return "unknown task must not contain dates"
    else:
        return "unknown date_confidence"
    return None


def validate_gold(gold: dict[str, Any], base_dir: Path) -> list[str]:
    errors: list[str] = []
    documents = gold.get("documents")
    tasks = gold.get("tasks")
    observation_documents = gold.get("observation_documents")
    observations = gold.get("ambiguity_observations")

    if not isinstance(documents, list):
        return ["documents must be a list"]
    if len(documents) != SCORED_DOCUMENTS:
        errors.append(f"expected {SCORED_DOCUMENTS} scored documents, got {len(documents)}")
    if not isinstance(tasks, list):
        return errors + ["tasks must be a list"]
    if len(tasks) != SCORED_TASKS:
        errors.append(f"expected {SCORED_TASKS} scored tasks, got {len(tasks)}")
    if not isinstance(observation_documents, list):
        errors.append("observation_documents must be a list")
        observation_documents = []
    if len(observation_documents) != OBSERVATION_DOCUMENTS:
        errors.append(
            f"expected {OBSERVATION_DOCUMENTS} observation documents, "
            f"got {len(observation_documents)}"
        )
    if not isinstance(observations, list):
        errors.append("ambiguity_observations must be a list")
        observations = []
    if len(observations) != OBSERVATION_DOCUMENTS:
        errors.append(
            f"expected {OBSERVATION_DOCUMENTS} ambiguity observations, "
            f"got {len(observations)}"
        )

    document_ids: set[str] = set()
    task_counts: dict[str, int] = {}
    for document in documents:
        doc_id = document.get("id")
        path_value = document.get("path")
        if not doc_id or doc_id in document_ids:
            errors.append(f"invalid or duplicate document id: {doc_id!r}")
            continue
        document_ids.add(doc_id)
        task_counts[doc_id] = 0
        if not path_value:
            errors.append(f"{doc_id}: missing path")
            continue
        path = base_dir / path_value
        if not path.exists():
            errors.append(f"{doc_id}: missing file {path_value}")
        elif document.get("sha256") and file_sha256(path) != document["sha256"]:
            errors.append(f"{doc_id}: sha256 mismatch")
        task_count = document.get("task_count")
        if not isinstance(task_count, int) or task_count <= 0:
            errors.append(f"{doc_id}: invalid task_count")

    observation_document_ids: set[str] = set()
    for document in observation_documents:
        doc_id = document.get("id")
        path_value = document.get("path")
        if not doc_id or doc_id in observation_document_ids:
            errors.append(f"invalid or duplicate observation document id: {doc_id!r}")
            continue
        observation_document_ids.add(doc_id)
        if not path_value:
            errors.append(f"{doc_id}: missing path")
            continue
        path = base_dir / path_value
        if not path.exists():
            errors.append(f"{doc_id}: missing file {path_value}")
        elif document.get("sha256") and file_sha256(path) != document["sha256"]:
            errors.append(f"{doc_id}: sha256 mismatch")

    task_ids: set[str] = set()
    for task in tasks:
        task_id = task.get("id")
        doc_id = task.get("doc_id")
        if not task_id or task_id in task_ids:
            errors.append(f"invalid or duplicate task id: {task_id!r}")
            continue
        task_ids.add(task_id)
        if doc_id not in document_ids:
            errors.append(f"{task_id}: unknown doc_id {doc_id!r}")
        else:
            task_counts[doc_id] += 1
        if not task.get("title"):
            errors.append(f"{task_id}: missing title")
        if not task.get("course_name"):
            errors.append(f"{task_id}: missing course_name")
        date_error = _valid_date_fields(task)
        if date_error:
            errors.append(f"{task_id}: {date_error}")

    for document in documents:
        doc_id = document.get("id")
        if doc_id in task_counts and task_counts[doc_id] != document.get("task_count"):
            errors.append(
                f"{doc_id}: expected {document.get('task_count')} tasks, "
                f"got {task_counts[doc_id]}"
            )

    for observation in observations:
        observation_id = observation.get("id")
        if not observation_id or observation_id in task_ids:
            errors.append(f"invalid observation id: {observation_id!r}")
        if observation.get("doc_id") not in observation_document_ids:
            errors.append(
                f"{observation_id}: unknown observation doc_id "
                f"{observation.get('doc_id')!r}"
            )
    return errors
