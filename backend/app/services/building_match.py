import re
import unicodedata

from ..schemas.tools import BuildingInput, BuildingOutput, Location, MatchEvidence, RentalCandidate
from .normalize import building, clean

PARCEL_FIELDS = ("sigunguCd", "bjdongCd", "platGbCd", "bun", "ji")
JIBUN = re.compile(r"(?:(산)\s*)?([0-9]{1,4})(?:-([0-9]{1,4}))?")
CAVEATS = ["건물 수준 판정이며 개별 세대나 임대차 계약의 안전성은 확인하지 않습니다."]


def parcel_number(lot):
    match = JIBUN.fullmatch(lot or "")
    if match is None or int(match[2]) == 0:
        return None
    return ("1" if match[1] else "0", match[2].zfill(4), (match[3] or "0").zfill(4))


def candidate_building_input(candidate: RentalCandidate, address: Location) -> BuildingInput:
    district = candidate.raw_location_fields["sggCd"]
    parcel = parcel_number(candidate.lot_number)
    b_code = address.b_code
    address_lot = address.address_lot or ""
    dong = re.escape(candidate.legal_dong or "")
    tail = re.search(rf"(?:^|\s){dong}\s+(산\s*[0-9-]+|[0-9-]+)$", address_lot)
    if (not candidate.legal_dong or parcel is None or not b_code
            or b_code[:5] != district or not tail or parcel_number(tail[1]) != parcel):
        return BuildingInput(candidate_id=candidate.candidate_id, sigungu_code=district)
    return BuildingInput(
        candidate_id=candidate.candidate_id, sigungu_code=district, bjdong_code=b_code[5:],
        lot_address=address_lot, parcel_type=parcel[0], bun=parcel[1], ji=parcel[2],
        building_name=candidate.building_name,
    )


def query_parcel(args):
    if args.bjdong_code and args.parcel_type is not None and args.bun and args.ji and int(args.bun):
        return args.sigungu_code, args.bjdong_code, args.parcel_type, args.bun.zfill(4), args.ji.zfill(4)
    return None


def _identity_value(field, row):
    value = clean(row.get(field))
    if field in {"bun", "ji"} and value and value.isascii() and value.isdigit():
        return value.zfill(4)
    return value


def _name(value):
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def match_building(args, parcel, rows, total):
    evidence = MatchEvidence(candidate_count=total)
    output = BuildingOutput(candidate_id=args.candidate_id, match_status="UNKNOWN",
                            match_evidence=evidence, caveats=CAVEATS)
    if not total:
        output.match_status = "NOT_FOUND"
    elif total != 1:
        output.match_status = "AMBIGUOUS"
    else:
        row = rows[0]
        for field, expected in zip(PARCEL_FIELDS, parcel):
            value = _identity_value(field, row)
            if value == expected:
                evidence.matched_fields.append(field)
            elif value is not None:
                evidence.conflict_fields.append(field)
        expected_name = _name(args.building_name)
        observed_name = _name(clean(row.get("bldNm")))
        if expected_name and observed_name:
            if expected_name == observed_name:
                evidence.matched_fields.append("bldNm")
            else:
                evidence.conflict_fields.append("bldNm")
        if evidence.conflict_fields:
            output.match_status = "AMBIGUOUS"
        elif len(evidence.matched_fields) == len(PARCEL_FIELDS) + 1:
            output.match_status = "MATCHED_BUILDING"
            output.matched_building = building(row)
    return output
