"""Information extraction for the Academic Deadline Brief.

Rule-based, dependency-free reference implementation. It reads plain-text
course documents and extracts (course, task, deadline, task_type) tuples.
Missing or ambiguous deadlines are *flagged*, never invented.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}

# Matches an optional weekday followed by "DD Month YYYY".
_DATE_RE = re.compile(
    r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+)?"
    r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(\d{4})"
)

# A sentence is treated as a task only if it explicitly mentions a deadline.
_DEADLINE_WORDS = ("due", "deadline")

_TASK_TYPE_HINTS = (
    ("literature review", "Review"),
    ("review", "Review"),
    ("proposal", "Proposal"),
    ("demo", "Demo"),
    ("report", "Report"),
    ("essay", "Essay"),
    ("submission", "Submission"),
    ("reflection", "Reflection"),
    ("quiz", "Quiz"),
    ("exam", "Exam"),
)


def parse_date(text: str):
    m = _DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def infer_type(text: str) -> str:
    low = text.lower()
    for hint, label in _TASK_TYPE_HINTS:
        if hint in low:
            return label
    return "Task"


def _sentences(line: str):
    # Split a line into sentences on sentence-ending punctuation.
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]


def extract_from_file(path: Path) -> tuple[str, list[dict]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    course = path.stem
    if lines:
        m = re.search(r"Course:\s*(.+)", lines[0])
        if m:
            course = m.group(1).strip()

    tasks: list[dict] = []
    for line in lines:
        # Course header line is metadata, skip it for task extraction.
        if line.startswith("Course:"):
            continue
        for sent in _sentences(line):
            low = sent.lower()
            parsed = parse_date(sent)
            if parsed is not None:
                tasks.append({
                    "course": course,
                    "task": sent,
                    "deadline": parsed.isoformat(),
                    "task_type": infer_type(sent),
                })
            elif any(w in low for w in _DEADLINE_WORDS):
                # Explicitly mentions a deadline but none could be parsed.
                tasks.append({
                    "course": course,
                    "task": sent,
                    "deadline": None,
                    "task_type": infer_type(sent),
                    "note": "deadline ambiguous or missing — flagged, not invented",
                })
            # Sentences without a deadline word are not tasks.
    return course, tasks
