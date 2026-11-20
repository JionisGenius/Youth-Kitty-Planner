from datetime import timezone
from email.utils import format_datetime, parsedate_to_datetime
from os import getenv
from pathlib import Path
import re
from time import monotonic
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import ValidationError
import requests

from ..tools.registry import TOOLS, agent_tool_specs


ENV_NAMES = ("GMS_KEY", "GMS_URL", "GMS_MODEL")


class GmsConfigurationError(ValueError):
    pass


def load_gms_config():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False, interpolate=False)
    config = {name: getenv(name, "").strip() for name in ENV_NAMES}
    if missing := [name for name, value in config.items() if not value]:
        raise GmsConfigurationError({"missing": missing})
    key, url, model = (config[name] for name in ENV_NAMES)
    try:
        endpoint = urlsplit(url)
        valid = (endpoint.scheme == "https" and endpoint.netloc == "gms.ssafy.io"
                 and endpoint.path in ("/gmsapi/api.openai.com/v1/responses", "/v1/responses")
                 and not (endpoint.query or endpoint.fragment))
    except ValueError:
        valid = False
    if not valid:
        raise GmsConfigurationError({"failure": "EXPECTED_GMS_RESPONSES_URL"})
    return key, url, model


def responses_tools():
    return [{**spec["function"], "type": "function", "strict": False} for spec in agent_tool_specs()]


def validate_call(item):
    name = item.get("name")
    if not isinstance(name, str) or name not in TOOLS:
        return "UNKNOWN_TOOL", None
    raw = item.get("arguments")
    if not isinstance(raw, str):
        return "INVALID_ARGUMENT", None
    try:
        model = TOOLS[name].input_model.model_validate_json(raw)
    except ValidationError:
        return "INVALID_ARGUMENT", None
    return "VALID", model


def response_items(data):
    items = data.get("output") if isinstance(data, dict) else None
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        return None
    return items


def text_parts(items):
    return [
        part["text"].strip()
        for item in items if item.get("type") == "message" and isinstance(item.get("content"), list)
        for part in item["content"] if isinstance(part, dict) and part.get("type") == "output_text"
        and isinstance(part.get("text"), str) and part["text"].strip()
    ]


def _retry_after(value):
    if value is None:
        return None
    if re.fullmatch(r"[0-9]{1,10}", value):
        return value
    try:
        return format_datetime(parsedate_to_datetime(value).astimezone(timezone.utc), usegmt=True)
    except (ValueError, TypeError, OverflowError):
        return "UNRECOGNIZED"


def request(session, url, model, prompt, tools=None, *, text_format=None, max_output_tokens=512, diagnostics=False):
    payload = {"model": model, "input": prompt, "store": False, "max_output_tokens": max_output_tokens}
    if tools is not None:
        payload.update(tools=tools, tool_choice="auto", parallel_tool_calls=False)
    if text_format is not None:
        payload["text"] = {"format": text_format}
    start = monotonic()
    evidence = {}
    data = None
    try:
        response = session.post(url, json=payload, timeout=(5, 60), allow_redirects=False)
        evidence["http"] = response.status_code
        if diagnostics:
            evidence["retry_after_present"] = "Retry-After" in response.headers
            evidence["retry_after"] = _retry_after(response.headers.get("Retry-After"))
        data = response.json()
    except requests.RequestException as error:
        evidence["failure"] = ("NON_JSON" if isinstance(error, requests.exceptions.JSONDecodeError)
                               else "TIMEOUT" if isinstance(error, requests.Timeout) else "TRANSPORT_ERROR")
    items = response_items(data)
    if isinstance(data, dict):
        status = data.get("status")
        evidence["response_status"] = status if status in ("completed", "failed", "incomplete") else "OTHER"
        observed_model = data.get("model")
        evidence["model_id_match"] = None if diagnostics and observed_model is None else observed_model == model
        error = data.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            allowed = ("model_not_found", "invalid_api_key", "unsupported_parameter", "invalid_request_error",
                       "insufficient_quota", "rate_limit_exceeded", "invalid_json_schema")
            evidence["error_code"] = code if code in allowed else "OTHER"
            if diagnostics:
                extra_codes = ("quota_exceeded", "model_rate_limit_exceeded", "server_overloaded",
                               "service_unavailable", "too_many_requests", "429", 429)
                kind = error.get("type")
                allowed_types = ("rate_limit_error", "rate_limit_exceeded", "insufficient_quota",
                                 "invalid_request_error", "authentication_error", "server_error",
                                 "service_unavailable", "overloaded_error", "api_error")
                evidence["error_code"] = code if code is None or code in allowed + extra_codes else "OTHER"
                evidence["error_type"] = kind if kind is None or kind in allowed_types else "OTHER"
    evidence["elapsed_ms"] = round((monotonic() - start) * 1000)
    completed = evidence.get("http") == 200 and evidence.get("response_status") == "completed"
    return items if completed and evidence.get("model_id_match") else None, evidence


