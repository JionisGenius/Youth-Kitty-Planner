from time import monotonic
from uuid import UUID, uuid4

from fastapi import APIRouter, Request, Response

from ...agents.state import RunAssessment
from ...core.errors import ApiProblem, not_found
from ...db.repositories import plans, runs
from ...db.repositories.sessions import create_session
from ...events.publisher import RunEvents
from ...schemas.api import (
    ApiError, ChatRequest, ChatResponse, DraftRead, PlanCreate, PlanList, PlanRead, PlanUpdate, SessionCreated,
)
from ...schemas.events import EventRead, LogDeleted, LogDetail, LogList
from ...services.provenance import evidence_for_run
from ..dependencies import CurrentSession, Page

router = APIRouter(prefix="/api/v1", responses={
    status: {"model": ApiError} for status in (401, 404, 409, 422, 500, 502, 503)
})


@router.get("/health", tags=["Health"])
def health(request: Request):
    with request.app.state.database.connect() as conn:
        conn.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@router.post("/sessions", status_code=201, response_model=SessionCreated, tags=["Sessions"])
def new_session(request: Request):
    return create_session(request.app.state.database)


@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(request: Request, data: ChatRequest, session: CurrentSession):
    services = request.app.state
    base = plans.base_constraints(services.database, session.id, data.base_plan_id) if data.base_plan_id else None
    run_id = uuid4()
    runs.create_run(services.database, session.id, run_id)
    events = RunEvents(services.publisher, run_id, session.id)
    started = monotonic()
    events.emit("RUN_STARTED")
    try:
        result = services.agent.run(session.id, data.message, events=events, base_constraints=base)
        aliases, evidence = evidence_for_run(session, result)
        reply = _chat_response(result, aliases)
    except Exception:
        runs.finish_run(services.database, session.id, run_id, status="FAILED", error="UNKNOWN_ERROR")
        events.emit("RUN_FAILED", start=started, status="FAILED", code="UNKNOWN_ERROR",
                    anomaly=RunAssessment().payload())
        raise ApiProblem(500, "UNKNOWN_ERROR", "요청을 처리하지 못했습니다.",
                         details={"run_id": str(run_id)}) from None

    error = result["errors"][-1].code if result["errors"] else None
    anomaly = result.get("run_assessment", RunAssessment()).payload()
    runs.finish_run(services.database, session.id, run_id, status=reply.status, intent=reply.intent,
                    replan_count=reply.replan_count, error=error)
    if reply.status == "FAILED":
        events.emit("RUN_FAILED", start=started, status=reply.status, code=error or "UNKNOWN_ERROR", anomaly=anomaly)
        raise ApiProblem(502, error or "UNKNOWN_ERROR", "대화 실행을 완료하지 못했습니다.",
                         details={"run_id": str(run_id)})
    events.emit("RUN_FINISHED", start=started, status=reply.status, replan_count=reply.replan_count,
                evidence=evidence, anomaly=anomaly)
    return reply


def _chat_response(result, aliases):
    evaluations = [item.model_copy(update={
        "source_refs": [aliases[ref] for ref in item.source_refs if ref in aliases],
    }) for item in result["constraint_results"]]
    draft = result.get("draft_plan")
    if draft is not None:
        draft = DraftRead.model_validate({
            **draft.model_dump(), "category": "FIRST_JOB_INDEPENDENCE",
            "source_refs": [aliases[ref] for ref in draft.source_refs if ref in aliases],
            "evaluations": evaluations,
        })
    summaries = []
    for step in result["workflow_steps"]:
        tool = result["tool_results"].get(step.step_id)
        item = {"step_id": step.step_id, "tool_name": step.tool_name, "status": step.status}
        if tool is not None:
            item.update(provider=tool.meta.provider, is_cached=tool.meta.is_cached)
            if not tool.ok:
                item["error_code"] = tool.error.code
            elif hasattr(tool.data, "candidates"):
                item["result_count"] = tool.data.count
            elif hasattr(tool.data, "locations"):
                item["result_count"] = len(tool.data.locations)
            elif hasattr(tool.data, "match_evidence"):
                item["result_count"] = tool.data.match_evidence.candidate_count
        summaries.append(item)
    return ChatResponse(
        run_id=result["run_id"], status=result["execution_status"], intent=result.get("intent"),
        assistant_message=result["assistant_message"], constraints=result["user_constraints"],
        changed_fields=result["changed_fields"], missing_fields=result["missing_fields"],
        tool_summaries=summaries, evaluations=evaluations, draft_plan=draft, warnings=result["warnings"],
        replan_count=result["replan_count"],
    )


@router.get("/runs/{run_id}/events", response_model=list[EventRead], tags=["Logs"])
def get_run_events(request: Request, run_id: UUID, session: CurrentSession):
    return runs.run_events(request.app.state.database, session.id, run_id)


@router.get("/logs", response_model=LogList, tags=["Logs"])
def get_logs(request: Request, session: CurrentSession, page: Page):
    return runs.list_logs(request.app.state.database, session.id, page.limit, page.offset)


@router.get("/logs/{session_id}", response_model=LogDetail, tags=["Logs"])
def get_log(request: Request, session_id: UUID, session: CurrentSession):
    _require_session(session_id, session)
    return runs.log_detail(request.app.state.database, session.id)


@router.delete("/logs/{session_id}", response_model=LogDeleted, tags=["Logs"])
def delete_log(request: Request, session_id: UUID, session: CurrentSession):
    _require_session(session_id, session)
    return runs.delete_logs(request.app.state.database, session.id)


def _require_session(session_id, session):
    if session_id != session.id:
        raise not_found()


@router.post("/plans", status_code=201, response_model=PlanRead, tags=["Plans"])
def new_plan(request: Request, data: PlanCreate, session: CurrentSession):
    return plans.create_plan(request.app.state.database, session, data)


@router.get("/plans", response_model=PlanList, tags=["Plans"])
def get_plans(request: Request, session: CurrentSession, page: Page):
    return plans.list_plans(request.app.state.database, session.id, page.limit, page.offset)


@router.get("/plans/{plan_id}", response_model=PlanRead, tags=["Plans"])
def get_plan(request: Request, plan_id: UUID, session: CurrentSession):
    return plans.get_plan(request.app.state.database, session.id, plan_id)


@router.patch("/plans/{plan_id}", response_model=PlanRead, tags=["Plans"])
def patch_plan(request: Request, plan_id: UUID, data: PlanUpdate, session: CurrentSession):
    return plans.update_plan(request.app.state.database, session.id, plan_id, data)


@router.delete("/plans/{plan_id}", status_code=204, tags=["Plans"])
def delete_plan(request: Request, plan_id: UUID, session: CurrentSession):
    plans.delete_plan(request.app.state.database, session.id, plan_id)
    return Response(status_code=204)

