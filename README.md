# Academic Deadline Brief

**Course:** AILT9019 · AI Literacy II — Project
**Midterm check:** due Monday 26 October 2026 (Week 9) — 5% of course grade

A small local tool that turns scattered course documents (syllabi, assignment
briefs, announcements) into a **prioritized weekly academic brief**: upcoming
tasks, deadlines, priorities, and deadline conflicts.

> Pipeline: `Course documents → Information extraction → Structured tasks → Prioritization → Weekly Academic Brief`

The core path is implemented as a minimal, **dependency-free** Python reference
implementation so it is fully reproducible from this repository. The interface
is a plain command line; a richer browser UI is a documented *should-have*.

---

## 1. What the system does (and does not)

- **Does:** extract course name, task, deadline, and task type from plain-text
  course documents; store them as a structured task list; prioritize by deadline
  proximity; flag missing/ambiguous deadlines instead of inventing them; detect
  deadline conflicts.
- **Does not:** access university accounts, submit coursework, message
  instructors, or make academic decisions. The demo runs only on the bundled
  synthetic sample documents — no real personal student data is used.

---

## 2. Repository access for course staff

This repository is shared with the AILT9019 course team so staff can **access
the current code and reproduce the core path**. To grant access:

- Either make the repository **Public**, or
- Add the course team's GitHub account(s) as **Collaborator(s)** (Settings →
  Collaborators).

The repository URL is also recorded in `repository_link.txt` (used for the ZIP
submission).

---

## 3. Setup

Requirements: Python 3.10+ (standard library only for the core path).

```bash
# clone (or download) the repository
git clone <repository-url>
cd academic-deadline-brief

# (optional) create an isolated environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# no third-party packages are required for the core path
```

Extended document formats (PDF / .docx) are optional — see `requirements.txt`.

---

## 4. How to run the core path

From the repository root:

```bash
python src/pipeline.py
```

This reads every file in `data/sample_inputs/`, extracts tasks, prioritizes
them, and writes a weekly brief to `data/sample_output/brief.json`. It also
prints a human-readable summary to the terminal.

---

## 5. How to check the result

1. **Terminal output** lists each upcoming task with its priority and deadline,
   and reports any detected deadline conflicts.
2. **`data/sample_output/brief.json`** is the machine-readable brief
   (`tasks`, `deadline_conflicts`, `counts`).
3. **Expected output** for the bundled sample is in
   `data/sample_output/expected_brief.json` (illustrative example of the
   format). Because priority depends on *today's date*, the exact priority
   labels may shift, but the extracted tasks, deadlines, and conflict flags are
   stable.
4. **Reproducibility test:**

   ```bash
   python tests/test_pipeline.py
   ```

   This re-runs the core path on the sample inputs and asserts the structure is
   correct (correct task count, valid ISO deadlines, missing deadlines flagged
   rather than fabricated, conflicts reported). A passing run prints
   `TEST PASSED` with the task counts.

---

## 6. Example input and expected output

**Example input** (`data/sample_inputs/sample_syllabus.txt`):

```
Course: AILT9019 — AI Literacy II
Week 4: Project Proposal due Friday 25 September 2026.
Week 6: Draft literature review due Monday 12 October 2026.
Week 8: Midterm check (ZIP submission) due Monday 26 October 2026.
Week 10: Prototype demo due Friday 13 November 2026.
Week 12: Final project report due Monday 30 November 2026.
```

**Expected behaviour:** five dated tasks extracted, each with course, task,
ISO `deadline`, and `task_type`; prioritized by deadline; missing/ambiguous
deadlines (if any) flagged with `note` rather than invented. See
`data/sample_output/expected_brief.json` for the full structure.

---

## 7. Project layout

```
academic-deadline-brief/
├── README.md                      # this file (setup / run / check)
├── repository_link.txt            # repository URL (for the ZIP submission)
├── STATUS_SHEET.md                # one-page midterm status sheet (companion)
├── LICENSE
├── requirements.txt
├── .gitignore
├── src/
│   ├── extract.py                 # information extraction (rule-based)
│   ├── prioritize.py              # prioritization + conflict detection
│   └── pipeline.py                # end-to-end orchestration (entry point)
├── data/
│   ├── sample_inputs/             # synthetic course documents (example input)
│   └── sample_output/             # generated brief + expected example
└── tests/
    └── test_pipeline.py           # reproducibility / correctness test
```

---

## 8. Limitations & known risks

- Extraction is **rule-based** (keyword + date matching), not an LLM. It handles
  the bundled formats reliably but may miss unusual phrasings.
- Priority is a simple function of days-until-deadline; it does not yet weight
  task importance.
- Deadline conflicts are flagged only when two dated tasks fall within 2 days.
- PDF / .docx ingestion is stubbed (text-based inputs are supported now).

These are explicitly surfaced so the brief is treated as an **organizational
aid**, not an authoritative source of university deadlines.
