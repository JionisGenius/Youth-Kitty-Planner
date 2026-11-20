from datetime import date, datetime, timezone
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
import pytest

from backend.app.agents.graph import BUILDING, LOCATION, RENT
from backend.app.agents.memory import open_agent
from backend.app.schemas.agent import Analysis, ConstraintPatch, LocationCondition
from backend.app.schemas.tools import (
    Building, BuildingOutput, Location, LocationOutput, MatchEvidence, RentalCandidate, RentalOutput,
    ToolError, ToolFailure, ToolMeta, ToolSuccess,
)

AREAS = [("서울 종로구", "11110"), ("서울 중구", "11140"), ("서울 용산구", "11170"), ("서울 성동구", "11200")]
PRIMARY = "서울 종로구(11110)"
ALTERNATIVES = "대안으로 서울 중구(11140), 서울 용산구(11170), 서울 성동구(11200) 허용"
BASE = (
    f"{PRIMARY} 희망, 보증금 3000만원, 월세 60만원. 2025년 1월 거래. "
    "준비 시작일 2026-11-20, 준비 기간 7일, 출근일 2026-12-01."
)
NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)


def create_plan(alt_count=0, **extra):
    alt = [LocationCondition(label=label, sigungu_code=code) for label, code in AREAS[1:1 + alt_count]]
    values = {
        "residential_preferences": [LocationCondition(label=AREAS[0][0], sigungu_code=AREAS[0][1])],
        "max_deposit_krw": 30_000_000, "max_monthly_rent_krw": 600_000,
        "preparation_days": 7, "planning_start_date": date(2026, 11, 20), "job_start_date": date(2026, 12, 1),
    }
    evidence = {"residential_preferences": PRIMARY, "max_deposit_krw": "보증금 3000만원",
                "max_monthly_rent_krw": "월세 60만원", "job_start_date": "출근일 2026-12-01",
                "planning_start_date": "준비 시작일 2026-11-20", "preparation_days": "준비 기간 7일",
                "contract_month": "2025년 1월"}
    if alt:
        values["allowed_alternative_areas"] = alt
        evidence["allowed_alternative_areas"] = ALTERNATIVES
    values.update(extra)
    return Analysis(intent="CREATE_PLAN", patch=ConstraintPatch(**values), evidence=evidence,
                    contract_month="202501")


class Planner:
    def __init__(self, *analyses):
        self.analyses = iter(analyses)
        self.planned = []

    def analyze(self, message, prior):
        return next(self.analyses)

    def plan(self, intent, tool, args):
        self.planned.append((tool, args.copy()))
        return tool, args


class Provider:
    def __init__(self, rents=None, failure=None):
        self.rents = rents or {}
        self.failure = failure
        self.calls = []

    def __call__(self, tool, args):
        self.calls.append((tool, args))
        provider = {RENT: "molit_rent", LOCATION: "kakao_local", BUILDING: "building_hub"}[tool]
        meta = ToolMeta(provider=provider, fetched_at=NOW)
        if self.failure and self.failure[0] == tool:
            return ToolFailure(meta=meta, error=ToolError(code=self.failure[1], message="fixture error"))
        if tool == RENT:
            district = args["sigungu_code"]
            candidate = RentalCandidate(
                candidate_id=f"fixture-{district}", legal_dong="예시동", lot_number="12-3", building_name="예시빌라",
                floor=2, exclusive_area_m2=45, deposit_krw=20_000_000,
                monthly_rent_krw=self.rents.get(district, 500_000), contract_date=date(2025, 1, 16),
                raw_location_fields={"sggCd": district}, evidence_refs=[f"fixture:{district}"],
            )
            out = RentalOutput(candidates=[candidate], requested_period=args.get("contract_month"),
                               effective_period="202501", count=1)
            return ToolSuccess[RentalOutput](data=out, meta=meta)
        if tool == LOCATION:
            district = next((code for label, code in AREAS if args["query"].startswith(label)), "11110")
            location = Location(name="예시", address_lot=args["query"], b_code=f"{district}10100")
            return ToolSuccess[LocationOutput](data=LocationOutput(
                locations=[location], query_resolution="RESOLVED"), meta=meta)
        building = Building(building_registry_pk="fixture", full_address=None, building_name="예시빌라",
                            primary_use="주택", approval_date=None, floor_count=None, household_count=None)
        return ToolSuccess[BuildingOutput](data=BuildingOutput(
            candidate_id=args["candidate_id"], match_status="MATCHED_BUILDING", matched_building=building,
            match_evidence=MatchEvidence(candidate_count=1), caveats=[]), meta=meta)


def test_plan_with_provider_evidence(tmp_path):
    provider = Provider()
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(create_plan()), run_tool=provider) as agent:
        state = agent.run(agent.new_session_id(), BASE)
    assert state["execution_status"] == "SUCCEEDED"
    assert [name for name, _ in provider.calls] == [RENT, LOCATION, BUILDING]
    assert provider.calls[-1][1]["candidate_id"] == state["selected_candidate"].candidate_id
    assert provider.calls[-1][1]["bjdong_code"] == "10100"
    assert state["workflow_steps"][-1].depends_on == ["r0-rent", "r0-parcel"]
    evaluations = {item.rule_code: item.status for item in state["draft_plan"].evaluations}
    assert evaluations == {"PLAN_TIMELINE": "PASS", "HISTORICAL_DEPOSIT": "PASS", "HISTORICAL_RENT": "PASS",
                           "BUILDING_MATCH": "PASS", "CURRENT_LISTING": "UNKNOWN"}
    assert state["draft_plan"].planning_end_date == date(2026, 11, 26)
    assert len(state["draft_plan"].source_refs) == 3
    assert "과거" in state["assistant_message"] and "현재 임대할 수 있는 매물인지는 확인되지 않았습니다" in state["assistant_message"]


def test_expensive_rent_replans_in_approved_area_only(tmp_path):
    provider = Provider(rents={"11110": 800_000})
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(create_plan(1)), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), BASE + " " + ALTERNATIVES)
    assert result["replan_count"] == 1
    assert result["execution_status"] == "SUCCEEDED"
    assert [args["sigungu_code"] for tool, args in provider.calls if tool == RENT] == ["11110", "11140"]
    assert all(args["contract_month"] == "202501" for tool, args in provider.calls if tool == RENT)
    assert result["user_constraints"].max_monthly_rent_krw == 600_000
    assert [e.status for e in result["constraint_results"] if e.rule_code == "HISTORICAL_RENT"] == ["FAIL", "PASS"]


def test_expensive_alternatives_stop_at_three_replans(tmp_path):
    provider = Provider(rents=dict.fromkeys((code for _, code in AREAS), 800_000))
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(create_plan(3)), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), BASE + " " + ALTERNATIVES)
    assert result["execution_status"] == "EXHAUSTED"
    assert result["replan_count"] == 3 and result["replan_reason"] == "MAX_REPLANS"
    assert len(set(result["attempted_strategies"])) == len(provider.calls) == 4
    assert len([e for e in result["constraint_results"] if e.rule_code == "HISTORICAL_RENT" and e.status == "FAIL"]) == 4
    assert result["selected_candidate"] is None


def test_building_failure_preserves_rental_and_marks_partial(tmp_path):
    provider = Provider(failure=(BUILDING, "TIMEOUT"))
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(create_plan()), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), BASE)
    assert result["execution_status"] == "PARTIAL"
    assert result["selected_candidate"]
    assert result["successful_steps"] == ["r0-rent", "r0-parcel"]
    assert result["failed_steps"] == ["r0-title"]
    assert result["errors"][0].code == "TIMEOUT"
    assert result["replan_count"] == 0
    assert any(e.rule_code == "BUILDING_MATCH" and e.status == "UNKNOWN" for e in result["constraint_results"])


def test_general_skips_planning_and_tools(tmp_path):
    planner = Planner(Analysis(intent="GENERAL"))
    provider = Provider()
    with open_agent(tmp_path / "memory.sqlite3", planner=planner, run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), "이 플래너는 어떻게 쓰나요?")
    assert result["execution_status"] == "SUCCEEDED"
    assert planner.planned == provider.calls == []
    assert result["tool_results"] == {}


def test_sqlite_memory_updates_rent_only_and_isolates_sessions(tmp_path):
    path = tmp_path / "memory.sqlite3"
    with open_agent(path, planner=Planner(create_plan()), run_tool=Provider()) as agent:
        session = agent.new_session_id()
        first = agent.run(session, BASE + " 저장하지 않을 대화 표식")
    update = Analysis(intent="UPDATE_CONSTRAINT", patch=ConstraintPatch(max_monthly_rent_krw=550_000),
                      evidence={"max_monthly_rent_krw": "월세만 55만원"})
    with open_agent(path, planner=Planner(update, update), run_tool=Provider()) as agent:
        second = agent.run(session, "월세만 55만원으로 바꿔줘.")
        other = agent.run(agent.new_session_id(), "월세만 55만원으로 바꿔줘.")
    assert second["run_id"] != first["run_id"] and second["changed_fields"] == ["max_monthly_rent_krw"]
    assert second["user_constraints"].max_monthly_rent_krw == 550_000
    assert second["user_constraints"].max_deposit_krw == 30_000_000
    assert second["user_constraints"].residential_preferences[0].sigungu_code == "11110"
    assert second["user_constraints"].job_start_date == date(2026, 12, 1)
    assert second["contract_month"] == "202501" and second["replan_count"] == 0
    assert other["execution_status"] == "NEEDS_INPUT" and other["tool_results"] == {}
    assert other["user_constraints"].residential_preferences == []
    with sqlite3.connect(path) as connection:
        checkpoint = SqliteSaver(connection).get({"configurable": {"thread_id": str(session)}})
    assert set(checkpoint["channel_values"]) <= {"constraints", "contract_month", "branch:to:run_turn", "__start__"}
    assert "저장하지 않을 대화 표식" not in repr(checkpoint)


@pytest.mark.parametrize("error", ["AUTH_FAILED", "SCHEMA_MISMATCH"])
def test_primary_api_failure_does_not_retry(error, tmp_path):
    provider = Provider(failure=(RENT, error))
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(create_plan(3)), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), BASE + " " + ALTERNATIVES)
    assert result["execution_status"] == "FAILED"
    assert result["replan_count"] == 0 and len(provider.calls) == 1


def test_model_cannot_expand_search_or_change_fixed_arguments(tmp_path):
    class InvalidPlanner(Planner):
        def plan(self, intent, tool, args):
            return tool, {**args, "sigungu_code": "11200"}

    provider = Provider()
    with open_agent(tmp_path / "memory.sqlite3", planner=InvalidPlanner(create_plan()), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), BASE)
    assert result["execution_status"] == "FAILED" and result["errors"][0].code == "INVALID_ARGUMENT"
    assert provider.calls == []


def test_duplicate_approved_strategy_never_repeats(tmp_path):
    analysis = create_plan()
    analysis.patch.allowed_alternative_areas = analysis.patch.residential_preferences
    analysis.evidence["allowed_alternative_areas"] = "대안으로 서울 종로구(11110) 허용"
    provider = Provider(rents={"11110": 800_000})
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(analysis), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), BASE + " 대안으로 서울 종로구(11110) 허용")
    assert result["replan_count"] == 0 and result["replan_reason"] == "NO_NEW_APPROVED_STRATEGY"
    assert len(provider.calls) == 1


def test_unmentioned_deposit_is_not_changed_by_extractor(tmp_path):
    update = Analysis(intent="UPDATE_CONSTRAINT", patch=ConstraintPatch(
        max_monthly_rent_krw=550_000, max_deposit_krw=55_000_000),
        evidence={"max_monthly_rent_krw": "월세만 55만원", "max_deposit_krw": "월세만 55만원"})
    provider = Provider()
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(create_plan(), update), run_tool=provider) as agent:
        session = agent.new_session_id()
        agent.run(session, BASE)
        calls_before = len(provider.calls)
        result = agent.run(session, "월세만 55만원으로 바꿔줘.")
    assert result["user_constraints"].max_deposit_krw == 30_000_000
    assert result["changed_fields"] == ["max_monthly_rent_krw"]
    assert result["execution_status"] == "NEEDS_INPUT" and len(provider.calls) == calls_before


def test_location_resolution_cannot_repeat_an_already_used_district(tmp_path):
    analysis = create_plan()
    analysis.patch.residential_preferences = [LocationCondition(label="서울 종로구")]
    analysis.patch.allowed_alternative_areas = [LocationCondition(label="서울 종로구", sigungu_code="11110")]
    analysis.evidence["residential_preferences"] = "서울 종로구 희망"
    analysis.evidence["allowed_alternative_areas"] = "대안으로 서울 종로구(11110) 허용"
    provider = Provider(rents={"11110": 800_000})
    message = BASE.replace(PRIMARY, "서울 종로구") + " 대안으로 서울 종로구(11110) 허용"
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(analysis), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), message)
    assert provider.calls[0][0] == LOCATION
    assert provider.calls[1][0] == RENT and provider.calls[1][1]["sigungu_code"] == "11110"
    assert len(provider.calls) == 2 and result["replan_count"] == 0


def test_known_timeline_conflict_does_not_schedule_tasks_after_start_of_job(tmp_path):
    analysis = create_plan(job_start_date=date(2026, 11, 23))
    analysis.evidence["job_start_date"] = "출근일 2026-11-23"
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(analysis), run_tool=Provider()) as agent:
        result = agent.run(agent.new_session_id(), BASE.replace("2026-12-01", "2026-11-23"))
    assert result["execution_status"] == "PARTIAL"
    assert result["user_constraints"].job_start_date == date(2026, 11, 23)
    assert any(e.rule_code == "PLAN_TIMELINE" and e.status == "FAIL" for e in result["constraint_results"])
    assert all(task.task_date is None or task.task_date < date(2026, 11, 23) for task in result["draft_plan"].tasks)


def test_budget_evidence_does_not_mix_deposit_and_rent(tmp_path):
    analysis = create_plan(max_monthly_rent_krw=30_000_000)
    analysis.evidence["max_monthly_rent_krw"] = "보증금 3000만원, 월세 60만원"
    provider = Provider()
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(analysis), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), BASE)
    assert result["execution_status"] == "NEEDS_INPUT"
    assert result["user_constraints"].max_monthly_rent_krw is None
    assert provider.calls == []


def test_wider_search_reuses_region_resolution_in_same_run(tmp_path):
    class WideProvider(Provider):
        def __call__(self, tool, args):
            result = super().__call__(tool, args)
            if tool != RENT or args["limit"] != 20:
                return result
            rows = [result.data.candidates[0].model_copy(update={
                "candidate_id": f"filtered-{n}", "monthly_rent_krw": 900_000,
            }) for n in range(20)]
            return result.model_copy(update={"data": result.data.model_copy(update={"candidates": rows, "count": 20})})

    analysis = create_plan()
    analysis.patch.residential_preferences = [LocationCondition(label="서울 종로구")]
    analysis.evidence["residential_preferences"] = "서울 종로구 희망"
    provider = WideProvider()
    with open_agent(tmp_path / "memory.sqlite3", planner=Planner(analysis), run_tool=provider) as agent:
        result = agent.run(agent.new_session_id(), BASE.replace(PRIMARY, "서울 종로구"))
    assert result["execution_status"] == "SUCCEEDED" and result["replan_count"] == 1
    assert [args["limit"] for tool, args in provider.calls if tool == RENT] == [20, 50]
    assert sum(tool == LOCATION and args["query"] == "서울 종로구" for tool, args in provider.calls) == 1
    assert result["tool_results"]["r1-area"].meta.is_cached is True
