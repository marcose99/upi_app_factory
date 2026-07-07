#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_certifying_authority_review_workspace import (
    READY as PHASE14F_READY,
    build_certifying_authority_review_workspace,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


APP_ID = "upi_dispute_resolution"
READY = "AUTHORITY_FINDINGS_REMEDIATION_LOOP_READY"

FINDING_SEVERITIES: tuple[str, ...] = ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL")
FINDING_STATUSES: tuple[str, ...] = (
    "OPEN",
    "REMEDIATION_PLANNED",
    "EVIDENCE_REQUESTED",
    "READY_FOR_REVIEW",
    "AUTHORITY_ACCEPTED",
    "AUTHORITY_REJECTED",
)
REQUIRED_REGISTERS: tuple[str, ...] = (
    "authority_findings_register",
    "remediation_plan_register",
    "evidence_request_register",
    "retest_gate_register",
    "authority_rereview_register",
    "official_decision_boundary",
)


@dataclass(frozen=True)
class FindingTemplate:
    finding_id: str
    severity: str
    status: str
    owner: str
    summary: str
    remediation_boundary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "owner": self.owner,
            "remediation_boundary": self.remediation_boundary,
            "severity": self.severity,
            "status": self.status,
            "summary": self.summary,
        }


def build_finding_templates() -> tuple[FindingTemplate, ...]:
    return (
        FindingTemplate(
            "AUTH-FINDING-PLACEHOLDER-001",
            "INFO",
            "OPEN",
            "certifying_authority",
            "Placeholder for authority-recorded review observation.",
            "Factory may plan remediation after authority finding is recorded; it must not self-certify closure.",
        ),
        FindingTemplate(
            "AUTH-EVIDENCE-REQUEST-001",
            "MEDIUM",
            "EVIDENCE_REQUESTED",
            "certifying_authority",
            "Placeholder for authority-requested additional evidence.",
            "Factory may package requested evidence; authority decides acceptance.",
        ),
        FindingTemplate(
            "AUTH-PROD-VALIDATION-001",
            "HIGH",
            "OPEN",
            "certifying_authority",
            "Placeholder for production-environment validation requirement.",
            "Factory can document readiness, but production validation is outside local-only certification-ready output.",
        ),
    )


def build_authority_findings_remediation_loop(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    review_workspace = build_certifying_authority_review_workspace(requirement_id=requirement_id)

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "automatic_remediation_execution_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_authority_verification_required": True,
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_applied": False,
        "finding_severities": list(FINDING_SEVERITIES),
        "finding_statuses": list(FINDING_STATUSES),
        "finding_templates": [template.to_dict() for template in build_finding_templates()],
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_decision_required": True,
        "official_certification_granted_by_factory": False,
        "registers": {
            "authority_findings_register": "PENDING_AUTHORITY_INPUT",
            "authority_rereview_register": "PENDING_AUTHORITY_INPUT",
            "evidence_request_register": "READY_FOR_AUTHORITY_USE",
            "official_decision_boundary": "AUTHORITY_ONLY",
            "remediation_plan_register": "READY_FOR_GOVERNED_PLANNING",
            "retest_gate_register": "READY_FOR_LOCAL_VALIDATION_PLANNING",
        },
        "release_execution_performed": False,
        "remediation_loop_only": True,
        "requirement_id": requirement_id,
        "schema_version": "authority-findings-remediation-loop.v1",
        "status": READY,
        "supporting_review_workspace_expected_status": PHASE14F_READY,
        "supporting_review_workspace_status": review_workspace["status"],
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_authority_findings_remediation_loop(loop: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if loop.get("schema_version") != "authority-findings-remediation-loop.v1":
        failures.append("Invalid authority findings loop schema")
    if loop.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if loop.get("status") != READY:
        failures.append("Findings remediation loop must be ready")
    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "remediation_loop_only",
    ]:
        if loop.get(key) is not True:
            failures.append(f"{key} must be true")
    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "automatic_remediation_execution_performed",
        "external_system_calls_performed",
        "factory_self_modification_applied",
        "live_provider_calls_performed",
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "release_execution_performed",
    ]:
        if loop.get(key) is not False:
            failures.append(f"{key} must be false")

    registers_value = loop.get("registers")
    if not isinstance(registers_value, dict):
        failures.append("Registers must be present")
    else:
        for register in REQUIRED_REGISTERS:
            if register not in registers_value:
                failures.append(f"Missing register: {register}")

    severity_value = loop.get("finding_severities")
    if not isinstance(severity_value, list):
        failures.append("Finding severities must be listed")
    else:
        severity_names = {str(item) for item in severity_value}
        for severity in FINDING_SEVERITIES:
            if severity not in severity_names:
                failures.append(f"Missing severity: {severity}")

    status_value = loop.get("finding_statuses")
    if not isinstance(status_value, list):
        failures.append("Finding statuses must be listed")
    else:
        status_names = {str(item) for item in status_value}
        for status in FINDING_STATUSES:
            if status not in status_names:
                failures.append(f"Missing finding status: {status}")

    boundary_value = loop.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if loop.get("supporting_review_workspace_status") != PHASE14F_READY:
        failures.append("Supporting Phase 14F review workspace must be ready")
    return failures


def write_authority_findings_loop(loop: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(loop, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build authority findings register and remediation loop.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    loop = build_authority_findings_remediation_loop(requirement_id=args.requirement_id)
    if args.audit_out is not None:
        write_authority_findings_loop(loop, args.audit_out)
    print(json.dumps(loop, indent=2, sort_keys=True))
    failures = validate_authority_findings_remediation_loop(loop)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
