import json

from .publisher import AgentEvent


class LoggingAgent:
    def __init__(self, database):
        self.database = database

    def __call__(self, event: AgentEvent):
        with self.database.connect(write=True) as conn:
            conn.execute(
                """INSERT INTO run_events
                    (id, run_id, sequence, event_type, node_name, occurred_at, duration_ms, payload_json)
                   SELECT ?, id, ?, ?, ?, ?, ?, ? FROM agent_runs WHERE id = ? AND session_id = ?""",
                (str(event.event_id), event.sequence, event.event_type, event.node_name,
                 event.timestamp.isoformat(timespec="microseconds"), event.duration_ms,
                 json.dumps(event.payload, ensure_ascii=False), str(event.run_id), str(event.session_id)),
            )

