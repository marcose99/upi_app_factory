from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import secrets
import sys
from typing import Any, Iterator, Mapping


SCHEMA_VERSION = "upi-app-factory.log.v1"
SERVICE_INSTANCE_ID = secrets.token_hex(16)
TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
SENSITIVE_KEY_RE = re.compile(
    r"authorization|cookie|token|secret|password|api_key|credential|account|vpa|"
    r"mobile|phone|email|pan|aadhaar|card|cvv|payload|body|content",
    re.IGNORECASE,
)
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
SEVERITY_NUMBERS = {
    "DEBUG": 5,
    "INFO": 9,
    "WARNING": 13,
    "ERROR": 17,
    "CRITICAL": 21,
}
_context: ContextVar[dict[str, str]] = ContextVar("upi_app_factory_log_context", default={})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _valid_hex(value: str, length: int) -> bool:
    return len(value) == length and bool(re.fullmatch(r"[0-9a-f]+", value)) and int(value, 16) != 0


def new_trace_context(*, request_id: str | None = None) -> dict[str, str]:
    return {
        "trace_id": secrets.token_hex(16),
        "span_id": secrets.token_hex(8),
        "trace_flags": "01",
        "request_id": request_id or secrets.token_hex(16),
    }


def trace_context_from_traceparent(
    traceparent: str | None,
    *,
    request_id: str | None = None,
) -> dict[str, str]:
    if traceparent:
        match = TRACEPARENT_RE.fullmatch(traceparent.strip())
        if match:
            trace_id, span_id, trace_flags = match.groups()
            if _valid_hex(trace_id, 32) and _valid_hex(span_id, 16):
                return {
                    "trace_id": trace_id,
                    "span_id": secrets.token_hex(8),
                    "trace_flags": trace_flags,
                    "parent_span_id": span_id,
                    "request_id": request_id or secrets.token_hex(16),
                }
    return new_trace_context(request_id=request_id)


def current_trace_headers() -> dict[str, str]:
    context = _context.get()
    headers: dict[str, str] = {}
    trace_id = context.get("trace_id")
    span_id = context.get("span_id")
    trace_flags = context.get("trace_flags", "01")
    if trace_id and span_id:
        headers["traceparent"] = f"00-{trace_id}-{span_id}-{trace_flags}"
    if request_id := context.get("request_id"):
        headers["x-request-id"] = request_id
    return headers


@contextmanager
def logging_context(**values: str | None) -> Iterator[None]:
    merged = {**_context.get()}
    for key, value in values.items():
        if value is not None:
            merged[key] = str(value)
    token = _context.set(merged)
    try:
        yield
    finally:
        _context.reset(token)


def _clean_string(value: str, *, limit: int = 800) -> str:
    cleaned = CONTROL_RE.sub(" ", value).replace("\r", " ").replace("\n", " ")
    return cleaned[:limit] + "...[truncated]" if len(cleaned) > limit else cleaned


def redacted(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return "[REDACTED:MAX_DEPTH]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 80:
                result["[truncated]"] = "max_items"
                break
            key_text = _clean_string(str(key), limit=120)
            result[key_text] = "[REDACTED]" if SENSITIVE_KEY_RE.search(key_text) else redacted(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [redacted(item, depth=depth + 1) for item in list(value)[:80]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _clean_string(value) if isinstance(value, str) else value
    return f"[{type(value).__name__}]"


class JsonLogFormatter(logging.Formatter):
    def __init__(self, *, service_name: str, service_namespace: str, service_version: str | None = None) -> None:
        super().__init__()
        self.service_name = service_name
        self.service_namespace = service_namespace
        self.service_version = service_version

    def format(self, record: logging.LogRecord) -> str:
        timestamp = _now()
        level = record.levelname
        extra = redacted(getattr(record, "attributes", {}) or {})
        if not isinstance(extra, dict):
            extra = {"attributes": extra}
        envelope: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": timestamp,
            "observed_timestamp": timestamp,
            "severity_text": level,
            "severity_number": SEVERITY_NUMBERS.get(level, record.levelno),
            "body": _clean_string(str(record.getMessage())),
            "event_name": _clean_string(str(getattr(record, "event_name", record.name)), limit=180),
            "service.name": self.service_name,
            "service.namespace": self.service_namespace,
            "service.instance.id": SERVICE_INSTANCE_ID,
            "deployment.environment.name": os.getenv("UPI_APP_FACTORY_ENVIRONMENT", "local"),
            "source": _clean_string(record.name, limit=180),
        }
        if self.service_version:
            envelope["service.version"] = self.service_version
        envelope.update({key: _clean_string(value) for key, value in _context.get().items()})
        envelope.update({key: value for key, value in extra.items() if value is not None})
        if record.exc_info and os.getenv("UPI_APP_FACTORY_LOG_INCLUDE_STACKTRACE", "false").lower() == "true":
            envelope["error.stacktrace"] = _clean_string(super().formatException(record.exc_info), limit=4000)
        return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def _level() -> int:
    return getattr(logging, os.getenv("UPI_APP_FACTORY_LOG_LEVEL", "INFO").upper(), logging.INFO)


def configure_logging(
    *,
    service_name: str,
    service_namespace: str = "upi_app_factory",
    service_version: str | None = None,
) -> None:
    formatter: logging.Formatter
    if os.getenv("UPI_APP_FACTORY_LOG_FORMAT", "json").lower() == "console":
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    else:
        formatter = JsonLogFormatter(
            service_name=service_name,
            service_namespace=service_namespace,
            service_version=service_version,
        )
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file := os.getenv("UPI_APP_FACTORY_LOG_FILE"):
        path = Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=int(os.getenv("UPI_APP_FACTORY_LOG_MAX_BYTES", "10485760")),
            backupCount=int(os.getenv("UPI_APP_FACTORY_LOG_BACKUP_COUNT", "3")),
            encoding="utf-8",
        )
        try:
            path.chmod(0o600)
        except OSError:
            pass
        handlers.append(file_handler)
    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(_level())
    for log_handler in handlers:
        log_handler.setFormatter(formatter)
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
