from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import TypeAdapter
import pytest

from backend.app.schemas.tools import tool_result_type
from backend.app.services.building_match import parcel_number
from backend.app.tools.executor import execute_tool
from backend.app.tools.registry import TOOLS, agent_tool_specs


def test_registry_contract_and_missing_key():
    for name, spec in TOOLS.items():
        assert spec.kind == "EXTERNAL_API"
        assert spec.schemas()["output"]["discriminator"]["propertyName"] == "ok"
        response = execute_tool(name, {}, session=None, keys={})
        assert not response.ok and response.error.code == "INVALID_ARGUMENT"
        assert TypeAdapter(tool_result_type(spec.output_model)).validate_json(response.model_dump_json()) == response
    valid = {
        "search_location": {"query": "광화문역", "mode": "KEYWORD"},
        "search_rental_transactions": {"sigungu_code": "11110"},
        "get_building_detail": {"candidate_id": "fixture", "sigungu_code": "11110",
                                "bjdong_code": "10100", "parcel_type": "0", "bun": "0012", "ji": "0000"},
    }
    for name, args in valid.items():
        result = execute_tool(name, args, session=None, keys={})
        assert not result.ok and result.error.code == "AUTH_FAILED"
        assert result.error.details == {"reason": "missing_api_key"}


def test_registry_specs_are_accepted_by_langchain():
    specs = agent_tool_specs()
    assert len(specs) == len(TOOLS)
    for spec in specs:
        descriptor = spec["function"]
        registration = TOOLS[descriptor["name"]]
        assert descriptor["description"] == registration.description
        assert descriptor["parameters"] == registration.schemas()["input"]
        assert convert_to_openai_tool(spec) == spec


@pytest.mark.parametrize("month", ["202613", "202600", "000012", "2026-01"])
def test_invalid_contract_month(month):
    result = execute_tool("search_rental_transactions", {
        "sigungu_code": "11110", "contract_month": month,
    }, session=None, keys={})
    assert result.error.code == "INVALID_ARGUMENT"


@pytest.mark.parametrize(("value", "expected"), [
    ("산 12-3", ("1", "0012", "0003")), ("12", ("0", "0012", "0000")),
    ("0", None), ("12-3 101호", None),
])
def test_parcel_numbers(value, expected):
    assert parcel_number(value) == expected

