"""End-to-end orchestration for the Academic Deadline Brief core path.

Usage:
    python src/pipeline.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Allow running as a script from the repo root or the src/ directory.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from extract import extract_from_file  # noqa: E402
from prioritize import prioritize     # noqa: E402

SUPPORTED_EXTS = (".txt", ".md", ".csv")


def run(input_dir: Path, out_path: Path) -> dict:
    input_dir = Path(input_dir)
    all_tasks: list[dict] = []
    for f in sorted(input_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
            _, tasks = extract_from_file(f)
            all_tasks.extend(tasks)

    ordered, conflicts = prioritize(all_tasks)

    brief = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "tasks": ordered,
        "deadline_conflicts": conflicts,
        "counts": {
            "total": len(ordered),
            "dated": len([t for t in ordered if t.get("deadline")]),
            "flagged_missing": len([t for t in ordered if not t.get("deadline")]),
        },
    }

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8")
    return brief


def main() -> None:
    base = _HERE.parent
    inp = base / "data" / "sample_inputs"
    out = base / "data" / "sample_output" / "brief.json"
    brief = run(inp, out)

    c = brief["counts"]
    print(f"Extracted {c['total']} tasks "
          f"({c['dated']} dated, {c['flagged_missing']} flagged missing).")
    print(f"Weekly brief written to {out}\n")
    print("Upcoming tasks (by deadline):")
    for t in brief["tasks"]:
        dl = t.get("deadline") or "NO DEADLINE (flagged)"
        print(f"  [{t.get('priority', '-')}] {t['course']}: {t['task'][:55]} -> {dl}")

    if brief["deadline_conflicts"]:
        print("\nDeadline conflicts detected:")
        for a, b in brief["deadline_conflicts"]:
            print(f"  ! {a[:40]}  <>  {b[:40]}")


if __name__ == "__main__":
    main()
