from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from ..schemas.tools import BuildingOutput, MatchEvidence, RentalOutput, ToolError, ToolFailure, ToolMeta, ToolSuccess
from ..services import normalize
from ..services.building_match import CAVEATS, match_building, query_parcel
from .providers import building_hub, kakao_local, molit_rent
from .providers.http import ProviderError
from .registry import TOOLS

KST = timezone(timedelta(hours=9))
MESSAGES = {
    "INVALID_ARGUMENT": "도구 입력을 확인해 주세요.",
    "AUTH_FAILED": "외부 서비스 인증 설정을 확인해 주세요.",
    "RATE_LIMITED": "외부 서비스 호출 한도에 도달했습니다.",
    "SERVICE_UNAVAILABLE": "외부 서비스에 연결할 수 없습니다.",
    "TIMEOUT": "외부 서비스 응답 시간이 초과되었습니다.",
    "SCHEMA_MISMATCH": "외부 데이터가 검증 규칙과 일치하지 않습니다.",
    "DATA_INCOMPLETE": "외부 데이터 조회를 완료하지 못했습니다.",
    "UNKNOWN_ERROR": "외부 서비스에서 분류되지 않은 오류가 발생했습니다.",
}


def _failure(meta, code, details=None):
    return ToolFailure(meta=meta, error=ToolError(
        code=code, message=MESSAGES[code],
        retryable=code in {"RATE_LIMITED", "SERVICE_UNAVAILABLE", "TIMEOUT"}, details=details,
    ))


def execute_tool(name, arguments, *, session, keys):
    spec = TOOLS.get(name)
    if spec is None:
        return _failure(ToolMeta(provider="registry"), "INVALID_ARGUMENT")
    meta = ToolMeta(provider=spec.provider)
    try:
        args = spec.input_model.model_validate(arguments)
    except ValidationError:
        return _failure(meta, "INVALID_ARGUMENT")
    parcel = query_parcel(args) if name == "get_building_detail" else None
    if name == "get_building_detail" and parcel is None:
        data = BuildingOutput(candidate_id=args.candidate_id, match_status="UNKNOWN",
                              match_evidence=MatchEvidence(),
                              caveats=[*CAVEATS, "검증 가능한 필지 식별자가 부족합니다."])
        return ToolSuccess[BuildingOutput](data=data, meta=meta)
    key = keys.get(spec.provider)
    if not key:
        return _failure(meta, "AUTH_FAILED", {"reason": "missing_api_key"})
    meta.query_as_of = datetime.now(KST).date()
    try:
        if name == "search_location":
            data = normalize.locations(kakao_local.search(session, key, args), args.mode)
        elif name == "search_rental_transactions":
            data = _rent(session, key, args, meta)
        else:
            rows, total = building_hub.titles(session, key, parcel)
            if total > 0 and not rows:
                raise ProviderError("SCHEMA_MISMATCH")
            data = match_building(args, parcel, rows, total)
        meta.fetched_at = datetime.now(timezone.utc)
        return ToolSuccess[spec.output_model](data=data, meta=meta)
    except ProviderError as exc:
        return _failure(meta, exc.code, exc.details or None)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return _failure(meta, "SCHEMA_MISMATCH")
    except Exception:
        return _failure(meta, "UNKNOWN_ERROR")


def _rent(session, key, args, meta):
    prior_month = meta.query_as_of.replace(day=1) - timedelta(days=1)
    month = args.contract_month or prior_month.strftime("%Y%m")
    if month > meta.query_as_of.strftime("%Y%m"):
        month = prior_month.strftime("%Y%m")
    meta.effective_period = month
    meta.caveats = [
        "신고된 과거 계약 자료입니다. 현재 임대 가능 여부는 확인할 수 없습니다.",
        "신고 및 공개 시차가 있을 수 있으며 빈 결과는 현재 매물 부재를 의미하지 않습니다.",
    ]
    if args.contract_month and args.contract_month != month:
        meta.caveats.append(f"미래 계약월 {args.contract_month} 대신 직전 완료 월 {month}을 조회했습니다.")
    candidates = []
    rows = molit_rent.pages(session, key, args.sigungu_code, month)
    for index, row in enumerate(rows):
        candidate = normalize.rental(row, args.sigungu_code, month, index)
        if _within(candidate.deposit_krw, args.max_deposit_krw) and _within(
            candidate.monthly_rent_krw, args.max_monthly_rent_krw
        ):
            candidates.append(candidate)
            if len(candidates) == args.limit:
                break
    return RentalOutput(candidates=candidates, requested_period=args.contract_month,
                        effective_period=month, count=len(candidates))


def _within(amount, maximum):
    return maximum is None or (amount is not None and amount <= maximum)
