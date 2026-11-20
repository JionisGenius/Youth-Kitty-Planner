import json
from datetime import datetime, timedelta

import pytest
import requests
from pydantic import TypeAdapter

from backend.app.schemas.tools import tool_result_type
from backend.app.services.building_match import candidate_building_input
from backend.app.tools.executor import KST, execute_tool
from backend.app.tools.registry import TOOLS
from scripts.provider_evidence import summarize_response

KEYS = {"kakao_local": "fake", "molit_rent": "fake%2Bkey", "building_hub": "fake"}
PASSED = {
    "sggCd": "11110", "umdNm": "예시동", "jibun": "12-3", "mhouseNm": "예시빌라",
    "dealYear": "2025", "dealMonth": "1", "dealDay": "5", "excluUseAr": "25.1",
    "deposit": "1,000", "monthlyRent": "35", "floor": "-1",
}
TITLE = {
    "sigunguCd": "11110", "bjdongCd": "10100", "platGbCd": "0", "bun": 12, "ji": 3,
    "bldNm": "예시빌라", "mgmBldrgstPk": "fixture", "mainPurpsCdNm": "공동주택",
    "grndFlrCnt": 4, "useAprDay": "20120101",
}
ADDRESS = {
    "address_name": "서울 종로구 예시동 12-3", "x": "127.0", "y": "37.5",
    "address": {"address_name": "서울 종로구 예시동 12-3", "b_code": "1111010100",
                "h_code": "1111050100"},
    "road_address": None,
}


def reply(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return response


def government(rows, total=None):
    return {"response": {"header": {"resultCode": "00"}, "body": {
        "totalCount": len(rows) if total is None else total, "items": {"item": rows},
    }}}


def test_normalization_and_candidate_chain(monkeypatch):
    xml_fields = "".join(f"<{key}>{value}</{key}>" for key, value in PASSED.items())
    xml = (f"<response><header><resultCode>000</resultCode></header><body>"
           f"<items><item>{xml_fields}</item></items><totalCount>1</totalCount></body></response>")
    replies = iter([reply(xml.encode()), reply({"meta": {"total_count": 1}, "documents": [ADDRESS]}),
                    reply(government([TITLE]))])
    with requests.Session() as session:
        calls = []

        def get(url, **kwargs):
            calls.append((url, kwargs))
            return next(replies)

        monkeypatch.setattr(session, "get", get)
        rental = execute_tool("search_rental_transactions", {
            "sigungu_code": "11110", "contract_month": "202501",
        }, session=session, keys=KEYS)
        candidate = rental.data.candidates[0]
        assert rental.data.is_historical and candidate.deposit_krw == 10_000_000
        assert candidate.monthly_rent_krw == 350_000 and candidate.contract_date.isoformat() == "2025-01-05"
        assert calls[0][1]["params"]["serviceKey"] == "fake+key"
        location = execute_tool("search_location", {"query": "예시동 12-3 101호", "mode": "ADDRESS"},
                                session=session, keys=KEYS)
        assert location.data.locations[0].address_lot.endswith("12-3")
        args = candidate_building_input(candidate, location.data.locations[0])
        assert args.bjdong_code == "10100"
        building = execute_tool("get_building_detail", args.model_dump(), session=session, keys=KEYS)
        assert building.data.match_status == "MATCHED_BUILDING"
        assert building.data.candidate_id == args.candidate_id == candidate.candidate_id
        assert building.data.matched_building.floor_count == 4
        assert calls[-1][1]["params"]["ji"] == "0003"
        for name, result in zip(("search_rental_transactions", "search_location", "get_building_detail"),
                                (rental, location, building)):
            adapter = TypeAdapter(tool_result_type(TOOLS[name].output_model))
            assert adapter.validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(("rows", "total", "expected"), [
    ([], 0, "NOT_FOUND"), ([TITLE], 2, "AMBIGUOUS"),
    ([{**TITLE, "ji": 9}], 1, "AMBIGUOUS"), ([{**TITLE, "bldNm": None}], 1, "UNKNOWN"),
])
def test_building_mismatch(monkeypatch, rows, total, expected):
    with requests.Session() as session:
        monkeypatch.setattr(session, "get", lambda *args, **kwargs: reply(government(rows, total)))
        result = execute_tool("get_building_detail", {
            "candidate_id": "test", "sigungu_code": "11110", "bjdong_code": "10100",
            "parcel_type": "0", "bun": "12", "ji": "3", "building_name": "예시빌라",
        }, session=session, keys=KEYS)
    assert result.data.match_status == expected
    assert result.data.matched_building is None


@pytest.mark.parametrize(("status", "code"), [
    (400, "INVALID_ARGUMENT"), (401, "AUTH_FAILED"), (403, "AUTH_FAILED"),
    (429, "RATE_LIMITED"), (503, "SERVICE_UNAVAILABLE"), (200, "SCHEMA_MISMATCH"),
])
def test_safe_errors(monkeypatch, status, code):
    with requests.Session() as session:
        monkeypatch.setattr(session, "get", lambda *args, **kwargs: reply(b"synthetic-secret", status))
        result = execute_tool("search_location", {"query": "예시", "mode": "KEYWORD"},
                              session=session, keys=KEYS)
    assert result.error.code == code
    assert "synthetic-secret" not in result.model_dump_json()


@pytest.mark.parametrize("requested", [None, "999901"])
def test_default_month_and_empty_result(monkeypatch, requested):
    with requests.Session() as session:
        def get(url, *, params, **kwargs):
            prior = datetime.now(KST).date().replace(day=1) - timedelta(days=1)
            assert params["DEAL_YMD"] == prior.strftime("%Y%m")
            return reply(government([]))

        monkeypatch.setattr(session, "get", get)
        result = execute_tool("search_rental_transactions", {"sigungu_code": "11110", "contract_month": requested},
                              session=session, keys=KEYS)
    assert result.ok and result.data.count == 0 and result.data.requested_period == requested
    assert result.data.effective_period != "999901"
    assert any("999901" in caveat for caveat in result.meta.caveats) == bool(requested)


def test_wrong_district_fails(monkeypatch):
    with requests.Session() as session:
        monkeypatch.setattr(session, "get", lambda *args, **kwargs: reply(government([PASSED])))
        result = execute_tool("search_rental_transactions", {
            "sigungu_code": "11680", "contract_month": "202501",
        }, session=session, keys=KEYS)
    assert result.error.code == "SCHEMA_MISMATCH"


def test_portal_auth_error_inside_http_200(monkeypatch):
    with requests.Session() as session:
        xml = b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
        monkeypatch.setattr(session, "get", lambda *args, **kwargs: reply(xml))
        result = execute_tool("search_rental_transactions", {
            "sigungu_code": "11110", "contract_month": "202501",
        }, session=session, keys=KEYS)
    assert result.error.code == "AUTH_FAILED" and result.error.details["result_code"] == "30"


@pytest.mark.parametrize("documents", [[], [{"place_name": "예시역", "id": "1",
    "x": "127.0", "y": "37.5", "place_url": "https://place.map.kakao.com/1"}]])
def test_keyword_results(monkeypatch, documents):
    with requests.Session() as session:
        def get(url, **kwargs):
            assert url.endswith("/keyword.json")
            return reply({"meta": {"total_count": len(documents)}, "documents": documents})

        monkeypatch.setattr(session, "get", get)
        result = execute_tool("search_location", {"query": "예시역", "mode": "KEYWORD"},
                              session=session, keys=KEYS)
    assert result.data.query_resolution == ("RESOLVED" if documents else "NO_RESULT")
    if documents:
        assert result.data.locations[0].place_url == documents[0]["place_url"]
        assert result.data.locations[0].b_code is None


def test_rental_filter_reads_next_page(monkeypatch):
    with requests.Session() as session:
        def get(url, *, params, **kwargs):
            deposit = {1: "1,000", 2: "500"}[params["pageNo"]]
            return reply(government([{**PASSED, "deposit": deposit}], total=2))

        monkeypatch.setattr(session, "get", get)
        result = execute_tool("search_rental_transactions", {
            "sigungu_code": "11110", "contract_month": "202501", "max_deposit_krw": 6_000_000,
        }, session=session, keys=KEYS)
    assert result.data.count == 1
    assert result.data.candidates[0].deposit_krw == 5_000_000


def test_timeout_is_safe(monkeypatch):
    with requests.Session() as session:
        def get(*args, **kwargs):
            raise requests.Timeout("synthetic-secret")

        monkeypatch.setattr(session, "get", get)
        result = execute_tool("search_location", {"query": "예시", "mode": "KEYWORD"},
                              session=session, keys=KEYS)
    assert result.error.code == "TIMEOUT" and result.error.retryable
    assert "synthetic-secret" not in result.model_dump_json()


@pytest.mark.parametrize(("provider_code", "tool_code"), [
    ("04", "SERVICE_UNAVAILABLE"), ("05", "TIMEOUT"),
])
def test_gateway_http_error_and_timeout_are_distinct(monkeypatch, provider_code, tool_code):
    xml = (f"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>{provider_code}"
           "</returnReasonCode><returnAuthMsg>synthetic-secret</returnAuthMsg>"
           "</cmmMsgHeader></OpenAPI_ServiceResponse>").encode()
    with requests.Session() as session:
        monkeypatch.setattr(session, "get", lambda *args, **kwargs: reply(xml))
        result = execute_tool("search_rental_transactions", {
            "sigungu_code": "11110", "contract_month": "202501",
        }, session=session, keys=KEYS)
    assert result.error.code == tool_code
    assert result.error.details == {"http_status": 200, "result_code": provider_code}
    assert "synthetic-secret" not in result.model_dump_json()


def test_live_schema_evidence_does_not_copy_provider_values_or_unknown_keys():
    evidence = summarize_response(reply(government([{
        "platPlc": "synthetic-address", "synthetic-key": "synthetic-secret", "bldNm": "",
    }])), "building_hub")
    assert evidence["fields"] == {"bldNm": ["str"], "platPlc": ["str"]}
    assert evidence["building_name_present"] == 0
    assert "synthetic" not in json.dumps(evidence)
