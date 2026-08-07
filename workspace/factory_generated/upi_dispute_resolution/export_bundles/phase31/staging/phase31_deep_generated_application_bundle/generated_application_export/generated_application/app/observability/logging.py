from __future__ import annotations

import json
import logging
from typing import Any

from generated_application.app.observability.tracing import current_trace_context
from generated_application.app.security.pii_redaction import redact_upi


SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "customer_upi",
    "upi",
    "password",
    "secret",
    "token",
}


def _redact_value(key: str, value: Any) -> Any:
    key_lower = key.lower()
    if value is None:
        return None
    if "upi" in key_lower and isinstance(value, str):
        return redact_upi(value)
    if any(marker in key_lower for marker in SENSITIVE_KEYS):
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(child_key): _redact_value(str(child_key), child)
            for child_key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(key, item) for item in value]
    return value


def safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {str(key): _redact_value(str(key), value) for key, value in fields.items()}


def log_event(logger: logging.Logger, event: str, fields: dict[str, Any]) -> None:
    context = current_trace_context()
    payload = {
        "schema_version": "upi_app_factory.generated.log.v1",
        "event": event,
        "trace_id": context.get("trace_id"),
        "span_id": context.get("span_id"),
        "trace_flags": context.get("trace_flags"),
        "correlation_id": context.get("correlation_id", "local"),
        **safe_fields(fields),
    }
    logger.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
