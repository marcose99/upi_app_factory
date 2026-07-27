from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import re
import secrets


TRACEPARENT_RE = re.compile(
    r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)
_TRACE_CONTEXT: ContextVar[dict[str, str]] = ContextVar(
    "trace_context",
    default={
        "trace_id": "0" * 32,
        "span_id": "0" * 16,
        "trace_flags": "00",
        "correlation_id": "local",
    },
)


def _valid_trace_id(value: str) -> bool:
    return value != "0" * 32 and bool(re.fullmatch(r"[0-9a-f]{32}", value))


def _valid_span_id(value: str) -> bool:
    return value != "0" * 16 and bool(re.fullmatch(r"[0-9a-f]{16}", value))


def new_trace_context(*, correlation_id: str = "local") -> dict[str, str]:
    return {
        "trace_id": secrets.token_hex(16),
        "span_id": secrets.token_hex(8),
        "trace_flags": "01",
        "correlation_id": correlation_id,
    }


def trace_context_from_headers(
    *,
    traceparent: str | None,
    tracestate: str | None = None,
    correlation_id: str = "local",
) -> dict[str, str]:
    if traceparent:
        match = TRACEPARENT_RE.fullmatch(traceparent.strip())
        if match:
            trace_id, span_id, trace_flags = match.groups()
            if _valid_trace_id(trace_id) and _valid_span_id(span_id):
                context = {
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "trace_flags": trace_flags,
                    "correlation_id": correlation_id,
                }
                if tracestate:
                    context["tracestate"] = tracestate[:256]
                return context
    return new_trace_context(correlation_id=correlation_id)


def current_trace_context() -> dict[str, str]:
    return dict(_TRACE_CONTEXT.get())


def current_traceparent() -> str:
    context = current_trace_context()
    return (
        f"00-{context['trace_id']}-{context['span_id']}-"
        f"{context.get('trace_flags', '01')}"
    )


def event_trace_context() -> dict[str, str]:
    context = current_trace_context()
    if not _valid_trace_id(context.get("trace_id", "")) or not _valid_span_id(
        context.get("span_id", "")
    ):
        context = new_trace_context(
            correlation_id=context.get("correlation_id", "local")
        )
    traceparent = (
        f"00-{context['trace_id']}-{context['span_id']}-"
        f"{context.get('trace_flags', '01')}"
    )
    payload = {
        "traceparent": traceparent,
        "trace_id": context["trace_id"],
        "span_id": context["span_id"],
        "trace_flags": context.get("trace_flags", "01"),
        "correlation_id": context.get("correlation_id", "local"),
    }
    if "tracestate" in context:
        payload["tracestate"] = context["tracestate"]
    return payload


def derive_child_span_id(name: str) -> str:
    context = current_trace_context()
    digest = hashlib.sha256(f"{context['span_id']}:{name}".encode("utf-8")).hexdigest()
    return digest[:16]


@contextmanager
def use_trace_context(context: dict[str, str]) -> Iterator[dict[str, str]]:
    token = _TRACE_CONTEXT.set(dict(context))
    try:
        yield current_trace_context()
    finally:
        _TRACE_CONTEXT.reset(token)


@contextmanager
def local_span(name: str, correlation_id: str) -> Iterator[dict[str, str]]:
    parent = current_trace_context()
    child = dict(parent)
    child["span_id"] = derive_child_span_id(name)
    child["correlation_id"] = correlation_id
    with use_trace_context(child):
        yield {
            "span": name,
            "trace_id": child["trace_id"],
            "span_id": child["span_id"],
            "correlation_id": correlation_id,
        }
