# Academic Deadline Brief

**Course:** AILT9019 · AI Literacy II — Project

A small local tool that turns scattered course documents (syllabi, assignment
briefs, announcements) into a **prioritized weekly academic brief**: upcoming
tasks, deadlines, priorities, and deadline conflicts.

> Pipeline: `Course documents → Information extraction → Structured tasks → Prioritization → Weekly Academic Brief`

## What the project does

- Extracts course name, task, deadline, and task type from course documents.
- Stores them as a structured task list.
- Prioritizes tasks by deadline proximity.
- Flags missing or ambiguous deadlines instead of inventing them.
- Detects deadline conflicts.

The tool is intended as an **organizational aid** for students and does not
access university accounts, submit coursework, message instructors, or make
academic decisions.

## Setup

TODO: fill in environment and dependency setup (e.g. language/runtime version
and how to install dependencies). Place the implementation under `code/`.

## How to run the core path

TODO: fill in the command(s) to run the end-to-end pipeline once the code is
implemented in `code/`.

## How to check the result

TODO: fill in how to verify the output (e.g. what file/format is produced and
how to confirm the result is correct).

## Example input and output

TODO: add a sample course document under `sample_data/` and the expected brief
output once the implementation is ready.

## Limitations

- Extraction may miss unusual phrasings depending on the chosen approach.
- Priority is a simple function of days-until-deadline and does not yet weight
  task importance.
- Deadline conflicts are only flagged when two dated tasks fall within a short
  window.
- The brief is an organizational aid, not an authoritative source of university
  deadlines.
