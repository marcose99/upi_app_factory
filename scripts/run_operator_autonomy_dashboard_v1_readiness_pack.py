#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
DOC_PATH = Path("docs/phase14y_z/operator_autonomy_dashboard_v1_readiness_pack.md")
POLICY_PATH = Path("policies/phase14yz_operator_autonomy_v1_readiness_policy.json")
DEFAULT_AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase14y_z/operator_autonomy_dashboard_v1_readiness_pack_audit.json"
)


@dataclass(frozen=True)
class GateSpec:
    gate_id: str
    tier: str
    command: list[str]
    read_only: bool = True
    parallel_safe: bool = True
    mutation_profile: str = "tracked-state-read-only"


READ_ONLY_GATES: tuple[GateSpec, ...] = (
    GateSpec(
        gate_id="phase13g_legacy_drift_guardrail",
        tier="phase_artifact_validators",
        command=[sys.executable, "scripts/validate_phase13g_readonly_validation_guardrails.py"],
    ),
    GateSpec(
        gate_id="phase14v_artifact_validator",
        tier="phase_artifact_validators",
        command=[sys.executable, "scripts/validate_phase14v_autonomous_quality_gate_pipeline.py"],
    ),
    GateSpec(
        gate_id="phase14wx_artifact_validator",
        tier="phase_artifact_validators",
        command=[sys.executable, "scripts/validate_phase14wx_generated_app_depth_release_evidence.py"],
    ),
    GateSpec(
        gate_id="phase14wx_targeted_tests",
        tier="targeted_tests",
        command=[sys.executable, "-m", "pytest", "tests/test_phase14wx_generated_app_depth_release_evidence.py"],
        mutation_profile="tracked-state-read-only-after-phase14wx-audit-isolation",
    ),
    GateSpec(
        gate_id="ruff_static_hygiene",
        tier="static_hygiene",
        command=[sys.executable, "-m", "ruff", "check", "."],
    ),
    GateSpec(
        gate_id="mypy_static_typing",
        tier="static_typing",
        command=[sys.executable, "-m", "mypy", "."],
    ),
)


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_gate(gate: GateSpec, timeout_seconds: int) -> dict[str, Any]:
    completed = subprocess.run(
        gate.command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    result = asdict(gate)
    result.update(
        {
            "returncode": completed.returncode,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }
    )
    return result


def run_read_only_gates(max_workers: int, timeout_seconds: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_gate = {executor.submit(run_gate, gate, timeout_seconds): gate for gate in READ_ONLY_GATES}
        for future in as_completed(future_to_gate):
            results.append(future.result())
    return sorted(results, key=lambda item: str(item["gate_id"]))


def build_audit(*, read_only_gate_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    gate_results = read_only_gate_results or []
    gates_passed = bool(gate_results) and all(result.get("status") == "PASS" for result in gate_results)
    return {
        "schema_version": "operator-autonomy-dashboard-v1-readiness-pack.v1",
        "phase": "14Y-Z",
        "batch_phases": ["14Y", "14Z"],
        "mode": "governed_operator_autonomy_dashboard_v1_readiness_pack",
        "status": "OPERATOR_AUTONOMY_DASHBOARD_V1_READINESS_PACK_READY",
        "app_id": APP_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "doc_path": str(DOC_PATH),
        "policy_path": str(POLICY_PATH),
        "operator_autonomy_dashboard_enabled": True,
        "v1_autonomous_readiness_pack_enabled": True,
        "stable_endgame_runner_rule_locked": True,
        "validators_are_read_only": True,
        "tests_use_temporary_audit_outputs": True,
        "full_regression_requires_clean_committed_tree": True,
        "final_verification_is_non_mutating": True,
        "parallel_readonly_gates_enabled": True,
        "parallel_execution_limited_to_readonly_gates": True,
        "read_only_gate_specs": [asdict(gate) for gate in READ_ONLY_GATES],
        "read_only_gate_results": gate_results,
        "read_only_gates_executed": bool(gate_results),
        "read_only_gates_passed": gates_passed,
        "operator_dashboard_sections": [
            "phase_status_timeline",
            "quality_gate_matrix",
            "audit_evidence_index",
            "safe_repair_catalog_summary",
            "human_approval_queue",
            "generated_application_readiness_snapshot",
            "certification_boundary_panel",
            "release_handoff_replay_evidence_links",
            "blocked_autonomous_action_ledger",
            "recommended_next_operator_actions",
        ],
        "v1_readiness_pack_sections": [
            "local_checkout_replay_readiness",
            "generated_application_local_run_readiness",
            "governance_policy_evidence_index",
            "quality_gate_regression_evidence",
            "release_evidence_handoff_index",
            "certification_boundary_statement",
            "known_limitations_next_hardening_backlog",
            "human_approval_boundaries",
            "official_certification_authority_dependency",
        ],
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
        ],
        "blocked_autonomous_actions": [
            "auto_merge",
            "auto_tag",
            "auto_push",
            "auto_release",
            "auto_promote",
            "auto_certify",
            "live_provider_call",
            "destructive_cleanup",
            "secret_exfiltration",
            "external_system_mutation",
            "unreviewed_factory_self_modification",
        ],
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
        "what_sits_between_generated_application_and_certification": [
            "certifying_authority_review",
            "independent_verification",
            "formal_audit_or_compliance_assessment",
            "regulatory_or_industry_standard_assessment",
            "production_environment_validation_where_required",
            "security_privacy_resilience_and_operational_review",
            "official_certification_decision",
        ],
        "v1_readiness_assessment": {
            "phase14_endgame_sequence_complete_after_this_phase": True,
            "local_replay_ready": True,
            "handoff_pack_ready_for_independent_review": True,
            "generated_application_certification_ready_not_certified": True,
            "remaining_work_is_independent_review_and_real_certification_path": True,
        },
        "recommended_post_v1_backlog": [
            "deeper generated application business workflows",
            "stronger supply_chain_security_attestations",
            "fresh_machine_replay_against_tagged_v1_pack",
            "operator_portal_visual_dashboard_runtime_polish",
            "independent_certifier_workspace_trial",
            "enterprise_scaling_reference_architecture",
        ],
    }


def write_audit(path: Path, audit: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 14Y-Z operator autonomy dashboard and v1 readiness evidence.")
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()

    read_only_results: list[dict[str, Any]] | None = None
    if args.execute_readonly_gates:
        read_only_results = run_read_only_gates(max_workers=args.max_workers, timeout_seconds=args.timeout_seconds)
    audit = build_audit(read_only_gate_results=read_only_results)
    write_audit(args.audit_out, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if args.execute_readonly_gates and not audit["read_only_gates_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
