from datetime import date, datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

T = TypeVar("T")
Code5 = Annotated[str, StringConstraints(pattern=r"^[0-9]{5}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[int, Field(ge=0, strict=True)]
ParcelNumber = Annotated[str, StringConstraints(pattern=r"^[0-9]{1,4}$")]
ErrorCode = Literal[
    "INVALID_ARGUMENT", "AUTH_FAILED", "RATE_LIMITED", "TIMEOUT", "NO_RESULT",
    "DATA_INCOMPLETE", "AMBIGUOUS_MATCH", "SCHEMA_MISMATCH", "SERVICE_UNAVAILABLE",
    "UNKNOWN_ERROR",
]


class ToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, allow_inf_nan=False)


class LocationInput(ToolModel):
    query: Text
    mode: Literal["ADDRESS", "KEYWORD"]
    limit: int = Field(default=5, ge=1, le=15, strict=True)


class Location(ToolModel):
    name: str
    external_place_id: str | None = None
    address_road: str | None = None
    address_lot: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    b_code: str | None = Field(default=None, pattern=r"^[0-9]{10}$")
    h_code: str | None = Field(default=None, pattern=r"^[0-9]{10}$")
    place_url: str | None = None


class LocationOutput(ToolModel):
    locations: list[Location]
    query_resolution: Literal["RESOLVED", "AMBIGUOUS", "NO_RESULT"]


class RentalInput(ToolModel):
    sigungu_code: Code5
    contract_month: str | None = Field(default=None, pattern=r"^[0-9]{4}(0[1-9]|1[0-2])$")
    max_deposit_krw: Money | None = None
    max_monthly_rent_krw: Money | None = None
    limit: int = Field(default=20, ge=1, le=100, strict=True)

    @field_validator("contract_month")
    @classmethod
    def check_year(cls, value: str | None) -> str | None:
        if value is not None:
            date(int(value[:4]), int(value[4:]), 1)
        return value


class RentalCandidate(ToolModel):
    candidate_id: str
    legal_dong: str | None
    lot_number: str | None
    building_name: str | None
    floor: int | None
    exclusive_area_m2: float | None = Field(ge=0)
    deposit_krw: Money | None
    monthly_rent_krw: Money | None
    contract_date: date | None
    raw_location_fields: dict[str, str]
    evidence_refs: list[str]


class RentalOutput(ToolModel):
    candidates: list[RentalCandidate]
    requested_period: str | None
    effective_period: str
    is_historical: Literal[True] = True
    count: int


class BuildingInput(ToolModel):
    candidate_id: Text
    sigungu_code: Code5
    bjdong_code: Code5 | None = None
    lot_address: Text | None = None
    parcel_type: Literal["0", "1", "2"] | None = None
    bun: ParcelNumber | None = None
    ji: ParcelNumber | None = None
    building_name: Text | None = None


class Building(ToolModel):
    building_registry_pk: str | None
    full_address: str | None
    building_name: str | None
    primary_use: str | None
    approval_date: date | None
    floor_count: int | None = Field(ge=0)
    household_count: int | None = Field(ge=0)


class MatchEvidence(ToolModel):
    matched_fields: list[str] = Field(default_factory=list)
    conflict_fields: list[str] = Field(default_factory=list)
    candidate_count: int = Field(default=0, ge=0)


class BuildingOutput(ToolModel):
    candidate_id: str
    match_status: Literal["MATCHED_BUILDING", "AMBIGUOUS", "NOT_FOUND", "UNKNOWN"]
    matched_building: Building | None = None
    match_evidence: MatchEvidence
    caveats: list[str]


class ToolMeta(ToolModel):
    provider: str
    fetched_at: datetime | None = None
    query_as_of: date | None = None
    effective_period: str | None = None
    is_cached: bool = False
    caveats: list[str] = Field(default_factory=list)


class ToolError(ToolModel):
    code: ErrorCode
    message: str
    retryable: bool = False
    details: dict[str, int | str] | None = None


class ToolSuccess(ToolModel, Generic[T]):
    ok: Literal[True] = True
    data: T
    error: None = None
    meta: ToolMeta


class ToolFailure(ToolModel):
    ok: Literal[False] = False
    data: None = None
    error: ToolError
    meta: ToolMeta


def tool_result_type(output_model: type[BaseModel]):
    return Annotated[ToolSuccess[output_model] | ToolFailure, Field(discriminator="ok")]

