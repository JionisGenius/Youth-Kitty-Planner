from datetime import date
from hashlib import sha256

from ..schemas.tools import Building, Location, LocationOutput, RentalCandidate
from ..tools.providers.http import ProviderError


def clean(value):
    return str(value).strip() or None if value is not None else None


def optional_int(value):
    return int(value) if clean(value) is not None else None


def locations(payload, mode):
    items = payload["documents"]
    if not isinstance(items, list):
        raise ValueError
    total = int(payload["meta"]["total_count"])
    if total < len(items) or (total > 0 and not items):
        raise ValueError
    result = []
    for item in items:
        address_mode = mode == "ADDRESS"
        lot = (item.get("address") or {}) if address_mode else {}
        road = (item.get("road_address") or {}) if address_mode else {}
        name = clean(item["address_name"] if address_mode else item["place_name"])
        if not name:
            raise ValueError
        result.append(Location(
            name=name, latitude=clean(item.get("y")), longitude=clean(item.get("x")),
            address_lot=clean(lot.get("address_name") if address_mode else item.get("address_name")),
            address_road=clean(road.get("address_name") if address_mode else item.get("road_address_name")),
            b_code=clean(lot.get("b_code")), h_code=clean(lot.get("h_code")),
            external_place_id=None if address_mode else clean(item.get("id")),
            place_url=None if address_mode else clean(item.get("place_url")),
        ))
    resolution = "NO_RESULT" if total == 0 else "RESOLVED" if total == 1 else "AMBIGUOUS"
    return LocationOutput(locations=result, query_resolution=resolution)


def rental(item, district, period, index):
    if not {"dealYear", "dealMonth", "dealDay", "deposit", "monthlyRent", "sggCd"} <= item.keys():
        raise ProviderError("SCHEMA_MISMATCH")
    contract_date = date(int(item["dealYear"]), int(item["dealMonth"]), int(item["dealDay"]))
    if clean(item["sggCd"]) != district or contract_date.strftime("%Y%m") != period:
        raise ProviderError("SCHEMA_MISMATCH")

    def won(field):
        amount = clean(item[field])
        return None if amount is None else int(amount.replace(",", "")) * 10_000

    candidate_id = sha256(f"molit_rent:{district}:{period}:{index}".encode()).hexdigest()[:24]
    return RentalCandidate(
        candidate_id=candidate_id, legal_dong=clean(item.get("umdNm")),
        lot_number=clean(item.get("jibun")), building_name=clean(item.get("mhouseNm")),
        floor=optional_int(item.get("floor")), exclusive_area_m2=clean(item.get("excluUseAr")),
        deposit_krw=won("deposit"), monthly_rent_krw=won("monthlyRent"),
        contract_date=contract_date,
        raw_location_fields={field: clean(item[field]) for field in ("sggCd", "umdNm", "jibun")
                             if clean(item.get(field)) is not None},
        evidence_refs=[f"molit_rent:{district}:{period}:{candidate_id}"],
    )


def building(item):
    approval = clean(item.get("useAprDay"))
    return Building(
        building_registry_pk=clean(item.get("mgmBldrgstPk")),
        full_address=clean(item.get("newPlatPlc")) or clean(item.get("platPlc")),
        building_name=clean(item.get("bldNm")), primary_use=clean(item.get("mainPurpsCdNm")),
        approval_date=date.fromisoformat(approval) if approval else None,
        floor_count=optional_int(item.get("grndFlrCnt")),
        household_count=optional_int(item.get("hhldCnt")),
    )
