#!/usr/bin/env python3
"""Propose governed factory self-engineering improvements.

This script intentionally proposes improvements only. It does not modify the
repository. Risky self-modification remains human-reviewed, evidence-gated,
test-gated, policy-gated, and rollback-planned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


CATEGORIES: tuple[str, ...] = (
    "prompt_quality",
    "policy_governance",
    "test_coverage",
    "documentation",
    "automation",
    "architecture",
    "observability",
    "release_safety",
)


@dataclass(frozen=True)
class FactorySelfEngineeringProposal:
    """One governed factory self-engineering proposal."""

    proposal_id: str
    category: str
    title: str
    rationale: str
    proposed_action: str
    automatic_application_allowed: bool
    human_approval_required: bool
    evidence_required: bool
    rollback_required: bool
    acceptance_gate: str
    risk_level: str

    def to_dict(self) -> dict[str, object]:
        return {
            "acceptance_gate": self.acceptance_gate,
            "automatic_application_allowed": self.automatic_application_allowed,
            "category": self.category,
            "evidence_required": self.evidence_required,
            "human_approval_required": self.human_approval_required,
            "proposal_id": self.proposal_id,
            "proposed_action": self.proposed_action,
            "rationale": self.rationale,
            "risk_level": self.risk_level,
            "rollback_required": self.rollback_required,
            "title": self.title,
        }


@dataclass(frozen=True)
class FactorySelfEngineeringProposalPack:
    """Governed proposal pack for safe factory self-development."""

    schema_version: str
    app_id: str
    proposal_mode: str
    proposals_only: bool
    self_modification_applied: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    proposal_digest: str
    proposals: tuple[FactorySelfEngineeringProposal, ...]

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "external_system_calls_performed": self.external_system_calls_performed,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "proposal_digest": self.proposal_digest,
            "proposal_mode": self.proposal_mode,
            "proposals": [proposal.to_dict() for proposal in self.proposals],
            "proposals_only": self.proposals_only,
            "schema_version": self.schema_version,
            "self_modification_applied": self.self_modification_applied,
        }


def _digest_proposals(proposals: Iterable[FactorySelfEngineeringProposal]) -> str:
    payload = [proposal.to_dict() for proposal in proposals]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_factory_self_engineering_proposal_pack(project_root: Path) -> FactorySelfEngineeringProposalPack:
    """Build a deterministic proposal-only factory self-engineering pack."""

    root = project_root.resolve()
    has_docs = (root / "docs").exists()
    has_policies = (root / "policies").exists()
    has_tests = (root / "tests").exists()

    proposals: tuple[FactorySelfEngineeringProposal, ...] = (
        FactorySelfEngineeringProposal(
            proposal_id="SELF-ENG-001",
            category="prompt_quality",
            title="Normalize application engineering terminology",
            rationale="Some historical artifacts may still use generation terminology; terminology should converge toward application engineering.",
            proposed_action="Scan future prompt and documentation packs for primary terminology alignment while preserving backward compatibility where test names are historical.",
            automatic_application_allowed=False,
            human_approval_required=True,
            evidence_required=True,
            rollback_required=True,
            acceptance_gate="Documentation and prompt terminology audit passes.",
            risk_level="medium",
        ),
        FactorySelfEngineeringProposal(
            proposal_id="SELF-ENG-002",
            category="policy_governance",
            title="Add self-modification policy gate",
            rationale="Factory self-engineering must remain bounded by explicit governance and human approval.",
            proposed_action="Introduce a policy gate that blocks automatic self-modification unless change risk, evidence, tests, rollback, and approval are present.",
            automatic_application_allowed=False,
            human_approval_required=True,
            evidence_required=True,
            rollback_required=True,
            acceptance_gate="Self-modification policy tests pass and risky actions are blocked.",
            risk_level="high",
        ),
        FactorySelfEngineeringProposal(
            proposal_id="SELF-ENG-003",
            category="test_coverage",
            title="Expand local capability certification coverage",
            rationale="The final factory should certify generated capabilities across unit, integration, policy, security, type, dependency, resilience, replay, and evidence dimensions.",
            proposed_action="Create a consolidated local capability certification runner for engineered applications.",
            automatic_application_allowed=False,
            human_approval_required=True,
            evidence_required=True,
            rollback_required=True,
            acceptance_gate="Certification runner passes on the current UPI dispute application in local mode.",
            risk_level="medium",
        ),
        FactorySelfEngineeringProposal(
            proposal_id="SELF-ENG-004",
            category="automation",
            title="Add self-healing repair catalog",
            rationale="Self-healing is safer when repairs are selected from an auditable catalog rather than ad-hoc modifications.",
            proposed_action="Define a repair catalog with allowed repair classes, required evidence, tests, and rollback metadata.",
            automatic_application_allowed=False,
            human_approval_required=True,
            evidence_required=True,
            rollback_required=True,
            acceptance_gate="Repair catalog validator blocks unknown repair classes.",
            risk_level="medium",
        ),
        FactorySelfEngineeringProposal(
            proposal_id="SELF-ENG-005",
            category="observability",
            title="Add factory self-improvement scorecard",
            rationale="Self-development should be measured through objective quality signals, not only successful commits.",
            proposed_action="Add a scorecard for proposal quality, gate results, repair success, evidence completeness, and regression trend.",
            automatic_application_allowed=False,
            human_approval_required=True,
            evidence_required=True,
            rollback_required=True,
            acceptance_gate="Scorecard emits deterministic JSON with no live provider calls.",
            risk_level="low",
        ),
    )

    if not (has_docs and has_policies and has_tests):
        proposals = proposals + (
            FactorySelfEngineeringProposal(
                proposal_id="SELF-ENG-006",
                category="architecture",
                title="Restore missing governance directory baseline",
                rationale="Factory self-engineering requires docs, policies, and tests baselines to exist.",
                proposed_action="Create a guarded baseline restoration plan for missing governance directories.",
                automatic_application_allowed=False,
                human_approval_required=True,
                evidence_required=True,
                rollback_required=True,
                acceptance_gate="Baseline directory validator passes.",
                risk_level="medium",
            ),
        )

    return FactorySelfEngineeringProposalPack(
        schema_version="factory-self-engineering-proposal-pack.v1",
        app_id="upi_dispute_resolution",
        proposal_mode="PROPOSALS_ONLY",
        proposals_only=True,
        self_modification_applied=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        proposal_digest=_digest_proposals(proposals),
        proposals=proposals,
    )


def validate_factory_self_engineering_proposal_pack(
    pack: FactorySelfEngineeringProposalPack,
) -> list[str]:
    """Validate the self-engineering proposal pack safety boundaries."""

    failures: list[str] = []
    if not pack.proposals_only:
        failures.append("Self-engineering pack must be proposals-only")
    if pack.self_modification_applied:
        failures.append("Self-engineering pack must not apply repository modifications")
    if pack.live_provider_calls_performed:
        failures.append("Self-engineering pack must not call live providers")
    if pack.external_system_calls_performed:
        failures.append("Self-engineering pack must not call external systems")
    if len(pack.proposal_digest) != 64:
        failures.append("Proposal digest must be SHA-256 hex")
    if not pack.proposals:
        failures.append("At least one self-engineering proposal is required")
    for proposal in pack.proposals:
        if proposal.automatic_application_allowed:
            failures.append(f"{proposal.proposal_id} must not be auto-applied")
        if not proposal.human_approval_required:
            failures.append(f"{proposal.proposal_id} must require human approval")
        if not proposal.evidence_required:
            failures.append(f"{proposal.proposal_id} must require evidence")
        if not proposal.rollback_required:
            failures.append(f"{proposal.proposal_id} must require rollback planning")
    return failures


def write_factory_self_engineering_proposal_pack(
    pack: FactorySelfEngineeringProposalPack,
    audit_out: Path,
) -> None:
    """Write deterministic JSON audit for a self-engineering proposal pack."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(pack.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Propose governed factory self-engineering improvements.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    pack = build_factory_self_engineering_proposal_pack(args.project_root)

    if args.audit_out is not None:
        write_factory_self_engineering_proposal_pack(pack, args.audit_out)

    print(json.dumps(pack.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_factory_self_engineering_proposal_pack(pack)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
