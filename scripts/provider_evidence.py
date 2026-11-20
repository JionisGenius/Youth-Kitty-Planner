"""Summarize only allowlisted schema metadata from live provider responses."""

from xml.etree import ElementTree

KAKAO_FIELDS = ("id", "place_name", "place_url", "address_name", "road_address_name", "x", "y")
KAKAO_ADDRESS_FIELDS = ("address_name", "b_code", "h_code", "main_address_no", "sub_address_no")
RENT_FIELDS = (
    "sggCd", "umdNm", "jibun", "mhouseNm", "dealYear", "dealMonth", "dealDay",
    "deposit", "monthlyRent", "excluUseAr", "floor",
)
TITLE_FIELDS = (
    "sigunguCd", "bjdongCd", "platGbCd", "bun", "ji", "bldNm", "mainPurpsCdNm",
    "useAprDay", "mgmBldrgstPk", "newPlatPlc", "platPlc", "grndFlrCnt", "hhldCnt",
)
RESULT_CODES = {"00", "000", "01", "02", "03", "04", "05", "10", "11", "12",
                "20", "21", "22", "30", "31", "32", "33", "99"}
KAKAO_ERRORS = {"AccessDeniedError", "InvalidArgument", "InvalidArgumentError",
                "InvalidRequest", "InvalidRequestError", "RequestThrottled"}


def summarize_response(response, provider):
    info = {"http_status": response.status_code}
    try:
        if provider == "kakao_local":
            info.update(_kakao(response.json()))
        else:
            info.update(_government(response, RENT_FIELDS if provider == "molit_rent" else TITLE_FIELDS))
    except (ValueError, TypeError, AttributeError, ElementTree.ParseError):
        info["body_shape"] = "unrecognized"
    return info


def _field_types(rows, fields):
    return {
        field: sorted({type(row[field]).__name__ for row in rows if field in row})
        for field in fields if any(field in row for row in rows)
    }


def _kakao(payload):
    documents = payload.get("documents")
    if not isinstance(documents, list):
        code = payload.get("errorType")
        return {"body_shape": "json error", "error_type": code if code in KAKAO_ERRORS else "other"}
    meta = payload.get("meta", {})
    info = {
        "body_shape": "json meta/documents",
        "rows": len(documents),
        "fields": _field_types(documents, KAKAO_FIELDS),
    }
    for label in ("total_count", "pageable_count"):
        value = meta.get(label)
        if type(value) is int and value >= 0:
            info[label] = value
    addresses = [row["address"] for row in documents if isinstance(row.get("address"), dict)]
    if addresses:
        info["address_fields"] = _field_types(addresses, KAKAO_ADDRESS_FIELDS)
        info["b_and_h_codes_differ"] = any(
            row.get("b_code") and row.get("h_code") and row["b_code"] != row["h_code"]
            for row in addresses
        )
    return info


def _government(response, fields):
    if response.content.lstrip().removeprefix(b"\xef\xbb\xbf").startswith(b"<"):
        root = ElementTree.fromstring(response.content)
        if root.tag == "OpenAPI_ServiceResponse":
            code = root.findtext("cmmMsgHeader/returnReasonCode")
            return {"body_shape": "xml gateway error", "result_code": _code(code)}
        if root.tag != "response":
            return {"body_shape": "unrecognized"}
        code = root.findtext("header/resultCode")
        rows = [{field.tag: field.text for field in row} for row in root.findall("body/items/item")]
        counts = {name: root.findtext(f"body/{name}") for name in ("pageNo", "numOfRows", "totalCount")}
        shape = "xml response/header/body/items/item"
    else:
        payload = response.json()
        if "OpenAPI_ServiceResponse" in payload:
            code = payload["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {}).get("returnReasonCode")
            return {"body_shape": "json gateway error", "result_code": _code(code)}
        envelope = payload.get("response")
        if not isinstance(envelope, dict):
            return {"body_shape": "unrecognized"}
        code = envelope.get("header", {}).get("resultCode")
        body = envelope.get("body") or {}
        rows = (body.get("items") or {}).get("item", [])
        if isinstance(rows, dict):
            rows = [rows]
        counts = {name: body.get(name) for name in ("pageNo", "numOfRows", "totalCount")}
        shape = "json response/header/body/items/item"

    info = {"body_shape": shape, "result_code": _code(code), "rows": len(rows),
            "fields": _field_types(rows, fields)}
    for name, value in counts.items():
        if str(value).isascii() and str(value).isdigit() and len(str(value)) <= 9:
            info[name] = int(value)
    if fields is TITLE_FIELDS and rows:
        info["building_name_present"] = sum(bool(str(row.get("bldNm") or "").strip()) for row in rows)
    return info


def _code(code):
    value = str(code).strip()
    return value if value in RESULT_CODES else "other"

