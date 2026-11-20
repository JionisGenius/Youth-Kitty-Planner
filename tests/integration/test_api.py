from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from backend.app.agents.graph import BUILDING
from backend.app.events.logging_agent import LoggingAgent
from backend.app.main import create_app
from backend.app.schemas.agent import Analysis, ConstraintPatch

from test_agent import ALTERNATIVES, AREAS, BASE, Planner, Provider, create_plan

PREFIX = "/api/v1"


def open_client(tmp_path, **options):
    app = create_app(database_path=tmp_path / "business.sqlite3", checkpoint_path=tmp_path / "memory.sqlite3", **options)
    return TestClient(app)


def auth(client):
    response = client.post(PREFIX + "/sessions")
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"access_token", "expires_at"}
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def chat(client, headers, message=BASE, **kwargs):
    response = client.post(PREFIX + "/chat", headers=headers, json={"message": message, **kwargs})
    assert response.status_code == 200, response.json()
    return response.json()


def task(title, start=None, end=None, *, when="2026-11-20"):
    return {"title": title, "task_date": when, "scheduled_start_at": start, "scheduled_end_at": end}


def plan_data(*tasks):
    return {"title": "계획", "category": "FIRST_JOB_INDEPENDENCE", "constraints": {},
            "planning_start_date": "2026-11-20", "planning_end_date": "2026-11-26", "tasks": list(tasks)}


def save(client, headers, data):
    response = client.post(PREFIX + "/plans", headers=headers, json=data)
    assert response.status_code == 201, response.json()
    return response.json()


def test_bearer_hash_expiry_and_public_health(tmp_path):
    with open_client(tmp_path) as client:
        assert client.get(PREFIX + "/health").json() == {"status": "ok"}
        response = client.get(PREFIX + "/plans")
        assert response.status_code == 401 and response.headers["www-authenticate"] == "Bearer"
        headers = auth(client)
        raw = headers["Authorization"].split()[1]
        with client.app.state.database.connect() as conn:
            stored = dict(conn.execute("SELECT * FROM sessions").fetchone())
        assert stored["token_hash"] == sha256(raw.encode()).hexdigest()
        assert raw not in repr(stored)
        assert client.get(PREFIX + "/plans", headers=headers).status_code == 200
        with client.app.state.database.connect(write=True) as conn:
            conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
        assert client.get(PREFIX + "/plans", headers=headers).status_code == 401


def test_chat_with_memory_and_session_isolation(tmp_path):
    update = Analysis(intent="UPDATE_CONSTRAINT", patch=ConstraintPatch(max_monthly_rent_krw=550_000),
                      evidence={"max_monthly_rent_krw": "월세만 55만원"})
    with open_client(tmp_path, planner=Planner(create_plan(), update, update), run_tool=Provider()) as client:
        a, b = auth(client), auth(client)
        first = chat(client, a)
        second = chat(client, a, "월세만 55만원으로 바꿔줘.")
        other = chat(client, b, "월세만 55만원으로 바꿔줘.")
        assert first["status"] == "SUCCEEDED"
        assert first["draft_plan"]["category"] == "FIRST_JOB_INDEPENDENCE"
        assert first["run_id"] != second["run_id"]
        assert second["changed_fields"] == ["max_monthly_rent_krw"]
        assert second["constraints"]["max_deposit_krw"] == first["constraints"]["max_deposit_krw"]
        assert other["status"] == "NEEDS_INPUT" and other["tool_summaries"] == []
        assert client.get(PREFIX + f"/runs/{first['run_id']}/events", headers=b).status_code == 404


def test_plan_crud_revision_and_transaction_rollback(tmp_path):
    with open_client(tmp_path) as client:
        headers = auth(client)
        plan = save(client, headers, plan_data(task("일정 미정")))
        path = PREFIX + "/plans/" + plan["id"]
        task_id = plan["tasks"][0]["id"]
        assert plan["tasks"][0]["scheduled_start_at"] is None
        assert client.get(PREFIX + "/plans", headers=headers).json()["items"][0]["id"] == plan["id"]
        assert client.get(path, headers=headers).json() == plan

        invalid = client.patch(path, headers=headers, json={"expected_revision_number": 1, "title": "rollback",
            "tasks": [{"op": "add", "task": task("rollback addition")},
                      {"op": "update", "task_id": task_id, "changes": {"scheduled_start_at": "2026-11-20T14:00:00+09:00"}}]})
        assert invalid.status_code == 422
        assert client.get(path, headers=headers).json() == plan

        patched = client.patch(path, headers=headers, json={"expected_revision_number": 1, "title": "수정",
            "tasks": [{"op": "update", "task_id": task_id, "changes": {"status": "DONE"}},
                      {"op": "add", "task": task("다음 일정")}]})
        assert patched.status_code == 200
        revision = patched.json()
        assert revision["revision_number"] == 2 and revision["title"] == "수정"
        assert revision["tasks"][0]["id"] == task_id and revision["tasks"][0]["status"] == "DONE"
        assert client.patch(path, headers=headers, json={"expected_revision_number": 1, "title": "오래된 수정"}).status_code == 409
        deleted = client.patch(path, headers=headers, json={"expected_revision_number": 2,
            "tasks": [{"op": "delete", "task_id": task_id}]})
        assert deleted.status_code == 200 and len(deleted.json()["tasks"]) == 1
        assert client.delete(path, headers=headers).status_code == 204
        assert client.get(path, headers=headers).status_code == 404
        with client.app.state.database.connect() as conn:
            assert conn.execute("SELECT count(*) FROM plan_tasks").fetchone()[0] == 0


def test_overlaps_save_with_warning_across_and_within_owned_plans(tmp_path):
    with open_client(tmp_path) as client:
        a, b = auth(client), auth(client)
        a_plan = save(client, a, plan_data(task("첫 일정", "2026-11-20T10:00:00+09:00", "2026-11-20T11:00:00+09:00")))
        assert a_plan["warnings"] == []
        assert save(client, b, plan_data(task("별도 소유자", "2026-11-20T10:00:00+09:00", "2026-11-20T11:00:00+09:00")))["warnings"] == []
        overlapping = save(client, a, plan_data(
            task("겹침", "2026-11-20T01:30:00Z", "2026-11-20T02:30:00Z"),
            task("경계", "2026-11-20T11:00:00+09:00", "2026-11-20T12:00:00+09:00"),
            task("시간 미정"),
        ))
        assert sorted(w["conflicting_plan_id"] for w in overlapping["warnings"]) == sorted([a_plan["id"], overlapping["id"]])
        boundary = overlapping["tasks"][1]["id"]
        changed = client.patch(PREFIX + "/plans/" + overlapping["id"], headers=a, json={
            "expected_revision_number": 1, "tasks": [{"op": "update", "task_id": boundary,
            "changes": {"scheduled_start_at": "2026-11-20T11:30:00+09:00"}}]})
        assert changed.status_code == 200 and len(changed.json()["warnings"]) == 1


def test_overlap_on_actual_kst_day_across_midnight(tmp_path):
    with open_client(tmp_path) as client:
        a = auth(client)
        save(client, a, plan_data(task("야간", "2026-11-20T23:30:00+09:00", "2026-11-21T00:30:00+09:00")))
        second = save(client, a, plan_data(task("자정 이후", "2026-11-21T00:15:00+09:00", "2026-11-21T01:00:00+09:00", when="2026-11-21")))
        assert len(second["warnings"]) == 1


def test_concurrent_revision_is_atomic(tmp_path):
    with open_client(tmp_path) as client:
        headers = auth(client)
        plan = save(client, headers, plan_data())
        path = PREFIX + "/plans/" + plan["id"]

        def update(title):
            response = client.patch(path, headers=headers, json={"expected_revision_number": 1, "title": title})
            return response.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(update, ("첫 변경", "두 번째 변경"))) == [200, 409]
        assert client.get(path, headers=headers).json()["revision_number"] == 2


def test_owner_scope_for_plan_operations_and_chat_base(tmp_path):
    with open_client(tmp_path, planner=Planner(Analysis(intent="GENERAL"))) as client:
        a, b = auth(client), auth(client)
        plan = save(client, a, plan_data(task("작업")))
        path = PREFIX + "/plans/" + plan["id"]
        assert client.get(PREFIX + "/plans", headers=b).json()["total"] == 0
        assert client.get(path, headers=b).status_code == 404
        assert client.patch(path, headers=b, json={"expected_revision_number": 1, "title": "금지"}).status_code == 404
        assert client.delete(path, headers=b).status_code == 404
        assert client.post(PREFIX + "/chat", headers=b, json={"message": "수정", "base_plan_id": plan["id"]}).status_code == 404
        b_plan = save(client, b, plan_data())
        foreign_task = client.patch(PREFIX + "/plans/" + b_plan["id"], headers=b, json={
            "expected_revision_number": 1, "tasks": [{"op": "delete", "task_id": plan["tasks"][0]["id"]}]})
        assert foreign_task.status_code == 404


def test_raw_safe_events_tool_failure_and_logs(tmp_path):
    originals = []
    counts = []

    class CountPlanner(Planner):
        def analyze(self, message, prior):
            counts.append("analyze")
            return super().analyze(message, prior)

        def plan(self, intent, tool, args):
            counts.append("plan")
            return super().plan(intent, tool, args)

    def logging_factory(database):
        logger = LoggingAgent(database)

        def consume(event):
            originals.append(event)
            logger(event)

        return consume

    secret = "raw_private_marker_12345"
    with open_client(tmp_path, planner=CountPlanner(create_plan()), run_tool=Provider(failure=(BUILDING, "TIMEOUT")),
                     subscriber_factory=logging_factory) as client:
        a, b = auth(client), auth(client)
        result = chat(client, a, BASE + " " + secret)
        assert result["status"] == "PARTIAL"
        path = PREFIX + f"/runs/{result['run_id']}/events"
        events = client.get(path, headers=a).json()
        ids = [event["event_type"] for event in events]
        assert ids[0] == "RUN_STARTED" and ids[-1] == "RUN_FINISHED"
        assert {"NODE_STARTED", "NODE_FINISHED", "INTENT_DECIDED", "WORKFLOW_CREATED", "TOOL_REQUESTED",
                "TOOL_SUCCEEDED", "TOOL_FAILED", "CONSTRAINT_EVALUATED"} <= set(ids)
        assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
        assert all(e["duration_ms"] >= 0 for e in events if e["event_type"] == "NODE_FINISHED")
        assert any(e["reason_summary"] and e["payload"]["intent"] == "CREATE_PLAN"
                   for e in events if e["event_type"] == "INTENT_DECIDED")
        assert next(e["payload"]["code"] for e in events if e["event_type"] == "TOOL_FAILED") == "TIMEOUT"
        assert [e["payload"] for e in events] == [e.payload for e in originals]
        assert secret not in json.dumps(events) and a["Authorization"] not in json.dumps(events)
        assert counts == ["analyze", "plan"]

        session = events[0]["session_id"]
        logs = PREFIX + "/logs"
        assert client.get(logs, headers=a).json()["items"][0]["run_count"] == 1
        assert client.get(logs, headers=b).json()["items"] == []
        assert client.get(logs + "/" + session, headers=a).json()["events"] == events
        assert client.get(logs + "/" + session, headers=b).status_code == 404
        assert client.delete(logs + "/" + session, headers=b).status_code == 404
        assert client.patch(logs + "/" + session, headers=a, json={}).status_code == 405
        assert set(client.get("/openapi.json").json()["paths"][logs + "/{session_id}"]) == {"get", "delete"}
        with pytest.raises(sqlite3.IntegrityError):
            with client.app.state.database.connect(write=True) as conn:
                conn.execute("UPDATE run_events SET sequence = 999")
        counts_before = counts.copy()
        deletion = client.delete(logs + "/" + session, headers=a)
        assert deletion.json()["deleted_events"] == len(events)
        assert client.get(path, headers=a).status_code == 404
        assert client.get(logs + "/" + session, headers=a).json()["events"] == []
        assert counts == counts_before


@pytest.mark.parametrize("mode", ["missing", "broken"])
def test_logging_outage_does_not_stop_agent(tmp_path, mode):
    def factory(database):
        def broken(event):
            raise RuntimeError("private upstream error")
        return broken

    with open_client(tmp_path, planner=Planner(create_plan()), run_tool=Provider(),
                     subscriber_factory=factory if mode == "broken" else None) as client:
        headers = auth(client)
        response = chat(client, headers)
        assert response["draft_plan"] is not None and response["status"] == "SUCCEEDED"
        assert client.get(PREFIX + f"/runs/{response['run_id']}/events", headers=headers).json() == []
        assert client.get(PREFIX + "/logs", headers=headers).json()["items"][0]["run_count"] == 1


def test_replan_terminal_events_and_failed_run(tmp_path):
    provider = Provider(rents=dict.fromkeys((code for _, code in AREAS), 800_000))
    with open_client(tmp_path, planner=Planner(create_plan(3), create_plan()), run_tool=provider) as client:
        headers = auth(client)
        response = chat(client, headers, BASE + " " + ALTERNATIVES)
        assert response["status"] == "EXHAUSTED"
        events = client.get(PREFIX + f"/runs/{response['run_id']}/events", headers=headers).json()
        types = [event["event_type"] for event in events]
        assert types.count("REPLAN_STARTED") == 3 and types.count("REPLAN_EXHAUSTED") == 1
        provider.failure = ("search_rental_transactions", "AUTH_FAILED")
        failure = client.post(PREFIX + "/chat", headers=headers, json={"message": BASE})
        assert failure.status_code == 502 and failure.json()["error"]["code"] == "AUTH_FAILED"
        session = events[0]["session_id"]
        detail = client.get(PREFIX + f"/logs/{session}", headers=headers).json()
        assert detail["runs"][-1]["status"] == "FAILED" and detail["events"][-1]["event_type"] == "RUN_FAILED"


def test_owned_run_citations_and_cascade_are_server_controlled(tmp_path):
    with open_client(tmp_path, planner=Planner(create_plan()), run_tool=Provider()) as client:
        a, b = auth(client), auth(client)
        reply = chat(client, a)
        draft = reply["draft_plan"]
        body = {key: draft[key] for key in ("title", "category", "planning_start_date", "planning_end_date",
                                            "constraints", "tasks", "source_refs")}
        body["generated_by_run_id"] = reply["run_id"]
        assert client.post(PREFIX + "/plans", headers=b, json=body).status_code == 404
        assert client.post(PREFIX + "/plans", headers=a, json={**body, "source_refs": [str(uuid4())]}).status_code == 422
        saved = save(client, a, body)
        assert len(saved["sources"]) == 3 and saved["evaluations"]
        assert all(source["verification_status"] == "SOURCE_CONFIRMED" for source in saved["sources"])
        changed = save(client, a, {**body, "constraints": {**body["constraints"], "max_deposit_krw": 1000}})
        assert changed["evaluations"] == []
        assert client.delete(PREFIX + "/logs/" + saved["session_id"], headers=a).status_code == 200
        path = PREFIX + "/plans/" + saved["id"]
        after = client.get(path, headers=a).json()
        assert after["generated_by_run_id"] is None and after["sources"] and after["evaluations"]
        assert client.delete(path, headers=a).status_code == 204
        with client.app.state.database.connect() as conn:
            for table in ("plan_tasks", "plan_sources", "plan_evaluations"):
                assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE plan_id = ?", (saved["id"],)).fetchone()[0] == 0


def test_rejects_invalid_dto_without_echo(tmp_path):
    with open_client(tmp_path) as client:
        headers = auth(client)
        invalid = client.post(PREFIX + "/chat", headers=headers, json={"message": "private marker", "thread_id": "override"})
        assert invalid.status_code == 422 and "private marker" not in invalid.text
        assert set(invalid.json()["error"]) == {"code", "message", "request_id"}
        event = task("시차 없는 작업", "2026-11-20T10:00:00", "2026-11-20T11:00:00")
        assert client.post(PREFIX + "/plans", headers=headers, json=plan_data(event)).status_code == 422



def test_owned_base_plan_and_sqlite_restart(tmp_path):
    constraints = create_plan().patch.model_dump(mode="json", exclude_none=True)
    with open_client(tmp_path) as client:
        headers = auth(client)
        saved = save(client, headers, {**plan_data(), "constraints": constraints})
    update = Analysis(intent="UPDATE_CONSTRAINT", patch=ConstraintPatch(max_monthly_rent_krw=550_000),
                      evidence={"max_monthly_rent_krw": "월세만 55만원"})
    with open_client(tmp_path, planner=Planner(update), run_tool=Provider()) as client:
        response = chat(client, headers, "월세만 55만원으로 바꿔줘.", base_plan_id=saved["id"])
        assert response["status"] == "SUCCEEDED"
        assert response["constraints"]["max_deposit_krw"] == 30_000_000
        assert response["constraints"]["max_monthly_rent_krw"] == 550_000
        read = client.get(PREFIX + "/plans/" + saved["id"], headers=headers).json()
        assert read["constraints"]["max_monthly_rent_krw"] == 600_000


def test_unexpected_provider_exception_is_sanitized_and_partial(tmp_path):
    class BrokenProvider(Provider):
        def __call__(self, tool, args):
            if tool == BUILDING:
                raise RuntimeError("private-provider-response")
            return super().__call__(tool, args)

    with open_client(tmp_path, planner=Planner(create_plan()), run_tool=BrokenProvider()) as client:
        headers = auth(client)
        result = chat(client, headers)
        assert result["status"] == "PARTIAL" and result["draft_plan"]
        events = client.get(PREFIX + f"/runs/{result['run_id']}/events", headers=headers)
        assert events.status_code == 200 and "private-provider-response" not in events.text
        failure = next(e for e in events.json() if e["event_type"] == "TOOL_FAILED")
        assert failure["payload"]["code"] == "UNKNOWN_ERROR"
