from dataclasses import dataclass
import json
from time import monotonic

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from pydantic import ValidationError

from ..events.publisher import RunEvents
from ..schemas.agent import ConstraintEvaluation, SafeError, Source, WorkflowStep
from ..schemas.tools import BuildingInput, RentalInput, ToolError, ToolFailure, ToolMeta
from ..services.building_match import candidate_building_input, parcel_number
from ..services.constraint_engine import draft_plan, planning_evaluations, rental_evaluations, rental_priority
from ..services.constraint_patch import apply_patch
from ..services.replan_policy import INITIAL_LIMIT, MAX_REPLANS, next_strategy
from ..tools.registry import TOOLS
from .planner import PlannerError
from .state import AgentState, Strategy

RENT = "search_rental_transactions"
LOCATION = "search_location"
BUILDING = "get_building_detail"
HISTORICAL = "신고된 과거 전월세 계약 사례이며 현재 임대할 수 있는 매물인지는 확인되지 않았습니다."
NOTICE = "이 계획은 계약·금융 전문가의 조언을 대신하지 않습니다."
INTENT_SUMMARIES = {
    "CREATE_PLAN": "독립 준비 일정과 주거 조건을 조합하는 계획 요청으로 분류했습니다.",
    "UPDATE_CONSTRAINT": "이전 조건 중 사용자가 지정한 조건을 조정하는 요청으로 분류했습니다.",
    "FACT_QUERY": "외부 자료로 확인할 수 있는 사실 조회 요청으로 분류했습니다.",
    "EXPLAIN_PLAN": "현재 대화에서 확인한 계획 조건의 설명을 요청한 것으로 분류했습니다.",
    "GENERAL": "외부 자료 조회가 필요 없는 일반 대화 또는 사용법 문의로 분류했습니다.",
}


@dataclass(frozen=True)
class GraphContext:
    events: RunEvents | None


def build_graph(planner, run_tool):
    def analyze_request(state):
        try:
            analysis = planner.analyze(state["user_message"], state["user_constraints"])
        except PlannerError as error:
            return _failure(state, "analyze_request", error.code)
        updates = {
            "analysis": analysis, "intent": analysis.intent,
            "intent_reason_summary": INTENT_SUMMARIES[analysis.intent],
        }
        if analysis.intent in ("CREATE_PLAN", "UPDATE_CONSTRAINT", "FACT_QUERY"):
            constraints, month, changed, unverified = apply_patch(
                state["user_constraints"], state["contract_month"], analysis, state["user_message"]
            )
            updates.update(user_constraints=constraints, contract_month=month, changed_fields=changed,
                           missing_fields=unverified)
        return updates

    def validate_input(state):
        analysis = state["analysis"]
        constraints = state["user_constraints"]
        missing = list(state["missing_fields"])
        if _location_fact(state):
            if analysis.location is None or analysis.location.query not in state["user_message"]:
                missing.append("location_query")
        elif state["intent"] == "FACT_QUERY" and analysis.fact_scope == "BUILDING":
            missing.append("verified_rental_candidate")
        else:
            if state["intent"] == "FACT_QUERY" and analysis.fact_scope != "RENTAL":
                missing.append("fact_scope")
            if not constraints.residential_preferences:
                missing.append("residential_preferences")
            if state["intent"] == "UPDATE_CONSTRAINT" and not analysis.patch.model_fields_set and not analysis.contract_month:
                missing.append("changed_fields")
        if missing:
            return {"missing_fields": missing, "execution_status": "NEEDS_INPUT"}
        if not _location_fact(state):
            return {"strategy": Strategy(constraints.residential_preferences[0], INITIAL_LIMIT)}
        return {}

    def plan_workflow(state):
        steps, rental_id = _workflow(state)
        first = steps[0]
        try:
            name, arguments = planner.plan(state["intent"], first.tool_name, first.args.copy())
            spec = TOOLS[first.tool_name]
            if name != first.tool_name or spec.input_model.model_validate(arguments) != spec.input_model.model_validate(first.args):
                return _failure(state, "plan_workflow", "INVALID_ARGUMENT")
        except PlannerError as error:
            return _failure(state, "plan_workflow", error.code)
        except (ValidationError, TypeError):
            return _failure(state, "plan_workflow", "INVALID_ARGUMENT")
        attempted = state["attempted_strategies"]
        if rental_id:
            attempted = [*attempted, state["strategy"].key(state["contract_month"])]
        return {"workflow_steps": [*state["workflow_steps"], *steps], "rental_step_id": rental_id,
                "attempted_strategies": attempted}

    def execute_tools(state, events):
        results = state["tool_results"].copy()
        cache = state["tool_cache"].copy()
        errors = list(state["errors"])
        steps = []
        for step in state["workflow_steps"]:
            if step.status != "PENDING":
                steps.append(step)
                continue
            args = _hydrate(step, state, results)
            if args is None:
                steps.append(step.model_copy(update={"status": "SKIPPED"}))
                continue
            key = json.dumps([step.tool_name, args], sort_keys=True, ensure_ascii=False)
            fields = {"step_id": step.step_id, "tool_name": step.tool_name, "is_cached": key in cache}
            started = monotonic()
            if events:
                try:
                    validated = TOOLS[step.tool_name].input_model.model_validate(args)
                    canonical_key = json.dumps(
                        [step.tool_name, validated.model_dump(mode="json")], sort_keys=True, ensure_ascii=False,
                    )
                except ValidationError:
                    canonical_key = key
                events.emit("TOOL_REQUESTED", node="execute_tools", **fields,
                            argument_fingerprint=events.fingerprint(canonical_key))
            if key in cache:
                result = cache[key]
                result = result.model_copy(update={"meta": result.meta.model_copy(update={"is_cached": True})})
            else:
                try:
                    result = run_tool(step.tool_name, args)
                except Exception:
                    result = ToolFailure(meta=ToolMeta(provider=TOOLS[step.tool_name].provider),
                                         error=ToolError(code="UNKNOWN_ERROR", message="도구 실행을 완료하지 못했습니다."))
                cache[key] = result
            if events:
                error = {} if result.ok else {"code": result.error.code}
                events.emit("TOOL_SUCCEEDED" if result.ok else "TOOL_FAILED", node="execute_tools",
                            start=started, **fields, **error)
            results[step.step_id] = result
            status = "SUCCEEDED" if result.ok else "FAILED"
            steps.append(step.model_copy(update={"args": args, "status": status,
                                                 "fixed_arg_names": list(args)}))
            if not result.ok:
                errors.append(SafeError(stage="execute_tools", code=result.error.code, step_id=step.step_id))
        return {"workflow_steps": steps, "tool_results": results, "tool_cache": cache, "errors": errors}

    def normalize_results(state):
        rental = state["tool_results"].get(state["rental_step_id"])
        candidates = rental.data.candidates if rental and rental.ok else []
        attempted = state["attempted_strategies"]
        if rental and not state["strategy"].area.sigungu_code:
            rent_step = next(step for step in state["workflow_steps"] if step.step_id == state["rental_step_id"])
            resolved = state["strategy"].area.model_copy(update={"sigungu_code": rent_step.args["sigungu_code"]})
            key = Strategy(resolved, state["strategy"].limit).key(state["contract_month"])
            if key not in attempted:
                attempted = [*attempted, key]
        sources = []
        seen_sources = set()
        for step_id, result in state["tool_results"].items():
            if not result.ok or result.meta.fetched_at is None or result.meta.is_cached:
                continue
            data = result.data
            if hasattr(data, "candidates") and data.candidates:
                records = [(ref, candidate.contract_date) for candidate in data.candidates
                           for ref in candidate.evidence_refs]
            else:
                records = [(f"{result.meta.provider}:{state['run_id']}:{step_id}", None)]
            for ref, observed in records:
                if ref not in seen_sources:
                    sources.append(Source(ref=ref, observed_at=observed, provider=result.meta.provider,
                                          fetched_at=result.meta.fetched_at, caveats=result.meta.caveats))
                    seen_sources.add(ref)
        return {"candidates": candidates, "sources": sources, "attempted_strategies": attempted,
                "successful_steps": [key for key, result in state["tool_results"].items() if result.ok],
                "failed_steps": [key for key, result in state["tool_results"].items() if not result.ok]}

    def evaluate_constraints(state):
        constraints = state["user_constraints"]
        if _location_fact(state):
            status = "SUCCEEDED" if state["successful_steps"] else "FAILED"
            return {"execution_status": status}
        current = state["tool_results"].get(state["rental_step_id"])
        candidates = state["candidates"]
        best = min(candidates, key=lambda candidate: rental_priority(candidate, constraints), default=None)
        priority = rental_priority(best, constraints) if best else None
        selected = best if best is not None and priority < 2 else None
        previous_checks = [check for check in state["constraint_results"]
                           if check.rule_code in {"HISTORICAL_RENT", "HISTORICAL_DEPOSIT"}]
        evaluations = [*previous_checks, *planning_evaluations(constraints)]
        if best:
            evaluations.extend(rental_evaluations(best, constraints))
        warnings = [HISTORICAL, NOTICE]
        if current and current.ok:
            warnings.append(f"조회 기준 계약월 {current.data.effective_period}. 신고·공개 시차와 조회 한도가 적용됩니다.")
        if any(check.status != "PASS" for check in evaluations if check.rule_code == "PLAN_TIMELINE"):
            warnings.append("준비 기간과 출근일을 함께 확인하고, 일정이 겹치면 사용자에게 조정을 요청합니다.")
        warnings.extend(check.caveat for check in evaluations if check.status == "UNKNOWN"
                        and check.rule_code in {"MAINTENANCE_FEE", "COMMUTE_TIME"} and check.caveat)
        detail = _current_detail(state)
        if selected:
            evaluations.append(ConstraintEvaluation(rule_code="CURRENT_LISTING", status="UNKNOWN",
                                                    reason_code="HISTORICAL_DATA_ONLY"))
        if selected and _requires_building(state):
            matched = detail and detail.ok and detail.data.match_status == "MATCHED_BUILDING"
            title_step = f"r{state['replan_count']}-title"
            evaluations.append(ConstraintEvaluation(
                rule_code="BUILDING_MATCH", status="PASS" if matched else "UNKNOWN",
                reason_code="PARCEL_AND_NAME_MATCH" if matched else "BUILDING_NOT_VERIFIED",
                source_refs=[source.ref for source in state["sources"] if source.provider == "building_hub"
                             and source.ref.endswith(f":{title_step}")],
            ))
            if not matched:
                warnings.append("건물 상세는 확인되지 않았습니다. 확인한 거래와 예산 비교 결과는 유지합니다.")
        if current is None or not current.ok:
            outcome = "ERROR"
            unresolved = current is None and not state["failed_steps"]
            status = "NEEDS_INPUT" if unresolved else "PARTIAL" if state["sources"] else "FAILED"
            if unresolved:
                warnings.append("지역을 하나로 확인할 수 없습니다. 시군구 코드나 더 구체적인 지역명을 알려 주세요.")
        elif not candidates or priority == 2:
            outcome = "NO_RESULT" if not candidates else "BUDGET_FAIL"
            status = "EXHAUSTED"
        else:
            outcome = "FOUND"
            incomplete = any(check.status != "PASS" and check.rule_code != "CURRENT_LISTING"
                             for check in evaluations[len(previous_checks):])
            status = "PARTIAL" if incomplete or state["failed_steps"] else "SUCCEEDED"
        return {"constraint_results": evaluations, "selected_candidate": selected, "rental_outcome": outcome,
                "warnings": warnings, "execution_status": status,
                "missing_fields": ["sigungu_code"] if status == "NEEDS_INPUT" else state["missing_fields"]}

    def route_after_evaluation(state):
        if (state.get("rental_outcome") in ("BUDGET_FAIL", "NO_RESULT")
                and state["intent"] in ("CREATE_PLAN", "UPDATE_CONSTRAINT")
                and not any(error.code == "AUTH_FAILED" for error in state["errors"])):
            return "replan"
        return "generate_response"

    def replan(state):
        strategy = next_strategy(state)
        if strategy is None:
            reason = "MAX_REPLANS" if state["replan_count"] >= MAX_REPLANS else "NO_NEW_APPROVED_STRATEGY"
            return {"execution_status": "EXHAUSTED", "replan_reason": reason}
        return {"strategy": strategy, "replan_count": state["replan_count"] + 1,
                "execution_status": "RUNNING", "replan_reason": state["rental_outcome"]}

    graph = StateGraph(AgentState, context_schema=GraphContext)
    for node in (analyze_request, validate_input, plan_workflow, execute_tools, normalize_results,
                 evaluate_constraints, replan, _generate_response):
        graph.add_node(node.__name__.lstrip("_"), _instrument(node))
    graph.add_edge(START, "analyze_request")
    graph.add_conditional_edges("analyze_request", lambda state: "generate_response" if
                                state["execution_status"] == "FAILED" or state["intent"] in {"GENERAL", "EXPLAIN_PLAN"}
                                else "validate_input", ["generate_response", "validate_input"])
    graph.add_conditional_edges("validate_input", lambda state: "generate_response" if
                                state["execution_status"] == "NEEDS_INPUT" else "plan_workflow",
                                ["generate_response", "plan_workflow"])
    graph.add_conditional_edges("plan_workflow", lambda state: "execute_tools" if
                                state["execution_status"] == "RUNNING" else "generate_response",
                                ["execute_tools", "generate_response"])
    graph.add_edge("execute_tools", "normalize_results")
    graph.add_edge("normalize_results", "evaluate_constraints")
    graph.add_conditional_edges("evaluate_constraints", route_after_evaluation, ["replan", "generate_response"])
    graph.add_conditional_edges("replan", lambda state: "plan_workflow" if
                                state["execution_status"] == "RUNNING" else "generate_response",
                                ["plan_workflow", "generate_response"])
    graph.add_edge("generate_response", END)
    return graph.compile()


def _instrument(node):
    name = node.__name__.lstrip("_")

    def wrapped(state, runtime: Runtime[GraphContext]):
        events = runtime.context.events if runtime.context else None
        started = monotonic()
        if events:
            events.emit("NODE_STARTED", node=name)
        try:
            output = node(state, events) if name == "execute_tools" else node(state)
            if events:
                _publish_decision(events, name, state, output)
        except Exception:
            if events:
                events.emit("NODE_FINISHED", node=name, start=started, outcome="FAILED")
            raise
        if events:
            payload = {}
            if name == "execute_tools":
                pending = {step.step_id for step in state["workflow_steps"] if step.status == "PENDING"}
                payload["steps"] = [
                    {"step_id": step.step_id, "tool_name": step.tool_name, "status": step.status}
                    for step in output["workflow_steps"] if step.step_id in pending
                ]
            events.emit("NODE_FINISHED", node=name, start=started, outcome="COMPLETED", **payload)
        return output

    return wrapped


def _publish_decision(events, name, state, output):
    if name == "analyze_request" and "intent" in output:
        events.emit("INTENT_DECIDED", node=name, intent=output["intent"],
                    reason_summary=output["intent_reason_summary"])
    elif name == "plan_workflow" and "workflow_steps" in output:
        steps = output["workflow_steps"][len(state["workflow_steps"]):]
        events.emit("WORKFLOW_CREATED", node=name, steps=[
            {"step_id": step.step_id, "tool_name": step.tool_name, "depends_on": step.depends_on}
            for step in steps
        ])
    elif name == "evaluate_constraints" and "constraint_results" in output:
        events.emit("CONSTRAINT_EVALUATED", node=name, checks=[
            {"rule": check.rule_code, "status": check.status, "reason": check.reason_code}
            for check in output["constraint_results"]
        ])
    elif name == "replan":
        exhausted = output["execution_status"] == "EXHAUSTED"
        events.emit("REPLAN_EXHAUSTED" if exhausted else "REPLAN_STARTED", node=name,
                    replan_count=output.get("replan_count", state["replan_count"]),
                    reason=output["replan_reason"])


def _location_fact(state):
    return state["intent"] == "FACT_QUERY" and state["analysis"].fact_scope == "LOCATION"


def _requires_building(state):
    return state["intent"] in {"CREATE_PLAN", "UPDATE_CONSTRAINT"}


def _workflow(state):
    prefix = f"r{state['replan_count']}"
    steps = []

    def add(suffix, name, args, purpose, dependencies=()):
        step = WorkflowStep(step_id=f"{prefix}-{suffix}", tool_name=name, args=args,
                            purpose=purpose, depends_on=list(dependencies), fixed_arg_names=list(args))
        steps.append(step)
        return step.step_id

    if _location_fact(state):
        add("location", LOCATION, state["analysis"].location.model_dump(), "FACT_LOCATION")
        return steps, ""
    strategy = state["strategy"]
    district = strategy.area.sigungu_code
    area_step = () if district else (add("area", LOCATION,
                                       {"query": strategy.area.label, "mode": "ADDRESS", "limit": 5},
                                       "RESOLVE_DISTRICT"),)
    args = {"limit": strategy.limit}
    if district:
        args["sigungu_code"] = district
    if state["contract_month"]:
        args["contract_month"] = state["contract_month"]
    rental = add("rent", RENT, args, "RENTAL_CANDIDATES", area_step)
    if _requires_building(state):
        address = add("parcel", LOCATION, {}, "RESOLVE_CANDIDATE_PARCEL", (rental,))
        add("title", BUILDING, {}, "VERIFY_BUILDING", (rental, address))
    return steps, rental


def _hydrate(step, state, results):
    if not step.depends_on:
        return step.args
    upstream = [results.get(step_id) for step_id in step.depends_on]
    if step.purpose == "RENTAL_CANDIDATES":
        location = _resolved_location(upstream[0])
        if not location or not location.b_code:
            return None
        return RentalInput(**step.args, sigungu_code=location.b_code[:5]).model_dump(exclude_none=True)

    rental = upstream[0]
    if not rental or not rental.ok or not rental.data.candidates:
        return None
    candidate = min(rental.data.candidates, key=lambda item: rental_priority(item, state["user_constraints"]))
    if rental_priority(candidate, state["user_constraints"]) == 2:
        return None
    if step.purpose == "RESOLVE_CANDIDATE_PARCEL":
        if not candidate.legal_dong or not parcel_number(candidate.lot_number):
            return None
        area = state["strategy"].area.label
        return {"query": f"{area} {candidate.legal_dong} {candidate.lot_number}", "mode": "ADDRESS", "limit": 5}
    location = _resolved_location(upstream[1])
    if location:
        args = candidate_building_input(candidate, location)
    else:
        args = BuildingInput(candidate_id=candidate.candidate_id,
                             sigungu_code=candidate.raw_location_fields["sggCd"])
    return args.model_dump(exclude_none=True)


def _resolved_location(result):
    if result and result.ok and result.data.query_resolution == "RESOLVED" and len(result.data.locations) == 1:
        return result.data.locations[0]
    return None


def _current_detail(state):
    suffix = f"r{state['replan_count']}-title"
    return state["tool_results"].get(suffix)


def _failure(state, stage, code):
    status = "PARTIAL" if state.get("successful_steps") else "FAILED"
    return {"execution_status": status, "errors": [*state["errors"], SafeError(stage=stage, code=code)]}


def _generate_response(state):
    status, intent = state["execution_status"], state.get("intent")
    if status == "NEEDS_INPUT":
        labels = {"residential_preferences": "희망 주거 지역", "sigungu_code": "시군구 코드",
                  "location_query": "검색할 주소 또는 장소", "changed_fields": "바꿀 조건과 값",
                  "fact_scope": "조회할 정보 종류", "verified_rental_candidate": "대조할 과거 계약 후보"}
        missing = ", ".join(labels.get(field, field) for field in state["missing_fields"])
        return {"assistant_message": f"다음 조건을 확인해 주세요. {missing}."}
    if status == "FAILED":
        code = state["errors"][-1].code if state["errors"] else "SERVICE_UNAVAILABLE"
        return {"assistant_message": f"요청을 완료하지 못했습니다. 오류 코드 {code}."}
    if intent == "GENERAL":
        return {"execution_status": "SUCCEEDED",
                "assistant_message": "안녕하세요. 희망 지역과 예산, 준비 일정을 알려 주시면 독립 준비 계획을 만들 수 있어요."}
    if intent == "EXPLAIN_PLAN":
        fields = ", ".join(sorted(state["user_constraints"].fixed_fields))
        return {"execution_status": "SUCCEEDED",
                "assistant_message": ("현재 대화에서 확인한 조건입니다. " + fields if fields
                                      else "이 대화에는 확인된 준비 조건이 없습니다.")}
    if _location_fact(state):
        places = [place for result in state["tool_results"].values() if result.ok for place in result.data.locations]
        answer = ", ".join(place.name for place in places[:5]) if places else "해당 조건의 장소를 찾지 못했습니다."
        return {"assistant_message": f"{answer} 출처는 카카오 로컬입니다."}

    candidate = state.get("selected_candidate")
    if candidate:
        name = candidate.building_name or candidate.legal_dong or "확인된 지역"
        amounts = [f"{label} {value:,}원" for label, value in
                   (("보증금", candidate.deposit_krw), ("월세", candidate.monthly_rent_krw)) if value is not None]
        detail = _current_detail(state)
        answer = f"{name}의 과거 계약 사례를 확인했습니다."
        if amounts:
            answer += " " + ", ".join(amounts) + "."
        if detail and detail.ok and detail.data.matched_building:
            use = detail.data.matched_building.primary_use
            answer += f" 건축물대장 표제부와 건물 수준에서 일치했습니다{f' (주용도 {use})' if use else ''}."
    elif status == "EXHAUSTED":
        reason = "재계획 3회 상한에 도달했습니다." if state["replan_reason"] == "MAX_REPLANS" else "승인된 추가 탐색 전략이 없습니다."
        answer = f"조회 범위에서 조건에 맞는 과거 거래 사례를 확인하지 못했습니다. {reason} 다른 지역이나 조회 범위를 지정해 주세요."
    else:
        answer = "조회한 결과는 유지했으나 일부 정보를 확인하지 못했습니다."
    if status == "EXHAUSTED":
        fields = {"HISTORICAL_RENT": "월세", "HISTORICAL_DEPOSIT": "보증금"}
        exceeded = {fields[check.rule_code] for check in state["constraint_results"]
                    if check.rule_code in fields and check.status == "FAIL"}
        if exceeded:
            answer += " 일부 사례는 " + ", ".join(sorted(exceeded)) + " 상한을 초과했습니다."
    if any(check.status == "FAIL" and check.rule_code == "PLAN_TIMELINE" for check in state["constraint_results"]):
        answer += " 준비 기간이 출근일 전에 끝나지 않습니다. 날짜 또는 기간을 확인해 주세요."
    if state.get("sources"):
        answer += " 출처는 " + ", ".join(dict.fromkeys(
            {"molit_rent": "국토교통부 전월세 실거래", "building_hub": "국토교통부 건축HUB",
             "kakao_local": "카카오 로컬"}.get(source.provider, source.provider) for source in state["sources"]
        )) + "입니다."
    warnings = state.get("warnings") or [HISTORICAL, NOTICE]
    response = {"assistant_message": answer + " " + " ".join(warnings)}
    if intent in {"CREATE_PLAN", "UPDATE_CONSTRAINT"}:
        response["draft_plan"] = draft_plan(state)
    return response

