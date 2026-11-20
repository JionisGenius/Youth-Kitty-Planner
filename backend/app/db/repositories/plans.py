from datetime import date, timedelta
import json
from uuid import uuid4

from pydantic import ValidationError

from ...core.errors import ApiProblem, invalid, not_found
from ...schemas.agent import UserConstraints
from ...schemas.api import TaskInput
from ...services.provenance import plan_evidence
from ...tools.executor import KST
from ..connection import utc_now
from .runs import owned_run

TASK_FIELDS = tuple(TaskInput.model_fields)


def owned_plan(conn, session_id, plan_id):
    row = conn.execute("SELECT * FROM plans WHERE id = ? AND session_id = ?",
                       (str(plan_id), str(session_id))).fetchone()
    if row is None:
        raise not_found()
    return dict(row)


def base_constraints(database, session_id, plan_id):
    with database.connect() as conn:
        plan = owned_plan(conn, session_id, plan_id)
    return UserConstraints.model_validate_json(plan["constraints_json"])


def _task_fields(task, start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if not first <= task.task_date <= last:
        raise invalid("작업 날짜가 계획 기간을 벗어났습니다.")
    if task.scheduled_start_at is not None:
        try:
            local_start = task.scheduled_start_at.astimezone(KST)
            last_active = (task.scheduled_end_at - timedelta(microseconds=1)).astimezone(KST)
        except OverflowError:
            raise invalid("작업 시간 범위를 확인해 주세요.") from None
        if local_start.date() != task.task_date or last_active.date() > last:
            raise invalid("작업의 한국시간 날짜 또는 계획 기간을 확인해 주세요.")
    data = task.model_dump(mode="json")
    for field in ("scheduled_start_at", "scheduled_end_at"):
        if (stamp := getattr(task, field)) is not None:
            data[field] = stamp.isoformat(timespec="microseconds")
    return [data[field] for field in TASK_FIELDS]


def _add_task(conn, plan, task, stamp, position):
    if "sort_order" not in task.model_fields_set:
        if position > 2**63 - 1:
            raise invalid("작업 순서를 명시해 주세요.")
        task = task.model_copy(update={"sort_order": position})
    values = _task_fields(task, plan["planning_start_date"], plan["planning_end_date"])
    columns = ", ".join(TASK_FIELDS)
    placeholders = ", ".join("?" for _ in TASK_FIELDS)
    conn.execute(
        f"""INSERT INTO plan_tasks (id, plan_id, {columns}, source_kind, created_at, updated_at)
            VALUES (?, ?, {placeholders}, 'USER_EDIT', ?, ?)""",
        (str(uuid4()), plan["id"], *values, stamp, stamp),
    )


def _overlaps(conn, plan):
    rows = conn.execute(
        """SELECT a.id AS task_id, b.id AS conflicting_task_id, b.plan_id AS conflicting_plan_id
           FROM plan_tasks a JOIN plan_tasks b
             ON a.scheduled_start_at < b.scheduled_end_at AND b.scheduled_start_at < a.scheduled_end_at
                AND (a.plan_id <> b.plan_id OR a.rowid < b.rowid)
           JOIN plans p ON p.id = b.plan_id
           WHERE a.plan_id = ? AND p.session_id = ?
           ORDER BY a.sort_order, a.rowid, b.sort_order, b.rowid""", (plan["id"], plan["session_id"]),
    )
    return [{"code": "TIME_OVERLAP", **dict(row)} for row in rows]


def _read(conn, plan):
    data = plan.copy()
    plan_id = (plan["id"],)
    data["constraints"] = json.loads(data.pop("constraints_json"))
    data["tasks"] = [dict(row) for row in conn.execute(
        "SELECT * FROM plan_tasks WHERE plan_id = ? ORDER BY sort_order, rowid", plan_id)]
    data["sources"] = [dict(row) for row in conn.execute(
        "SELECT * FROM plan_sources WHERE plan_id = ? ORDER BY rowid", plan_id)]
    evaluations = []
    for row in conn.execute("SELECT * FROM plan_evaluations WHERE plan_id = ? ORDER BY rowid", plan_id):
        item = dict(row)
        for field in ("expected", "observed"):
            value = item.pop(f"{field}_json")
            item[f"{field}_value"] = json.loads(value) if value is not None else None
        evaluations.append(item)
    data["evaluations"] = evaluations
    data["warnings"] = _overlaps(conn, plan)
    return data


def create_plan(database, session, data):
    plan_id = str(uuid4())
    stamp = utc_now()
    run_id = str(data.generated_by_run_id) if data.generated_by_run_id is not None else None
    with database.connect(write=True) as conn:
        if run_id:
            run = owned_run(conn, session.id, run_id)
            if run["status"] in {"RUNNING", "FAILED", "NEEDS_INPUT"}:
                raise invalid("저장할 수 있는 완료된 실행을 지정해 주세요.")
        sources, checks = plan_evidence(conn, session, data)
        conn.execute(
            """INSERT INTO plans (id, session_id, title, category, planning_start_date, planning_end_date,
                   work_location_label, constraints_json, generated_by_run_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plan_id, str(session.id), data.title, data.category, data.planning_start_date.isoformat(),
             data.planning_end_date.isoformat(), _work_label(data.constraints), data.constraints.model_dump_json(),
             run_id, stamp, stamp),
        )
        plan = owned_plan(conn, session.id, plan_id)
        for order, task in enumerate(data.tasks):
            _add_task(conn, plan, task, stamp, order)
        _save_evidence(conn, plan_id, data.constraints, sources, checks, stamp)
        return _read(conn, plan)


def _save_evidence(conn, plan_id, constraints, sources, checks, stamp):
    ids = {}
    for source in sources:
        ids[source["ref"]] = str(uuid4())
        conn.execute(
            """INSERT INTO plan_sources (id, plan_id, source_type, provider, source_ref, source_url,
                   fetched_at, observed_at, verification_status, caveat)
               VALUES (?, ?, 'OFFICIAL_API', ?, ?, ?, ?, ?, 'SOURCE_CONFIRMED', ?)""",
            (ids[source["ref"]], plan_id, source["provider"], source["ref"], source["url"],
             source["fetched_at"], source["observed_at"], source["caveat"]),
        )
    expected = {
        "HISTORICAL_DEPOSIT": constraints.max_deposit_krw,
        "HISTORICAL_RENT": constraints.max_monthly_rent_krw,
        "MAINTENANCE_FEE": constraints.max_maintenance_fee_krw,
        "COMMUTE_TIME": constraints.max_commute_minutes,
        "PLAN_TIMELINE": constraints.job_start_date.isoformat() if constraints.job_start_date else None,
    }
    for check in checks:
        source_id = ids[check["refs"][0]] if check["refs"] else None
        limit = expected.get(check["rule"])
        conn.execute(
            """INSERT INTO plan_evaluations
                   (id, plan_id, rule_code, status, expected_json, reason_code, source_id, checked_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid4()), plan_id, check["rule"], check["status"], json.dumps(limit) if limit is not None else None,
             check["reason"], source_id, stamp),
        )


def get_plan(database, session_id, plan_id):
    with database.connect() as conn:
        return _read(conn, owned_plan(conn, session_id, plan_id))


def list_plans(database, session_id, limit, offset):
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM plans WHERE session_id = ? ORDER BY updated_at DESC, id LIMIT ? OFFSET ?",
            (str(session_id), limit, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM plans WHERE session_id = ?", (str(session_id),)).fetchone()[0]
        return {"items": [_read(conn, dict(row)) for row in rows], "total": total, "limit": limit, "offset": offset}


def _work_label(constraints):
    return constraints.work_location.label if constraints.work_location else None


def update_plan(database, session_id, plan_id, data):
    with database.connect(write=True) as conn:
        plan = owned_plan(conn, session_id, plan_id)
        if plan["revision_number"] != data.expected_revision_number:
            raise ApiProblem(409, "REVISION_CONFLICT", "계획이 변경되었습니다. 최신 버전을 확인해 주세요.")
        stamp = utc_now()
        existing_constraints = UserConstraints.model_validate_json(plan["constraints_json"])
        constraints = data.constraints if data.constraints is not None else existing_constraints
        if constraints != existing_constraints:
            conn.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", (plan["id"],))
        for op in data.tasks or []:
            _apply_task_operation(conn, plan, op, stamp)
        if conn.execute("SELECT COUNT(*) FROM plan_tasks WHERE plan_id = ?", (plan["id"],)).fetchone()[0] > 100:
            raise invalid("계획당 작업은 최대 100개입니다.")
        conn.execute(
            """UPDATE plans SET title = ?, constraints_json = ?, work_location_label = ?,
                   updated_at = ?, revision_number = revision_number + 1
               WHERE id = ? AND session_id = ?""",
            (data.title or plan["title"], constraints.model_dump_json(), _work_label(constraints),
             stamp, plan["id"], str(session_id)),
        )
        return _read(conn, owned_plan(conn, session_id, plan_id))


def _apply_task_operation(conn, plan, op, stamp):
    plan_id = plan["id"]
    if op.op == "add":
        position = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM plan_tasks WHERE plan_id = ?",
                                (plan_id,)).fetchone()[0] + 1
        _add_task(conn, plan, op.task, stamp, position)
        return
    keys = (str(op.task_id), plan_id)
    row = conn.execute("SELECT * FROM plan_tasks WHERE id = ? AND plan_id = ?", keys).fetchone()
    if row is None:
        raise not_found()
    if op.op == "delete":
        conn.execute("DELETE FROM plan_tasks WHERE id = ? AND plan_id = ?", keys)
        return
    try:
        task = TaskInput.model_validate({
            **{field: row[field] for field in TASK_FIELDS}, **op.changes.model_dump(exclude_unset=True),
        })
    except ValidationError:
        raise invalid("작업의 필수 값과 시작·종료 시각을 확인해 주세요.") from None
    values = _task_fields(task, plan["planning_start_date"], plan["planning_end_date"])
    setters = ", ".join(f"{field} = ?" for field in TASK_FIELDS)
    conn.execute(f"UPDATE plan_tasks SET {setters}, source_kind = 'USER_EDIT', updated_at = ? WHERE id = ? AND plan_id = ?",
                 (*values, stamp, *keys))


def delete_plan(database, session_id, plan_id):
    with database.connect(write=True) as conn:
        if not conn.execute("DELETE FROM plans WHERE id = ? AND session_id = ?",
                            (str(plan_id), str(session_id))).rowcount:
            raise not_found()

