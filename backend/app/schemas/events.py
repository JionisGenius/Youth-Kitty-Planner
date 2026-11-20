from uuid import UUID

from pydantic import AwareDatetime

from ..events.publisher import EventType
from .agent import Intent, RunStatus
from .tools import ToolModel


class EventRead(ToolModel):
    event_id: UUID
    run_id: UUID
    session_id: UUID
    sequence: int
    timestamp: AwareDatetime
    event_type: EventType
    node_name: str | None
    duration_ms: int | None
    payload: dict
    reason_summary: str | None = None


class RunRead(ToolModel):
    id: UUID
    session_id: UUID
    intent: Intent | None
    status: RunStatus
    replan_count: int
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    safe_error_code: str | None


class LogSummary(ToolModel):
    session_id: UUID
    run_count: int
    last_run_at: AwareDatetime


class LogList(ToolModel):
    items: list[LogSummary]
    total: int
    limit: int
    offset: int


class LogDetail(ToolModel):
    session_id: UUID
    runs: list[RunRead]
    events: list[EventRead]


class LogDeleted(ToolModel):
    session_id: UUID
    deleted_runs: int
    deleted_events: int

