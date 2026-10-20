"""Reproducibility / correctness test for the core path.

Run with:  python tests/test_pipeline.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE / "src"))

from pipeline import run  # noqa: E402


def test_core_path() -> dict:
    inp = _BASE / "data" / "sample_inputs"
    out = _BASE / "data" / "sample_output" / "brief_test.json"
    brief = run(inp, out)

    # 1) We extracted a sensible number of tasks from the bundled samples.
    assert brief["counts"]["total"] >= 6, "expected at least 6 tasks"

    # 2) Every task either has a valid ISO deadline or is explicitly flagged
    #    as missing — i.e. the system never fabricates a deadline.
    for t in brief["tasks"]:
        if t.get("deadline") is None:
            assert "flagged" in t.get("note", "").lower(), \
                f"undated task not flagged: {t['task']}"
        else:
            date.fromisoformat(t["deadline"])  # raises if malformed

    # 3) Conflict detection produced a list (and found the known 26/27 Oct clash).
    assert isinstance(brief["deadline_conflicts"], list)
    flat = [item for pair in brief["deadline_conflicts"] for item in pair]
    assert any("26 October" in x or "27 October" in x for x in flat), \
        "expected 26/27 Oct deadline conflict to be detected"

    print("TEST PASSED:", json.dumps(brief["counts"]))
    return brief


if __name__ == "__main__":
    test_core_path()
