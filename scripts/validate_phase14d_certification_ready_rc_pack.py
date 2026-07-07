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

from scripts.build_certification_ready_release_candidate_evidence_pack import (
    READY,
    REQUIRED_SECTIONS,
    build_release_candidate_evidence_pack,
    validate_release_candidate_evidence_pack,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


POLICY_PATH = Path("policies/phase14d_certification_ready_release_candidate_evidence_policy.json")
DOC_PATH = Path("docs/phase14d/certification_ready_release_candidate_evidence_pack.md")
PACK_PATH = Path("scripts/build_certification_ready_release_candidate_evidence_pack.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14d/certification_ready_release_candidate_evidence_audit.json"
)
PHASE14C_BOUNDARY = Path("scripts/build_human_approved_promotion_certification_boundary.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, PACK_PATH, AUDIT_PATH, PHASE14C_BOUNDARY]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "certification-ready-release-candidate-evidence-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "CERTIFICATION_READY_RELEASE_CANDIDATE_EVIDENCE_PACK":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")
    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "release_candidate_pack_only",
    ]:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")

    for key in [
        "official_certification_claimed",
        "release_execution_allowed",
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
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
    ]:
        if audit.get(key) is not True:
            failures.append(f"Audit must keep {key} true")

    for key in [
        "official_certification_claimed",
        "release_execution_performed",
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

    pack = build_release_candidate_evidence_pack()
    if pack.get("status") != READY:
        failures.append("Release candidate evidence pack should be ready")
    failures.extend(validate_release_candidate_evidence_pack(pack))

    boundary_value = pack.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Pack must list what sits between generated application and certification")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Pack missing boundary item: {item}")

    sections_value = pack.get("evidence_sections")
    if not isinstance(sections_value, list):
        failures.append("Pack must list evidence sections")
    else:
        section_ids: set[str] = set()
        for section in sections_value:
            if isinstance(section, dict):
                section_id = section.get("section_id")
                if isinstance(section_id, str):
                    section_ids.add(section_id)
        for section in REQUIRED_SECTIONS:
            if section not in section_ids:
                failures.append(f"Pack missing section: {section}")

    cli = subprocess.run(
        [sys.executable, str(PACK_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Release candidate evidence pack CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Release candidate evidence pack CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "certification-ready release candidate evidence pack",
        "the factory does not self-certify generated applications",
        "generated application is certification-ready, not certified",
        "final certification remains with authorized certifying authorities",
        "certifying authority review",
        "official certification decision",
        "does not execute release actions",
        "does not claim official certification",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14D validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14D certification-ready release candidate evidence pack artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
