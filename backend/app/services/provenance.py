from datetime import datetime, time, timezone
from hmac import compare_digest, digest
import json
from uuid import uuid5

from ..core.errors import invalid
from .constraint_engine import preparation_end

PROVIDERS = {
    "molit_rent": ("MOLIT_RENT", "https://www.data.go.kr/data/15126473/openapi.do"),
    "building_hub": ("BUILDING_HUB", "https://www.data.go.kr/data/15134735/openapi.do"),
    "kakao_local": ("KAKAO_LOCAL", "https://developers.kakao.com/docs/ko/local/dev-guide"),
}
DATE_INDEPENDENT_CHECKS = {"HISTORICAL_DEPOSIT", "HISTORICAL_RENT", "CURRENT_LISTING", "BUILDING_MATCH"}


def _scope(session, run_id, constraints, start, end):
    data = constraints.model_dump(mode="json")
    data["fixed_fields"].sort()
    raw = json.dumps([str(run_id), data, str(start), str(end)], sort_keys=True, ensure_ascii=False)
    return digest(bytes.fromhex(session.token_hash), raw.encode(), "sha256").hex()


def evidence_for_run(session, result):
    run_id = result["run_id"]
    aliases = {source.ref: str(uuid5(run_id, source.ref))
               for source in result["sources"] if source.provider in PROVIDERS}
    sources = []
    for source in result["sources"]:
        if source.ref not in aliases or source.provider not in PROVIDERS:
            continue
        provider, url = PROVIDERS[source.provider]
        date_observed = datetime.combine(source.observed_at, time.min, tzinfo=timezone.utc) if source.observed_at else None
        sources.append({
            "ref": aliases[source.ref], "provider": provider, "url": url,
            "fetched_at": source.fetched_at.isoformat() if source.fetched_at else None,
            "observed_at": date_observed.isoformat() if date_observed else None,
            "caveat": "과거 신고 거래이며 현재 임대 여부는 확인되지 않았습니다." if provider == "MOLIT_RENT" else None,
        })
    draft = result.get("draft_plan")
    checks = []
    scope = None
    if draft is not None:
        scope = _scope(session, run_id, draft.constraints, draft.planning_start_date, draft.planning_end_date)
        checks = [{"rule": check.rule_code, "status": check.status, "reason": check.reason_code,
                   "refs": [aliases[ref] for ref in check.source_refs if ref in aliases]}
                  for check in draft.evaluations]
    return aliases, {"scope": scope, "sources": sources, "checks": checks}


def plan_evidence(conn, session, run_id, constraints, start, end, source_refs):
    if run_id is None:
        return [], []
    row = conn.execute(
        """SELECT e.payload_json FROM run_events e JOIN agent_runs r ON r.id = e.run_id
           WHERE r.id = ? AND r.session_id = ? AND e.event_type = 'RUN_FINISHED'
           ORDER BY e.sequence DESC LIMIT 1""",
        (str(run_id), str(session.id)),
    ).fetchone()
    evidence = json.loads(row[0]).get("evidence", {}) if row else {}
    available = {source["ref"]: source for source in evidence.get("sources", [])}
    refs = [str(ref) for ref in source_refs] if source_refs is not None else list(available)
    if any(ref not in available for ref in refs):
        raise invalid("이 실행에서 확인한 출처만 저장할 수 있습니다.")
    scope = _scope(session, run_id, constraints, start, end)
    recorded_scope = evidence.get("scope") or ""
    checks = evidence.get("checks", [])
    if not compare_digest(recorded_scope, scope):
        # The draft dates are derived from the original constraints. Only date-independent
        # results survive when the saved dates differ but those constraints still match.
        draft_scope = _scope(session, run_id, constraints, constraints.planning_start_date, preparation_end(constraints))
        checks = ([check for check in checks if check["rule"] in DATE_INDEPENDENT_CHECKS]
                  if compare_digest(recorded_scope, draft_scope) else [])
    selected = set(refs)
    return [available[ref] for ref in refs], [check for check in checks if set(check["refs"]) <= selected]

