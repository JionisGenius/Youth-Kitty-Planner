import pytest

from backend.app.tools.registry import TOOLS
from scripts.verify_gms_preflight import evaluate_selection, response_items, responses_tools


def test_responses_uses_flat_tool_descriptors_with_existing_schemas():
    descriptors = responses_tools()
    assert {descriptor["name"] for descriptor in descriptors} == set(TOOLS)
    for descriptor in descriptors:
        registration = TOOLS[descriptor["name"]]
        assert descriptor["type"] == "function"
        assert descriptor["parameters"] == registration.input_model.model_json_schema()
        assert descriptor["strict"] is False
        assert "function" not in descriptor


@pytest.mark.parametrize(("name", "args", "reason"), [
    ("unknown-fixture-tool", '{"query":"synthetic-secret"}', "UNKNOWN_TOOL"),
    ("search_location", '{"query":"synthetic-secret","mode":"INVALID"}', "INVALID_ARGUMENT"),
    ("search_location", '{"query":', "INVALID_ARGUMENT"),
    ("search_location", {"query": "synthetic-secret"}, "INVALID_ARGUMENT"),
])
def test_rejects_unregistered_tools_or_invalid_arguments(name, args, reason):
    items = [{"type": "function_call", "name": name, "arguments": args}]
    passed, evidence = evaluate_selection(items, "search_location", {})
    assert not passed
    assert evidence["validation"] == [reason]
    assert "synthetic-secret" not in str(evidence)
    assert "unknown-fixture-tool" not in str(evidence)


def test_does_not_accept_chat_completions_envelope():
    assert response_items({"choices": [{"message": {"content": "text"}}]}) is None

