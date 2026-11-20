from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID

from ..schemas.agent import (
    Analysis, ConstraintEvaluation, Intent, LocationCondition, PlanDraft, RunStatus,
    SafeError, Source, UserConstraints, WorkflowStep,
)
from ..schemas.tools import RentalCandidate, ToolFailure, ToolSuccess


@dataclass(frozen=True)
class Strategy:
    area: LocationCondition
    limit: int

    def key(self, month: str | None) -> str:
        target = self.area.sigungu_code or "".join(self.area.label.casefold().split())
        return f"{target}:{month or 'previous'}:{self.limit}"


class AgentState(TypedDict, total=False):
    thread_id: str
    run_id: UUID
    user_message: str
    messages: list[dict[str, str]]
    intent: Intent
    intent_reason_summary: str
    analysis: Analysis
    user_constraints: UserConstraints
    contract_month: str | None
    changed_fields: list[str]
    missing_fields: list[str]
    workflow_steps: list[WorkflowStep]
    tool_results: dict[str, ToolSuccess | ToolFailure]
    tool_cache: dict[str, ToolSuccess | ToolFailure]
    candidates: list[RentalCandidate]
    constraint_results: list[ConstraintEvaluation]
    sources: list[Source]
    selected_candidate: RentalCandidate | None
    replan_count: int
    attempted_strategies: list[str]
    strategy: Strategy
    errors: list[SafeError]
    draft_plan: PlanDraft
    execution_status: RunStatus
    assistant_message: str
    rental_step_id: str
    rental_outcome: str
    warnings: list[str]
    successful_steps: list[str]
    failed_steps: list[str]
    replan_reason: str
