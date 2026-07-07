"""Contracts for Phase 13W generated multi-capability dispute app."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceUpload:
    case_id: str
    filename: str
    content_hash: str
    size_bytes: int


@dataclass(frozen=True)
class DisputeCase:
    case_id: str
    age_hours: int
    sla_hours: int
    amount_paise: int
    channel: str


@dataclass(frozen=True)
class EvidenceValidationResult:
    case_id: str
    accepted: bool
    issues: tuple[str, ...]


@dataclass(frozen=True)
class TriageDecision:
    case_id: str
    queue: str
    needs_escalation: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MultiCapabilityResult:
    case_id: str
    evidence: EvidenceValidationResult
    triage: TriageDecision
    external_ecosystem_mode: str
