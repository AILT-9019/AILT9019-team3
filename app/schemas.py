from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1


class TaskType(str, Enum):
    assignment = "assignment"
    quiz = "quiz"
    exam = "exam"
    project = "project"
    reading = "reading"
    presentation = "presentation"
    other = "other"


class DateConfidence(str, Enum):
    exact = "exact"
    range = "range"
    unknown = "unknown"


class SourceType(str, Enum):
    upload = "upload"
    paste = "paste"


class ExtractionStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Subtask(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class ExtractedTask(BaseModel):
    """Fields returned by the LLM; also the persisted task shape."""

    model_config = ConfigDict(extra="ignore")

    course_name: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    task_type: TaskType
    due_date: date | None = None
    due_range_start: date | None = None
    due_range_end: date | None = None
    date_confidence: DateConfidence
    ambiguity_reason: str | None = Field(default=None, max_length=500)
    source_quote: str = Field(min_length=1, max_length=1000)
    subtasks: list[Subtask] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_deadline(self) -> ExtractedTask:
        if self.date_confidence == DateConfidence.exact:
            if self.due_date is None:
                raise ValueError("exact deadline requires due_date")
            if self.due_range_start is not None or self.due_range_end is not None:
                raise ValueError("exact deadline must not have a range")
        elif self.date_confidence == DateConfidence.range:
            if self.due_date is not None:
                raise ValueError("range deadline must not have due_date")
            if self.due_range_start is None or self.due_range_end is None:
                raise ValueError("range deadline requires both bounds")
            if self.due_range_start > self.due_range_end:
                raise ValueError("due_range_start must be <= due_range_end")
        else:
            if any(
                value is not None
                for value in (self.due_date, self.due_range_start, self.due_range_end)
            ):
                raise ValueError("unknown deadline must not contain dates")
        return self


class TaskRecord(ExtractedTask):
    id: str
    upload_id: str


class ExtractionInfo(BaseModel):
    model: str | None = None
    prompt_version: str = "v1"
    status: ExtractionStatus = ExtractionStatus.pending
    error: str | None = None


class UploadRecord(BaseModel):
    uploaded_at: datetime
    source_type: SourceType
    original_filename: str | None = None
    text_file: str
    original_file: str | None = None
    course_hint: str | None = None
    extraction: ExtractionInfo = Field(default_factory=ExtractionInfo)


class DuplicateGroup(BaseModel):
    task_ids: list[str] = Field(min_length=2)
    source: Literal["ai", "exact"] = "ai"


class DbState(BaseModel):
    schema_version: int = SCHEMA_VERSION
    uploads: dict[str, UploadRecord] = Field(default_factory=dict)
    tasks: list[TaskRecord] = Field(default_factory=list)
    duplicate_groups: dict[str, DuplicateGroup] = Field(default_factory=dict)


class ExtractionResponse(BaseModel):
    tasks: list[ExtractedTask] = Field(default_factory=list)


class PasteRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    course_hint: str | None = Field(default=None, max_length=120)
    text: str = Field(min_length=1, max_length=200000)


class ExtractionRequest(BaseModel):
    upload_ids: list[str] | None = None


class UploadItemResult(BaseModel):
    filename: str
    upload_id: str | None = None
    error: str | None = None


class UploadBatchResponse(BaseModel):
    items: list[UploadItemResult] = Field(default_factory=list)


class ExtractionStartResponse(BaseModel):
    upload_ids: list[str] = Field(default_factory=list)
