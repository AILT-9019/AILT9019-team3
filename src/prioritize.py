"""Prioritization and deadline-conflict detection."""
from __future__ import annotations

from datetime import date


def prioritize(tasks: list[dict], today: date | None = None) -> tuple[list[dict], list[list[str]]]:
    """Order tasks by deadline and flag conflicts.

    Returns (ordered_tasks, conflicts) where conflicts is a list of
    [task_a, task_b] pairs whose deadlines fall within 2 days of each other.
    """
    today = today or date.today()

    dated = [t for t in tasks if t.get("deadline")]
    undated = [t for t in tasks if not t.get("deadline")]

    for t in dated:
        dl = date.fromisoformat(t["deadline"])
        days_left = (dl - today).days
        t["days_left"] = days_left
        if days_left < 7:
            t["priority"] = "High"
        elif days_left < 14:
            t["priority"] = "Medium"
        else:
            t["priority"] = "Low"

    dated.sort(key=lambda t: t["deadline"])
    ordered = dated + undated

    conflicts: list[list[str]] = []
    for i in range(len(dated) - 1):
        a, b = dated[i], dated[i + 1]
        gap = (date.fromisoformat(b["deadline"]) - date.fromisoformat(a["deadline"])).days
        if 0 <= gap <= 2:
            conflicts.append([a["task"], b["task"]])

    return ordered, conflicts
