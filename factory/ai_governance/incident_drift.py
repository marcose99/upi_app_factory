from __future__ import annotations

from typing import Any, Protocol


class IncidentStore(Protocol):
    def record_incident(self, campaign_id: str, activity_id: str | None, failure_class: str, payload: dict[str, Any]) -> str: ...


class IncidentDriftRecorder:
    def __init__(self, store: IncidentStore) -> None:
        self.store = store

    def record(self, campaign_id: str, failure_class: str, detail: str, activity_id: str | None = None) -> str:
        return self.store.record_incident(campaign_id, activity_id, failure_class, {"governance_detail": detail})

    def drift(self, campaign_id: str, detail: str) -> str:
        return self.record(campaign_id, "GOVERNANCE_DRIFT", detail)
