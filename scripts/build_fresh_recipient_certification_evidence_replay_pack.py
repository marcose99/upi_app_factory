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

from scripts.build_certification_ready_release_candidate_evidence_pack import (
    READY as PHASE14D_READY,
    build_release_candidate_evidence_pack,
)
from scripts.build_human_approved_promotion_certification_boundary import CERTIFICATION_BOUNDARY


APP_ID = "upi_dispute_resolution"
READY = "FRESH_RECIPIENT_CERTIFICATION_EVIDENCE_REPLAY_READY"

REPLAY_STEPS: tuple[str, ...] = (
    "verify_python_runtime",
    "install_project_dependencies",
    "run_policy_validators",
    "run_certification_ready_evidence_pack_builder",
    "run_sandbox_replay_report",
    "run_governance_and_security_tests",
    "run_full_local_test_suite",
    "review_certification_boundary",
    "record_authority_review_required",
)


@dataclass(frozen=True)
class ReplayStep:
    step_id: str
    command_preview: str
    expected_result: str
    purpose: str

    def to_dict(self) -> dict[str, object]:
        return {
            "command_preview": self.command_preview,
            "expected_result": self.expected_result,
            "purpose": self.purpose,
            "step_id": self.step_id,
        }


def build_replay_steps() -> tuple[ReplayStep, ...]:
    return (
        ReplayStep("verify_python_runtime", "python --version", "Python 3.10.x", "Confirm runtime compatibility."),
        ReplayStep("install_project_dependencies", "python -m pip install -e .", "Dependencies install locally", "Prepare fresh recipient environment."),
        ReplayStep("run_policy_validators", "python scripts/validate_phase14d_certification_ready_rc_pack.py", "Validator passes", "Verify certification-ready evidence policy."),
        ReplayStep("run_certification_ready_evidence_pack_builder", "python scripts/build_certification_ready_release_candidate_evidence_pack.py", "Evidence pack emits READY", "Rebuild evidence pack independently."),
        ReplayStep("run_sandbox_replay_report", "python scripts/run_sandbox_autonomous_generation_validation_loop.py", "Sandbox replay emits READY", "Replay sandbox-only evidence."),
        ReplayStep("run_governance_and_security_tests", "python -m pytest tests/test_phase13av_agentic_ai_threat_tests.py tests/test_regulatory_governance.py", "Tests pass", "Verify governance/security evidence."),
        ReplayStep("run_full_local_test_suite", "python -m pytest", "Full test suite passes", "Verify complete local behavior."),
        ReplayStep("review_certification_boundary", "python scripts/build_human_approved_promotion_certification_boundary.py", "Boundary emits READY", "Confirm not-certified boundary."),
        ReplayStep("record_authority_review_required", "manual authority record", "Independent certification decision required", "Document that certification authority review remains required."),
    )


def build_fresh_recipient_replay_pack(
    requirement_id: str = "upi_dispute_resolution.default_requirement",
) -> dict[str, object]:
    evidence_pack = build_release_candidate_evidence_pack(requirement_id=requirement_id)
    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "boundary_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
        "certification_authority_verification_required": True,
        "certification_ready_not_certified": True,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "external_system_calls_performed": False,
        "factory_does_not_self_certify": True,
        "factory_self_modification_applied": False,
        "fresh_recipient_replay_required": True,
        "live_provider_calls_performed": False,
        "official_certification_claimed": False,
        "official_certification_decision_required": True,
        "release_execution_performed": False,
        "requirement_id": requirement_id,
        "replay_steps": [step.to_dict() for step in build_replay_steps()],
        "schema_version": "fresh-recipient-certification-evidence-replay-pack.v1",
        "status": READY,
        "supporting_evidence_pack_status": evidence_pack["status"],
        "supporting_evidence_pack_expected_status": PHASE14D_READY,
        "what_sits_between_generated_application_and_certification": list(CERTIFICATION_BOUNDARY),
    }


def validate_fresh_recipient_replay_pack(pack: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if pack.get("schema_version") != "fresh-recipient-certification-evidence-replay-pack.v1":
        failures.append("Invalid fresh recipient replay pack schema")
    if pack.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if pack.get("status") != READY:
        failures.append("Replay pack must be ready")
    for key in [
        "factory_does_not_self_certify",
        "certification_ready_not_certified",
        "certification_authority_verification_required",
        "official_certification_decision_required",
        "fresh_recipient_replay_required",
    ]:
        if pack.get(key) is not True:
            failures.append(f"{key} must be true")
    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "external_system_calls_performed",
        "factory_self_modification_applied",
        "live_provider_calls_performed",
        "official_certification_claimed",
        "release_execution_performed",
    ]:
        if pack.get(key) is not False:
            failures.append(f"{key} must be false")

    steps_value = pack.get("replay_steps")
    if not isinstance(steps_value, list):
        failures.append("Replay steps must be listed")
    else:
        step_ids: set[str] = set()
        for step in steps_value:
            if isinstance(step, dict):
                step_id = step.get("step_id")
                if isinstance(step_id, str):
                    step_ids.add(step_id)
        for step_id in REPLAY_STEPS:
            if step_id not in step_ids:
                failures.append(f"Missing replay step: {step_id}")

    boundary_value = pack.get("what_sits_between_generated_application_and_certification")
    if not isinstance(boundary_value, list):
        failures.append("Certification boundary must be listed")
    else:
        boundary_names = {str(item) for item in boundary_value}
        for item in CERTIFICATION_BOUNDARY:
            if item not in boundary_names:
                failures.append(f"Missing certification boundary item: {item}")

    if pack.get("supporting_evidence_pack_status") != PHASE14D_READY:
        failures.append("Supporting Phase 14D evidence pack must be ready")
    return failures


def write_replay_pack(pack: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(pack, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build fresh-recipient certification evidence replay pack.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    pack = build_fresh_recipient_replay_pack(requirement_id=args.requirement_id)
    if args.audit_out is not None:
        write_replay_pack(pack, args.audit_out)
    print(json.dumps(pack, indent=2, sort_keys=True))
    failures = validate_fresh_recipient_replay_pack(pack)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
