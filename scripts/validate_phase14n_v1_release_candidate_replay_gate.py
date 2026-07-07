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

from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY
from scripts.build_v1_release_candidate_replay_gate import (
    EVIDENCE_ARTIFACTS,
    READY,
    REPLAY_GATE_STEPS,
    build_v1_release_candidate_replay_gate,
    validate_v1_release_candidate_replay_gate,
)


POLICY_PATH = Path("policies/phase14n_v1_release_candidate_replay_gate_policy.json")
DOC_PATH = Path("docs/phase14n/v1_release_candidate_replay_gate.md")
GATE_PATH = Path("scripts/build_v1_release_candidate_replay_gate.py")
AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14n/v1_release_candidate_replay_gate_audit.json"
)
PHASE14M_SWEEP = Path("scripts/build_generated_application_maturity_sweep.py")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def validate() -> list[str]:
    failures: list[str] = []
    for path in [POLICY_PATH, DOC_PATH, GATE_PATH, AUDIT_PATH, PHASE14M_SWEEP]:
        if not path.exists():
            failures.append(f"Missing required artifact: {path}")
    if failures:
        return failures

    policy = load_json(POLICY_PATH)
    audit = load_json(AUDIT_PATH)

    if policy.get("schema_version") != "v1-release-candidate-replay-gate-policy.v1":
        failures.append("Invalid policy schema_version")
    if policy.get("mode") != "V1_RELEASE_CANDIDATE_REPLAY_GATE":
        failures.append("Policy mode mismatch")
    if policy.get("preferred_term") != "application engineering":
        failures.append("Policy must prefer application engineering")

    true_keys = [
        "release_candidate_gate_only",
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "human_approval_required_for_release_candidate_declaration",
        "human_approval_required_for_promotion",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_release",
    ]
    for key in true_keys:
        if policy.get(key) is not True:
            failures.append(f"Policy must keep {key} true")
        if audit.get(key) is not True:
            failures.append(f"Audit must keep {key} true")

    false_policy_keys = [
        "release_execution_allowed",
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "real_generated_application_delete_allowed",
        "real_generated_application_overwrite_allowed_without_approval",
        "arbitrary_shell_execution_allowed",
        "live_provider_calls_allowed",
        "external_system_calls_allowed",
        "factory_self_modification_without_policy_allowed",
        "auto_merge_allowed",
        "auto_tag_allowed",
        "auto_release_allowed",
    ]
    for key in false_policy_keys:
        if policy.get(key) is not False:
            failures.append(f"Policy must keep {key} false")

    false_audit_keys = [
        "release_execution_performed",
        "official_certification_claimed",
        "official_certification_granted_by_factory",
        "real_generated_application_deleted",
        "real_generated_application_overwritten",
        "arbitrary_shell_execution_performed",
        "live_provider_calls_performed",
        "external_system_calls_performed",
        "factory_self_modification_without_policy_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
    ]
    for key in false_audit_keys:
        if audit.get(key) is not False:
            failures.append(f"Audit must keep {key} false")

    for step in REPLAY_GATE_STEPS:
        if step not in policy.get("required_replay_gate_steps", []):
            failures.append(f"Policy missing replay gate step: {step}")
    for artifact_path in EVIDENCE_ARTIFACTS:
        if not Path(artifact_path).exists():
            failures.append(f"Evidence artifact missing: {artifact_path}")

    gate = build_v1_release_candidate_replay_gate()
    if gate.get("status") != READY:
        failures.append("v1 release-candidate replay gate should be ready")
    failures.extend(validate_v1_release_candidate_replay_gate(gate))

    boundary_value = gate.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Gate must list certification boundary")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Gate missing boundary item: {item}")

    cli = subprocess.run(
        [sys.executable, str(GATE_PATH), "--requirement-id", "upi_dispute_resolution.demo"],
        check=False,
        text=True,
        capture_output=True,
    )
    if cli.returncode != 0:
        failures.append("v1 release-candidate replay gate CLI should pass")
    elif READY not in cli.stdout:
        failures.append("v1 release-candidate replay gate CLI did not emit ready status")

    doc_text = DOC_PATH.read_text(encoding="utf-8").lower()
    for phrase in [
        "v1.0 release-candidate replay gate",
        "does not declare the final release",
        "does not grant certification",
        "generated application remains certification-ready, not certified",
        "final certification remains with authorized certifying authorities",
        "human approval is required before release-candidate declaration",
    ]:
        if phrase not in doc_text:
            failures.append(f"Documentation missing phrase: {phrase}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Phase 14N validation failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("Phase 14N v1 release-candidate replay gate artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
