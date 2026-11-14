from __future__ import annotations

import hashlib
import json
from datetime import date
from html import escape
from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parent
DATASET_DIR = ROOT / "dataset"
OBSERVATION_DIR = DATASET_DIR / "observations"
GOLD_PATH = ROOT / "gold.json"
GOLD_HASH_PATH = ROOT / "gold.sha256"
FROZEN_AT = "2026-11-15"

DOCS = [
    {
        "id": "D1",
        "course": "COMP2119",
        "course_name": "Introduction to Data Structures and Algorithms",
        "format": "pdf",
        "filename": "D1_COMP2119_pa1.pdf",
        "imported": True,
        "title": (
            "COMP2119A/B/C Introduction to Data Structures and Algorithms - "
            "Programming Assignment 1"
        ),
        "tasks": [
            {
                "title": "Programming Assignment 1",
                "task_type": "assignment",
                "due_date": "2026-11-04",
                "description": (
                    "Students implement three C++ tasks about course "
                    "prerequisite graphs: the lowest-difficulty study path, "
                    "the number of courses made unreachable, and a course "
                    "ordering number."
                ),
                "subtasks": [
                    {
                        "label": "Task A",
                        "description": (
                            "Find the lowest total difficulty of a study path "
                            "that makes course s eligible."
                        ),
                    },
                    {
                        "label": "Task B",
                        "description": (
                            "Count courses that become unreachable when "
                            "course s cannot be passed."
                        ),
                    },
                    {
                        "label": "Task C",
                        "description": (
                            "Find the ordering number of course s in a "
                            "tie-broken topological order."
                        ),
                    },
                ],
                "source_quote": (
                    "COMP2119A/B/C Introduction to Data Structures and "
                    "Algorithms\nProgramming Assignment 1 - Course Selection "
                    "Challenge\nDue Date: Nov 4, 2026 7:00pm"
                ),
            },
        ],
    },
    {
        "id": "D2",
        "course": "AILT9019",
        "course_name": "AI Literacy II",
        "format": "docx",
        "filename": "D2_AILT9019_project_brief.docx",
        "title": "AILT9019 AI Literacy II - Project Brief",
        "intro": (
            "This brief describes the team project milestones for AILT9019 "
            "AI Literacy II in Semester 1, 2026/27. The project examines an "
            "academic task-management problem."
        ),
        "tasks": [
            {
                "title": "Project Proposal",
                "task_type": "project",
                "due_date": "2026-10-09",
                "description": "The team submits the revised project proposal.",
            },
            {
                "title": "Midterm Status Sheet",
                "task_type": "other",
                "due_date": "2026-10-26",
                "description": "The one-page status sheet records progress and the plan.",
            },
            {
                "title": "Midterm Demo Video",
                "task_type": "other",
                "due_date": "2026-10-23",
                "description": "The video shows one real input and the resulting output.",
            },
            {
                "title": "Week 10 Progress Update",
                "task_type": "assignment",
                "due_date": "2026-11-04",
                "description": "The update reports the Week 10 milestone.",
            },
            {
                "title": "Final Report Draft",
                "task_type": "project",
                "due_date": "2026-11-13",
                "description": "The draft covers the approach, results and limitations.",
            },
        ],
    },
    {
        "id": "D3",
        "course": "ECON1210",
        "course_name": "Introduction to Economics",
        "format": "pdf",
        "filename": "D3_ECON1210_announcement.pdf",
        "title": "ECON1210 Introduction to Economics - Assessment Announcement",
        "intro": (
            "This announcement lists the assessment schedule for ECON1210 "
            "Introduction to Economics in Semester 1, 2026/27. The course "
            "introduces microeconomic and macroeconomic principles."
        ),
        "tasks": [
            {
                "title": "Problem Set 1",
                "task_type": "assignment",
                "due_date": "2026-09-18",
                "description": "The problem set covers supply and demand.",
            },
            {
                "title": "Problem Set 2",
                "task_type": "assignment",
                "due_date": "2026-10-09",
                "description": "The problem set covers market structures.",
            },
            {
                "title": "Quiz 1",
                "task_type": "quiz",
                "due_date": "2026-10-16",
                "description": "The quiz covers the first four lectures.",
            },
            {
                "title": "Essay Outline",
                "task_type": "assignment",
                "due_date": "2026-11-06",
                "description": "The outline presents the argument for the final essay.",
            },
            {
                "title": "Final Essay",
                "task_type": "assignment",
                "due_date": "2026-11-27",
                "description": "The essay analyses a current economic policy issue.",
            },
            {
                "title": "Final Examination",
                "task_type": "exam",
                "due_date": "2026-12-05",
                "description": "The final examination covers the whole course.",
            },
        ],
    },
    {
        "id": "D4",
        "course": "STAT2601",
        "course_name": "Statistics",
        "format": "txt",
        "filename": "D4_STAT2601_schedule.txt",
        "title": "STAT2601 Statistics - Course Schedule",
        "intro": (
            "This schedule describes the assessments for STAT2601 Statistics "
            "in Semester 1, 2026/27. The course covers descriptive statistics, "
            "probability and regression."
        ),
        "tasks": [
            {
                "title": "Homework 1",
                "task_type": "assignment",
                "due_date": "2026-09-22",
                "description": "The homework covers descriptive statistics.",
            },
            {
                "title": "Homework 2",
                "task_type": "assignment",
                "due_date": "2026-10-20",
                "description": "The homework covers probability distributions.",
            },
            {
                "title": "Data Analysis Report",
                "task_type": "project",
                "due_date": "2026-11-17",
                "description": "The report analyses a provided dataset.",
            },
            {
                "title": "Midterm Test",
                "task_type": "exam",
                "due_date": "2026-11-10",
                "description": "The test covers the first half of the course.",
            },
        ],
    },
    {
        "id": "D5",
        "course": "COMP2119",
        "course_name": "Introduction to Data Structures and Algorithms",
        "format": "pdf",
        "filename": "D5_COMP2119_wa3.pdf",
        "imported": True,
        "title": (
            "COMP2119 Introduction to Data Structures and Algorithms - "
            "Written Assignment 3"
        ),
        "tasks": [
            {
                "title": "Written Assignment 3",
                "task_type": "assignment",
                "due_date": "2026-11-25",
                "description": (
                    "A written assignment on trees, binary search trees, AVL "
                    "trees, bitonic search and a robust QuickSort."
                ),
                "subtasks": [
                    {
                        "label": "Question 1",
                        "description": (
                            "Trees: missing child count, reconstruction, "
                            "traversals and leftmost-child/right-sibling "
                            "representation."
                        ),
                    },
                    {
                        "label": "Question 2",
                        "description": (
                            "Binary search tree and AVL tree operations, "
                            "deletions, insertions and rotations."
                        ),
                    },
                    {
                        "label": "Question 3",
                        "description": (
                            "Find the peak of a bitonic array and search it "
                            "in O(log n) time."
                        ),
                    },
                    {
                        "label": "Question 4",
                        "description": (
                            "Analyse QuickSort and design RobustQuickSort "
                            "with a worst-case O(n log n) bound."
                        ),
                    },
                ],
                "source_quote": (
                    "COMP2119 Introduction to Data Structures and Algorithms\n"
                    "Written Assignment 3 - Trees, Searching & Sorting "
                    "Algorithms\nDue date: Nov 25, 2026, 7:00pm"
                ),
            },
        ],
    },
    {
        "id": "D6",
        "course": "AILT9019",
        "course_name": "AI Literacy II",
        "format": "pdf",
        "filename": "D6_AILT9019_final_project.pdf",
        "title": "AILT9019 AI Literacy II - Final Project Brief",
        "intro": (
            "This brief describes the final project deliverables for AILT9019 "
            "AI Literacy II. The project continues the team's semester work."
        ),
        "tasks": [
            {
                "title": "Project Proposal Revision",
                "task_type": "project",
                "due_date": "2026-10-16",
                "description": "The revision responds to the proposal review.",
            },
            {
                "title": "Cross-team Peer Review",
                "task_type": "other",
                "due_date": "2026-11-27",
                "description": "Each team reviews another team's project gallery.",
            },
            {
                "title": "Final Report",
                "task_type": "project",
                "due_date": "2026-11-20",
                "description": "The report covers the final system and evaluation.",
            },
            {
                "title": "Project Presentation",
                "task_type": "presentation",
                "due_date": "2026-11-24",
                "description": "The team presents the final project.",
            },
            {
                "title": "Gallery Poster",
                "task_type": "other",
                "due_date": "2026-11-30",
                "description": "The poster summarises the project for the gallery.",
            },
        ],
    },
    {
        "id": "D7",
        "course": "ECON1210",
        "course_name": "Introduction to Economics",
        "format": "docx",
        "filename": "D7_ECON1210_reading_exam.docx",
        "title": "ECON1210 Introduction to Economics - Reading and Assessment Guide",
        "intro": (
            "This guide describes the reading responses and remaining "
            "assessments for ECON1210 Introduction to Economics."
        ),
        "tasks": [
            {
                "title": "Reading Response 1",
                "task_type": "reading",
                "due_date": "2026-09-30",
                "description": "The response discusses the assigned chapter on scarcity.",
            },
            {
                "title": "Reading Response 2",
                "task_type": "reading",
                "due_date": "2026-10-21",
                "description": "The response discusses the assigned chapter on trade.",
            },
            {
                "title": "Group Presentation",
                "task_type": "presentation",
                "due_date": "2026-11-11",
                "description": "The group presents a market analysis.",
            },
            {
                "title": "Term Paper",
                "task_type": "assignment",
                "due_date": "2026-11-25",
                "description": "The paper applies an economic model to a policy case.",
            },
            {
                "title": "Weekly Reading Quiz",
                "task_type": "quiz",
                "due_date": "2026-12-01",
                "description": "The quiz covers the final reading week.",
            },
        ],
    },
    {
        "id": "D8",
        "course": "STAT2601",
        "course_name": "Statistics",
        "format": "pdf",
        "filename": "D8_STAT2601_reading_week.pdf",
        "title": "STAT2601 Statistics - Reading Week and Lab Schedule",
        "intro": (
            "This schedule describes the lab and project work for STAT2601 "
            "Statistics. Reading week is 2-6 November 2026."
        ),
        "tasks": [
            {
                "title": "Lab Exercise 1",
                "task_type": "assignment",
                "due_date": "2026-09-29",
                "description": "The exercise introduces statistical software.",
            },
            {
                "title": "Lab Exercise 2",
                "task_type": "assignment",
                "due_date": "2026-10-27",
                "description": "The exercise covers hypothesis testing.",
            },
            {
                "title": "Regression Project",
                "task_type": "project",
                "due_date": "2026-11-19",
                "description": "The project fits and evaluates a regression model.",
            },
            {
                "title": "Reading Week Assignment",
                "task_type": "assignment",
                "due_date": "2026-11-06",
                "description": "The assignment accompanies the reading week material.",
            },
            {
                "title": "Quiz 3",
                "task_type": "quiz",
                "due_date": "2026-12-03",
                "description": "The quiz covers regression and model evaluation.",
            },
        ],
    },
]

OBS_DOCS = [
    {
        "id": "OBS1",
        "course": "ECON1210",
        "course_name": "Introduction to Economics",
        "format": "txt",
        "filename": "OBS1_ECON1210_quiz_tba.txt",
        "title": "ECON1210 - Quiz 2 Announcement",
        "intro": "Quiz 2 will be held on a date to be announced later by the instructor.",
        "observation": {
            "id": "OBS-1",
            "title": "Quiz 2",
            "reason": "The announcement says the date will be announced later.",
        },
    },
    {
        "id": "OBS2",
        "course": "STAT2601",
        "course_name": "Statistics",
        "format": "docx",
        "filename": "OBS2_STAT2601_reading_week_report.docx",
        "title": "STAT2601 - Final Project Report Notice",
        "intro": (
            "The final project report is due at the end of reading week. "
            "The exact date will be confirmed later."
        ),
        "observation": {
            "id": "OBS-2",
            "title": "Final Project Report",
            "reason": "The document refers to the end of reading week and says the date is not yet confirmed.",
        },
    },
    {
        "id": "OBS3",
        "course": "COMP3234",
        "course_name": "Computer and Communication Networks",
        "format": "pdf",
        "filename": "OBS3_COMP3234_game_house.pdf",
        "imported": True,
        "title": (
            "COMP3234 / ELEC3443 - A Simple Game House Application"
        ),
        "observation": {
            "id": "OBS-3",
            "title": "A Simple Game House Application",
            "reason": (
                "The handout gives no submission date; it only says the zip "
                "must be submitted before the deadline."
            ),
        },
    },
]


def human_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


def task_line(index: int, task: dict) -> str:
    return (
        f"{index}. {task['title']} - due {human_date(task['due_date'])}. "
        f"{task['description']}"
    )


def body_lines(doc: dict) -> list[str]:
    lines = [
        doc["title"],
        f"Course: {doc['course']} - {doc['course_name']}",
        "Semester 1, 2026/27",
        "",
        doc["intro"],
        "",
        "Assessment schedule",
        "",
    ]
    for index, task in enumerate(doc["tasks"], start=1):
        lines.append(task_line(index, task))
        lines.append("")
    return lines


def observation_lines(doc: dict) -> list[str]:
    return [
        doc["title"],
        f"Course: {doc['course']} - {doc['course_name']}",
        "Semester 1, 2026/27",
        "",
        doc["intro"],
    ]


def write_pdf(path: Path, title: str, lines: list[str]) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CourseBriefTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=10,
    )
    body_style = ParagraphStyle(
        "CourseBriefBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        spaceAfter=4,
    )
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=52,
        rightMargin=52,
        topMargin=48,
        bottomMargin=48,
        title=title,
    )
    story = []
    for index, line in enumerate(lines):
        style = title_style if index == 0 else body_style
        story.append(Paragraph(escape(line), style))
        if index == 0:
            story.append(Spacer(1, 8))
    document.build(story)


def write_docx(path: Path, title: str, lines: list[str]) -> None:
    document = Document()
    document.add_heading(title, level=0)
    for line in lines[1:]:
        if line:
            document.add_paragraph(line)
    document.save(path)


def write_text(path: Path, lines: list[str], markdown: bool) -> None:
    if markdown:
        text = "\n".join(
            (f"# {line}" if index == 0 else line)
            for index, line in enumerate(lines)
        )
    else:
        text = "\n".join(lines)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    OBSERVATION_DIR.mkdir(parents=True, exist_ok=True)

    documents = []
    tasks = []
    for doc in DOCS:
        path = DATASET_DIR / doc["filename"]
        if doc.get("imported"):
            if not path.exists():
                raise FileNotFoundError(
                    f"missing imported document for {doc['id']}: {path}"
                )
        else:
            lines = body_lines(doc)
            if doc["format"] == "pdf":
                write_pdf(path, doc["title"], lines)
            elif doc["format"] == "docx":
                write_docx(path, doc["title"], lines)
            else:
                write_text(path, lines, markdown=doc["format"] == "markdown")
        documents.append(
            {
                "id": doc["id"],
                "path": f"dataset/{doc['filename']}",
                "course": doc["course"],
                "format": doc["format"],
                "task_count": len(doc["tasks"]),
                "sha256": sha256(path),
            }
        )
        for index, task in enumerate(doc["tasks"], start=1):
            tasks.append(
                {
                    "id": f"{doc['id']}-T{index}",
                    "doc_id": doc["id"],
                    "course_name": doc["course"],
                    "title": task["title"],
                    "description": task["description"],
                    "task_type": task["task_type"],
                    "date_confidence": "exact",
                    "due_date": task["due_date"],
                    "due_range_start": None,
                    "due_range_end": None,
                    "subtasks": task.get("subtasks", []),
                    "source_quote": task.get("source_quote") or task_line(index, task),
                }
            )

    observation_documents = []
    observations = []
    for doc in OBS_DOCS:
        path = OBSERVATION_DIR / doc["filename"]
        if doc.get("imported"):
            if not path.exists():
                raise FileNotFoundError(
                    f"missing imported document for {doc['id']}: {path}"
                )
        else:
            lines = observation_lines(doc)
            if doc["format"] == "pdf":
                write_pdf(path, doc["title"], lines)
            elif doc["format"] == "docx":
                write_docx(path, doc["title"], lines)
            else:
                write_text(path, lines, markdown=False)
        observation_documents.append(
            {
                "id": doc["id"],
                "path": f"dataset/observations/{doc['filename']}",
                "course": doc["course"],
                "format": doc["format"],
                "task_count": 1,
                "sha256": sha256(path),
            }
        )
        observations.append(
            {
                "id": doc["observation"]["id"],
                "doc_id": doc["id"],
                "title": doc["observation"]["title"],
                "reason": doc["observation"]["reason"],
                "expected_date_confidence": "unknown",
            }
        )

    gold = {
        "version": "eval-v2",
        "frozen_at": FROZEN_AT,
        "changelog": [
            "Initial frozen synthetic evaluation set",
            "Replaced the synthetic COMP3230 syllabus and deadline-change documents with the real COMP2119 PA1 and WA3 handouts",
            "Replaced the synthetic Game House observation document with the real COMP3234/ELEC3443 handout",
        ],
        "documents": documents,
        "tasks": tasks,
        "observation_documents": observation_documents,
        "ambiguity_observations": observations,
    }
    GOLD_PATH.write_text(
        json.dumps(gold, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    gold_hash = sha256(GOLD_PATH)
    GOLD_HASH_PATH.write_text(f"{gold_hash}  gold.json\n", encoding="utf-8")
    print(
        f"built {len(documents)} documents, {len(tasks)} tasks, "
        f"{len(observation_documents)} observation documents"
    )
    print(f"gold sha256: {gold_hash}")


if __name__ == "__main__":
    build()
