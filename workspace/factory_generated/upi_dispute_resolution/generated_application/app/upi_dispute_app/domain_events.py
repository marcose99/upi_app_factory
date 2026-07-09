from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import DisputeRecord, new_id, utc_now_iso


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_id: str
    occurred_at_utc: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "occurred_at_utc": self.occurred_at_utc,
            "payload": self.payload,
        }


@dataclass
class DomainEventCollector:
    events: list[DomainEvent] = field(default_factory=list)

    def record(self, event: DomainEvent) -> None:
        self.events.append(event)

    def drain(self) -> list[DomainEvent]:
        drained = list(self.events)
        self.events.clear()
        return drained


def dispute_created_event(record: DisputeRecord) -> DomainEvent:
    return DomainEvent(
        event_id=new_id("evt"),
        event_type="dispute.created",
        aggregate_id=record.dispute_id,
        occurred_at_utc=utc_now_iso(),
        payload={
            "client_request_id": record.client_request_id,
            "dispute_type": record.dispute_type.value,
            "status": record.status.value,
            "external_ecosystem_integrations": "mocked_or_simulated_only",
        },
    )


def mock_ecosystem_checked_event(
    record: DisputeRecord,
    *,
    decision: str,
    sources: list[str],
) -> DomainEvent:
    return DomainEvent(
        event_id=new_id("evt"),
        event_type="dispute.mock_ecosystem_checked",
        aggregate_id=record.dispute_id,
        occurred_at_utc=utc_now_iso(),
        payload={
            "decision": decision,
            "new_status": record.status.value,
            "mock_sources_checked": sources,
            "external_ecosystem_integrations": "mocked_or_simulated_only",
        },
    )
