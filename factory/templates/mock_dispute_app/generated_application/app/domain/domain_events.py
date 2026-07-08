from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    aggregate_id: str
    payload: dict[str, str]
    occurred_at_utc: str


def dispute_event(event_type: str, aggregate_id: str, payload: dict[str, str]) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        payload=payload,
        occurred_at_utc=datetime.now(timezone.utc).isoformat(),
    )
