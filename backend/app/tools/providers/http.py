from xml.etree import ElementTree
from urllib.parse import unquote

import requests

from ...schemas.tools import ErrorCode


class ProviderError(Exception):
    def __init__(self, code: ErrorCode, **details: int | str):
        super().__init__(code)
        self.code = code
        self.details = details


def fetch(session, url, params, headers=None):
    try:
        response = session.get(url, params=params, headers=headers, timeout=(3, 10),
                               allow_redirects=False)
    except requests.Timeout:
        raise ProviderError("TIMEOUT") from None
    except requests.RequestException:
        raise ProviderError("SERVICE_UNAVAILABLE") from None
    status = response.status_code
    if status != 200:
        code = {400: "INVALID_ARGUMENT", 401: "AUTH_FAILED", 403: "AUTH_FAILED",
                429: "RATE_LIMITED", 408: "TIMEOUT"}.get(status, "SERVICE_UNAVAILABLE")
        raise ProviderError(code, http_status=status)
    return response


def government_page(session, url, key, params):
    response = fetch(session, url, {**params, "serviceKey": unquote(key)})
    try:
        if response.content.lstrip().startswith(b"<"):
            root = ElementTree.fromstring(response.content)
            if root.tag == "OpenAPI_ServiceResponse":
                code = root.findtext("cmmMsgHeader/returnReasonCode")
                return _page(code, None, None)
            code = root.findtext("header/resultCode")
            body = root.find("body")
            rows = [{field.tag: field.text for field in item}
                    for item in root.findall("body/items/item")]
            total = body.findtext("totalCount") if body is not None else None
        else:
            payload = response.json()
            if "OpenAPI_ServiceResponse" in payload:
                code = payload["OpenAPI_ServiceResponse"]["cmmMsgHeader"]["returnReasonCode"]
                return _page(str(code), None, None)
            envelope = payload["response"]
            code = envelope["header"]["resultCode"]
            body = envelope.get("body") or {}
            items = body.get("items") or {}
            rows = items.get("item", [])
            if isinstance(rows, dict):
                rows = [rows]
            total = body.get("totalCount")
        return _page(str(code).strip(), rows, total)
    except (KeyError, TypeError, ValueError, AttributeError, ElementTree.ParseError):
        raise ProviderError("SCHEMA_MISMATCH", http_status=200) from None


def _page(code, rows, total):
    if code == "03":
        return [], 0
    if code not in {"00", "000"}:
        mapped = {
            "01": "SERVICE_UNAVAILABLE", "02": "SERVICE_UNAVAILABLE",
            "04": "SERVICE_UNAVAILABLE", "05": "TIMEOUT", "10": "INVALID_ARGUMENT",
            "11": "INVALID_ARGUMENT", "12": "SERVICE_UNAVAILABLE",
            "20": "AUTH_FAILED", "21": "AUTH_FAILED", "22": "RATE_LIMITED",
            "30": "AUTH_FAILED", "31": "AUTH_FAILED", "32": "AUTH_FAILED",
            "33": "AUTH_FAILED", "99": "UNKNOWN_ERROR",
        }
        details = {"http_status": 200}
        if code in mapped:
            details["result_code"] = code
        raise ProviderError(mapped.get(code, "SCHEMA_MISMATCH"), **details)
    count = int(total)
    if not isinstance(rows, list) or count < len(rows) or any(not isinstance(row, dict) for row in rows):
        raise ProviderError("SCHEMA_MISMATCH", http_status=200)
    return rows, count
