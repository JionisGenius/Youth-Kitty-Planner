from collections import defaultdict

from ..agents.planner import DIAGNOSIS_CAUSES, PlannerError
from ..agents.state import RunAssessment
from ..db.repositories.runs import run_events
from ..services.replan_policy import MAX_REPLANS
from .publisher import RunEvents


def assess_run(database, stream: RunEvents, replan_count: int, diagnose) -> RunAssessment:
    try:
        events = run_events(database, stream.session_id, stream.run_id)
        assessment = evaluate_events(events, stream.sequence, replan_count)
    except Exception:
        # Missing, unreadable or invalid logs cannot prove an anomaly.
        return RunAssessment()
    if assessment.status != "ANOMALOUS":
        return assessment

    assessment.diagnosis = {"status": "INCOMPLETE", "code": "DIAGNOSIS_UNAVAILABLE"}
    if diagnose is not None:
        try:
            cause = diagnose(tuple(assessment.findings))
            if cause in DIAGNOSIS_CAUSES:
                assessment.diagnosis = {"status": "COMPLETED", "cause": cause}
            else:
                assessment.diagnosis["code"] = "SCHEMA_MISMATCH"
        except PlannerError as error:
            assessment.diagnosis["code"] = error.code if error.code in {
                "RATE_LIMITED", "AUTH_FAILED", "TIMEOUT", "SERVICE_UNAVAILABLE", "SCHEMA_MISMATCH",
            } else "DIAGNOSIS_UNAVAILABLE"
        except Exception:
            pass
    return assessment


def evaluate_events(events, published_count: int, replan_count: int) -> RunAssessment:
    if not events or [e["sequence"] for e in events] != list(range(1, published_count + 1)):
        return RunAssessment()
    if events[0]["event_type"] != "RUN_STARTED":
        return RunAssessment()

    findings = defaultdict(set)
    mismatch = findings["WORKFLOW_EXECUTION_MISMATCH"]
    planned = {}
    pending = set()
    performed = {}
    outstanding = {}
    results = {}
    intents = []
    replans = []
    active_node = None
    completed_nodes = []
    for event in events[1:]:
        kind, seq = event["event_type"], event["sequence"]
        node, payload = event["node_name"], event["payload"]
        if kind == "NODE_STARTED":
            if active_node is not None or not node:
                return RunAssessment()
            active_node = node
            continue
        if active_node is None or node != active_node:
            return RunAssessment()

        if kind == "INTENT_DECIDED":
            if node != "analyze_request" or not payload.get("intent"):
                return RunAssessment()
            intents.append(seq)
        elif kind == "WORKFLOW_CREATED":
            if node != "plan_workflow" or not payload["steps"]:
                return RunAssessment()
            for step in payload["steps"]:
                step_id = step["step_id"]
                if step_id in planned:
                    mismatch.update((planned[step_id][2], seq))
                planned[step_id] = (step["tool_name"], step["depends_on"], seq)
                pending.add(step_id)
        elif kind == "TOOL_REQUESTED":
            if node != "execute_tools":
                return RunAssessment()
            step_id, name, cached = payload["step_id"], payload["tool_name"], payload["is_cached"]
            fingerprint = payload["argument_fingerprint"]
            if type(cached) is not bool or not isinstance(fingerprint, str) or len(fingerprint) != 64:
                return RunAssessment()
            key = (name, fingerprint)
            if not cached:
                if key in performed:
                    findings["DUPLICATE_TOOL_CALL"].update((performed[key], seq))
                performed[key] = seq
            plan = planned.get(step_id)
            if plan is None or plan[0] != name:
                findings["UNPLANNED_TOOL"].add(seq)
            elif step_id not in pending or any(dep not in results for dep in plan[1]):
                mismatch.update((plan[2], seq))
            if step_id in outstanding:
                return RunAssessment()
            if step_id in results:
                mismatch.update((results[step_id][3], seq))
            outstanding[step_id] = (name, cached, seq)
        elif kind in {"TOOL_SUCCEEDED", "TOOL_FAILED"}:
            if node != "execute_tools":
                return RunAssessment()
            step_id = payload["step_id"]
            request = outstanding.pop(step_id, None)
            if request is None or type(payload["is_cached"]) is not bool:
                return RunAssessment()
            if request[:2] != (payload["tool_name"], payload["is_cached"]):
                mismatch.update((request[2], seq))
            status = "SUCCEEDED" if kind == "TOOL_SUCCEEDED" else "FAILED"
            results[step_id] = (payload["tool_name"], status, payload["is_cached"], seq)
        elif kind == "REPLAN_STARTED":
            count = payload["replan_count"]
            if node != "replan" or type(count) is not int:
                return RunAssessment()
            replans.append(seq)
            if count > MAX_REPLANS or len(replans) > MAX_REPLANS:
                findings["REPLAN_LIMIT_EXCEEDED"].add(seq)
        elif kind == "NODE_FINISHED":
            if payload.get("outcome") != "COMPLETED":
                return RunAssessment()
            if node == "execute_tools":
                if outstanding or not isinstance(payload.get("steps"), list):
                    return RunAssessment()
                _compare_steps(payload["steps"], planned, pending, results, seq, mismatch)
                pending.clear()
                results.clear()
            active_node = None
            completed_nodes.append(node)

    if active_node is not None or len(intents) != 1 or not completed_nodes or completed_nodes[-1] != "generate_response":
        return RunAssessment()
    for step_id in pending:
        mismatch.add(planned[step_id][2])
    if replan_count > MAX_REPLANS:
        findings["REPLAN_LIMIT_EXCEEDED"].add(events[-1]["sequence"])
    elif len(replans) != replan_count and "REPLAN_LIMIT_EXCEEDED" not in findings:
        return RunAssessment()
    evidence = {code: sorted(sequences) for code, sequences in findings.items() if sequences}
    return RunAssessment(status="ANOMALOUS" if evidence else "NORMAL", findings=evidence)


def _compare_steps(steps, planned, pending, results, seq, mismatch):
    reported = set()
    for step in steps:
        step_id, name, status = step["step_id"], step["tool_name"], step["status"]
        actual = results.get(step_id)
        if step_id in reported or step_id not in pending or planned[step_id][0] != name:
            mismatch.add(seq)
        if status == "SKIPPED":
            if actual is not None:
                mismatch.update((actual[3], seq))
        elif status not in {"SUCCEEDED", "FAILED"} or actual is None or actual[:2] != (name, status):
            mismatch.add(seq)
            if actual is not None:
                mismatch.add(actual[3])
        reported.add(step_id)
    for step_id in pending - reported:
        mismatch.update((planned[step_id][2], seq))
    for step_id in results.keys() - reported:
        mismatch.update((results[step_id][3], seq))
