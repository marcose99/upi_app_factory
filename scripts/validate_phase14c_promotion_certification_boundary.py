#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from scripts.build_human_approved_promotion_certification_boundary import (
    CERTIFICATION_BOUNDARY,
    CERTIFICATION_EVIDENCE,
    READY,
    build_promotion_certification_boundary,
    validate_promotion_certification_boundary,
)


POLICY_PATH = Path("policies/phase14c_human_approved_promotion_certification_boundary_policy.json")
DOC_PATH = Path("docs/phase14c/human_approved_promotion_certification_boundary.md")
BOUNDARY_PATH = Path("scripts/build_human_approved_promotion_certification_boundary.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14c/human_approved_promotion_certification_boundary_audit.json"
)
PHASE14B_LOOP = Path("scripts/run_sandbox_autonomous_generation_validation_loop.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, BOUNDARY_PATH, AUDIT_PATH, PHASE14B_LOOP]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "human-approved-promotion-certification-boundary-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "HUMAN_APPROVED_PROMOTION_GATE_AND_CERTIFICATION_READY_BOUNDARY":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "official_certification_boundary_required",
        "certification_authority_verification_required",
        "promotion_requires_human_approval",
    ]:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")
        if audit.get(key) is not True:
            failures.append(f"Audit must keep {key} true")

    for key in [
        "automatic_promotion_allowed",
        "real_generated_application_delete_allowed",
        "real_generated_application_overwrite_allowed_without_approval",
        "arbitrary_shell_execution_allowed",
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "factory_self_modification_allowed",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    for key in [
        "automatic_promotion_performed",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "arbitrary_shell_execution_performed",
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "factory_self_modification_applied",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]:
        if audit.get(key) is not False:
            failures.append(f"Audit must keep {key} false")

    for item in CERTIFICATION_BOUNDARY:
        if item not in policy.get("boundary_between_generated_application_and_certification", []):
            failures.append(f"Policy missing certification boundary item: {item}")
    for item in CERTIFICATION_EVIDENCE:
        if item not in policy.get("required_certification_evidence", []):
            failures.append(f"Policy missing certification evidence item: {item}")

    boundary = build_promotion_certification_boundary()
    if boundary.get("status") != READY:
        failures.append("Promotion/certification boundary should be ready")
    failures.extend(validate_promotion_certification_boundary(boundary))

    approved_boundary = build_promotion_certification_boundary(human_approved=True)
    promotion = approved_boundary.get("promotion_gate")
    if not isinstance(promotion, dict):
        failures.append("Approved boundary must include promotion gate")
    else:
        if promotion.get("promotion_allowed_now") is not True:
            failures.append("Human-approved boundary should allow promotion decision")
        if promotion.get("real_worktree_mutation_performed_by_this_phase") is not False:
            failures.append("Even approved boundary must not mutate real worktree in Phase 14C")

    cli = subprocess.run(
        [sys.executable, str(BOUNDARY_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Promotion/certification boundary CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Promotion/certification boundary CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "certification-ready evidence boundary",
        "the factory does not self-certify generated applications",
        "generated application is certification-ready, not certified",
        "final certification remains with authorized certifying authorities",
        "independent certifying authority review",
        "official certification decision",
        "does not automatically promote sandbox output to the real worktree",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14C validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14C human-approved promotion and certification boundary artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
