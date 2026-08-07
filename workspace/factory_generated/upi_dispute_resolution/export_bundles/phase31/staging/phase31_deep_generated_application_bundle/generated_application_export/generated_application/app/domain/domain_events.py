from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    aggregate_id: str
    aggregate_version: int
    payload: dict[str, Any]
    occurred_at_utc: str


def dispute_event(
    event_type: str,
    aggregate_id: str,
    aggregate_version: int,
    payload: dict[str, Any],
) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        payload=payload,
        occurred_at_utc=datetime.now(timezone.utc).isoformat(),
    )


@dataclass(frozen=True)
class PortableEventEnvelope:
    schema_version: str
    envelope_version: int
    message_id: str
    event_type: str
    aggregate_id: str
    aggregate_version: int
    occurred_at_utc: str
    producer: str
    trace_id: str
    traceparent: str
    tracestate: str | None
    correlation_id: str
    payload: dict[str, Any]
    payload_sha256: str

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))


def portable_event_envelope(
    event: DomainEvent,
    *,
    producer: str = "generated_application.local",
    trace_id: str = "local-trace",
    trace_context: dict[str, str] | None = None,
) -> PortableEventEnvelope:
    payload_json = json.dumps(event.payload, sort_keys=True, separators=(",", ":"))
    payload_sha256 = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    identity = "|".join(
        [
            event.event_type,
            event.aggregate_id,
            str(event.aggregate_version),
            event.occurred_at_utc,
            payload_sha256,
        ]
    )
    message_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    resolved_trace_context = trace_context or {
        "trace_id": trace_id,
        "traceparent": f"00-{trace_id[:32].ljust(32, '0')}-0000000000000001-01",
        "correlation_id": trace_id,
    }
    return PortableEventEnvelope(
        schema_version="upi_app_factory.event_envelope.v1",
        envelope_version=1,
        message_id=message_id,
        event_type=event.event_type,
        aggregate_id=event.aggregate_id,
        aggregate_version=event.aggregate_version,
        occurred_at_utc=event.occurred_at_utc,
        producer=producer,
        trace_id=resolved_trace_context.get("trace_id", trace_id),
        traceparent=resolved_trace_context.get("traceparent", ""),
        tracestate=resolved_trace_context.get("tracestate"),
        correlation_id=resolved_trace_context.get("correlation_id", trace_id),
        payload=event.payload,
        payload_sha256=payload_sha256,
    )
