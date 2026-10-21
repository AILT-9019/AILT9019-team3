# AILT 9019 Group Project

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



## How to run the core path



## How to check the result


## Example input and output



## Limitations

- Extraction may miss unusual phrasings depending on the chosen approach.
- Priority is a simple function of days-until-deadline and does not yet weight
  task importance.
- Deadline conflicts are only flagged when two dated tasks fall within a short
  window.
- The brief is an organizational aid, not an authoritative source of university
  deadlines.
