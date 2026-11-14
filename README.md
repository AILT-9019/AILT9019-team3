# CourseBrief

**English** | [简体中文](README.zh-CN.md)

CourseBrief extracts academic tasks from course documents and displays them in a month calendar and a week view. The current version is a local prototype: a frozen evaluation set, gold data and an evaluation harness are implemented; a live evaluation report was generated on 2026-11-15 and passed all three measured metrics on the fixed evaluation set.

## Quick start

1. Install Python 3.11+ and the runtime dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. Copy `apikey.env.example` to `apikey.env`. Choose `LLM_PROVIDER=deepseek` or `qwen` and fill in `LLM_API_KEY`. Keep keys only in this ignored file. The committed `.env` contains non-sensitive model, semester and application settings.
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
- **No confirmed deadline** means the task was extracted but its date could not be confirmed. Labels distinguish TBA, a missing date and a date needing review. Clicking such a task opens details in its upload week; the date shown is the import date, not a deadline.
- A task in the **No confirmed deadline** section has a **Delete** button in its details. Deletion requires a second confirmation and removes only the extracted task; the uploaded source and its text remain in `data/`.
- An estimated range appears on its start date and remains labeled as estimated.

## Data and privacy

Structured uploads, tasks and duplicate groups are stored in `data/db.json`; extracted text and original files are stored in `data/texts/` and `data/originals/`. Copy the whole `data/` directory to back it up. `db.json.bak` holds the state before the latest successful write.

Files are stored locally. Live extraction sends document text and context to the configured LLM endpoint. Use suitable test materials and check the source before relying on a deadline. The app does not access university accounts or submit work.

## Evaluation

The frozen evaluation set and harness in `eval/` are the repository's fixed test and evaluation assets and the project's public evaluation entry point:

- `eval/gold.json`: 8 scored documents with 32 tasks, including two real COMP2119 assignment handouts, plus 3 ambiguity observation documents;
- within each document, normalized titles are matched one-to-one with a greedy algorithm using a similarity threshold of `0.8`; a short title that is a whole-word prefix of a longer `name - subtitle` title also counts as a match;
- metrics: extraction precision/recall, deadline accuracy and course association;
- pass lines: precision/recall ≥ 90% (at least 29/32), deadline accuracy ≥ 90% (at least 29/32), course association ≥ 95% (at least 31/32);
- The 3 observation documents only record system output and are not subject to a hard-fail check.

The set was updated on 2026-11-15 (`eval-v2`) to replace two synthetic COMP3230 documents with real COMP2119 assignment handouts and to use a real handout for the Game House observation. The latest local live run (`deepseek-chat`, prompt v2) matched all 32 tasks; precision/recall, deadline accuracy and course association were all 100%.

Both commands must be run from the **project root**, the folder that contains `run.py`.

Validate the evaluation set without calling a model:

```bash
python eval/run_eval.py --check
```

You can also double-click `eval/run_eval.py`; it runs the default `--check`. The console may close when it finishes, so run it from a terminal to read the full output.

Run the live evaluation, which requires `EXTRACTOR_MODE=live` and a configured `LLM_API_KEY`:

```bash
python eval/run_eval.py --live
```

`--check` only prints a per-document validation table and a checklist; it does not write a file. `--live` prints per-document and per-metric result tables, then writes `report.md` and `report.json` to the local `data/eval_reports/<timestamp>/` folder. That folder is ignored by Git and is not part of the repository. A live run makes about 11 model calls. Reports include per-document matches, false positives/negatives, near-miss dates and aggregate metrics. Exit codes: `0` pass, `1` below a pass line, `2` configuration, data or API error.

`--check` only validates the data; it does not measure model accuracy. Accuracy can only come from a live evaluation report.
