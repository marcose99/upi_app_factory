#!/usr/bin/env python3
"""Build Phase 14W-X generated-app-depth and release-evidence batch artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
PHASE = "14W-X"
SCHEMA_VERSION = "generated-app-depth-release-evidence-batch.v1"
DOC_PATH = Path("docs/phase14w_x/generated_application_depth_release_evidence_batch.md")
POLICY_PATH = Path("policies/phase14wx_generated_app_depth_release_evidence_policy.json")
DEFAULT_AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14w_x/"
    "generated_app_depth_release_evidence_batch_audit.json"
)

HUMAN_GATED_ACTIONS = [
    "merge",
    "tag",
    "push",
    "release",
    "promotion",
    "release_candidate_declaration",
    "live_provider_calls",
    "destructive_operations",
    "official_certification_claims",
]

BLOCKED_AUTONOMOUS_ACTIONS = [
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
]

GENERATED_APP_DEPTH_ROADMAP = [
    "dispute_lifecycle_state_depth",
    "evidence_pack_traceability",
    "sla_escalation_and_exception_handling",
    "mock_ecosystem_contract_depth",
    "privacy_and_pii_control_depth",
    "operator_workflow_surface_depth",
    "negative_resilience_and_replay_scenarios",
    "requirement_to_code_test_evidence_traceability",
]

RELEASE_EVIDENCE_INDUSTRIALIZATION = [
    "quality_gate_matrix",
    "validator_and_test_evidence_index",
    "policy_governance_evidence_index",
    "certification_boundary_statement",
    "release_readiness_summary",
    "reproducible_handoff_evidence",
]

CERTIFICATION_GAP = [
    "certifying_authority_review",
    "independent_verification",
    "formal_audit_or_compliance_assessment",
    "regulatory_or_industry_standard_assessment",
    "production_environment_validation_where_required",
    "security_privacy_resilience_and_operational_review",
    "official_certification_decision",
]


@dataclass(frozen=True)
class GateSpec:
    gate_id: str
    command: list[str]
    tier: str
    read_only: bool = True
    parallel_safe: bool = True
    mutation_profile: str = "tracked-state-read-only"


def _python() -> str:
    return sys.executable


def read_only_gate_specs() -> list[GateSpec]:
    python = _python()
    return [
        GateSpec(
            gate_id="phase14v_artifact_validator",
            command=[python, "scripts/validate_phase14v_autonomous_quality_gate_pipeline.py"],
            tier="phase_artifact_validators",
        ),
        GateSpec(
            gate_id="phase14v_targeted_tests",
            command=[python, "-m", "pytest", "tests/test_phase14v_autonomous_quality_gate_pipeline.py"],
            tier="targeted_tests",
            mutation_profile="tracked-state-read-only-after-phase14v-audit-isolation",
        ),
        GateSpec(
            gate_id="phase13g_legacy_drift_guardrail",
            command=[python, "scripts/validate_phase13g_readonly_validation_guardrails.py"],
            tier="phase_artifact_validators",
        ),
        GateSpec(
            gate_id="ruff_static_hygiene",
            command=[python, "-m", "ruff", "check", "."],
            tier="static_hygiene",
        ),
        GateSpec(
            gate_id="mypy_static_typing",
            command=[python, "-m", "mypy", "."],
            tier="static_typing",
        ),
    ]


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_gate(gate: GateSpec, timeout_seconds: int) -> dict[str, Any]:
    completed = subprocess.run(
        gate.command,
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "gate_id": gate.gate_id,
        "command": gate.command,
        "tier": gate.tier,
        "read_only": gate.read_only,
        "parallel_safe": gate.parallel_safe,
        "mutation_profile": gate.mutation_profile,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def execute_read_only_gates(max_workers: int, timeout_seconds: int) -> list[dict[str, Any]]:
    gates = read_only_gate_specs()
    worker_count = max(1, min(max_workers, len(gates)))
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_gate = {executor.submit(run_gate, gate, timeout_seconds): gate for gate in gates}
        for future in as_completed(future_to_gate):
            results.append(future.result())
    return sorted(results, key=lambda item: str(item["gate_id"]))


def build_generated_app_depth_release_evidence_batch(
    *,
    execute_readonly_gates: bool,
    max_workers: int = 3,
    timeout_seconds: int = 240,
    audit_out: Path = DEFAULT_AUDIT_PATH,
) -> dict[str, Any]:
    gate_specs = read_only_gate_specs()
    gate_results = (
        execute_read_only_gates(max_workers=max_workers, timeout_seconds=timeout_seconds)
        if execute_readonly_gates
        else []
    )
    gates_passed = bool(gate_results) and all(result["status"] == "PASS" for result in gate_results)
    audit: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "batch_phases": ["14W", "14X"],
        "mode": "governed_generated_application_depth_release_evidence_batch",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "doc_path": str(DOC_PATH),
        "policy_path": str(POLICY_PATH),
        "generated_application_depth_roadmap_executor_enabled": True,
        "release_evidence_industrialization_enabled": True,
        "generated_application_depth_roadmap": GENERATED_APP_DEPTH_ROADMAP,
        "release_evidence_industrialization": RELEASE_EVIDENCE_INDUSTRIALIZATION,
        "quality_preserving_fast_path": [
            "validators_are_read_only",
            "tests_use_temporary_audit_outputs",
            "full_regression_requires_clean_committed_tree",
            "commit_only_explicit_lifecycle_audit_refreshes_after_regression",
            "final_verification_is_non_mutating",
            "human_gated_irreversible_boundaries_preserved",
        ],
        "parallel_readonly_gates_enabled": True,
        "parallel_execution_limited_to_readonly_gates": True,
        "read_only_gate_specs": [
            {
                "gate_id": gate.gate_id,
                "command": gate.command,
                "tier": gate.tier,
                "read_only": gate.read_only,
                "parallel_safe": gate.parallel_safe,
                "mutation_profile": gate.mutation_profile,
            }
            for gate in gate_specs
        ],
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gate_results": gate_results,
        "read_only_gates_passed": gates_passed if execute_readonly_gates else False,
        "safe_repair_catalog_operator_loop_enabled": True,
        "safe_repair_classes_known": [
            "ruff_unused_variable_cleanup",
            "ruff_unused_import_cleanup",
            "mypy_test_typing_cast",
            "mypy_validator_json_object_cast",
            "mypy_redundant_cast_cleanup",
            "ruff_e402_import_order_cleanup",
            "validator_direct_execution_pythonpath_environment",
            "generated_app_runtime_cache_cleanup",
            "ignored_workspace_audit_artifact_forced_staging",
            "validator_rerun_ordering",
            "adoption_gate_sample_runner_reference",
            "legacy_drift_guardrail_clean_tree_regression",
        ],
        "human_gated_actions": HUMAN_GATED_ACTIONS,
        "blocked_autonomous_actions": BLOCKED_AUTONOMOUS_ACTIONS,
        "auto_merge_performed": False,
        "auto_tag_performed": False,
        "auto_push_performed": False,
        "auto_release_performed": False,
        "auto_promotion_performed": False,
        "auto_certification_performed": False,
        "live_provider_calls_performed": False,
        "destructive_cleanup_performed": False,
        "external_system_mutation_performed": False,
        "factory_does_not_self_certify": True,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "certification_ready_not_certified_boundary_preserved": True,
        "what_sits_between_generated_application_and_certification": CERTIFICATION_GAP,
        "supports_next_phase_goal": "operator_autonomy_dashboard_and_v1_readiness_pack_batch",
        "status": "GENERATED_APPLICATION_DEPTH_RELEASE_EVIDENCE_BATCH_READY",
    }
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT_PATH)
    args = parser.parse_args()

    audit = build_generated_app_depth_release_evidence_batch(
        execute_readonly_gates=args.execute_readonly_gates,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout_seconds,
        audit_out=args.audit_out,
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    if args.execute_readonly_gates and not audit["read_only_gates_passed"]:
        failing = [
            str(result["gate_id"])
            for result in audit["read_only_gate_results"]
            if result["status"] != "PASS"
        ]
        print(f"ERROR: Failing read-only gates: {', '.join(failing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
