#!/usr/bin/env python3
"""Build a governed self-healing repair catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    root_for_path = Path(__file__).resolve().parents[1]
    if str(root_for_path) not in sys.path:
        sys.path.insert(0, str(root_for_path))

from scripts.build_fresh_recipient_handover_replay_pack import (  # noqa: E402
    READY as REPLAY_READY,
    build_fresh_recipient_replay_pack,
)
from scripts.propose_factory_self_engineering_improvements import (  # noqa: E402
    build_factory_self_engineering_proposal_pack,
    validate_factory_self_engineering_proposal_pack,
)

APP_ID = "upi_dispute_resolution"
READY = "REPAIR_CATALOG_READY_FOR_HUMAN_REVIEW"
BLOCKED = "REPAIR_CATALOG_BLOCKED_BY_FRESH_RECIPIENT_REPLAY"

CATALOG_ITEMS: tuple[str, ...] = (
    "repair_classes_defined",
    "risk_tiers_defined",
    "evidence_requirements_defined",
    "rollback_requirements_defined",
    "approval_requirements_defined",
    "blocked_actions_defined",
    "fresh_recipient_replay_dependency_verified",
    "self_engineering_proposal_dependency_verified",
    "repair_application_remains_blocked",
)


@dataclass(frozen=True)
class RepairClass:
    repair_class_id: str
    category: str
    title: str
    risk_tier: str
    required_evidence: tuple[str, ...]
    required_validation_gates: tuple[str, ...]
    rollback_required: bool
    human_approval_required: bool
    auto_apply_allowed_in_this_phase: bool
    auto_apply_eligible_in_future: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "auto_apply_allowed_in_this_phase": self.auto_apply_allowed_in_this_phase,
            "auto_apply_eligible_in_future": self.auto_apply_eligible_in_future,
            "category": self.category,
            "human_approval_required": self.human_approval_required,
            "repair_class_id": self.repair_class_id,
            "required_evidence": list(self.required_evidence),
            "required_validation_gates": list(self.required_validation_gates),
            "risk_tier": self.risk_tier,
            "rollback_required": self.rollback_required,
            "title": self.title,
        }


@dataclass(frozen=True)
class CatalogItem:
    name: str
    satisfied: bool
    evidence: str

    def to_dict(self) -> dict[str, object]:
        return {"evidence": self.evidence, "name": self.name, "satisfied": self.satisfied}


@dataclass(frozen=True)
class GovernedRepairCatalog:
    app_id: str
    catalog_status: str
    preferred_term: str
    project_root: str
    fresh_recipient_replay_ready: bool
    self_engineering_proposals_valid: bool
    catalog_digest: str
    self_engineering_proposal_digest: str
    repair_classes: tuple[RepairClass, ...]
    catalog_items: tuple[CatalogItem, ...]
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    destructive_execution_performed: bool
    factory_self_healing_repair_applied: bool
    factory_self_modification_applied: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.catalog_status == READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "catalog_digest": self.catalog_digest,
            "catalog_items": [item.to_dict() for item in self.catalog_items],
            "catalog_status": self.catalog_status,
            "destructive_execution_performed": self.destructive_execution_performed,
            "external_system_calls_performed": self.external_system_calls_performed,
            "factory_self_healing_repair_applied": self.factory_self_healing_repair_applied,
            "factory_self_modification_applied": self.factory_self_modification_applied,
            "fresh_recipient_replay_ready": self.fresh_recipient_replay_ready,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "reasons": list(self.reasons),
            "repair_classes": [repair.to_dict() for repair in self.repair_classes],
            "schema_version": "governed-self-healing-repair-catalog.v1",
            "self_engineering_proposal_digest": self.self_engineering_proposal_digest,
            "self_engineering_proposals_valid": self.self_engineering_proposals_valid,
        }


def default_repair_classes() -> tuple[RepairClass, ...]:
    evidence = ("failure_summary", "affected_paths", "before_state_digest", "rollback_plan")
    return (
        RepairClass(
            "REPAIR-DOC-001",
            "documentation",
            "Missing documentation artifact proposal",
            "low",
            evidence,
            ("documentation_phrase_gate", "phase_validator"),
            True,
            True,
            False,
            True,
        ),
        RepairClass(
            "REPAIR-POLICY-001",
            "policy",
            "Missing policy field proposal",
            "medium",
            evidence + ("policy_schema_diff",),
            ("policy_validator", "ruff", "mypy", "full_pytest"),
            True,
            True,
            False,
            False,
        ),
        RepairClass(
            "REPAIR-TYPE-001",
            "typing",
            "Type annotation repair proposal",
            "low",
            evidence + ("mypy_failure_text",),
            ("mypy", "targeted_tests", "full_pytest"),
            True,
            True,
            False,
            True,
        ),
        RepairClass(
            "REPAIR-TEST-001",
            "tests",
            "Validator test coverage repair proposal",
            "medium",
            evidence + ("test_gap_reason",),
            ("targeted_tests", "ruff", "mypy", "full_pytest"),
            True,
            True,
            False,
            False,
        ),
        RepairClass(
            "REPAIR-EVIDENCE-001",
            "evidence",
            "Missing lifecycle evidence manifest proposal",
            "medium",
            evidence + ("evidence_schema_ref",),
            ("evidence_validator", "targeted_tests", "full_pytest"),
            True,
            True,
            False,
            False,
        ),
        RepairClass(
            "REPAIR-TERM-001",
            "terminology",
            "Application engineering terminology alignment proposal",
            "low",
            evidence + ("terminology_diff",),
            ("terminology_validator", "ruff", "mypy", "full_pytest"),
            True,
            True,
            False,
            True,
        ),
    )


def build_items(
    replay_ready: bool,
    proposals_valid: bool,
    repair_classes: tuple[RepairClass, ...],
) -> tuple[CatalogItem, ...]:
    values = {
        "repair_classes_defined": (len(repair_classes) >= 5, "Repair classes are defined."),
        "risk_tiers_defined": (
            {repair.risk_tier for repair in repair_classes} >= {"low", "medium"},
            "Low and medium risk tiers are present.",
        ),
        "evidence_requirements_defined": (
            all(repair.required_evidence for repair in repair_classes),
            "Every repair class defines evidence.",
        ),
        "rollback_requirements_defined": (
            all(repair.rollback_required for repair in repair_classes),
            "Every repair class requires rollback.",
        ),
        "approval_requirements_defined": (
            all(repair.human_approval_required for repair in repair_classes),
            "Every repair class requires human approval.",
        ),
        "blocked_actions_defined": (True, "Policy blocks destructive and self-modifying actions."),
        "fresh_recipient_replay_dependency_verified": (replay_ready, "Phase 13AQ replay status."),
        "self_engineering_proposal_dependency_verified": (
            proposals_valid,
            "Self-engineering proposal validation status.",
        ),
        "repair_application_remains_blocked": (
            all(not repair.auto_apply_allowed_in_this_phase for repair in repair_classes),
            "No repair class auto-applies in Phase 13AR.",
        ),
    }
    return tuple(CatalogItem(name, values[name][0], values[name][1]) for name in CATALOG_ITEMS)


def digest_catalog(
    repair_classes: tuple[RepairClass, ...],
    items: tuple[CatalogItem, ...],
) -> str:
    payload = {
        "items": [item.to_dict() for item in items],
        "repair_classes": [repair.to_dict() for repair in repair_classes],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_governed_repair_catalog(
    project_root: Path,
    approval_token: Path | None = None,
    operator_confirmation: bool = False,
) -> GovernedRepairCatalog:
    root = project_root.resolve()
    replay_pack = build_fresh_recipient_replay_pack(root, approval_token, operator_confirmation)
    proposal_pack = build_factory_self_engineering_proposal_pack(root)
    proposals_valid = not validate_factory_self_engineering_proposal_pack(proposal_pack)
    repairs = default_repair_classes()
    replay_ready = replay_pack.replay_status == REPLAY_READY
    items = build_items(replay_ready, proposals_valid, repairs)
    status = READY if replay_ready and all(item.satisfied for item in items) else BLOCKED
    reasons = list(replay_pack.reasons)
    reasons.append("Governed repair catalog is ready for human review." if status == READY else "Repair catalog blocked.")

    return GovernedRepairCatalog(
        app_id=APP_ID,
        catalog_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        fresh_recipient_replay_ready=replay_ready,
        self_engineering_proposals_valid=proposals_valid,
        catalog_digest=digest_catalog(repairs, items),
        self_engineering_proposal_digest=proposal_pack.proposal_digest,
        repair_classes=repairs,
        catalog_items=items,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        destructive_execution_performed=False,
        factory_self_healing_repair_applied=False,
        factory_self_modification_applied=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        reasons=tuple(reasons),
    )


def validate_governed_repair_catalog(catalog: GovernedRepairCatalog) -> list[str]:
    failures: list[str] = []
    if catalog.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")
    if catalog.real_generated_application_deleted or catalog.real_generated_application_overwritten:
        failures.append("Real generated application must not be deleted or overwritten")
    if catalog.destructive_execution_performed:
        failures.append("Phase 13AR must not perform destructive execution")
    if catalog.factory_self_healing_repair_applied or catalog.factory_self_modification_applied:
        failures.append("Phase 13AR must not apply repairs or self-modifications")
    if catalog.live_provider_calls_performed or catalog.external_system_calls_performed:
        failures.append("External or live provider calls must not occur")
    if catalog.auto_merge_performed or catalog.auto_tag_performed or catalog.auto_release_performed:
        failures.append("Phase 13AR must not merge, tag, or release")
    if len(catalog.catalog_digest) != 64 or len(catalog.self_engineering_proposal_digest) != 64:
        failures.append("Catalog and proposal digests must be SHA-256 hex")
    if {item.name for item in catalog.catalog_items} != set(CATALOG_ITEMS):
        failures.append("Catalog must include every required catalog item")
    for repair in catalog.repair_classes:
        if repair.auto_apply_allowed_in_this_phase:
            failures.append(f"{repair.repair_class_id} must not auto-apply in this phase")
        if not repair.human_approval_required or not repair.rollback_required:
            failures.append(f"{repair.repair_class_id} must require approval and rollback")
        if not repair.required_evidence or not repair.required_validation_gates:
            failures.append(f"{repair.repair_class_id} must define evidence and gates")
    return failures


def write_governed_repair_catalog(catalog: GovernedRepairCatalog, audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(catalog.to_audit_dict(), indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governed self-healing repair catalog.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--operator-confirms-final-human-approval", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    catalog = build_governed_repair_catalog(
        args.project_root,
        args.approval_token,
        args.operator_confirms_final_human_approval,
    )
    if args.audit_out is not None:
        write_governed_repair_catalog(catalog, args.audit_out)
    print(json.dumps(catalog.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_governed_repair_catalog(catalog)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0 if catalog.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
