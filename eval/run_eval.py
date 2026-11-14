from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.metrics import (
    PASS_COURSE_ACCURACY,
    PASS_DATE_ACCURACY,
    PASS_PRECISION,
    PASS_RECALL,
    Match,
    compute_metrics,
    field,
    file_sha256,
    load_gold,
    match_tasks,
    passed,
    validate_gold,
)


def _settings():
    from app.config import get_settings

    get_settings.cache_clear()
    return get_settings()


def _check_live(settings: Any) -> None:
    if settings.extractor_mode != "live":
        raise RuntimeError(
            "Evaluation requires EXTRACTOR_MODE=live; "
            f"current mode is {settings.extractor_mode}."
        )
    if not settings.llm_api_key:
        raise RuntimeError(
            "LLM_API_KEY is not configured. Set it in apikey.env before running evaluation."
        )


def _extract_document(path: Path, settings: Any) -> dict[str, Any]:
    """Run one document through the existing upload and extraction pipeline."""
    temp_root = Path(tempfile.mkdtemp(prefix="coursebrief-eval-"))
    os.environ["DATA_DIR"] = str(temp_root / "data")
    os.environ["EXTRACTOR_MODE"] = "live"
    try:
        from app.config import get_settings

        get_settings.cache_clear()
        from app.services.extractor import extract_upload
        from app.services.parsers import parse_upload
        from app.storage import create_upload, read_state

        text = parse_upload(path.name, path.read_bytes())
        upload_id, _ = create_upload(text, "upload", original_filename=path.name)
        extract_upload(upload_id)
        state = read_state()
        record = state.uploads[upload_id]
        tasks = [task for task in state.tasks if task.upload_id == upload_id]
        return {
            "tasks": tasks,
            "status": record.extraction.status.value,
            "error": record.extraction.error,
        }
    except Exception as exc:  # noqa: BLE001 - report one failed document and continue
        return {"tasks": [], "status": "failed", "error": str(exc)}
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def _date_value(value: Any) -> str | None:
    from app.services.normalizer import _coerce_date

    parsed = _coerce_date(value)
    return parsed.isoformat() if parsed else None


def _gold_summary(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "doc_id": task.get("doc_id"),
        "title": task.get("title"),
        "course_name": task.get("course_name"),
        "date_confidence": task.get("date_confidence"),
        "due_date": task.get("due_date"),
        "due_range_start": task.get("due_range_start"),
        "due_range_end": task.get("due_range_end"),
    }


def _system_summary(task: Any) -> dict[str, Any]:
    date_confidence = field(task, "date_confidence")
    return {
        "id": field(task, "id"),
        "title": field(task, "title"),
        "course_name": field(task, "course_name"),
        "date_confidence": getattr(date_confidence, "value", date_confidence),
        "due_date": _date_value(field(task, "due_date")),
        "due_range_start": _date_value(field(task, "due_range_start")),
        "due_range_end": _date_value(field(task, "due_range_end")),
        "source_quote": field(task, "source_quote"),
    }


def _match_for_document(
    gold_tasks: list[dict[str, Any]],
    system_tasks: list[Any],
) -> tuple[list[Match], list[int], list[int], dict[str, Any]]:
    matches, false_positives, false_negatives = match_tasks(gold_tasks, system_tasks)
    metrics = compute_metrics(
        gold_tasks,
        system_tasks,
        matches,
        false_positives,
        false_negatives,
    )
    return matches, false_positives, false_negatives, metrics


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    metrics = report["metrics"]

    def pct(value: float) -> str:
        return f"{value * 100:.1f}%"

    def status(value: float, threshold: float) -> str:
        return "PASS" if value >= threshold else "FAIL"

    lines = [
        "# CourseBrief Evaluation Report",
        "",
        f"- Run at: {report['run_at']}",
        f"- Provider: {report['provider']}",
        f"- Model: {report['model']}",
        f"- Prompt version: {report['prompt_version']}",
        f"- Dataset version: {report['dataset_version']}",
        f"- Gold SHA-256: `{report['gold_sha256']}`",
        "",
        "## Overall",
        "",
        "| Metric | Result | Pass line | Status |",
        "| --- | --- | --- | --- |",
        f"| Extraction precision | {pct(metrics['precision'])} | {PASS_PRECISION:.0%} | {status(metrics['precision'], PASS_PRECISION)} |",
        f"| Extraction recall | {pct(metrics['recall'])} | {PASS_RECALL:.0%} | {status(metrics['recall'], PASS_RECALL)} |",
        f"| Deadline accuracy | {pct(metrics['date_accuracy'])} | {PASS_DATE_ACCURACY:.0%} | {status(metrics['date_accuracy'], PASS_DATE_ACCURACY)} |",
        f"| Course association | {pct(metrics['course_accuracy'])} | {PASS_COURSE_ACCURACY:.0%} | {status(metrics['course_accuracy'], PASS_COURSE_ACCURACY)} |",
        "",
        f"- Gold tasks: {metrics['gold_tasks']}",
        f"- System tasks: {metrics['system_tasks']}",
        f"- Matched: {metrics['matched']}",
        f"- Date correct: {metrics['date_correct']}",
        f"- Near-miss dates: {metrics['near_miss']}",
        f"- Course correct: {metrics['course_correct']}",
        f"- Fully recovered: {pct(metrics['fully_recovered'])}",
        f"- Overall: {'PASS' if report['passed'] else 'FAIL'}",
        "",
        "## Documents",
        "",
        "| ID | Course | Status | Gold | System | Matched | Precision | Recall | Date | Course |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for document in report["documents"]:
        item = document["metrics"]
        lines.append(
            f"| {document['id']} | {document['course']} | {document['status']} | "
            f"{item['gold_tasks']} | {item['system_tasks']} | {item['matched']} | "
            f"{pct(item['precision'])} | {pct(item['recall'])} | "
            f"{pct(item['date_accuracy'])} | {pct(item['course_accuracy'])} |"
        )

    lines.extend(["", "## Failures", ""])
    false_negatives = metrics["false_negatives"]
    false_positives = metrics["false_positives"]
    if not false_negatives and not false_positives:
        lines.append("No unmatched tasks.")
    else:
        if false_negatives:
            lines.append("### False negatives")
            for task in false_negatives:
                lines.append(f"- {task['doc_id']} / {task['id']}: {task['title']}")
        if false_positives:
            lines.append("### False positives")
            for task in false_positives:
                lines.append(
                    f"- {task['id']}: {task['title']} ({task['course_name']})"
                )

    near_miss = metrics["near_miss_details"]
    if near_miss:
        lines.extend(["", "## Near-miss dates", ""])
        for item in near_miss:
            lines.append(
                f"- {item['gold']['id']}: {item['gold']['title']} "
                f"(gold {item['gold']['due_date']}, system {item['system']['due_date']})"
            )

    lines.extend(["", "## Ambiguity observations", ""])
    observations = report["observations"]
    if not observations:
        lines.append("No observation documents were run.")
    for observation in observations:
        lines.append(
            f"### {observation['id']} — {observation['title']}"
        )
        lines.append("")
        lines.append(f"- Expected confidence: {observation['expected_date_confidence']}")
        lines.append(f"- Extraction status: {observation['status']}")
        if observation.get("error"):
            lines.append(f"- Error: {observation['error']}")
        if not observation["system_tasks"]:
            lines.append("- System output: no task extracted")
        for task in observation["system_tasks"]:
            lines.append(
                f"- System output: {task['title']} | "
                f"{task['date_confidence']} | due={task['due_date']} | "
                f"range={task['due_range_start']}..{task['due_range_end']}"
            )
        lines.append("")

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _rule(char: str = "-", width: int = 74) -> None:
    print(char * width)


def _banner(title: str) -> None:
    print()
    _rule("=")
    print(f"  {title}")
    _rule("=")


def _table(headers: list[str], rows: list[list[Any]]) -> None:
    text_rows = [[str(value) for value in row] for row in rows]
    widths = []
    for index, header in enumerate(headers):
        column = [len(str(header))]
        column.extend(len(row[index]) for row in text_rows)
        widths.append(max(column))

    def separator() -> None:
        print("+" + "+".join("-" * (width + 2) for width in widths) + "+")

    separator()
    print(
        "| "
        + " | ".join(
            f"{header:<{width}}"
            for header, width in zip(headers, widths)
        )
        + " |"
    )
    separator()
    for row in text_rows:
        print(
            "| "
            + " | ".join(
                f"{value:<{width}}"
                for value, width in zip(row, widths)
            )
            + " |"
        )
    separator()


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _print_live_summary(report: dict[str, Any], run_dir: Path) -> None:
    metrics = report["metrics"]
    _banner("COURSEBRIEF LIVE EVALUATION")
    print(f"Run at     : {report['run_at']}")
    print(f"Provider   : {report['provider']}")
    print(f"Model      : {report['model']}")
    print(f"Prompt     : {report['prompt_version']}")
    print(f"Dataset    : {report['dataset_version']}")
    print(f"Gold SHA-256: {report['gold_sha256']}")
    print(
        f"Scope      : {len(report['documents'])} scored documents, "
        f"{metrics['gold_tasks']} tasks, "
        f"{len(report['observations'])} ambiguity observations"
    )
    print()

    print("Document results")
    _table(
        ["ID", "Course", "Status", "Gold", "System", "Matched"],
        [
            [
                document["id"],
                document["course"],
                document["status"],
                document["metrics"]["gold_tasks"],
                document["metrics"]["system_tasks"],
                document["metrics"]["matched"],
            ]
            for document in report["documents"]
        ],
    )
    succeeded = sum(
        1 for document in report["documents"] if document["status"] == "succeeded"
    )
    print(
        f"Documents extracted: {succeeded}/{len(report['documents'])} succeeded"
    )
    print()

    print("Metric results")
    metric_rows = [
        (
            "Extraction precision",
            metrics["precision"],
            PASS_PRECISION,
        ),
        (
            "Extraction recall",
            metrics["recall"],
            PASS_RECALL,
        ),
        (
            "Deadline accuracy",
            metrics["date_accuracy"],
            PASS_DATE_ACCURACY,
        ),
        (
            "Course association",
            metrics["course_accuracy"],
            PASS_COURSE_ACCURACY,
        ),
    ]
    _table(
        ["Metric", "Result", "Pass line", "Status"],
        [
            [
                name,
                f"{value * 100:.1f}%",
                f"{threshold:.0%}",
                _status(value >= threshold),
            ]
            for name, value, threshold in metric_rows
        ],
    )
    passed_checks = sum(1 for _, value, threshold in metric_rows if value >= threshold)
    print(f"Metric checks: {passed_checks}/4 passed")
    print(f"Matched: {metrics['matched']}/{metrics['gold_tasks']} gold tasks")
    print(
        f"False positives: {len(metrics['false_positives'])} | "
        f"False negatives: {len(metrics['false_negatives'])} | "
        f"Near-miss dates: {metrics['near_miss']}"
    )
    print()

    print("Ambiguity observations")
    for observation in report["observations"]:
        if observation["system_tasks"]:
            observed = "; ".join(
                f"{task['title']} ({task['date_confidence']})"
                for task in observation["system_tasks"]
            )
        else:
            observed = "no task extracted"
        print(f"[OBS] {observation['id']}: {observation['title']} -> {observed}")
    print()

    _rule()
    print(f"Report: {run_dir / 'report.md'}")
    print(f"Result: {_status(report['passed'])}")
    _rule("=")
    print()


def _run_observation(
    document: dict[str, Any],
    observation: dict[str, Any],
    base_dir: Path,
    settings: Any,
) -> dict[str, Any]:
    result = _extract_document(base_dir / document["path"], settings)
    tasks = result["tasks"]
    matched, _, _ = match_tasks([observation], tasks)
    selected = [tasks[match.system_index] for match in matched]
    if not selected:
        selected = tasks
    return {
        "id": observation["id"],
        "doc_id": observation["doc_id"],
        "course": document["course"],
        "title": observation["title"],
        "reason": observation.get("reason"),
        "expected_date_confidence": observation.get(
            "expected_date_confidence", "unknown"
        ),
        "status": result["status"],
        "error": result["error"],
        "system_tasks": [_system_summary(task) for task in selected],
    }


def run(gold_path: Path, out_dir: Path) -> int:
    base_dir = gold_path.parent
    gold = load_gold(gold_path)
    errors = validate_gold(gold, base_dir)
    if errors:
        print("Gold validation failed:")
        for error in errors:
            print(f"- {error}")
        return 2

    hash_path = gold_path.with_name("gold.sha256")
    if not hash_path.exists():
        print(f"Missing gold hash file: {hash_path}")
        return 2
    expected_hash = hash_path.read_text(encoding="utf-8").split()[0]
    actual_hash = file_sha256(gold_path)
    if expected_hash != actual_hash:
        print("Gold SHA-256 does not match gold.sha256.")
        return 2

    try:
        settings = _settings()
        _check_live(settings)
    except Exception as exc:  # noqa: BLE001 - configuration boundary
        print(str(exc))
        return 2

    gold_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in gold["tasks"]:
        gold_by_doc[task["doc_id"]].append(task)

    document_reports = []
    all_gold: list[Any] = []
    all_system: list[Any] = []
    all_matches: list[Match] = []
    all_false_positives: list[int] = []
    all_false_negatives: list[int] = []

    for document in gold["documents"]:
        gold_tasks = gold_by_doc[document["id"]]
        result = _extract_document(base_dir / document["path"], settings)
        system_tasks = result["tasks"]
        matches, false_positives, false_negatives, metrics = _match_for_document(
            gold_tasks, system_tasks
        )
        document_reports.append(
            {
                "id": document["id"],
                "course": document["course"],
                "path": document["path"],
                "status": result["status"],
                "error": result["error"],
                "system_tasks": [_system_summary(task) for task in system_tasks],
                "metrics": metrics,
            }
        )

        gold_offset = len(all_gold)
        system_offset = len(all_system)
        all_gold.extend(gold_tasks)
        all_system.extend(system_tasks)
        all_matches.extend(
            Match(
                match.gold_index + gold_offset,
                match.system_index + system_offset,
                match.ratio,
            )
            for match in matches
        )
        all_false_positives.extend(
            system_offset + index for index in false_positives
        )
        all_false_negatives.extend(gold_offset + index for index in false_negatives)

    aggregate = compute_metrics(
        all_gold,
        all_system,
        all_matches,
        all_false_positives,
        all_false_negatives,
    )

    observations = []
    for observation in gold["ambiguity_observations"]:
        document = next(
            item
            for item in gold["observation_documents"]
            if item["id"] == observation["doc_id"]
        )
        observations.append(
            _run_observation(document, observation, base_dir, settings)
        )

    report = {
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "prompt_version": settings.prompt_version,
        "dataset_version": gold.get("version"),
        "gold_sha256": actual_hash,
        "metrics": aggregate,
        "documents": document_reports,
        "observations": observations,
        "passed": passed(aggregate),
    }

    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
    run_dir = out_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_markdown(report, run_dir / "report.md")
    _print_live_summary(report, run_dir)
    return 0 if report["passed"] else 1


def _print_check(gold: dict[str, Any], gold_hash: str, *, live: bool = False) -> None:
    _banner("COURSEBRIEF EVALUATION CHECK")
    print(
        "Mode        : validation + live model calls"
        if live
        else "Mode        : validation only; no model calls"
    )
    print(f"Dataset     : {gold.get('version')} (frozen {gold.get('frozen_at')})")
    print(f"Gold SHA-256: {gold_hash}")
    print(
        f"Scope       : {len(gold['documents'])} scored documents, "
        f"{len(gold['tasks'])} scored tasks, "
        f"{len(gold['observation_documents'])} observation documents"
    )
    print()

    print("Scored documents")
    _table(
        ["ID", "Course", "Format", "Tasks", "SHA-256"],
        [
            [
                document["id"],
                document["course"],
                document["format"],
                document["task_count"],
                str(document.get("sha256", ""))[:12],
            ]
            for document in gold["documents"]
        ],
    )
    print(f"Scored tasks: {len(gold['tasks'])}")
    print()

    print("Observation documents")
    _table(
        ["ID", "Course", "Format", "SHA-256"],
        [
            [
                document["id"],
                document["course"],
                document["format"],
                str(document.get("sha256", ""))[:12],
            ]
            for document in gold["observation_documents"]
        ],
    )
    print(f"Observation items: {len(gold['ambiguity_observations'])}")
    print()

    print("Validation checklist")
    print(
        f"[OK] {len(gold['documents'])} scored document files exist "
        "and their SHA-256 hashes match"
    )
    print(
        f"[OK] {len(gold['tasks'])} scored tasks; "
        "document task counts match the frozen table"
    )
    print("[OK] Date fields are valid for exact/range/unknown tasks")
    print(
        f"[OK] {len(gold['observation_documents'])} observation documents exist "
        "and their hashes match"
    )
    print(
        f"[OK] {len(gold['ambiguity_observations'])} ambiguity observation items "
        "are separate from scored tasks"
    )
    print("[OK] gold SHA-256 matches eval/gold.sha256")
    print("Validation checks: 6/6 passed")
    print()
    _rule()
    print("Result: CHECK PASSED")
    print(
        "Next  : running live evaluation"
        if live
        else "Next  : python eval/run_eval.py --live"
    )
    _rule("=")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CourseBrief evaluation set.")
    parser.add_argument(
        "--gold",
        type=Path,
        default=ROOT / "eval" / "gold.json",
        help="Path to gold.json.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "eval_reports",
        help="Directory for report.md and report.json (default: data/eval_reports).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Validate gold and dataset hashes without calling the model (default).",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Call the configured model and write an evaluation report.",
    )
    args = parser.parse_args()

    gold_path = args.gold.resolve()
    gold = load_gold(gold_path)
    base_dir = gold_path.parent
    errors = validate_gold(gold, base_dir)
    if errors:
        print("Gold validation failed:")
        for error in errors:
            print(f"- {error}")
        return 2
    if not gold_path.with_name("gold.sha256").exists():
        print(f"Missing gold hash file: {gold_path.with_name('gold.sha256')}")
        return 2
    expected_hash = gold_path.with_name("gold.sha256").read_text(
        encoding="utf-8"
    ).split()[0]
    actual_hash = file_sha256(gold_path)
    if actual_hash != expected_hash:
        print("Gold SHA-256 does not match gold.sha256.")
        return 2
    _print_check(gold, actual_hash, live=args.live)
    if not args.live:
        return 0
    return run(gold_path, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
