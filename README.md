# CourseBrief

CourseBrief turns course documents into a calendar of deadlines. Upload a syllabus, assignment brief, or announcement; the backend converts it to text, extracts tasks with an LLM, stores them in one JSON file, and the browser renders a month calendar that expands into a week view.

## Status

- Backend: FastAPI, single-file JSON storage, PDF/DOCX/TXT/Markdown parsing.
- Extraction: live OpenAI-compatible LLM, or `EXTRACTOR_MODE=mock` for offline development.
- UI: month calendar; click a date to expand the week; hover a date for task titles; hover a task for details and source expansion.
- Not yet: task editing/deletion, calendar export, evaluation harness.

## Quick start

1. Python 3.11+.
2. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env`.

   - For a no-key demo, set `EXTRACTOR_MODE=mock` in `.env`. The current local `.env` is already set to mock.
   - For real extraction, set `EXTRACTOR_MODE=live`, `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`.

4. Start the app:

   ```bash
   python run.py
   ```

   The browser opens `http://127.0.0.1:8000`.

5. Click **Upload** or **Paste**, then wait for extraction to finish.

## Data layout

```text
data/
├── db.json                  # all structured data (uploads + tasks)
├── db.json.bak              # previous successful write
├── texts/
│   └── 2026-10-22_143012.txt
└── originals/
    └── 2026-10-22_143012.pdf
```

- The upload timestamp is the unique ID and the text filename.
- `db.json` stores only structured data; raw text and original files stay outside it.
- There is no database. Back up by copying `data/`.

## Tests

```bash
python -m pytest -q
python -m ruff check .
```

Tests use `EXTRACTOR_MODE=mock` and a temporary data directory; they do not call an external API.

## Known limits

- Mock mode returns one heuristic task per upload. It is for development and demos, not evaluation.
- Live mode requires an OpenAI-compatible endpoint and API key.
- Scanned PDFs are rejected because there is no OCR.
- The calendar places exact deadlines and the start date of estimated ranges; undated tasks appear in the **Undated** section.
- Task editing, task deletion, and export are not implemented yet.
