"""Deterministic source adapters for the three governed architecture patterns."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchitectureAdapter:
    pattern_id: str
    adapter_id: str

    def render(self, app_id: str) -> dict[str, str]:
        if self.pattern_id == "WORKFLOW_CENTRIC_MODULAR_MONOLITH":
            return self._workflow(app_id)
        if self.pattern_id == "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX":
            return self._event(app_id)
        return {}

    def _workflow(self, app_id: str) -> dict[str, str]:
        return {f"app/{app_id}/application/workflows/dispute_workflow.py": '''from __future__ import annotations

HUMAN_REVIEW_STATES = ("investigation", "resolution_proposed")
DEADLINE_POLICY = {"investigation": "P2D", "resolution_proposed": "P1D"}
REENTRY_POLICY = {"evidence_pending": "additional_evidence", "investigation": "review_return"}


def next_state(current: str, signal: str) -> str:
    transitions = {
        ("evidence_pending", "evidence_complete"): "investigation",
        ("investigation", "review_complete"): "resolution_proposed",
        ("resolution_proposed", "approve"): "resolved",
    }
    return transitions[(current, signal)]
'''}

    def _event(self, app_id: str) -> dict[str, str]:
        events = '''from __future__ import annotations

from dataclasses import dataclass

EVENT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    dispute_id: str
    event_type: str
    idempotency_key: str
    schema_version: str = EVENT_SCHEMA_VERSION
'''
        outbox = '''from __future__ import annotations

from app.%s.application.events import DomainEvent


class InMemoryOutbox:
    def __init__(self) -> None:
        self._events: dict[str, DomainEvent] = {}

    def append(self, event: DomainEvent) -> None:
        self._events.setdefault(event.idempotency_key, event)

    def pending(self) -> list[DomainEvent]:
        return list(self._events.values())
''' % app_id
        service = '''from __future__ import annotations

from dataclasses import asdict

from app.%s.application.events import DomainEvent
from app.%s.domain.aggregates.dispute_case import DisputeCase
from app.%s.infrastructure.messaging.outbox import InMemoryOutbox


class DisputeApplicationService:
    def __init__(self) -> None:
        self._cases: dict[str, DisputeCase] = {}
        self._idempotency: dict[str, str] = {}
        self.outbox = InMemoryOutbox()

    def create(self, payload: dict[str, str], idempotency_key: str) -> dict[str, object]:
        if idempotency_key in self._idempotency:
            return self.get(self._idempotency[idempotency_key])
        case = DisputeCase(dispute_id=payload["dispute_id"], transaction_reference=payload["transaction_reference"], amount=payload["amount"], reason=payload["reason"])
        self._cases[case.dispute_id] = case
        self._idempotency[idempotency_key] = case.dispute_id
        self.outbox.append(DomainEvent(idempotency_key, case.dispute_id, "dispute.created", idempotency_key))
        return asdict(case)

    def get(self, dispute_id: str) -> dict[str, object]:
        return asdict(self._cases[dispute_id])

    def list(self) -> list[dict[str, object]]:
        return [asdict(case) for case in self._cases.values()]

    def action(self, dispute_id: str, target: str, event: str) -> dict[str, object]:
        case = self._cases[dispute_id]
        case.transition(target, event)
        key = f"{dispute_id}:{case.version}:{event}"
        self.outbox.append(DomainEvent(key, dispute_id, event, key))
        return asdict(case)
''' % (app_id, app_id, app_id)
        migration = '''PRAGMA foreign_keys = ON;
CREATE TABLE dispute_cases (dispute_id TEXT PRIMARY KEY, transaction_reference TEXT NOT NULL UNIQUE, amount TEXT NOT NULL, reason TEXT NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL);
CREATE TABLE idempotency_records (idempotency_key TEXT PRIMARY KEY, dispute_id TEXT NOT NULL REFERENCES dispute_cases(dispute_id));
CREATE TABLE audit_records (sequence INTEGER PRIMARY KEY AUTOINCREMENT, dispute_id TEXT NOT NULL, event_type TEXT NOT NULL, previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL);
CREATE TABLE outbox_events (event_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, dispute_id TEXT NOT NULL, event_type TEXT NOT NULL, schema_version TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0);
'''
        return {
            f"app/{app_id}/application/events.py": events,
            f"app/{app_id}/infrastructure/messaging/outbox.py": outbox,
            f"app/{app_id}/application/services/dispute_service.py": service,
            f"app/{app_id}/infrastructure/persistence/migrations/0001_initial.sql": migration,
        }
