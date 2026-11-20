from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from time import monotonic
from typing import Literal
from uuid import UUID, uuid4

EventType = Literal[
    "RUN_STARTED", "NODE_STARTED", "NODE_FINISHED", "INTENT_DECIDED", "WORKFLOW_CREATED",
    "TOOL_REQUESTED", "TOOL_SUCCEEDED", "TOOL_FAILED", "CONSTRAINT_EVALUATED",
    "REPLAN_STARTED", "REPLAN_EXHAUSTED", "RUN_FINISHED", "RUN_FAILED",
]
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentEvent:
    event_id: UUID
    run_id: UUID
    session_id: UUID
    sequence: int
    timestamp: datetime
    event_type: EventType
    node_name: str | None
    duration_ms: int | None
    payload: dict


class Publisher:
    def __init__(self, *subscribers):
        self._subscribers = tuple(subscribers)

    def publish(self, event: AgentEvent):
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception:
                # The diagnostics must not serialize the event or exception message.
                log.warning("YKP event subscriber failed")


@dataclass
class RunEvents:
    publisher: Publisher
    run_id: UUID
    session_id: UUID
    sequence: int = field(default=0, init=False)

    def emit(self, event_type, *, node=None, start=None, **payload):
        # Callers construct payloads from allowlisted summaries, never requests or tool data.
        self.sequence += 1
        self.publisher.publish(AgentEvent(
            event_id=uuid4(), run_id=self.run_id, session_id=self.session_id,
            sequence=self.sequence, timestamp=datetime.now(timezone.utc), event_type=event_type,
            node_name=node, duration_ms=None if start is None else round((monotonic() - start) * 1000),
            payload=payload,
        ))

