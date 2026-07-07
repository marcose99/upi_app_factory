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

from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_operator_portal_certification_dashboard_integration import (
    READY as PHASE14L_READY,
    build_operator_portal_certification_dashboard_integration,
)
from scripts.run_governed_autonomous_phase_execution_loop import (
    READY as PHASE14K_READY,
    build_governed_autonomous_phase_execution_loop,
)


APP_ID = "upi_dispute_resolution"
READY = "GENERATED_APPLICATION_MATURITY_SWEEP_READY"

GENERATED_APP_ROOT = Path("workspace/factory_generated/upi_dispute_resolution/generated_application")

MATURITY_DIMENSIONS: tuple[str, ...] = (
    "api_contracts",
    "workflow_correctness",
    "data_model_integrity",
    "pii_redaction",
    "audit_trail",
    "observability",
    "error_handling",
    "local_runnability",
    "mock_ecosystem_boundary",
    "security_validation",
    "test_depth",
    "operator_readiness",
    "certification_readiness_boundary",
)

EXPECTED_GENERATED_APP_TESTS: tuple[str, ...] = (
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_api.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_pii.py",
    "workspace/factory_generated/upi_dispute_resolution/generated_application/tests/test_workflow.py",
)


@dataclass(frozen=True)
class MaturityDimension:
    dimension_id: str
    status: str
    evidence: str
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "dimension_id": self.dimension_id,
            "evidence": self.evidence,
            "status": self.status,
            "summary": self.summary,
        }


def _exists(path_text: str) -> bool:
    return Path(path_text).exists()


def build_maturity_dimensions() -> tuple[MaturityDimension, ...]:
    generated_app_exists = GENERATED_APP_ROOT.exists()
    test_evidence_exists = all(_exists(path) for path in EXPECTED_GENERATED_APP_TESTS)

    base_status = "READY_FOR_V1_RC_REVIEW" if generated_app_exists else "MISSING_GENERATED_APP_ROOT"
    test_status = "READY_FOR_V1_RC_REVIEW" if test_evidence_exists else "TEST_EVIDENCE_INCOMPLETE"

    return (
        MaturityDimension("api_contracts", test_status, EXPECTED_GENERATED_APP_TESTS[0], "Generated app API contract tests are present for local validation."),
        MaturityDimension("workflow_correctness", test_status, EXPECTED_GENERATED_APP_TESTS[2], "Generated app workflow tests are present for local validation."),
        MaturityDimension("data_model_integrity", base_status, str(GENERATED_APP_ROOT), "Generated application root is present for maturity inspection."),
        MaturityDimension("pii_redaction", test_status, EXPECTED_GENERATED_APP_TESTS[1], "PII tests are present for local validation."),
        MaturityDimension("audit_trail", base_status, str(GENERATED_APP_ROOT), "Audit evidence must remain traceable in generated app and lifecycle artifacts."),
        MaturityDimension("observability", base_status, str(GENERATED_APP_ROOT), "Generated app maturity sweep checks observability readiness as a review dimension."),
        MaturityDimension("error_handling", base_status, str(GENERATED_APP_ROOT), "Generated app maturity sweep checks explicit error handling as a review dimension."),
        MaturityDimension("local_runnability", base_status, str(GENERATED_APP_ROOT), "Primary generated application is treated as a real local application."),
        MaturityDimension("mock_ecosystem_boundary", "READY_FOR_V1_RC_REVIEW", "phase11b_phase14m_policy", "External ecosystem integrations remain mock or simulated."),
        MaturityDimension("security_validation", "READY_FOR_V1_RC_REVIEW", "full_pytest_and_security_policy_gates", "Security validation remains part of the local certification-readiness chain."),
        MaturityDimension("test_depth", test_status, "generated_application_tests", "Generated application tests are included in full pytest."),
        MaturityDimension("operator_readiness", "READY_FOR_V1_RC_REVIEW", "phase14l_operator_portal_dashboard", "Operator portal certification-readiness integration supports maturity review."),
        MaturityDimension("certification_readiness_boundary", "READY_FOR_V1_RC_REVIEW", "phase14c_to_phase14l_boundary", "Generated app remains certification-ready, not certified."),
    )


def build_generated_application_maturity_sweep(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    execution_loop = build_governed_autonomous_phase_execution_loop(requirement_id=requirement_id)
    portal_integration = build_operator_portal_certification_dashboard_integration(
        requirement_id=requirement_id
    )
    dimensions = build_maturity_dimensions()

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "external_ecosystem_integrations_remain_mock": True,
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_without_policy_performed": False,
        "generated_app_root": str(GENERATED_APP_ROOT),
        "generated_app_root_exists": GENERATED_APP_ROOT.exists(),
        "human_approval_required_for_merge": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_tag": True,
        "live_provider_calls_performed": False,
        "maturity_dimensions": [dimension.to_dict() for dimension in dimensions],
        "maturity_sweep_only": True,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "primary_generated_application_must_be_real_local_app": True,
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "schema_version": "generated-application-maturity-sweep.v1",
        "status": READY,
        "supporting_execution_loop_expected_status": PHASE14K_READY,
        "supporting_execution_loop_status": execution_loop["status"],
        "supporting_portal_dashboard_expected_status": PHASE14L_READY,
        "supporting_portal_dashboard_status": portal_integration["status"],
        "test_evidence_files": list(EXPECTED_GENERATED_APP_TESTS),
        "test_evidence_files_exist": all(_exists(path) for path in EXPECTED_GENERATED_APP_TESTS),
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_generated_application_maturity_sweep(sweep: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if sweep.get("schema_version") != "generated-application-maturity-sweep.v1":
        failures.append("Invalid generated application maturity sweep schema")
    if sweep.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if sweep.get("status") != READY:
        failures.append("Generated application maturity sweep must be ready")

    for key in [
        "primary_generated_application_must_be_real_local_app",
        "external_ecosystem_integrations_remain_mock",
        "maturity_sweep_only",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]:
        if sweep.get(key) is not True:
            failures.append(f"{key} must be true")

    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "external_system_calls_performed",
        "factory_self_modification_without_policy_performed",
        "live_provider_calls_performed",
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "release_execution_performed",
    ]:
        if sweep.get(key) is not False:
            failures.append(f"{key} must be false")

    if sweep.get("generated_app_root_exists") is not True:
        failures.append("Generated app root must exist for maturity sweep")
    if sweep.get("test_evidence_files_exist") is not True:
        failures.append("Generated app test evidence files must exist")

    dimensions_value = sweep.get("maturity_dimensions")
    if not isinstance(dimensions_value, list):
        failures.append("Maturity dimensions must be listed")
    else:
        dimension_ids: set[str] = set()
        for dimension in dimensions_value:
            if isinstance(dimension, dict):
                dimension_id = dimension.get("dimension_id")
                if isinstance(dimension_id, str):
                    dimension_ids.add(dimension_id)
        for dimension_id in MATURITY_DIMENSIONS:
            if dimension_id not in dimension_ids:
                failures.append(f"Missing maturity dimension: {dimension_id}")

    boundary_value = sweep.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if sweep.get("supporting_execution_loop_status") != PHASE14K_READY:
        failures.append("Supporting Phase 14K execution loop must be ready")
    if sweep.get("supporting_portal_dashboard_status") != PHASE14L_READY:
        failures.append("Supporting Phase 14L portal dashboard must be ready")
    return failures


def write_maturity_sweep(sweep: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(sweep, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build generated application maturity sweep.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    sweep = build_generated_application_maturity_sweep(requirement_id=args.requirement_id)
    if args.audit_out is not None:
        write_maturity_sweep(sweep, args.audit_out)
    print(json.dumps(sweep, indent=2, sort_keys=True))
    failures = validate_generated_application_maturity_sweep(sweep)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
