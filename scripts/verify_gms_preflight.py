"""Check SSAFY GMS Responses and validate suggested local calls without executing them."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import re

import requests

from backend.app.core.gms import (
    GmsConfigurationError, load_gms_config, request, response_items, responses_tools,
    text_parts, validate_call,
)
from backend.app.tools.registry import TOOLS


CASES = (
    ("location", "광화문역을 키워드로 검색해 줘.", "search_location",
     {"mode": "KEYWORD", "query": "광화문역"}),
    ("rental", "종로구 시군구 코드 11110의 2025년 1월 과거 연립다세대 전월세 실거래를 조회해 줘.",
     "search_rental_transactions", {"sigungu_code": "11110", "contract_month": "202501"}),
    ("building", "합성 후보 candidate-example의 건축물대장 표제부를 조회해 줘. "
     "시군구 11680, 법정동 10300, 대지 구분 0, 본번 0012, 부번 0000을 사용해 줘.",
     "get_building_detail", {"candidate_id": "candidate-example", "sigungu_code": "11680",
                             "bjdong_code": "10300", "parcel_type": "0", "bun": "0012", "ji": "0000"}),
    ("no_tool", "안녕하세요! 도구가 필요 없는 일상 인사예요. 짧게 답해 주세요.", None, {}),
)


def evaluate_selection(items, expected_name, expected_arguments):
    calls = [item for item in items if item.get("type") == "function_call"]
    validated = [validate_call(call) for call in calls]
    selection = [call["name"] if isinstance(call.get("name"), str) and call["name"] in TOOLS
                 else "UNREGISTERED" for call in calls]
    evidence = {"selected_tools": selection, "validation": [status for status, _ in validated]}
    if expected_name is None:
        passed = not calls and bool(text_parts(items))
        evidence["text_present"] = bool(text_parts(items))
    else:
        passed = selection == [expected_name] and validated[0][0] == "VALID"
        if passed:
            arguments = validated[0][1].model_dump()
            passed = all(arguments[field] == value for field, value in expected_arguments.items())
        evidence["expected_arguments_match"] = passed
    return passed, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--single-request", action="store_true", help="Check GMS connectivity once, without tools")
    options = parser.parse_args()
    try:
        key, url, model = load_gms_config()
    except GmsConfigurationError as error:
        print(json.dumps({"check": "config", "passed": False, **error.args[0]}))
        return 1
    if options.single_request and model != "gpt-6.1-sol":
        print(json.dumps({"check": "config", "failure": "EXPECTED_GMS_MODEL", "request_count": 0, "passed": False}))
        return 1
    safe_model = model if re.fullmatch(r"(?:gpt|o[1-9])[-a-z0-9.]{1,40}", model) and key not in model else None
    with requests.Session() as session:
        session.headers["Authorization"] = f"Bearer {key}"
        started_kst = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
        items, evidence = request(session, url, model, "Reply with exactly YKP_OK.",
                                  diagnostics=options.single_request)
        passed = items is not None and text_parts(items) == ["YKP_OK"]
        if options.single_request:
            result = dict.fromkeys(("http", "retry_after_present", "retry_after", "error_code",
                                    "error_type", "model_id_match", "response_status"))
            print(json.dumps({**result, **evidence, "check": "single_request", "requested_at_kst": started_kst,
                              "request_count": 1, "configured_model": safe_model,
                              "completed": evidence.get("http") == 200 and evidence.get("response_status") == "completed",
                              "text_check": passed, "passed": passed}))
            return int(not passed)
        print(json.dumps({"check": "connection", "mode": "LIVE", "configured_model": safe_model,
                          "text_check": passed, "passed": passed, **evidence}))
        if not passed:
            return 1

        tools = responses_tools()
        print(json.dumps({"check": "registered_tools", "mode": "LOCAL",
                          "tools": [spec["name"] for spec in tools]}))
        all_passed = True
        for check, prompt, expected_name, expected_arguments in CASES:
            items, evidence = request(session, url, model, prompt, tools)
            if items is None:
                passed, selection = False, {}
            else:
                passed, selection = evaluate_selection(items, expected_name, expected_arguments)
            print(json.dumps({"check": check, "mode": "LIVE", "passed": passed, **evidence, **selection}))
            all_passed &= passed
    return int(not all_passed)


if __name__ == "__main__":
    raise SystemExit(main())
