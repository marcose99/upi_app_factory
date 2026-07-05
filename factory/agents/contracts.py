"""Small, explicit contracts for governed deterministic role agents.

The code in this module is intentionally beginner-readable.  The goal is to
make each agent output easy to inspect, validate, and debug.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


AGENT_SEQUENCE: tuple[str, ...] = (
    "requirement_agent",
    "domain_agent",
    "architect_agent",
    "planner_agent",
    "developer_agent",
    "test_agent",
    "security_agent",
    "governance_agent",
    "evidence_agent",
    "reviewer_agent",
    "release_agent",
    "operations_agent",
    "regeneration_agent",
    "traceability_agent",
    "validation_agent",
)

HONESTY_LABELS: tuple[str, ...] = (
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
)

COMMON_POLICY_IDS: tuple[str, ...] = (
    "POL-EVIDENCE-LEDGER",
    "POL-HONESTY-LABELS",
    "POL-MOCK-BOUNDARY",
)


@dataclass(frozen=True)
class AgentDefinition:
    """Definition of one governed role-agent."""

    agent_id: str
    agent_role: str
    prompt_path: str
    responsibility: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AgentOutput:
    """Traceable output produced by one deterministic role-agent."""

    schema_version: str
    run_id: str
    agent_id: str
    agent_role: str
    prompt_path: str
    input_refs: list[str]
    output_refs: list[str]
    requirement_ids: list[str]
    task_ids: list[str]
    policy_ids: list[str]
    evidence_refs: list[str]
    assumptions: list[str]
    decisions: list[str]
    known_limitations: list[str]
    honesty_labels: list[str]
    validation_status: str
    summary: str
    debug_notes: list[str]
    produced_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
