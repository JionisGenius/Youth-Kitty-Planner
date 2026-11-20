"""Run live checks and print only allowlisted, non-identifying evidence."""

import argparse
from collections import Counter
from datetime import datetime, timedelta
import json
from time import monotonic

import requests

from backend.app.core.config import load_api_keys
from backend.app.services.building_match import candidate_building_input
from backend.app.tools.executor import KST, execute_tool
from backend.app.tools.providers import building_hub, kakao_local, molit_rent
from backend.app.tools.providers.http import ProviderError, fetch, government_page
from backend.app.tools.registry import TOOLS, agent_tool_specs

from .provider_evidence import summarize_response

RENT_SAMPLE = {"LAWD_CD": "11110", "DEAL_YMD": "202501"}
TITLE_SAMPLE = {"sigunguCd": "11680", "bjdongCd": "10300", "platGbCd": "0",
                "bun": "0012", "ji": "0000", "_type": "json"}


class Checks:
    def __init__(self, session, keys, mode):
        self.session = session
        self.keys = keys
        self.mode = mode
        self.responses = []
        self.provider = None
        self.failures = 0
        session.hooks["response"].append(self._observe)

    def _observe(self, response, **kwargs):
        self.responses.append(summarize_response(response, self.provider))

    def _start(self, provider):
        self.provider = provider
        self.responses.clear()
        return monotonic()

    def _emit(self, label, start, passed, **fields):
        self.failures += int(not passed)
        print(json.dumps({
            "check": label, "mode": self.mode, "provider": self.provider,
            "http": self.responses, "elapsed_ms": round((monotonic() - start) * 1000),
            "passed": passed, **fields,
        }, ensure_ascii=True))

    def tool(self, label, name, arguments, expected=None):
        start = self._start(TOOLS[name].provider)
        result = execute_tool(name, arguments, session=self.session, keys=self.keys)
        info = {"tool_ok": result.ok}
        if result.ok:
            for field in ("query_resolution", "count", "requested_period", "effective_period",
                          "is_historical", "match_status"):
                if hasattr(result.data, field):
                    info[field] = getattr(result.data, field)
            if hasattr(result.data, "match_evidence"):
                info["match_evidence"] = result.data.match_evidence.model_dump()
                info["candidate_id_preserved"] = result.data.candidate_id == arguments["candidate_id"]
                if result.data.matched_building:
                    info["normalized_fields"] = _present_types(result.data.matched_building)
            elif hasattr(result.data, "candidates") and result.data.candidates:
                info["normalized_fields"] = _present_types(result.data.candidates[0])
            elif hasattr(result.data, "locations") and result.data.locations:
                info["normalized_fields"] = _present_types(result.data.locations[0])
        else:
            info["error"] = result.error.code
            if result.error.details == {"reason": "missing_api_key"}:
                info["reason"] = "missing_api_key"
        passed = expected(result) if expected else result.ok and bool(self.responses)
        self._emit(label, start, passed, **info)
        return result

    def probe(self, label, provider, invoke, expected):
        start = self._start(provider)
        key = self.keys.get(provider)
        if not key:
            self._emit(label, start, False, error="AUTH_FAILED", reason="missing_api_key")
            return
        try:
            value = invoke(key)
        except ProviderError as error:
            self._emit(label, start, expected(None, error), error=error.code)
        else:
            self._emit(label, start, expected(value, None))


def _present_types(model):
    return {name: type(value).__name__ for name, value in model
            if value is not None and not name.endswith("_id")}


def _auth_rejected(result):
    return not result.ok and result.error.code == "AUTH_FAILED"


def _extended_checks(checks):
    checks.tool("address_empty", "search_location",
                {"query": "ykp-no-such-place-qz914727", "mode": "ADDRESS"},
                lambda result: result.ok and result.data.query_resolution == "NO_RESULT")
    checks.probe("kakao_invalid_size", "kakao_local", lambda key: fetch(
        checks.session, f"{kakao_local.BASE_URL}/search/keyword.json",
        {"query": "광화문역", "size": 16}, {"Authorization": f"KakaoAK {key}"},
    ), lambda _, error: error is not None and error.code == "INVALID_ARGUMENT")

    previous = (datetime.now(KST).date().replace(day=1) - timedelta(days=1)).strftime("%Y%m")
    checks.tool("rent_default", "search_rental_transactions", {"sigungu_code": "11110", "limit": 1},
                lambda result: result.ok and result.data.requested_period is None
                and result.data.effective_period == previous)
    checks.tool("rent_empty", "search_rental_transactions",
                {"sigungu_code": "11110", "contract_month": "200001"},
                lambda result: result.ok and result.data.count == 0)
    checks.tool("title_empty", "get_building_detail", {
        "candidate_id": "empty-example", "sigungu_code": "11680", "bjdong_code": "10300",
        "parcel_type": "0", "bun": "9999", "ji": "9999",
    }, lambda result: result.ok and result.data.match_status == "NOT_FOUND")

    for provider, url, sample in (("molit_rent", molit_rent.URL, RENT_SAMPLE),
                                  ("building_hub", building_hub.URL, TITLE_SAMPLE)):
        def get_pages(key):
            return tuple(government_page(checks.session, url, key, {
                **sample, "numOfRows": 2, "pageNo": page,
            }) for page in (1, 2))

        def pages_differ(value, error):
            if error is not None:
                return False
            (first, first_total), (second, second_total) = value
            return (first_total == second_total and bool(first) and bool(second) and first != second
                    and [item.get("pageNo") for item in checks.responses] == [1, 2])

        checks.probe(f"{provider}_pages_1_2", provider, get_pages, pages_differ)

    checks.tool("rent_dto_missing_district", "search_rental_transactions",
                {"contract_month": RENT_SAMPLE["DEAL_YMD"]},
                lambda result: not result.ok and result.error.code == "INVALID_ARGUMENT"
                and not checks.responses)
    checks.probe("rent_provider_missing_district", "molit_rent", lambda key: government_page(
        checks.session, molit_rent.URL, key, {"DEAL_YMD": RENT_SAMPLE["DEAL_YMD"], "numOfRows": 1},
    ), lambda page, error: error is None and page == ([], 0))
    checks.probe("rent_gateway_error", "molit_rent", lambda key: government_page(
        checks.session, molit_rent.URL, key, {**RENT_SAMPLE, "numOfRows": "abc"},
    ), lambda _, error: error is not None and error.code == "SERVICE_UNAVAILABLE"
       and error.details == {"http_status": 200, "result_code": "04"})


def _match_candidates(checks, rentals):
    counts = Counter(dict.fromkeys(("MATCHED_BUILDING", "AMBIGUOUS", "NOT_FOUND", "UNKNOWN"), 0))
    attempted = registry_requests = provider_errors = 0
    reasons = Counter()
    for candidate in rentals.data.candidates if rentals.ok else []:
        attempted += 1
        if not (candidate.legal_dong and candidate.lot_number and candidate.building_name):
            counts["UNKNOWN"] += 1
            reasons["rental_identifier_missing"] += 1
            continue
        address = checks.tool("candidate_address", "search_location", {
            "query": f"서울 종로구 {candidate.legal_dong} {candidate.lot_number}", "mode": "ADDRESS",
        })
        if not address.ok:
            provider_errors += 1
            continue
        resolution = address.data.query_resolution
        if resolution != "RESOLVED":
            counts["AMBIGUOUS" if resolution == "AMBIGUOUS" else "UNKNOWN"] += 1
            reasons["parcel_address_unresolved"] += 1
            continue
        match_input = candidate_building_input(candidate, address.data.locations[0])
        match = checks.tool("candidate_title", "get_building_detail", match_input.model_dump(),
                            lambda result: result.ok and result.data.candidate_id == candidate.candidate_id)
        registry_requests += len(checks.responses)
        if not match.ok:
            provider_errors += 1
            continue
        if match.data.match_status == "UNKNOWN":
            if not checks.responses:
                reasons["parcel_identity_unconfirmed"] += 1
            elif checks.responses[-1].get("building_name_present") == 0:
                reasons["registry_building_name_missing"] += 1
            else:
                reasons["registry_identity_incomplete"] += 1
        counts[match.data.match_status] += 1

    print(json.dumps({"check": "candidate_link", "mode": checks.mode, "attempted": attempted,
                      "registry_requests": registry_requests, "provider_errors": provider_errors,
                      "statuses": counts, "reasons": reasons}, ensure_ascii=True))
    return counts["MATCHED_BUILDING"] > 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--invalid-credentials", action="store_true")
    modes.add_argument("--extended", action="store_true")
    modes.add_argument("--tool-specs", action="store_true")
    parser.add_argument("--match", action="store_true", help="Cross-check up to three Jongno rental candidates")
    options = parser.parse_args()
    if options.tool_specs:
        print(json.dumps(agent_tool_specs(), ensure_ascii=True, indent=2))
        return 0

    keys = load_api_keys()
    if options.invalid_credentials:
        keys = dict.fromkeys(keys, "ykp-invalid-credential")
    with requests.Session() as session:
        mode = "INVALID_CREDENTIALS" if options.invalid_credentials else "LIVE"
        checks = Checks(session, keys, mode)
        expected = _auth_rejected if options.invalid_credentials else None

        checks.tool("address", "search_location",
                    {"query": "서울 종로구 세종대로 175", "mode": "ADDRESS"},
                    expected or (lambda result: result.ok and bool(result.data.locations)))
        checks.tool("keyword", "search_location", {"query": "광화문역", "mode": "KEYWORD"},
                    expected or (lambda result: result.ok and bool(result.data.locations)))
        rentals = checks.tool("rent", "search_rental_transactions",
                              {"sigungu_code": "11110", "contract_month": "202501", "limit": 3},
                              expected or (lambda result: result.ok and result.data.count > 0))
        checks.tool("title", "get_building_detail",
                    {"candidate_id": "official-sample", "sigungu_code": "11680", "bjdong_code": "10300",
                     "parcel_type": "0", "bun": "0012", "ji": "0000"},
                    expected or (lambda result: result.ok and result.data.match_evidence.candidate_count > 0))
        if options.extended:
            _extended_checks(checks)
        linked = _match_candidates(checks, rentals) if options.match else True
    return int(checks.failures > 0 or not linked)


if __name__ == "__main__":
    raise SystemExit(main())

