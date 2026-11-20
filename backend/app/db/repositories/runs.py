import json

from ...core.errors import not_found
from ..connection import utc_now

RUN_COLUMNS = "id, session_id, intent, status, replan_count, started_at, finished_at, safe_error_code"
EVENT_COLUMNS = """e.id AS event_id, e.run_id, r.session_id, e.sequence,
                   e.occurred_at AS timestamp, e.event_type, e.node_name, e.duration_ms, e.payload_json"""


def create_run(database, session_id, run_id):
    with database.connect(write=True) as conn:
        conn.execute(
            """INSERT INTO agent_runs(id, session_id, thread_id, status, started_at)
               VALUES (?, ?, ?, 'RUNNING', ?)""", (str(run_id), str(session_id), str(session_id), utc_now()),
        )


def finish_run(database, session_id, run_id, *, status, intent=None, replan_count=0, error=None):
    with database.connect(write=True) as conn:
        conn.execute(
            """UPDATE agent_runs SET status = ?, intent = ?, replan_count = ?, finished_at = ?, safe_error_code = ?
               WHERE id = ? AND session_id = ?""",
            (status, intent, replan_count, utc_now(), error, str(run_id), str(session_id)),
        )


def owned_run(conn, session_id, run_id):
    run = conn.execute(f"SELECT {RUN_COLUMNS} FROM agent_runs WHERE id = ? AND session_id = ?",
                       (str(run_id), str(session_id))).fetchone()
    if run is None:
        raise not_found()
    return dict(run)


def _events(conn, session_id, run_id=None):
    sql = f"""SELECT {EVENT_COLUMNS} FROM run_events e JOIN agent_runs r ON r.id = e.run_id
               WHERE r.session_id = ?"""
    params = [str(session_id)]
    if run_id is not None:
        sql += " AND r.id = ?"
        params.append(str(run_id))
    sql += " ORDER BY r.started_at, r.rowid, e.sequence"
    events = []
    for row in conn.execute(sql, params):
        data = dict(row)
        payload = json.loads(data.pop("payload_json"))
        events.append({**data, "payload": payload, "reason_summary": payload.get("reason_summary")})
    return events


def run_events(database, session_id, run_id):
    with database.connect() as conn:
        owned_run(conn, session_id, run_id)
        return _events(conn, session_id, run_id)


def list_logs(database, session_id, limit, offset):
    with database.connect() as conn:
        rows = conn.execute(
            """SELECT session_id, COUNT(*) AS run_count, MAX(started_at) AS last_run_at
               FROM agent_runs WHERE session_id = ? GROUP BY session_id""", (str(session_id),),
        ).fetchall()
    return {"items": [dict(row) for row in rows[offset:offset + limit]], "total": len(rows),
            "limit": limit, "offset": offset}


def log_detail(database, session_id):
    with database.connect() as conn:
        rows = conn.execute(f"SELECT {RUN_COLUMNS} FROM agent_runs WHERE session_id = ? ORDER BY started_at, rowid",
                            (str(session_id),))
        return {"session_id": session_id, "runs": [dict(row) for row in rows], "events": _events(conn, session_id)}


def delete_logs(database, session_id):
    with database.connect(write=True) as conn:
        params = (str(session_id),)
        events = conn.execute(
            """SELECT COUNT(*) FROM run_events e JOIN agent_runs r ON r.id = e.run_id WHERE r.session_id = ?""",
            params,
        ).fetchone()[0]
        deleted = conn.execute("DELETE FROM agent_runs WHERE session_id = ?", params).rowcount
    return {"session_id": session_id, "deleted_runs": deleted, "deleted_events": events}

