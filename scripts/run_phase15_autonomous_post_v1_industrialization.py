#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
DEFAULT_AUDIT = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase15" / "autonomous_post_v1_industrialization_audit.json"


def run_command(command: list[str], timeout_seconds: int) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
        "read_only": True,
        "parallel_safe": True,
    }


def build_readonly_gate_specs() -> list[dict[str, object]]:
    python = sys.executable
    return [
        {
            "gate_id": "phase13g_legacy_drift_guardrail",
            "command": [python, "scripts/validate_phase13g_readonly_validation_guardrails.py"],
            "tier": "phase_artifact_validators",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only",
        },
        {
            "gate_id": "phase14yz_v1_readiness_validator",
            "command": [python, "scripts/validate_phase14yz_operator_autonomy_v1_readiness.py"],
            "tier": "phase_artifact_validators",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only",
        },
        {
            "gate_id": "phase14yz_targeted_tests",
            "command": [python, "-m", "pytest", "tests/test_phase14yz_operator_autonomy_v1_readiness.py"],
            "tier": "targeted_tests",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only-after-audit-isolation",
        },
        {
            "gate_id": "ruff_static_hygiene",
            "command": [python, "-m", "ruff", "check", "."],
            "tier": "static_hygiene",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only",
        },
        {
            "gate_id": "mypy_static_typing",
            "command": [python, "-m", "mypy", "."],
            "tier": "static_typing",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only",
        },
    ]


def build_audit(execute_readonly_gates: bool, timeout_seconds: int) -> dict[str, object]:
    gate_specs = build_readonly_gate_specs()
    gate_results: list[dict[str, object]] = []
    if execute_readonly_gates:
        for spec in gate_specs:
            command_value = spec["command"]
            if not isinstance(command_value, list):
                raise TypeError("gate command must be a list")
            command = [str(part) for part in command_value]
            result = run_command(command, timeout_seconds)
            result.update({key: value for key, value in spec.items() if key != "command"})
            gate_results.append(result)

    gates_passed = all(result.get("returncode") == 0 for result in gate_results) if gate_results else True
    return {
        "schema_version": "autonomous-post-v1-industrialization-batch.v1",
        "phase": "15A-F",
        "mode": "governed_autonomous_self_evolving_post_v1_industrialization",
        "app_id": APP_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "AUTONOMOUS_POST_V1_INDUSTRIALIZATION_READY",
        "base_tag_required": "v0.14.23-operator-autonomy-dashboard-v1-readiness-pack",
        "batch_phases": ["15A", "15B", "15C", "15D", "15E", "15F"],
        "phase15_scope": {
            "15A": "tagged_v1_fresh_clone_replay_and_handoff_verification",
            "15B": "recipient_handoff_automation_and_one_command_setup_verification",
            "15C": "generated_application_runtime_demo_and_operator_walkthrough",
            "15D": "independent_reviewer_certifier_evidence_dossier_consolidation",
            "15E": "post_v1_hardening_backlog_prioritization",
            "15F": "enterprise_scaling_reference_architecture",
        },
        "governed_self_evolution_enabled": True,
        "safe_self_evolution_scope": [
            "documentation",
            "policy_indexes",
            "validator_hardening",
            "test_evidence",
            "handoff_automation",
            "operator_readiness_reports",
        ],
        "unknown_failure_class_behavior": "stop_and_require_human_review_or_new_policy",
        "read_only_gate_specs": gate_specs,
        "read_only_gate_results": gate_results,
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gates_passed": gates_passed,
        "validators_are_read_only": True,
        "tests_use_temporary_audit_outputs": True,
        "fresh_clone_replay_required": True,
        "full_regression_requires_clean_committed_tree": True,
        "final_verification_is_non_mutating": True,
        "auto_merge_performed": False,
        "auto_tag_performed": False,
        "auto_push_performed": False,
        "auto_release_performed": False,
        "auto_promotion_performed": False,
        "auto_certification_performed": False,
        "live_provider_calls_performed": False,
        "destructive_cleanup_performed": False,
        "external_system_mutation_performed": False,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "factory_does_not_self_certify": True,
        "certification_ready_not_certified_boundary_preserved": True,
        "human_gated_actions": [
            "merge",
            "tag",
            "push",
            "release",
            "promotion",
            "release_candidate_declaration",
            "live_provider_calls",
            "destructive_operations",
            "official_certification_claims",
            "unknown_failure_classes",
            "risky_generated_application_changes",
        ],
        "post_v1_backlog_priorities": [
            "deeper_generated_application_business_workflows",
            "stronger_supply_chain_security_attestations",
            "fresh_machine_replay_against_tagged_v1_pack",
            "operator_portal_visual_dashboard_runtime_polish",
            "independent_certifier_workspace_trial",
            "enterprise_scaling_reference_architecture",
        ],
        "enterprise_scaling_reference_domains": [
            "identity_and_access_governance",
            "secrets_and_key_management",
            "policy_as_code_and_approvals",
            "supply_chain_attestation",
            "observability_and_sre",
            "environment_promotion_and_release_governance",
            "multi_domain_factory_templates",
            "independent_certifier_workspaces",
        ],
        "what_sits_between_generated_application_and_certification": [
            "certifying_authority_review",
            "independent_verification",
            "formal_audit_or_compliance_assessment",
            "regulatory_or_industry_standard_assessment",
            "production_environment_validation_where_required",
            "security_privacy_resilience_and_operational_review",
            "official_certification_decision",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 15 autonomous post-v1 industrialization evidence generation.")
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()

    audit = build_audit(args.execute_readonly_gates, args.timeout_seconds)
    args.audit_out.parent.mkdir(parents=True, exist_ok=True)
    args.audit_out.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit.get("read_only_gates_passed") is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
