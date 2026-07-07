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

from scripts.build_fresh_recipient_certification_evidence_replay_pack import (
    READY,
    REPLAY_STEPS,
    build_fresh_recipient_replay_pack,
    validate_fresh_recipient_replay_pack,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


POLICY_PATH = Path("policies/phase14e_fresh_recipient_certification_evidence_replay_policy.json")
DOC_PATH = Path("docs/phase14e/fresh_recipient_certification_evidence_replay_pack.md")
PACK_PATH = Path("scripts/build_fresh_recipient_certification_evidence_replay_pack.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14e/fresh_recipient_certification_evidence_replay_audit.json"
)
PHASE14D_PACK = Path("scripts/build_certification_ready_release_candidate_evidence_pack.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, PACK_PATH, AUDIT_PATH, PHASE14D_PACK]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "fresh-recipient-certification-evidence-replay-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "FRESH_RECIPIENT_CERTIFICATION_EVIDENCE_REPLAY_PACK":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "fresh_recipient_replay_required",
    ]:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")
        if audit.get(key) is not True:
            failures.append(f"Audit must keep {key} true")

    for key in [
        "official_certification_claimed",
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

    for step_id in REPLAY_STEPS:
        if step_id not in policy.get("required_replay_steps", []):
            failures.append(f"Policy missing replay step: {step_id}")

    pack = build_fresh_recipient_replay_pack()
    if pack.get("status") != READY:
        failures.append("Fresh recipient replay pack should be ready")
    failures.extend(validate_fresh_recipient_replay_pack(pack))

    boundary_value = pack.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Replay pack must list certification boundary")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Replay pack missing boundary item: {item}")

    cli = subprocess.run(
        [sys.executable, str(PACK_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("Fresh recipient replay pack CLI should pass")
    elif READY not in cli.stdout:
        failures.append("Fresh recipient replay pack CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "fresh-recipient certification evidence replay pack",
        "generated application is certification-ready, not certified",
        "the factory does not self-certify generated applications",
        "final certification remains with authorized certifying authorities",
        "certifying authority review",
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
        print("Phase 14E validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14E fresh-recipient certification evidence replay artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
