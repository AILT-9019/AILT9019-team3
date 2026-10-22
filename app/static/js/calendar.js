export const TYPE_WEIGHT = {
  exam: 20,
  project: 18,
  assignment: 15,
  quiz: 12,
  presentation: 10,
  reading: 5,
  other: 8,
};

const DAY_MS = 86400000;

export function toISODate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseISODate(value) {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function startOfWeek(date) {
  const day = date.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + diff);
}

export function addDays(date, days) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

export function sameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function formatMonth(date) {
  return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" }).format(date);
}

export function formatWeekRange(start) {
  const end = addDays(start, 6);
  const fmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
  return `${fmt.format(start)} – ${fmt.format(end)}`;
}

export function formatShortDate(value) {
  const date = parseISODate(value);
  if (!date) return "";
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(date);
}

export function formatLongDate(date) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(date);
}

export function formatWeekday(date) {
  return new Intl.DateTimeFormat("en-GB", { weekday: "short" }).format(date);
}

export function monthCells(date) {
  const start = startOfWeek(startOfMonth(date));
  return Array.from({ length: 42 }, (_, index) => addDays(start, index));
}

export function taskDate(task) {
  if (task.date_confidence === "exact" && task.due_date) {
    return parseISODate(task.due_date);
  }
  if (task.date_confidence === "range" && task.due_range_start) {
    return parseISODate(task.due_range_start);
  }
  return null;
}

export function tasksForDate(tasks, date) {
  const iso = toISODate(date);
  return tasks.filter((task) => {
    if (task.date_confidence === "exact" && task.due_date) {
      return task.due_date === iso;
    }
    if (task.date_confidence === "range" && task.due_range_start) {
      return task.due_range_start === iso;
    }
    return false;
  });
}

export function taskDueLabel(task) {
  if (task.date_confidence === "exact" && task.due_date) {
    return formatShortDate(task.due_date);
  }
  if (task.date_confidence === "range" && task.due_range_start && task.due_range_end) {
    return `${formatShortDate(task.due_range_start)} – ${formatShortDate(task.due_range_end)} (estimated)`;
  }
  return "No deadline";
}

function dayNumber(date) {
  return Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / DAY_MS);
}

export function priorityFor(task, today = new Date()) {
  const date = taskDate(task);
  let urgency = 0;
  if (date) {
    const daysLeft = dayNumber(date) - dayNumber(today);
    if (daysLeft < 0) urgency = 50;
    else if (daysLeft <= 1) urgency = 45;
    else if (daysLeft <= 3) urgency = 35;
    else if (daysLeft <= 7) urgency = 25;
    else if (daysLeft <= 14) urgency = 15;
    else urgency = 5;
  }

  const typeWeight = TYPE_WEIGHT[task.task_type] ?? 8;
  const penalty = task.date_confidence === "exact" ? 0 : 5;
  const score = urgency + typeWeight - penalty;
  const bucket = score >= 55 ? "P0" : score >= 40 ? "P1" : "P2";
  return { score, bucket };
}

export function isEstimated(task) {
  return task.date_confidence !== "exact";
}

// Kept for the evaluation harness; the UI does not display conflict warnings.
export function conflictDates(tasks) {
  const dated = tasks.filter(
    (task) => task.date_confidence === "exact" && task.due_date,
  );
  const conflicts = new Map();

  for (let i = 0; i < dated.length; i += 1) {
    for (let j = i + 1; j < dated.length; j += 1) {
      const left = dated[i];
      const right = dated[j];
      const leftDate = parseISODate(left.due_date);
      const rightDate = parseISODate(right.due_date);
      if (!leftDate || !rightDate) continue;

      const diff = Math.abs(dayNumber(leftDate) - dayNumber(rightDate));
      const weights = (TYPE_WEIGHT[left.task_type] ?? 8) + (TYPE_WEIGHT[right.task_type] ?? 8);
      const highImportance = [left.task_type, right.task_type].some((type) =>
        ["exam", "project", "assignment"].includes(type),
      );

      if ((diff === 0 && highImportance) || (diff <= 2 && weights >= 30)) {
        conflicts.set(left.due_date, "Deadline conflict");
        conflicts.set(right.due_date, "Deadline conflict");
      }
    }
  }

  return conflicts;
}
