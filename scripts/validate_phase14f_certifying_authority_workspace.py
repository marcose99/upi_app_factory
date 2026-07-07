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

from scripts.build_certifying_authority_review_workspace import (
    READY,
    REVIEW_SECTIONS,
    build_certifying_authority_review_workspace,
    validate_certifying_authority_review_workspace,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


POLICY_PATH = Path("policies/phase14f_certifying_authority_review_workspace_policy.json")
DOC_PATH = Path("docs/phase14f/certifying_authority_review_workspace.md")
WORKSPACE_PATH = Path("scripts/build_certifying_authority_review_workspace.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14f/certifying_authority_review_workspace_audit.json"
)
PHASE14D_PACK = Path("scripts/build_certification_ready_release_candidate_evidence_pack.py")
PHASE14E_REPLAY = Path("scripts/build_fresh_recipient_certification_evidence_replay_pack.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, WORKSPACE_PATH, AUDIT_PATH, PHASE14D_PACK, PHASE14E_REPLAY]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "certifying-authority-review-workspace-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "CERTIFYING_AUTHORITY_REVIEW_WORKSPACE":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "review_workspace_only",
    ]:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")
        if audit.get(key) is not True:
            failures.append(f"Audit must keep {key} true")

    for key in [
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "release_execution_allowed",
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
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "release_execution_performed",
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

    for section_id in REVIEW_SECTIONS:
        if section_id not in policy.get("required_review_sections", []):
            failures.append(f"Policy missing review section: {section_id}")

    workspace = build_certifying_authority_review_workspace()
    if workspace.get("status") != READY:
        failures.append("Certifying authority workspace should be ready")
    failures.extend(validate_certifying_authority_review_workspace(workspace))

    boundary_value = workspace.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Workspace must list certification boundary")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Workspace missing boundary item: {item}")

    cli = subprocess.run(
        [sys.executable, str(WORKSPACE_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Certifying authority workspace CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Certifying authority workspace CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "certifying authority review workspace",
        "generated application is certification-ready, not certified",
        "the factory does not self-certify generated applications",
        "the factory does not grant official certification",
        "final certification remains with authorized certifying authorities",
        "official certification decision",
        "does not claim official certification",
        "does not execute a release",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14F validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14F certifying authority review workspace artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
