from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisputeTriageRequest:
    dispute_id: str
    age_hours: int
    amount_minor: int
    customer_segment: str
    regulatory_complaint: bool
    fraud_signal_score: int


@dataclass(frozen=True)
class DisputeTriageDecision:
    dispute_id: str
    action: str
    priority: str
    rationale: str
    policy_ids: tuple[str, ...]
