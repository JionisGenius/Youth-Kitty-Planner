from datetime import date, timezone
from typing import Annotated, Literal
import unicodedata
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints, field_validator, model_validator

from .agent import ConstraintEvaluation, Intent, PlanDraft, RunStatus, ToolName, UserConstraints
from .tools import ErrorCode, ToolModel

Category = Literal["FIRST_JOB_INDEPENDENCE"]
TaskStatus = Literal["TODO", "IN_PROGRESS", "DONE", "SKIPPED"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
NonNegative = Annotated[int, Field(strict=True, ge=0, le=2**63-1)]
Positive = Annotated[int, Field(strict=True, ge=1, le=2**63-1)]


def safe_strings(value, *, multiline=False):
    if isinstance(value, ToolModel):
        safe_strings(value.model_dump(), multiline=multiline)
    elif isinstance(value, (list, tuple, set)):
        for entry in value:
            safe_strings(entry, multiline=multiline)
    elif isinstance(value, dict):
        for entry in value.values():
            safe_strings(entry, multiline=multiline)
    elif isinstance(value, str):
        if len(value) > 4000 or any(
            unicodedata.category(char) in {"Cc", "Cs"} and (not multiline or char not in "\n\r\t")
            for char in value
        ):
            raise ValueError("Invalid string")


class ErrorDetail(ToolModel):
    code: str
    message: str
    request_id: UUID
    details: dict | None = None


class ApiError(ToolModel):
    error: ErrorDetail


class SessionCreated(ToolModel):
    access_token: str
    expires_at: AwareDatetime


class ChatRequest(ToolModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    base_plan_id: UUID | None = None

    @field_validator("message")
    @classmethod
    def check_controls(cls, value):
        safe_strings(value, multiline=True)
        return value


class ToolSummary(ToolModel):
    step_id: str
    tool_name: ToolName
    status: Literal["PENDING", "SUCCEEDED", "FAILED", "SKIPPED"]
    provider: str | None = None
    error_code: ErrorCode | None = None
    is_cached: bool = False
    result_count: int | None = None


class DraftRead(PlanDraft):
    # Keep the Phase 2 draft contract intact. The agreed public/save category is adapted here.
    category: Category = "FIRST_JOB_INDEPENDENCE"


class ChatResponse(ToolModel):
    run_id: UUID
    status: RunStatus
    intent: Intent | None
    assistant_message: str
    constraints: UserConstraints
    changed_fields: list[str]
    missing_fields: list[str]
    tool_summaries: list[ToolSummary]
    evaluations: list[ConstraintEvaluation]
    draft_plan: DraftRead | None = None
    warnings: list[str]
    replan_count: int


class TaskPatch(ToolModel):
    title: Title | None = None
    description: str | None = Field(default=None, max_length=2000)
    task_date: date | None = None
    scheduled_start_at: AwareDatetime | None = None
    scheduled_end_at: AwareDatetime | None = None
    status: TaskStatus | None = None
    estimated_cost_krw: NonNegative | None = None
    actual_cost_krw: NonNegative | None = None
    estimated_duration_minutes: Positive | None = None
    actual_duration_minutes: Positive | None = None
    sort_order: NonNegative | None = None

    @field_validator("title", "description")
    @classmethod
    def check_controls(cls, value):
        safe_strings(value)
        return value

    @field_validator("scheduled_start_at", "scheduled_end_at")
    @classmethod
    def to_utc(cls, value):
        if value is not None:
            try:
                return value.astimezone(timezone.utc)
            except OverflowError:
                raise ValueError("Invalid UTC time range") from None
        return None


class TaskInput(TaskPatch):
    title: Title
    task_date: date
    status: TaskStatus = "TODO"
    sort_order: NonNegative = 0

    @model_validator(mode="after")
    def check_interval(self):
        start, end = self.scheduled_start_at, self.scheduled_end_at
        if (start is None) != (end is None) or (start is not None and end <= start):
            raise ValueError("Expected a complete, increasing interval")
        return self


class AddTask(ToolModel):
    op: Literal["add"]
    task: TaskInput


class UpdateTask(ToolModel):
    op: Literal["update"]
    task_id: UUID
    changes: TaskPatch

    @model_validator(mode="after")
    def require_changes(self):
        if not self.changes.model_fields_set:
            raise ValueError("Empty task update")
        return self


class DeleteTask(ToolModel):
    op: Literal["delete"]
    task_id: UUID


TaskOperation = Annotated[AddTask | UpdateTask | DeleteTask, Field(discriminator="op")]


class PlanFields(ToolModel):
    title: Title | None = None
    constraints: UserConstraints | None = None

    @field_validator("title", "constraints")
    @classmethod
    def check_text(cls, value):
        safe_strings(value)
        return value


class PlanCreate(PlanFields):
    title: Title
    category: Category
    planning_start_date: date
    planning_end_date: date
    constraints: UserConstraints
    tasks: list[TaskInput] = Field(max_length=100)
    source_refs: list[UUID] | None = Field(default=None, max_length=500)
    generated_by_run_id: UUID | None = None

    @model_validator(mode="after")
    def check_plan(self):
        if self.planning_end_date < self.planning_start_date:
            raise ValueError("Invalid plan dates")
        if self.source_refs and self.generated_by_run_id is None:
            raise ValueError("Sources require an originating run")
        if self.source_refs and len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("Duplicate sources")
        return self


class PlanUpdate(PlanFields):
    expected_revision_number: Positive
    tasks: list[TaskOperation] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_changes(self):
        changes = self.model_fields_set - {"expected_revision_number"}
        if not changes or any(getattr(self, name) is None for name in changes):
            raise ValueError("Missing changes")
        targets = [op.task_id for op in self.tasks or [] if op.op != "add"]
        if len(targets) != len(set(targets)):
            raise ValueError("Duplicate task operation")
        return self


class TaskRead(TaskInput):
    id: UUID
    plan_id: UUID
    source_kind: Literal["RULE", "AI_DRAFT", "USER_EDIT", "FORK_IMPORT"]
    created_at: AwareDatetime
    updated_at: AwareDatetime


class SourceRead(ToolModel):
    id: UUID
    plan_id: UUID
    task_id: UUID | None
    source_type: str
    provider: str | None
    source_ref: str | None
    source_url: str | None
    fetched_at: AwareDatetime | None
    observed_at: AwareDatetime | None
    verification_status: str
    caveat: str | None


class EvaluationRead(ToolModel):
    id: UUID
    plan_id: UUID
    candidate_id: str | None
    rule_code: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    expected_value: int | str | None
    observed_value: int | str | None
    reason_code: str
    source_id: UUID | None
    checked_at: AwareDatetime


class PlanWarning(ToolModel):
    code: Literal["TIME_OVERLAP"]
    task_id: UUID
    conflicting_task_id: UUID
    conflicting_plan_id: UUID


class PlanRead(PlanFields):
    id: UUID
    session_id: UUID
    title: Title
    category: Category
    planning_start_date: date
    planning_end_date: date
    constraints: UserConstraints
    work_location_label: str | None
    generated_by_run_id: UUID | None
    revision_number: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    tasks: list[TaskRead]
    sources: list[SourceRead]
    evaluations: list[EvaluationRead]
    warnings: list[PlanWarning]


class PlanList(ToolModel):
    items: list[PlanRead]
    total: int
    limit: int
    offset: int

