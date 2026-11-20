from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from threading import Lock
from typing import TypedDict
from uuid import UUID, uuid4

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langsmith import tracing_context
import requests

from ..core.config import load_api_keys
from ..events.publisher import RunEvents
from ..schemas.agent import UserConstraints
from ..tools.executor import execute_tool
from .graph import GraphContext, build_graph
from .planner import GmsPlanner
from .state import AgentState

DEFAULT_CHECKPOINT = Path(__file__).resolve().parents[2] / "data" / "agent-checkpoint.sqlite3"


class MemoryState(TypedDict, total=False):
    constraints: dict
    contract_month: str | None


@dataclass
class Turn:
    thread_id: UUID
    message: str
    run_id: UUID
    events: RunEvents | None = None
    base_constraints: UserConstraints | None = None
    result: AgentState | None = None


class Agent:
    def __init__(self, saver, planner, run_tool, assess=None):
        execution = build_graph(planner, run_tool)

        def run_turn(state: MemoryState, runtime: Runtime[Turn]):
            turn = runtime.context
            turn.result = execution.invoke({
                "thread_id": str(turn.thread_id), "run_id": turn.run_id, "user_message": turn.message,
                "messages": [], "user_constraints": turn.base_constraints or UserConstraints.model_validate(state.get("constraints", {})),
                "contract_month": None if turn.base_constraints else state.get("contract_month"),
                "changed_fields": [], "missing_fields": [],
                "workflow_steps": [], "tool_results": {}, "tool_cache": {}, "candidates": [],
                "constraint_results": [], "sources": [], "errors": [], "warnings": [], "replan_count": 0,
                "attempted_strategies": [], "execution_status": "RUNNING", "replan_reason": "",
            }, config={"recursion_limit": 40}, context=GraphContext(turn.events))
            if turn.result.get("intent") not in {"CREATE_PLAN", "UPDATE_CONSTRAINT"}:
                return {}
            return {"constraints": turn.result["user_constraints"].model_dump(mode="json"),
                    "contract_month": turn.result["contract_month"]}

        graph = StateGraph(MemoryState, context_schema=Turn)
        graph.add_node("run_turn", run_turn)
        graph.add_edge(START, "run_turn")
        graph.add_edge("run_turn", END)
        self._memory = graph.compile(checkpointer=saver)
        self._locks = [Lock() for _ in range(32)]
        self._assess = assess
        self._diagnose = getattr(planner, "diagnose_anomaly", None)

    @staticmethod
    def new_session_id() -> UUID:
        return uuid4()

    def run(self, thread_id: UUID, message: str, *, events: RunEvents | None = None,
            base_constraints: UserConstraints | None = None) -> AgentState:
        # The API supplies the authenticated session UUID as the thread identifier.
        if not isinstance(thread_id, UUID):
            raise ValueError("A server-issued session UUID is required.")
        if not isinstance(message, str) or not message.strip() or len(message) > 4000:
            raise ValueError("The message must contain 1 to 4000 characters.")
        if events is not None and events.session_id != thread_id:
            raise ValueError("Event stream session does not match the agent thread.")
        turn = Turn(thread_id, message.strip(), events.run_id if events else uuid4(), events, base_constraints)
        with self._locks[thread_id.int % len(self._locks)], tracing_context(enabled=False):
            self._memory.invoke({}, config={"configurable": {"thread_id": str(thread_id)}}, context=turn)
        if turn.result is None:
            raise RuntimeError("The graph did not complete the turn.")
        if events is not None and self._assess is not None:
            assessment = self._assess(events, turn.result["replan_count"], self._diagnose)
            turn.result["run_assessment"] = assessment
            if assessment.status == "ANOMALOUS":
                turn.result["warnings"] = [
                    *turn.result["warnings"],
                    "실행 기록에서 이상 징후가 확인되었습니다. 실행 기록을 확인해 주세요.",
                ]
        return turn.result


@contextmanager
def open_agent(checkpoint_path: Path = DEFAULT_CHECKPOINT, *, planner=None, run_tool=None, assess=None):
    checkpoint_path = Path(checkpoint_path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    if run_tool is None:
        keys = load_api_keys()

        def run_tool(name, args):
            # Provider auth stays separate from the GMS HTTP session.
            with requests.Session() as session:
                return execute_tool(name, args, session=session, keys=keys)

    with closing(sqlite3.connect(checkpoint_path, check_same_thread=False)) as connection:
        saver = SqliteSaver(connection, serde=JsonPlusSerializer(allowed_msgpack_modules=[]))
        yield Agent(saver, GmsPlanner() if planner is None else planner, run_tool, assess)

