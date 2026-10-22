# CourseBrief

CourseBrief extracts academic tasks from course documents and displays them in a month calendar and a week view. It is an early local prototype; formal evaluation has not been implemented.

## Quick start

1. Install Python 3.11+ and the runtime dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Copy `apikey.env.example` to `apikey.env`. Choose `LLM_PROVIDER=deepseek` or `LLM_PROVIDER=qwen` and fill in `LLM_API_KEY`. Keep keys only in this ignored file. The committed `.env` contains non-sensitive model, semester and application settings.
3. Start the app:

   ```bash
   python run.py
   ```

   The browser opens `http://127.0.0.1:32922`; `PORT` in `.env` changes the port. Restart the service after changing settings or Python code.
4. Select **Upload** for PDF, DOCX, TXT or Markdown, or use **Paste**. Wait for extraction to finish. Failed uploads appear separately with a **Retry extraction** button. Parsing failures require a corrected file; retrying extraction cannot repair a damaged or scanned document.

For offline development, set `EXTRACTOR_MODE=mock` in `.env`. Mock mode produces one heuristic task per upload and does not measure extraction quality.

## Reading the calendar

- Click a date to open its week. Task cards show priority badges; tasks within a day retain their stored order.
- Open a task and select **Show source** to inspect its source quotes or open the full extracted text. Duplicate uploads can share one displayed task while retaining separate sources.
- **No confirmed deadline** means the task was extracted but its date could not be confirmed. Labels distinguish TBA, a missing date and a date needing review. Clicking such a task opens details in its upload week; the upload date is not a deadline.
- An estimated range appears on its start date and remains labeled as estimated.

## Data and privacy

Structured uploads, tasks and duplicate groups are stored in `data/db.json`; extracted text and original files are stored in `data/texts/` and `data/originals/`. Copy the whole `data/` directory to back it up. `db.json.bak` holds the state before the latest successful write.

Files are stored locally. Live extraction sends document text and context to the configured LLM endpoint. Use suitable test materials and check the source before relying on a deadline. The app does not access university accounts or submit work.

## Development checks

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
```

Automated tests use temporary data and mock responses rather than external API calls. Live manual checks and formal evaluation are separate activities.

## Documentation

| File | Purpose |
| --- | --- |
| `实现计划.md` | Product behavior, current gaps, test plan and verification records |
| `项目文件说明.md` | Repository layout, file responsibilities and configuration reference |
| `README.group.md` | Historical project overview |
| `test_files/` | Manual test fixtures; distinct from the planned formal evaluation set |

## Current limits

No OCR, task editing/deletion, completion tracking, export, multi-user support or formal evaluation harness. The UI does not display conflict warnings or a sorted priority list. Extraction and duplicate detection still depend on model output; see the implementation plan for verification scope and unresolved requirements.
