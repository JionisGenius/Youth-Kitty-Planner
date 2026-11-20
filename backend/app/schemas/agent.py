from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .tools import Code5, ErrorCode, LocationInput, Money, RentalInput, Text, ToolModel

Intent = Literal["CREATE_PLAN", "UPDATE_CONSTRAINT", "FACT_QUERY", "EXPLAIN_PLAN", "GENERAL"]
RunStatus = Literal["RUNNING", "SUCCEEDED", "PARTIAL", "NEEDS_INPUT", "FAILED", "EXHAUSTED"]
Positive = Annotated[int, Field(ge=1, strict=True)]
ToolName = Literal["search_location", "search_rental_transactions", "get_building_detail"]


class LocationCondition(ToolModel):
    label: Text
    sido_code: str | None = None
    sigungu_code: Code5 | None = None
    bjdong_code: Code5 | None = None
    address: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    resolution_status: Literal["UNRESOLVED", "RESOLVED", "AMBIGUOUS"] = "UNRESOLVED"


class ConstraintPatch(ToolModel):
    work_location: LocationCondition | None = None
    residential_preferences: list[LocationCondition] | None = Field(default=None, max_length=8)
    allowed_alternative_areas: list[LocationCondition] | None = Field(default=None, max_length=8)
    max_deposit_krw: Money | None = None
    max_monthly_rent_krw: Money | None = None
    max_maintenance_fee_krw: Money | None = None
    planning_start_date: date | None = None
    preparation_days: Positive | None = None
    job_start_date: date | None = None
    max_commute_minutes: Positive | None = None
    transport_mode: Literal["TRANSIT", "WALKING", "DRIVING"] | None = None


class UserConstraints(ConstraintPatch):
    residential_preferences: list[LocationCondition] = Field(default_factory=list, max_length=8)
    allowed_alternative_areas: list[LocationCondition] = Field(default_factory=list, max_length=8)
    fixed_fields: set[str] = Field(default_factory=set)


class Analysis(ToolModel):
    intent: Intent
    patch: ConstraintPatch = Field(default_factory=ConstraintPatch)
    evidence: dict[str, str] = Field(default_factory=dict)
    contract_month: str | None = None
    fact_scope: Literal["LOCATION", "RENTAL", "BUILDING"] | None = None
    location: LocationInput | None = None

    @model_validator(mode="after")
    def check_month(self):
        RentalInput(sigungu_code="00000", contract_month=self.contract_month)
        return self


class WorkflowStep(ToolModel):
    step_id: str
    tool_name: ToolName
    args: dict
    depends_on: list[str] = Field(default_factory=list)
    purpose: str
    fixed_arg_names: list[str] = Field(default_factory=list)
    status: Literal["PENDING", "SUCCEEDED", "FAILED", "SKIPPED"] = "PENDING"


class SafeError(ToolModel):
    stage: str
    code: ErrorCode
    step_id: str | None = None


class ConstraintEvaluation(ToolModel):
    rule_code: str
    status: Literal["PASS", "FAIL", "UNKNOWN"]
    expected_value: int | str | None = None
    observed_value: int | str | None = None
    source_refs: list[str] = Field(default_factory=list)
    reason_code: str
    caveat: str | None = None


class Source(ToolModel):
    ref: str
    provider: str
    source_type: Literal["OFFICIAL_API"] = "OFFICIAL_API"
    observed_at: date | None = None
    fetched_at: datetime | None = None
    verification_status: Literal["PROVIDER_REPORTED"] = "PROVIDER_REPORTED"
    caveats: list[str] = Field(default_factory=list)


class TaskDraft(ToolModel):
    title: str
    description: str | None = None
    task_date: date | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    estimated_cost_krw: Money | None = None
    estimated_duration_minutes: Positive | None = None
    status: Literal["TODO"] = "TODO"


class PlanDraft(ToolModel):
    title: str
    category: Literal["INDEPENDENT_LIVING"] = "INDEPENDENT_LIVING"
    planning_start_date: date | None = None
    planning_end_date: date | None = None
    constraints: UserConstraints
    tasks: list[TaskDraft]
    evaluations: list[ConstraintEvaluation]
    source_refs: list[str]
    warnings: list[str]
    is_confirmed: Literal[False] = False
