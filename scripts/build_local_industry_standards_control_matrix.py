#!/usr/bin/env python3
"""Build a local industry standards control matrix.

Phase 13AS is non-destructive. It converts standards gaps into local control
records, including policy, validator, tests, evidence, replay command, and
self-healing/repair-catalog linkage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


from scripts.build_governed_self_healing_repair_catalog import (  # noqa: E402
    READY as REPAIR_CATALOG_READY,
    build_governed_repair_catalog,
)


APP_ID = "upi_dispute_resolution"
READY = "STANDARDS_CONTROL_MATRIX_READY"
BLOCKED = "STANDARDS_CONTROL_MATRIX_BLOCKED_BY_REPAIR_CATALOG"

STANDARD_FAMILIES: tuple[str, ...] = (
    "NIST_SSDF",
    "OWASP_SAMM",
    "NIST_AI_RMF",
    "OWASP_LLM_TOP_10",
    "SLSA_PROVENANCE",
    "CYCLONEDX_SBOM",
    "OPENSFF_SCORECARD_STYLE",
    "OPENTELEMETRY_OBSERVABILITY",
    "PAYMENT_COMPLIANCE_TRACEABILITY",
    "FACTORY_SELF_HEALING",
)

STATUS_PRESENT = "LOCAL_CONTROL_PRESENT"
STATUS_PLANNED = "LOCAL_CONTROL_PLANNED"


@dataclass(frozen=True)
class StandardsControl:
    """One standards-style local control."""

    control_id: str
    standard_family: str
    title: str
    local_status: str
    policy_ref: str
    validator_ref: str
    test_ref: str
    evidence_ref: str
    replay_command: str
    self_healing_linkage: str
    gap_eliminated_locally: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "control_id": self.control_id,
            "evidence_ref": self.evidence_ref,
            "gap_eliminated_locally": self.gap_eliminated_locally,
            "local_status": self.local_status,
            "policy_ref": self.policy_ref,
            "replay_command": self.replay_command,
            "self_healing_linkage": self.self_healing_linkage,
            "standard_family": self.standard_family,
            "test_ref": self.test_ref,
            "title": self.title,
            "validator_ref": self.validator_ref,
        }


@dataclass(frozen=True)
class StandardsControlMatrix:
    """Local standards control matrix."""

    app_id: str
    matrix_status: str
    preferred_term: str
    project_root: str
    repair_catalog_ready: bool
    matrix_digest: str
    standard_families: tuple[str, ...]
    controls: tuple[StandardsControl, ...]
    locally_eliminated_gap_count: int
    planned_gap_count: int
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
        return self.matrix_status == READY

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "controls": [control.to_dict() for control in self.controls],
            "destructive_execution_performed": self.destructive_execution_performed,
            "external_system_calls_performed": self.external_system_calls_performed,
            "factory_self_healing_repair_applied": self.factory_self_healing_repair_applied,
            "factory_self_modification_applied": self.factory_self_modification_applied,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "locally_eliminated_gap_count": self.locally_eliminated_gap_count,
            "matrix_digest": self.matrix_digest,
            "matrix_status": self.matrix_status,
            "planned_gap_count": self.planned_gap_count,
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "reasons": list(self.reasons),
            "repair_catalog_ready": self.repair_catalog_ready,
            "schema_version": "local-industry-standards-control-matrix.v1",
            "standard_families": list(self.standard_families),
        }


def _control(
    control_id: str,
    family: str,
    title: str,
    status: str,
    policy: str,
    validator: str,
    test: str,
    evidence: str,
    command: str,
    linkage: str,
) -> StandardsControl:
    return StandardsControl(
        control_id=control_id,
        standard_family=family,
        title=title,
        local_status=status,
        policy_ref=policy,
        validator_ref=validator,
        test_ref=test,
        evidence_ref=evidence,
        replay_command=command,
        self_healing_linkage=linkage,
        gap_eliminated_locally=status == STATUS_PRESENT,
    )


def build_standards_controls() -> tuple[StandardsControl, ...]:
    """Build deterministic local standards controls."""

    return (
        _control(
            "STD-SSDF-001",
            "NIST_SSDF",
            "Secure SDLC phase validation",
            STATUS_PRESENT,
            "policies/phase10_2_sdlc_best_practice_governance_policy.json",
            "scripts/validate_phase13ar_self_healing_repair_catalog.py",
            "tests/test_phase13ar_self_healing_repair_catalog.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ar/governed_self_healing_repair_catalog_audit.json",
            "python scripts/validate_phase13ar_self_healing_repair_catalog.py",
            "REPAIR-POLICY-001",
        ),
        _control(
            "STD-SAMM-001",
            "OWASP_SAMM",
            "Software security maturity scorecard",
            STATUS_PLANNED,
            "policies/phase13as_local_industry_standards_control_matrix_policy.json",
            "scripts/validate_phase13as_standards_control_matrix.py",
            "tests/test_phase13as_standards_control_matrix.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            "python scripts/validate_phase13as_standards_control_matrix.py",
            "REPAIR-EVIDENCE-001",
        ),
        _control(
            "STD-AIRMF-001",
            "NIST_AI_RMF",
            "AI risk register and human oversight matrix",
            STATUS_PLANNED,
            "policies/phase13as_local_industry_standards_control_matrix_policy.json",
            "scripts/validate_phase13as_standards_control_matrix.py",
            "tests/test_phase13as_standards_control_matrix.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            "python scripts/validate_phase13as_standards_control_matrix.py",
            "REPAIR-EVIDENCE-001",
        ),
        _control(
            "STD-LLM-001",
            "OWASP_LLM_TOP_10",
            "Agentic AI prompt/tool/RAG threat test controls",
            STATUS_PLANNED,
            "policies/phase13as_local_industry_standards_control_matrix_policy.json",
            "scripts/validate_phase13as_standards_control_matrix.py",
            "tests/test_phase13as_standards_control_matrix.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            "python scripts/validate_phase13as_standards_control_matrix.py",
            "REPAIR-TEST-001",
        ),
        _control(
            "STD-SLSA-001",
            "SLSA_PROVENANCE",
            "Local provenance and build attestation controls",
            STATUS_PLANNED,
            "policies/phase13as_local_industry_standards_control_matrix_policy.json",
            "scripts/validate_phase13as_standards_control_matrix.py",
            "tests/test_phase13as_standards_control_matrix.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            "python scripts/validate_phase13as_standards_control_matrix.py",
            "REPAIR-EVIDENCE-001",
        ),
        _control(
            "STD-SBOM-001",
            "CYCLONEDX_SBOM",
            "Local SBOM evidence controls",
            STATUS_PLANNED,
            "policies/phase13as_local_industry_standards_control_matrix_policy.json",
            "scripts/validate_phase13as_standards_control_matrix.py",
            "tests/test_phase13as_standards_control_matrix.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            "python scripts/validate_phase13as_standards_control_matrix.py",
            "REPAIR-EVIDENCE-001",
        ),
        _control(
            "STD-OSF-001",
            "OPENSFF_SCORECARD_STYLE",
            "Repository hygiene and security posture controls",
            STATUS_PLANNED,
            "policies/phase13as_local_industry_standards_control_matrix_policy.json",
            "scripts/validate_phase13as_standards_control_matrix.py",
            "tests/test_phase13as_standards_control_matrix.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            "python scripts/validate_phase13as_standards_control_matrix.py",
            "REPAIR-POLICY-001",
        ),
        _control(
            "STD-OTEL-001",
            "OPENTELEMETRY_OBSERVABILITY",
            "Factory run observability event schema controls",
            STATUS_PLANNED,
            "policies/phase13as_local_industry_standards_control_matrix_policy.json",
            "scripts/validate_phase13as_standards_control_matrix.py",
            "tests/test_phase13as_standards_control_matrix.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            "python scripts/validate_phase13as_standards_control_matrix.py",
            "REPAIR-DOC-001",
        ),
        _control(
            "STD-PAY-001",
            "PAYMENT_COMPLIANCE_TRACEABILITY",
            "UPI/payment-domain compliance traceability controls",
            STATUS_PLANNED,
            "policies/phase13as_local_industry_standards_control_matrix_policy.json",
            "scripts/validate_phase13as_standards_control_matrix.py",
            "tests/test_phase13as_standards_control_matrix.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13as/local_industry_standards_control_matrix_audit.json",
            "python scripts/validate_phase13as_standards_control_matrix.py",
            "REPAIR-EVIDENCE-001",
        ),
        _control(
            "STD-SELF-001",
            "FACTORY_SELF_HEALING",
            "Governed self-healing repair catalog controls",
            STATUS_PRESENT,
            "policies/phase13ar_governed_self_healing_repair_catalog_policy.json",
            "scripts/validate_phase13ar_self_healing_repair_catalog.py",
            "tests/test_phase13ar_self_healing_repair_catalog.py",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ar/governed_self_healing_repair_catalog_audit.json",
            "python scripts/validate_phase13ar_self_healing_repair_catalog.py",
            "REPAIR-TERM-001",
        ),
    )


def _digest_controls(controls: tuple[StandardsControl, ...]) -> str:
    payload = [control.to_dict() for control in controls]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_local_standards_control_matrix(
    project_root: Path,
    approval_token: Path | None = None,
    operator_confirmation: bool = False,
) -> StandardsControlMatrix:
    """Build local standards control matrix."""

    root = project_root.resolve()
    repair_catalog = build_governed_repair_catalog(
        project_root=root,
        approval_token=approval_token,
        operator_confirmation=operator_confirmation,
    )
    repair_catalog_ready = repair_catalog.catalog_status == REPAIR_CATALOG_READY

    controls = build_standards_controls()
    locally_eliminated = sum(1 for control in controls if control.gap_eliminated_locally)
    planned = sum(1 for control in controls if control.local_status == STATUS_PLANNED)
    status = READY if repair_catalog_ready and len(controls) >= len(STANDARD_FAMILIES) else BLOCKED

    reasons = list(repair_catalog.reasons)
    if status == READY:
        reasons.append("Local industry standards control matrix is ready for standards-gap elimination planning.")
    else:
        reasons.append("Local industry standards control matrix is blocked until repair catalog dependencies are ready.")

    return StandardsControlMatrix(
        app_id=APP_ID,
        matrix_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        repair_catalog_ready=repair_catalog_ready,
        matrix_digest=_digest_controls(controls),
        standard_families=STANDARD_FAMILIES,
        controls=controls,
        locally_eliminated_gap_count=locally_eliminated,
        planned_gap_count=planned,
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


def validate_local_standards_control_matrix(matrix: StandardsControlMatrix) -> list[str]:
    """Validate local standards control matrix safety and completeness."""

    failures: list[str] = []
    if matrix.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")
    if matrix.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")
    if matrix.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")
    if matrix.destructive_execution_performed:
        failures.append("Phase 13AS must not perform destructive execution")
    if matrix.factory_self_healing_repair_applied:
        failures.append("Phase 13AS must not apply self-healing repairs")
    if matrix.factory_self_modification_applied:
        failures.append("Phase 13AS must not apply factory self-modification")
    if matrix.live_provider_calls_performed:
        failures.append("Live provider calls must not occur")
    if matrix.external_system_calls_performed:
        failures.append("External system calls must not occur")
    if matrix.auto_merge_performed or matrix.auto_tag_performed or matrix.auto_release_performed:
        failures.append("Phase 13AS must not merge, tag, or release")
    if len(matrix.matrix_digest) != 64:
        failures.append("Matrix digest must be SHA-256 hex")

    families = {control.standard_family for control in matrix.controls}
    if families != set(STANDARD_FAMILIES):
        failures.append("Matrix must include every required standard family")

    if matrix.locally_eliminated_gap_count < 2:
        failures.append("Matrix must have at least two locally present controls")
    if matrix.planned_gap_count < 5:
        failures.append("Matrix must maintain planned backlog for remaining gap elimination")

    for control in matrix.controls:
        if control.local_status not in {STATUS_PRESENT, STATUS_PLANNED}:
            failures.append(f"{control.control_id} has invalid local status")
        if not control.policy_ref:
            failures.append(f"{control.control_id} missing policy ref")
        if not control.validator_ref:
            failures.append(f"{control.control_id} missing validator ref")
        if not control.test_ref:
            failures.append(f"{control.control_id} missing test ref")
        if not control.evidence_ref:
            failures.append(f"{control.control_id} missing evidence ref")
        if not control.replay_command.startswith("python "):
            failures.append(f"{control.control_id} replay command must be local Python command")
        if not control.self_healing_linkage.startswith("REPAIR-"):
            failures.append(f"{control.control_id} must link to repair catalog")

    return failures


def write_local_standards_control_matrix(matrix: StandardsControlMatrix, audit_out: Path) -> None:
    """Write deterministic JSON audit for local standards control matrix."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(matrix.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local industry standards control matrix.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--operator-confirms-final-human-approval", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    matrix = build_local_standards_control_matrix(
        project_root=args.project_root,
        approval_token=args.approval_token,
        operator_confirmation=args.operator_confirms_final_human_approval,
    )

    if args.audit_out is not None:
        write_local_standards_control_matrix(matrix, args.audit_out)

    print(json.dumps(matrix.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_local_standards_control_matrix(matrix)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if matrix.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
