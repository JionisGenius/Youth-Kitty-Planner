from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, TypeAdapter

from ..schemas.tools import (
    BuildingInput, BuildingOutput, LocationInput, LocationOutput, RentalInput, RentalOutput,
    tool_result_type,
)


@dataclass(frozen=True)
class ToolSpec:
    description: str
    provider: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    kind: Literal["EXTERNAL_API"] = "EXTERNAL_API"

    def schemas(self):
        return {
            "input": self.input_model.model_json_schema(),
            "output": TypeAdapter(tool_result_type(self.output_model)).json_schema(),
        }


TOOLS = MappingProxyType({
    "search_location": ToolSpec("주소를 좌표·지역 코드로 확인하거나 키워드로 주변 장소를 찾을 때 사용합니다.",
                                "kakao_local", LocationInput, LocationOutput),
    "search_rental_transactions": ToolSpec("지역과 계약월의 과거 연립다세대 임대차 사례를 비교할 때 사용합니다.",
                                           "molit_rent", RentalInput, RentalOutput),
    "get_building_detail": ToolSpec("과거 계약 후보의 지번과 건물명을 표제부와 대조할 때 사용합니다.",
                                    "building_hub", BuildingInput, BuildingOutput),
})



def agent_tool_specs():
    """Function descriptors for model binding, with execution managed by the registry."""
    return [
        {"type": "function", "function": {
            "name": name,
            "description": spec.description,
            "parameters": spec.input_model.model_json_schema(),
        }}
        for name, spec in TOOLS.items()
    ]
