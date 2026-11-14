import {
  deleteTask,
  getHealth,
  getState,
  getUploadText,
  pasteText,
  startExtractions,
  uploadFiles,
} from "./api.js";
import {
  addDays,
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
  failedUploads: $("#failed-uploads"),
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
  deleteModal: $("#delete-modal"),
  deleteModalTitle: $("#delete-modal-title"),
  deleteModalMessage: $("#delete-modal-message"),
  deleteCancel: $("#delete-cancel"),
  deleteConfirm: $("#delete-confirm"),
};

let state = { schema_version: 1, uploads: {}, tasks: [], duplicate_groups: {} };
let view = "month";
let currentMonth = startOfMonth(new Date());
let currentWeek = startOfWeek(new Date());
let popoverPinned = false;
let popoverTarget = null;
let popoverTaskId = null;
let popoverTaskSnapshot = null;
let deleteTargetTask = null;
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

function displayTasks(tasks = state.tasks) {
  const tasksById = new Map(tasks.map((task) => [task.id, task]));
  const groupById = new Map();
  for (const [primaryId, group] of Object.entries(state.duplicate_groups || {})) {
    const ids = Array.isArray(group.task_ids) ? group.task_ids : [];
    const sources = ids.map((id) => tasksById.get(id)).filter(Boolean);
    if (sources.length < 2) continue;
    const representative = tasksById.get(primaryId) || sources[0];
    for (const source of sources) {
      groupById.set(source.id, { representative, sources });
    }
  }
  return tasks.flatMap((task) => {
    const group = groupById.get(task.id);
    if (!group) return [task];
    if (group.representative.id !== task.id) return [];
    return [{ ...group.representative, sourceTasks: group.sources }];
  });
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
  const sourceCount = task.sourceTasks?.length || 1;
  chip.title = `${task.title} — ${taskDueLabel(task)}${sourceCount > 1 ? ` · ${sourceCount} sources` : ""}`;
  return chip;
}

function render() {
  renderFailedUploads();
  const pinnedAnchor = popoverPinned && popoverTarget ? {
    taskId: popoverTarget.dataset.taskId,
    weekDate: popoverTarget.dataset.weekDate,
  } : null;
  els.monthView.classList.toggle("is-hidden", view !== "month");
  els.weekView.classList.toggle("is-hidden", view !== "week");

  if (view === "month") {
    renderMonth();
    renderUndated(els.undatedSection, els.undatedList);
  } else {
    renderWeek();
    renderUndated(els.weekUndatedSection, els.weekUndatedList);
  }
  if (pinnedAnchor) {
    const panel = view === "month" ? els.monthView : els.weekView;
    const target = [...panel.querySelectorAll("[data-task-id], [data-week-date]")].find(
      (element) => pinnedAnchor.taskId
        ? element.dataset.taskId === pinnedAnchor.taskId
        : element.dataset.weekDate === pinnedAnchor.weekDate,
    );
    const currentTask = displayTasks().find((task) => task.id === popoverTaskId);
    if (target && (!popoverTaskId || currentTask)) {
      popoverTarget = target;
      if (currentTask && JSON.stringify(currentTask) !== popoverTaskSnapshot) {
        const expanded = els.popover.querySelector('[data-action="source"]')?.getAttribute("aria-expanded") === "true";
        const scrollTop = els.popover.querySelector(".popover-content")?.scrollTop || 0;
        showTaskPopover(currentTask, target, true);
        if (expanded) els.popover.querySelector('[data-action="source"]')?.click();
        const content = els.popover.querySelector(".popover-content");
        if (content) content.scrollTop = scrollTop;
      }
      positionPopover();
    } else {
      hidePopover();
    }
  }
}

function renderFailedUploads() {
  const failed = Object.entries(state.uploads).filter(
    ([, upload]) => upload.extraction.status === "failed",
  );
  els.failedUploads.classList.toggle("is-hidden", failed.length === 0);
  els.failedUploads.replaceChildren();
  for (const [uploadId, upload] of failed) {
    const row = document.createElement("div");
    const message = document.createElement("span");
    message.textContent = `${upload.original_filename || uploadId}: ${upload.extraction.error || strings.extractionFailed} `;
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "button button-small";
    retry.textContent = strings.retryExtraction;
    retry.addEventListener("click", async () => {
      retry.disabled = true;
      try {
        await runExtraction([uploadId]);
      } finally {
        retry.disabled = false;
      }
    });
    row.append(message, retry);
    els.failedUploads.append(row);
  }
}

function renderMonth() {
  els.monthLabel.textContent = formatMonth(currentMonth);
  els.monthGrid.replaceChildren();
  // Background refreshes (e.g. extraction polling) must not close a pinned bubble.
  if (!popoverPinned) hidePopover();

  const shownTasks = displayTasks();
  const today = new Date();

  for (const date of monthCells(currentMonth)) {
    const iso = toISODate(date);
    const dayTasks = tasksForDate(shownTasks, date);
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
  if (!popoverPinned) hidePopover();

  const shownTasks = displayTasks();
  const today = new Date();

  for (let index = 0; index < 7; index += 1) {
    const date = addDays(currentWeek, index);
    const dayTasks = tasksForDate(shownTasks, date);

    const header = document.createElement("div");
    header.className = "week-day-header";
    header.dataset.weekDate = toISODate(date);
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
        column.append(renderTaskCard(task));
      }
    }
    els.weekGrid.append(column);
  }
}

function renderTaskCard(task) {
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
  card.dataset.taskId = task.id;
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
  const undated = displayTasks().filter((task) => task.date_confidence === "unknown");

  section.classList.toggle("is-hidden", undated.length === 0);
  list.replaceChildren();

  for (const task of undated) {
    const chip = taskChip(task);
    chip.dataset.taskId = task.id;
    chip.tabIndex = 0;
    chip.setAttribute("role", "button");
    chip.textContent += ` · ${undatedReason(task)}`;
    const filenames = (task.sourceTasks || [task]).map(
      (source) => state.uploads[source.upload_id]?.original_filename || source.upload_id,
    );
    chip.title = `${undatedReason(task)} · ${filenames.join(", ")} · Click for details and sources`;
    chip.addEventListener("click", (event) => {
      event.stopPropagation();
      jumpToTaskWeek(task);
    });
    chip.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        jumpToTaskWeek(task);
      }
    });
    list.append(chip);
  }
}

function undatedReason(task) {
  const evidence = `${task.source_quote || ""} ${task.ambiguity_reason || ""}`;
  if (/\b(TBA|TBD|to be announced|to be determined)\b/i.test(evidence)) {
    return strings.deadlineTba;
  }
  if (/outside|invalid|conflict|ambiguous/i.test(task.ambiguity_reason || "")) {
    return strings.dateNeedsReview;
  }
  return strings.dateMissing;
}

function importedDateLabel(task) {
  const upload = state.uploads[task.upload_id];
  if (!upload?.uploaded_at) return "";
  return formatShortDate(upload.uploaded_at.slice(0, 10));
}

function showDatePopover(date, tasks, target) {
  if (popoverPinned) return;
  if (tasks.length === 0) {
    hidePopover();
    return;
  }

  const title = `<div class="popover-title">${escapeHtml(formatLongDate(date))}</div>`;
  const items = tasks
    .map((task) => {
      const priority = priorityFor(task);
      return `<li><strong>${escapeHtml(task.title)}</strong><br><span class="muted">${escapeHtml(
        task.course_name,
      )} · ${priority.bucket}</span></li>`;
    })
    .join("");
  showPopover(
    `<div class="popover-content">${title}<ul class="popover-list">${items}</ul></div>`,
    target,
    false,
  );
}

function showTaskPopover(task, target, pin) {
  if (popoverPinned && !pin) return;
  const priority = priorityFor(task);
  const sourceTasks = task.sourceTasks || [task];
  const isUndated = task.date_confidence === "unknown";
  const imported = isUndated ? importedDateLabel(task) : "";
  const importedNote = imported
    ? strings.importedOnNote.replace("{date}", imported)
    : strings.importedDateNote;

  const html = `
    <div class="popover-content">
      ${isUndated ? `<div class="popover-note">${escapeHtml(importedNote)}</div>` : ""}
      <div class="popover-head">
        <div class="popover-title">${escapeHtml(task.title)}</div>
        <span class="priority-badge priority-${priority.bucket.toLowerCase()}">${priority.bucket}</span>
      </div>
      <p class="popover-desc" title="${escapeHtml(
        task.description || strings.noDescription,
      )}">${escapeHtml(task.description || strings.noDescription)}</p>
      ${
        task.subtasks?.length
          ? `<div class="subtask-block">
               <div class="source-label">${strings.subtasks} (${task.subtasks.length})</div>
               <div class="subtask-summary" title="${escapeHtml(
                 task.subtasks
                   .map((item) =>
                     item.description ? `${item.label} — ${item.description}` : item.label,
                   )
                   .join("\n"),
               )}">${task.subtasks.map((item) => escapeHtml(item.label)).join(" · ")}</div>
             </div>`
          : ""
      }
      <div class="popover-meta" title="${escapeHtml(task.course_name)}">${strings.due}: ${escapeHtml(
        taskDueLabel(task),
      )} · ${escapeHtml(task.course_name)}</div>
      ${isUndated ? `<div class="popover-warning">${escapeHtml(undatedReason(task))}</div>` : ""}
      ${
        task.ambiguity_reason
          ? `<div class="popover-warning">${escapeHtml(task.ambiguity_reason)}</div>`
          : ""
      }
      <div class="source-block is-hidden">
        ${sourceTasks.map((sourceTask) => {
          const upload = state.uploads[sourceTask.upload_id];
          return `<section class="source-entry">
            <div class="source-label">${strings.source}: ${escapeHtml(
              upload?.original_filename || sourceTask.upload_id,
            )}</div>
            <blockquote class="source-quote">${escapeHtml(sourceTask.source_quote)}</blockquote>
            <button class="button button-small" type="button" data-upload-id="${escapeHtml(
              sourceTask.upload_id,
            )}">${strings.openFullText}</button>
          </section>`;
        }).join("")}
      </div>
    </div>
    <div class="popover-actions">
      <button class="button button-small" type="button" data-action="source" aria-expanded="false">${strings.showSource}</button>
      ${isUndated ? `<button class="button button-small button-danger" type="button" data-action="delete">${strings.delete}</button>` : ""}
    </div>
  `;

  showPopover(html, target, pin);
  popoverTaskId = task.id;
  popoverTaskSnapshot = JSON.stringify(task);

  const sourceButton = els.popover.querySelector('[data-action="source"]');
  const sourceBlock = els.popover.querySelector(".source-block");
  const content = els.popover.querySelector(".popover-content");

  sourceButton?.addEventListener("click", () => {
    if (!sourceBlock) return;
    const expanded = !sourceBlock.classList.toggle("is-hidden");
    sourceButton.textContent = expanded ? strings.hideSource : strings.showSource;
    sourceButton.setAttribute("aria-expanded", String(expanded));
    // Keep the bubble open while the user reads the expanded sources.
    popoverPinned = true;
    clearTimeout(hideTimer);
    content.scrollTop = expanded ? content.scrollHeight : 0;
    positionPopover();
  });

  els.popover.querySelector('[data-action="delete"]')?.addEventListener("click", () => {
    requestDeleteTask(task);
  });

  for (const fullTextButton of els.popover.querySelectorAll("[data-upload-id]")) {
    fullTextButton.addEventListener("click", async () => {
      const uploadId = fullTextButton.dataset.uploadId;
      const upload = state.uploads[uploadId];
      try {
        const text = await getUploadText(uploadId);
        openTextModal(upload?.original_filename || strings.sourceText, text);
      } catch (error) {
        showToast(`${strings.requestFailed}: ${error.message}`, "error");
      }
    });
  }
}

function showPopover(html, target, pin) {
  clearTimeout(hideTimer);
  popoverPinned = Boolean(pin);
  popoverTarget = target;
  popoverTaskId = null;
  popoverTaskSnapshot = null;
  els.popover.innerHTML = html;
  els.popover.classList.remove("is-hidden");
  const content = els.popover.querySelector(".popover-content");
  if (content) content.scrollTop = 0;
  positionPopover();
}

function positionPopover() {
  if (!popoverTarget) return;
  const rect = popoverTarget.getBoundingClientRect();
  // Always open above the target. Cap the height to the space above and to a
  // compact maximum, so the bubble does not cover the page or grow a scrollbar.
  const available = Math.max(80, rect.top - 16);
  els.popover.style.maxHeight = `${Math.min(available, 340)}px`;
  const popRect = els.popover.getBoundingClientRect();

  let left = rect.left;
  if (left + popRect.width > window.innerWidth - 8) {
    left = Math.max(8, window.innerWidth - popRect.width - 8);
  }
  const top = Math.max(8, rect.top - popRect.height - 8);
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
  popoverTarget = null;
  popoverTaskId = null;
  popoverTaskSnapshot = null;
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

function jumpToTaskWeek(task) {
  const upload = state.uploads[task.upload_id];
  const anchor = upload ? new Date(upload.uploaded_at) : new Date();
  currentWeek = startOfWeek(anchor);
  view = "week";
  hidePopover();
  render();
  requestAnimationFrame(() => {
    const iso = toISODate(anchor);
    const dayHeader = document.querySelector(`.week-day-header[data-week-date="${iso}"]`);
    if (dayHeader) {
      showTaskPopover(task, dayHeader, true);
    }

    const target = [...document.querySelectorAll("#week-undated-list .task-chip")].find(
      (chip) => chip.dataset.taskId === task.id,
    );
    if (!target) return;
    target.classList.add("is-flashing");
    setTimeout(() => target.classList.remove("is-flashing"), 1600);
  });
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
  closeDeleteModal();
}

function closeDeleteModal() {
  closeModal(els.deleteModal);
  deleteTargetTask = null;
}

function requestDeleteTask(task) {
  deleteTargetTask = task;
  els.deleteModalTitle.textContent = strings.deleteTitle;
  els.deleteModalMessage.textContent = `${task.title} — ${strings.deleteMessage}`;
  openModal(els.deleteModal);
  els.deleteCancel.focus();
}

async function confirmDeleteTask() {
  if (!deleteTargetTask) return;
  const taskId = deleteTargetTask.id;
  setButtonBusy(els.deleteConfirm, true);
  try {
    await deleteTask(taskId);
  } catch (error) {
    setButtonBusy(els.deleteConfirm, false);
    showToast(`${strings.deleteFailed}: ${error.message}`, "error");
    return;
  }
  setButtonBusy(els.deleteConfirm, false);
  closeDeleteModal();
  hidePopover();
  try {
    await refreshState();
  } catch (error) {
    showToast(`${strings.requestFailed}: ${error.message}`, "error");
    return;
  }
  showToast(strings.deleteDone, "ok");
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
    hidePopover();
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1);
    render();
  });
  els.nextMonth.addEventListener("click", () => {
    hidePopover();
    currentMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1);
    render();
  });
  els.prevWeek.addEventListener("click", () => {
    hidePopover();
    currentWeek = addDays(currentWeek, -7);
    render();
  });
  els.nextWeek.addEventListener("click", () => {
    hidePopover();
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
  els.deleteCancel.addEventListener("click", closeDeleteModal);
  els.deleteConfirm.addEventListener("click", confirmDeleteTask);
  els.uploadSubmit.addEventListener("click", handleUpload);
  els.pasteSubmit.addEventListener("click", handlePaste);
  els.pasteText.addEventListener("input", updatePasteCount);

  for (const modal of [els.uploadModal, els.pasteModal, els.textModal, els.deleteModal]) {
    modal.addEventListener("click", (event) => {
      if (event.target !== modal) return;
      if (modal === els.deleteModal) closeDeleteModal();
      else closeModal(modal);
    });
  }

  els.popover.addEventListener("mouseenter", () => clearTimeout(hideTimer));
  els.popover.addEventListener("mouseleave", scheduleHide);
  // Interacting with the bubble pins it so it does not vanish mid-click.
  els.popover.addEventListener("mousedown", () => {
    popoverPinned = true;
    clearTimeout(hideTimer);
  });
  els.popover.addEventListener("focusin", () => {
    popoverPinned = true;
    clearTimeout(hideTimer);
  });

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
  els.deleteCancel.textContent = strings.cancel;
  els.deleteConfirm.textContent = strings.delete;
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
