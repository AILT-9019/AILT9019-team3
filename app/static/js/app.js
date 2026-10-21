import {
  getHealth,
  getState,
  getUploadText,
  pasteText,
  startExtractions,
  uploadFiles,
} from "./api.js";
import {
  addDays,
  conflictDates,
  formatLongDate,
  formatMonth,
  formatShortDate,
  formatWeekRange,
  formatWeekday,
  isEstimated,
  monthCells,
  priorityFor,
  sameDay,
  startOfMonth,
  startOfWeek,
  taskDueLabel,
  tasksForDate,
  toISODate,
} from "./calendar.js";
import { strings } from "./strings.js";

const $ = (selector) => document.querySelector(selector);

const els = {
  monthView: $("#month-view"),
  weekView: $("#week-view"),
  monthLabel: $("#month-label"),
  weekLabel: $("#week-label"),
  monthGrid: $("#month-grid"),
  weekHeader: $("#week-header"),
  weekGrid: $("#week-grid"),
  prevMonth: $("#prev-month"),
  nextMonth: $("#next-month"),
  prevWeek: $("#prev-week"),
  nextWeek: $("#next-week"),
  backToMonth: $("#back-to-month"),
  undatedSection: $("#undated-section"),
  undatedList: $("#undated-list"),
  weekUndatedSection: $("#week-undated-section"),
  weekUndatedList: $("#week-undated-list"),
  popover: $("#popover"),
  toast: $("#toast"),
  statusBar: $("#status-bar"),
  uploadButton: $("#upload-button"),
  pasteButton: $("#paste-button"),
  uploadModal: $("#upload-modal"),
  uploadModalTitle: $("#upload-modal-title"),
  uploadFilesInput: $("#upload-files"),
  uploadCourse: $("#upload-course"),
  uploadSubmit: $("#upload-submit"),
  uploadCancel: $("#upload-cancel"),
  uploadResults: $("#upload-results"),
  pasteModal: $("#paste-modal"),
  pasteModalTitle: $("#paste-modal-title"),
  pasteTitle: $("#paste-title"),
  pasteCourse: $("#paste-course"),
  pasteText: $("#paste-text"),
  pasteCount: $("#paste-count"),
  pasteSubmit: $("#paste-submit"),
  pasteCancel: $("#paste-cancel"),
  textModal: $("#text-modal"),
  textModalTitle: $("#text-modal-title"),
  textModalBody: $("#text-modal-body"),
  textModalClose: $("#text-modal-close"),
};

let state = { schema_version: 1, uploads: {}, tasks: [] };
let view = "month";
let currentMonth = startOfMonth(new Date());
let currentWeek = startOfWeek(new Date());
let popoverPinned = false;
let hideTimer = null;
let statusTimer = null;
let toastTimer = null;

const ESCAPES = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function priorityClass(task) {
  return `priority-${priorityFor(task).bucket.toLowerCase()}`;
}

function taskChip(task) {
  const chip = document.createElement("div");
  chip.className = [
    "task-chip",
    priorityClass(task),
    isEstimated(task) ? "is-estimated" : "",
  ]
    .filter(Boolean)
    .join(" ");
  chip.textContent = `${task.course_name} · ${task.title}`;
  chip.title = `${task.title} — ${taskDueLabel(task)}`;
  return chip;
}

function render() {
  els.monthView.classList.toggle("is-hidden", view !== "month");
  els.weekView.classList.toggle("is-hidden", view !== "week");

  if (view === "month") {
    renderMonth();
    renderUndated(els.undatedSection, els.undatedList);
  } else {
    renderWeek();
    renderUndated(els.weekUndatedSection, els.weekUndatedList);
  }
}

function renderMonth() {
  els.monthLabel.textContent = formatMonth(currentMonth);
  els.monthGrid.replaceChildren();
  hidePopover();

  const conflicts = conflictDates(state.tasks);
  const today = new Date();

  for (const date of monthCells(currentMonth)) {
    const iso = toISODate(date);
    const dayTasks = tasksForDate(state.tasks, date);
    const cell = document.createElement("div");
    cell.className = "day-cell";
    cell.tabIndex = 0;
    cell.setAttribute("role", "button");
    cell.setAttribute("aria-label", `${formatLongDate(date)}, ${dayTasks.length} tasks`);
    cell.dataset.date = iso;

    if (date.getMonth() !== currentMonth.getMonth()) {
      cell.classList.add("is-outside");
    }
    if (sameDay(date, today)) {
      cell.classList.add("is-today");
    }

    const header = document.createElement("div");
    header.className = "day-number";
    const number = document.createElement("span");
    number.textContent = String(date.getDate());
    header.append(number);

    if (conflicts.has(iso)) {
      const badge = document.createElement("span");
      badge.className = "conflict-badge";
      badge.textContent = "⚠";
      badge.title = conflicts.get(iso);
      header.append(badge);
    }
    cell.append(header);

    for (const task of dayTasks.slice(0, 3)) {
      cell.append(taskChip(task));
    }
    if (dayTasks.length > 3) {
      const more = document.createElement("div");
      more.className = "task-chip more-chip";
      more.textContent = `+${dayTasks.length - 3} more`;
      cell.append(more);
    }

    cell.addEventListener("mouseenter", () => showDatePopover(date, dayTasks, cell));
    cell.addEventListener("mouseleave", scheduleHide);
    cell.addEventListener("focus", () => showDatePopover(date, dayTasks, cell));
    cell.addEventListener("blur", scheduleHide);
    cell.addEventListener("click", () => openWeek(date));
    cell.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openWeek(date);
      }
    });

    els.monthGrid.append(cell);
  }
}

function renderWeek() {
  els.weekLabel.textContent = formatWeekRange(currentWeek);
  els.weekHeader.replaceChildren();
  els.weekGrid.replaceChildren();
  hidePopover();

  const conflicts = conflictDates(state.tasks);
  const today = new Date();

  for (let index = 0; index < 7; index += 1) {
    const date = addDays(currentWeek, index);
    const dayTasks = tasksForDate(state.tasks, date);

    const header = document.createElement("div");
    header.className = "week-day-header";
    if (sameDay(date, today)) {
      header.classList.add("is-today");
    }
    const weekday = document.createElement("span");
    weekday.className = "weekday";
    weekday.textContent = formatWeekday(date);
    const weekdate = document.createElement("span");
    weekdate.className = "weekdate";
    weekdate.textContent = formatShortDate(toISODate(date));
    header.append(weekday, weekdate);
    els.weekHeader.append(header);

    const column = document.createElement("div");
    column.className = "week-column";

    if (dayTasks.length === 0) {
      const empty = document.createElement("div");
      empty.className = "week-empty";
      empty.textContent = strings.noTasks;
      column.append(empty);
    } else {
      for (const task of dayTasks) {
        column.append(renderTaskCard(task, conflicts));
      }
    }
    els.weekGrid.append(column);
  }
}

function renderTaskCard(task, conflicts) {
  const priority = priorityFor(task);
  const card = document.createElement("div");
  card.className = [
    "task-card",
    `priority-${priority.bucket.toLowerCase()}`,
    isEstimated(task) ? "is-estimated" : "",
  ]
    .filter(Boolean)
    .join(" ");
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `${task.title}, ${taskDueLabel(task)}`);

  const title = document.createElement("div");
  title.className = "task-card-title";
  title.textContent = task.title;

  const meta = document.createElement("div");
  meta.className = "task-card-meta";

  const course = document.createElement("span");
  course.textContent = task.course_name;
  meta.append(course);

  const due = document.createElement("span");
  due.textContent = taskDueLabel(task);
  if (isEstimated(task)) {
    due.classList.add("estimated-label");
  }
  meta.append(due);

  const badge = document.createElement("span");
  badge.className = `priority-badge priority-${priority.bucket.toLowerCase()}`;
  badge.textContent = priority.bucket;
  meta.append(badge);

  if (task.due_date && conflicts.has(task.due_date)) {
    const conflict = document.createElement("span");
    conflict.className = "conflict-badge";
    conflict.textContent = "⚠";
    conflict.title = conflicts.get(task.due_date);
    meta.append(conflict);
  }

  card.append(title, meta);

  card.addEventListener("mouseenter", () => showTaskPopover(task, card, false));
  card.addEventListener("mouseleave", scheduleHide);
  card.addEventListener("focus", () => showTaskPopover(task, card, false));
  card.addEventListener("blur", scheduleHide);
  card.addEventListener("click", (event) => {
    event.stopPropagation();
    showTaskPopover(task, card, true);
  });
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      showTaskPopover(task, card, true);
    }
  });

  return card;
}

function renderUndated(section, list) {
  const undated = state.tasks.filter((task) => task.date_confidence === "unknown");
  section.classList.toggle("is-hidden", undated.length === 0);
  list.replaceChildren();

  for (const task of undated) {
    const chip = taskChip(task);
    chip.tabIndex = 0;
    chip.setAttribute("role", "button");
    chip.addEventListener("mouseenter", () => showTaskPopover(task, chip, false));
    chip.addEventListener("mouseleave", scheduleHide);
    chip.addEventListener("focus", () => showTaskPopover(task, chip, false));
    chip.addEventListener("blur", scheduleHide);
    chip.addEventListener("click", (event) => {
      event.stopPropagation();
      showTaskPopover(task, chip, true);
    });
    chip.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        showTaskPopover(task, chip, true);
      }
    });
    list.append(chip);
  }
}

function showDatePopover(date, tasks, target) {
  const title = `<div class="popover-title">${escapeHtml(formatLongDate(date))}</div>`;
  if (tasks.length === 0) {
    showPopover(`${title}<p class="muted">${strings.noTasks}</p>`, target, false);
    return;
  }

  const items = tasks
    .map((task) => {
      const priority = priorityFor(task);
      return `<li><strong>${escapeHtml(task.title)}</strong><br><span class="muted">${escapeHtml(
        task.course_name,
      )} · ${priority.bucket}</span></li>`;
    })
    .join("");
  showPopover(`${title}<ul class="popover-list">${items}</ul>`, target, false);
}

function showTaskPopover(task, target, pin) {
  const priority = priorityFor(task);
  const upload = state.uploads[task.upload_id];
  const conflicts = conflictDates(state.tasks);
  const conflict = task.due_date && conflicts.has(task.due_date);

  const html = `
    <div class="popover-head">
      <div>
        <div class="popover-title">${escapeHtml(task.title)}</div>
        <div class="popover-subtitle">${escapeHtml(task.course_name)}</div>
      </div>
      <span class="priority-badge priority-${priority.bucket.toLowerCase()}">${priority.bucket}</span>
    </div>
    <p class="popover-desc">${escapeHtml(task.description || strings.noDescription)}</p>
    <div class="popover-meta">${strings.due}: ${escapeHtml(taskDueLabel(task))}</div>
    ${
      task.ambiguity_reason
        ? `<div class="popover-warning">${escapeHtml(task.ambiguity_reason)}</div>`
        : ""
    }
    ${conflict ? `<div class="popover-warning">⚠ ${escapeHtml(strings.conflict)}</div>` : ""}
    <div class="popover-actions">
      <button class="button button-small" type="button" data-action="source">${strings.showSource}</button>
      <button class="button button-small" type="button" data-action="full-text">${strings.openFullText}</button>
    </div>
    <div class="source-block is-hidden">
      <div class="source-label">${strings.source}: ${escapeHtml(
        upload?.original_filename || task.upload_id,
      )}</div>
      <blockquote class="source-quote">${escapeHtml(task.source_quote)}</blockquote>
    </div>
  `;

  showPopover(html, target, pin);

  const sourceButton = els.popover.querySelector('[data-action="source"]');
  const fullTextButton = els.popover.querySelector('[data-action="full-text"]');
  const sourceBlock = els.popover.querySelector(".source-block");

  sourceButton?.addEventListener("click", () => {
    sourceBlock?.classList.toggle("is-hidden");
  });

  fullTextButton?.addEventListener("click", async () => {
    try {
      const text = await getUploadText(task.upload_id);
      openTextModal(upload?.original_filename || strings.sourceText, text);
    } catch (error) {
      showToast(`${strings.requestFailed}: ${error.message}`, "error");
    }
  });
}

function showPopover(html, target, pin) {
  clearTimeout(hideTimer);
  popoverPinned = Boolean(pin);
  els.popover.innerHTML = html;
  els.popover.classList.remove("is-hidden");
  els.popover.scrollTop = 0;

  const rect = target.getBoundingClientRect();
  const popRect = els.popover.getBoundingClientRect();
  let left = rect.left;
  if (left + popRect.width > window.innerWidth - 8) {
    left = Math.max(8, window.innerWidth - popRect.width - 8);
  }
  let top = rect.bottom + 8;
  if (top + popRect.height > window.innerHeight - 8) {
    top = Math.max(8, rect.top - popRect.height - 8);
  }
  els.popover.style.left = `${Math.max(8, left)}px`;
  els.popover.style.top = `${top}px`;
}

function scheduleHide() {
  if (popoverPinned) return;
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    if (!popoverPinned) hidePopover();
  }, 180);
}

function hidePopover() {
  clearTimeout(hideTimer);
  popoverPinned = false;
  els.popover.classList.add("is-hidden");
  els.popover.innerHTML = "";
}

function openWeek(date) {
  currentWeek = startOfWeek(date);
  view = "week";
  hidePopover();
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openModal(element) {
  element.classList.remove("is-hidden");
}

function closeModal(element) {
  element.classList.add("is-hidden");
}

function closeAllModals() {
  closeModal(els.uploadModal);
  closeModal(els.pasteModal);
  closeModal(els.textModal);
}

function setStatus(text, kind = "") {
  clearTimeout(statusTimer);
  els.statusBar.textContent = text;
  els.statusBar.className = `status-bar${kind ? ` is-${kind}` : ""}`;
  els.statusBar.classList.remove("is-hidden");
  if (kind !== "busy") {
    statusTimer = setTimeout(() => els.statusBar.classList.add("is-hidden"), 4000);
  }
}

function showToast(text, kind = "") {
  clearTimeout(toastTimer);
  els.toast.textContent = text;
  els.toast.className = `toast${kind === "error" ? " is-error" : ""}`;
  els.toast.classList.remove("is-hidden");
  toastTimer = setTimeout(() => els.toast.classList.add("is-hidden"), 4500);
}

function openTextModal(title, text) {
  els.textModalTitle.textContent = title;
  els.textModalBody.textContent = text;
  openModal(els.textModal);
}

function setButtonBusy(button, busy) {
  button.disabled = busy;
}

async function refreshState() {
  state = await getState();
  render();
}

async function runExtraction(uploadIds) {
  if (!uploadIds.length) return;
  try {
    await startExtractions(uploadIds);
    setStatus(strings.extracting, "busy");
    const deadline = Date.now() + 180000;

    while (Date.now() < deadline) {
      await sleep(1000);
      state = await getState();
      render();

      const statuses = uploadIds.map(
        (uploadId) => state.uploads[uploadId]?.extraction.status || "failed",
      );
      const finished = statuses.filter(
        (status) => status !== "pending" && status !== "running",
      ).length;

      if (finished === statuses.length) {
        const failed = statuses.filter((status) => status === "failed").length;
        if (failed) {
          const firstFailed = uploadIds
            .map((uploadId) => state.uploads[uploadId])
            .find((upload) => upload?.extraction.status === "failed");
          setStatus(`${failed} ${strings.extractionFailed}`, "error");
          showToast(
            `${strings.extractionFailed}: ${
              firstFailed?.extraction.error || "unknown error"
            }`,
            "error",
          );
        } else {
          setStatus(strings.extractionDone, "ok");
        }
        return;
      }
      setStatus(`${strings.extracting} (${finished}/${statuses.length})`, "busy");
    }
    setStatus(strings.extractionTimeout, "error");
  } catch (error) {
    setStatus(`${strings.requestFailed}: ${error.message}`, "error");
    showToast(`${strings.requestFailed}: ${error.message}`, "error");
  }
}

async function handleUpload() {
  const files = els.uploadFilesInput.files;
  if (!files || files.length === 0) {
    showToast(strings.uploadNoFiles);
    return;
  }

  setButtonBusy(els.uploadSubmit, true);
  els.uploadResults.replaceChildren();
  try {
    const result = await uploadFiles(files, els.uploadCourse.value.trim());
    const uploadIds = [];

    for (const item of result.items) {
      const row = document.createElement("div");
      row.className = `upload-result${item.error ? " is-error" : ""}`;
      row.textContent = item.error
        ? `${item.filename}: ${item.error}`
        : `${item.filename}: ${strings.uploaded}`;
      els.uploadResults.append(row);
      if (item.upload_id && !item.error) {
        uploadIds.push(item.upload_id);
      }
    }

    const failedItems = result.items.filter((item) => item.error);
    if (failedItems.length) {
      showToast(`${failedItems.length} file(s) failed: ${failedItems[0].error}`, "error");
    }

    if (uploadIds.length) {
      els.uploadFilesInput.value = "";
      els.uploadCourse.value = "";
      closeModal(els.uploadModal);
      await runExtraction(uploadIds);
    }
  } catch (error) {
    showToast(`${strings.uploadFailed}: ${error.message}`, "error");
  } finally {
    setButtonBusy(els.uploadSubmit, false);
  }
}

async function handlePaste() {
  const text = els.pasteText.value.trim();
  if (!text) {
    showToast(strings.pasteEmpty);
    return;
  }
  if (text.length > 200000) {
    showToast(strings.pasteTooLong);
    return;
  }

  setButtonBusy(els.pasteSubmit, true);
  try {
    const result = await pasteText({
      title: els.pasteTitle.value.trim(),
      courseHint: els.pasteCourse.value.trim(),
      text,
    });
    const item = result.items[0];
    if (!item?.upload_id) {
      throw new Error(item?.error || strings.pasteFailed);
    }
    els.pasteTitle.value = "";
    els.pasteCourse.value = "";
    els.pasteText.value = "";
    updatePasteCount();
    closeModal(els.pasteModal);
    await runExtraction([item.upload_id]);
  } catch (error) {
    showToast(`${strings.pasteFailed}: ${error.message}`, "error");
  } finally {
    setButtonBusy(els.pasteSubmit, false);
  }
}

function updatePasteCount() {
  els.pasteCount.textContent = `${els.pasteText.value.length} ${strings.characters}`;
}

function bindEvents() {
  els.prevMonth.addEventListener("click", () => {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1);
    render();
  });
  els.nextMonth.addEventListener("click", () => {
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);
    render();
  });
  els.prevWeek.addEventListener("click", () => {
    currentWeek = addDays(currentWeek, -7);
    render();
  });
  els.nextWeek.addEventListener("click", () => {
    currentWeek = addDays(currentWeek, 7);
    render();
  });
  els.backToMonth.addEventListener("click", () => {
    view = "month";
    currentMonth = startOfMonth(currentWeek);
    hidePopover();
    render();
  });

  els.uploadButton.addEventListener("click", () => {
    els.uploadResults.replaceChildren();
    openModal(els.uploadModal);
  });
  els.pasteButton.addEventListener("click", () => {
    updatePasteCount();
    openModal(els.pasteModal);
  });
  els.uploadCancel.addEventListener("click", () => closeModal(els.uploadModal));
  els.pasteCancel.addEventListener("click", () => closeModal(els.pasteModal));
  els.textModalClose.addEventListener("click", () => closeModal(els.textModal));
  els.uploadSubmit.addEventListener("click", handleUpload);
  els.pasteSubmit.addEventListener("click", handlePaste);
  els.pasteText.addEventListener("input", updatePasteCount);

  for (const modal of [els.uploadModal, els.pasteModal, els.textModal]) {
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeModal(modal);
    });
  }

  els.popover.addEventListener("mouseenter", () => clearTimeout(hideTimer));
  els.popover.addEventListener("mouseleave", scheduleHide);

  document.addEventListener("click", (event) => {
    if (els.popover.classList.contains("is-hidden")) return;
    if (event.target.closest("#popover")) return;
    if (event.target.closest(".task-card, .task-chip")) return;
    hidePopover();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hidePopover();
      closeAllModals();
    }
  });

  window.addEventListener("resize", hidePopover);
}

async function boot() {
  document.title = strings.appName;
  els.uploadButton.textContent = strings.upload;
  els.pasteButton.textContent = strings.paste;
  els.uploadSubmit.textContent = strings.uploadSubmit;
  els.pasteSubmit.textContent = strings.pasteSubmit;
  els.uploadCancel.textContent = strings.cancel;
  els.pasteCancel.textContent = strings.cancel;
  els.textModalClose.textContent = strings.close;
  els.uploadModalTitle.textContent = strings.uploadTitle;
  els.pasteModalTitle.textContent = strings.pasteTitle;
  els.textModalTitle.textContent = strings.sourceText;
  document.querySelector(".calendar-subtitle").textContent = strings.monthSubtitle;

  bindEvents();
  updatePasteCount();

  try {
    await getHealth();
    state = await getState();
    render();
  } catch (error) {
    showToast(`${strings.requestFailed}: ${error.message}`, "error");
    render();
  }
}

boot();
