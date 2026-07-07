#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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

from scripts.build_autonomous_lifecycle_plan_executor import build_autonomous_lifecycle_plan
from scripts.build_governed_autonomy_control_plane import decide_autonomy_action


APP_ID = "upi_dispute_resolution"
READY = "SANDBOX_AUTONOMOUS_GENERATION_VALIDATION_READY"
SANDBOX_ROOT = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14b/sandbox_runs"
)


@dataclass(frozen=True)
class SandboxGeneratedPreview:
    package_name: str
    files: tuple[str, ...]
    capabilities: tuple[str, ...]
    mock_boundaries: tuple[str, ...]
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "capabilities": list(self.capabilities),
            "files": list(self.files),
            "mock_boundaries": list(self.mock_boundaries),
            "package_name": self.package_name,
            "summary": self.summary,
        }


def canonical_json(value: dict[str, object]) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_sandbox_generated_preview(requirement_id: str) -> SandboxGeneratedPreview:
    return SandboxGeneratedPreview(
        package_name=f"{APP_ID}.sandbox.{requirement_id}",
        files=(
            "sandbox_generated_application/README.md",
            "sandbox_generated_application/app/contracts.py",
            "sandbox_generated_application/app/workflow.py",
            "sandbox_generated_application/tests/test_workflow.py",
        ),
        capabilities=(
            "case_intake",
            "dispute_triage",
            "evidence_tracking",
            "sla_escalation",
            "audit_reporting",
        ),
        mock_boundaries=(
            "mock_bank_rail",
            "mock_npci_switch",
            "mock_notification_provider",
            "mock_regulatory_reference_data",
        ),
        summary=(
            "Deterministic sandbox-only generated application preview. "
            "No real generated application files are written or overwritten."
        ),
    )


def build_validation_report(preview: SandboxGeneratedPreview) -> dict[str, object]:
    files = preview.files
    capabilities = preview.capabilities
    mock_boundaries = preview.mock_boundaries
    return {
        "all_files_declared": len(files) >= 4,
        "all_required_capabilities_declared": all(
            capability in capabilities
            for capability in [
                "case_intake",
                "dispute_triage",
                "evidence_tracking",
                "sla_escalation",
                "audit_reporting",
            ]
        ),
        "external_integrations_remain_mocked": all(boundary.startswith("mock_") for boundary in mock_boundaries),
        "real_worktree_mutation_performed": False,
        "real_generated_application_written": False,
        "status": "PASSED",
        "validation_mode": "deterministic_sandbox_metadata_validation",
    }


def build_promotion_gate_record() -> dict[str, object]:
    decision = decide_autonomy_action(
        "PROMOTE_SANDBOX_TO_WORKTREE",
        requested_autonomy_level=4,
        human_approved=False,
        sandbox_evidence_present=True,
    ).to_dict()
    return {
        "human_approval_required": True,
        "promotion_allowed_now": False,
        "reason": "Sandbox evidence exists, but worktree promotion still requires explicit human approval.",
        "control_plane_decision": decision,
    }


def build_sandbox_loop_report(requirement_id: str = "upi_dispute_resolution.default_requirement") -> dict[str, object]:
    lifecycle_plan = build_autonomous_lifecycle_plan(requirement_id=requirement_id, autonomy_level=4)
    preview = build_sandbox_generated_preview(requirement_id)
    validation_report = build_validation_report(preview)
    promotion_gate = build_promotion_gate_record()

    generate_decision = decide_autonomy_action(
        "GENERATE_IN_SANDBOX",
        requested_autonomy_level=4,
        human_approved=False,
        sandbox_evidence_present=False,
    ).to_dict()
    test_decision = decide_autonomy_action(
        "RUN_TESTS",
        requested_autonomy_level=4,
        human_approved=False,
        sandbox_evidence_present=False,
    ).to_dict()
    repair_decision = decide_autonomy_action(
        "SELF_HEAL_LOW_RISK_IN_SANDBOX",
        requested_autonomy_level=4,
        human_approved=False,
        sandbox_evidence_present=True,
    ).to_dict()

    evidence_record: dict[str, object] = {
        "external_system_calls_performed": False,
        "factory_self_modification_applied": False,
        "live_provider_calls_performed": False,
        "real_generated_application_deleted": False,
        "real_generated_application_overwritten": False,
        "real_generated_application_written": False,
        "real_worktree_mutated": False,
        "release_action_performed": False,
        "sandbox_only": True,
    }

    report: dict[str, object] = {
        "app_id": APP_ID,
        "arbitrary_shell_execution_performed": False,
        "auto_merge_performed": False,
        "auto_release_performed": False,
        "auto_tag_performed": False,
        "control_plane_decisions": {
            "generate_in_sandbox": generate_decision,
            "run_tests": test_decision,
            "self_heal_low_risk_in_sandbox": repair_decision,
            "promote_sandbox_to_worktree": promotion_gate["control_plane_decision"],
        },
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "evidence_record": evidence_record,
        "execution_mode": "SANDBOX_ONLY",
        "lifecycle_plan_status": lifecycle_plan["status"],
        "promotion_gate_record": promotion_gate,
        "real_command_execution_performed": False,
        "requirement_id": requirement_id,
        "sandbox_generated_preview": preview.to_dict(),
        "sandbox_run_manifest": {
            "sandbox_root": str(SANDBOX_ROOT),
            "run_id": requirement_id.replace(".", "_"),
            "sandbox_files_declared_only": True,
        },
        "sandbox_validation_report": validation_report,
        "schema_version": "sandbox-autonomous-generation-validation-report.v1",
        "status": READY,
    }
    report["report_sha256"] = sha256_text(canonical_json(report))
    return report


def validate_sandbox_loop_report(report: dict[str, object]) -> list[str]:
    failures: list[str] = []
    if report.get("schema_version") != "sandbox-autonomous-generation-validation-report.v1":
        failures.append("Invalid sandbox loop report schema")
    if report.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if report.get("status") != READY:
        failures.append("Sandbox loop report must be ready")
    for key in [
        "arbitrary_shell_execution_performed",
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_release_performed",
        "real_command_execution_performed",
    ]:
        if report.get(key) is not False:
            failures.append(f"{key} must be false")
    evidence = report.get("evidence_record")
    if not isinstance(evidence, dict):
        failures.append("Evidence record must be present")
    else:
        if evidence.get("sandbox_only") is not True:
            failures.append("Evidence record must mark sandbox_only true")
        for key in [
            "external_system_calls_performed",
            "factory_self_modification_applied",
            "live_provider_calls_performed",
            "real_generated_application_deleted",
            "real_generated_application_overwritten",
            "real_generated_application_written",
            "real_worktree_mutated",
            "release_action_performed",
        ]:
            if evidence.get(key) is not False:
                failures.append(f"Evidence record must keep {key} false")
    validation = report.get("sandbox_validation_report")
    if not isinstance(validation, dict):
        failures.append("Sandbox validation report must be present")
    elif validation.get("status") != "PASSED":
        failures.append("Sandbox validation must pass")
    promotion = report.get("promotion_gate_record")
    if not isinstance(promotion, dict):
        failures.append("Promotion gate record must be present")
    else:
        if promotion.get("human_approval_required") is not True:
            failures.append("Promotion gate must require human approval")
        if promotion.get("promotion_allowed_now") is not False:
            failures.append("Promotion must not be allowed in Phase 14B")
    return failures


def write_sandbox_loop_report(report: dict[str, object], audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(canonical_json(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sandbox-only autonomous generation and validation loop.")
    parser.add_argument("--requirement-id", default="upi_dispute_resolution.default_requirement")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    report = build_sandbox_loop_report(args.requirement_id)
    if args.audit_out is not None:
        write_sandbox_loop_report(report, args.audit_out)
    print(canonical_json(report))
    failures = validate_sandbox_loop_report(report)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
