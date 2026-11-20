from ..agents.state import Strategy

MAX_REPLANS = 3
INITIAL_LIMIT = 20


def next_strategy(state):
    if state["replan_count"] >= MAX_REPLANS:
        return None
    constraints = state["user_constraints"]
    preferred = constraints.residential_preferences
    proposals = [Strategy(area, INITIAL_LIMIT) for area in [*preferred, *constraints.allowed_alternative_areas]]
    current = state["strategy"]
    if len(state["candidates"]) >= current.limit:
        wider = next((limit for limit in (50, 100) if limit > current.limit), None)
        if wider is not None:
            proposals.append(Strategy(current.area, wider))
    attempted = set(state["attempted_strategies"])
    return next((option for option in proposals if option.key(state.get("contract_month")) not in attempted), None)

