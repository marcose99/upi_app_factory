#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

PHASE = "14U"
SCHEMA_VERSION = "autonomous-phase-discovery-and-planning.v1"
READY_STATUS = "AUTONOMOUS_PHASE_DISCOVERY_AND_PLANNING_READY"
DEFAULT_AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14u/"
    "autonomous_phase_discovery_and_planning_audit.json"
)
DOC_PATH = Path("docs/phase14u/autonomous_phase_discovery_and_planning.md")
POLICY_PATH = Path("policies/phase14u_autonomous_phase_discovery_policy.json")

PLANNED_PHASE_SEQUENCE: list[str] = [
    "phase14v/autonomous-quality-gate-pipeline-hardening",
    "phase14w/generated-application-depth-roadmap-executor",
    "phase14x/release-evidence-industrialization",
    "phase14y/operator-autonomy-dashboard",
    "phase14z/v1-autonomous-readiness-pack",
]

HUMAN_GATED_ACTIONS: list[str] = [
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

BLOCKED_AUTONOMOUS_ACTIONS: list[str] = [
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

SAFE_REPAIR_CLASSES: list[str] = [
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
]


def _gate_specs() -> list[JsonDict]:
    python = sys.executable
    return [
        {
            "gate_id": "phase14t_artifact_validator",
            "command": [python, "scripts/validate_phase14t_autonomous_safe_repair_catalog_operator_loop.py"],
            "read_only": True,
            "parallel_safe": True,
        },
        {
            "gate_id": "phase14t_targeted_tests",
            "command": [python, "-m", "pytest", "tests/test_phase14t_autonomous_safe_repair_catalog_operator_loop.py"],
            "read_only": True,
            "parallel_safe": True,
        },
        {
            "gate_id": "phase14s_artifact_validator",
            "command": [python, "scripts/validate_phase14s_multi_phase_autonomous_continuation.py"],
            "read_only": True,
            "parallel_safe": True,
        },
        {
            "gate_id": "ruff_static_hygiene",
            "command": [python, "-m", "ruff", "check", "."],
            "read_only": True,
            "parallel_safe": True,
        },
        {
            "gate_id": "mypy_static_typing",
            "command": [python, "-m", "mypy", "."],
            "read_only": True,
            "parallel_safe": True,
        },
    ]


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:]


def _run_gate(spec: JsonDict, timeout_seconds: int) -> JsonDict:
    command = spec["command"]
    if not isinstance(command, list):
        raise TypeError(f"Gate command must be a list: {spec}")
    result = subprocess.run(
        [str(part) for part in command],
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return {
        "gate_id": spec["gate_id"],
        "command": command,
        "read_only": spec["read_only"],
        "parallel_safe": spec["parallel_safe"],
        "returncode": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout_tail": _tail(result.stdout),
        "stderr_tail": _tail(result.stderr),
    }


def _run_readonly_gates(max_workers: int, timeout_seconds: int) -> list[JsonDict]:
    specs = _gate_specs()
    workers = max(1, min(max_workers, len(specs)))
    results: list[JsonDict] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_run_gate, spec, timeout_seconds) for spec in specs]
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda item: str(item["gate_id"]))


def build_autonomous_phase_discovery_and_planning(
    *,
    execute_readonly_gates: bool = False,
    max_workers: int = 3,
    timeout_seconds: int = 240,
) -> JsonDict:
    gate_specs = _gate_specs()
    gate_results = _run_readonly_gates(max_workers, timeout_seconds) if execute_readonly_gates else []
    gates_passed = all(result["status"] == "PASS" for result in gate_results) if execute_readonly_gates else False
    return {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "status": READY_STATUS,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "governed_autonomous_phase_discovery_and_planning",
        "doc_path": str(DOC_PATH),
        "policy_path": str(POLICY_PATH),
        "end_phase_target": "phase14z/v1-autonomous-readiness-pack",
        "discovered_next_phase": PLANNED_PHASE_SEQUENCE[0],
        "planned_phase_sequence": PLANNED_PHASE_SEQUENCE,
        "planned_phase_count": len(PLANNED_PHASE_SEQUENCE),
        "fast_distance_strategy": [
            "batch_read_only_validation_where_safe",
            "auto_apply_policy_cataloged_low_risk_repairs",
            "rerun_impacted_gates_after_repair",
            "stop_on_unknown_failure_classes",
            "preserve_human_gated_irreversible_boundaries",
            "generate_audit_evidence_for_every_step",
        ],
        "phase_batching_recommendation": [
            "phase14v_quality_gate_pipeline_hardening_single_phase",
            "phase14w_to_phase14x_batch_generated_app_depth_and_release_evidence_when_safe",
            "phase14y_to_phase14z_batch_operator_dashboard_and_readiness_pack_when_safe",
        ],
        "safe_repair_classes_known": SAFE_REPAIR_CLASSES,
        "read_only_gate_specs": gate_specs,
        "read_only_gate_results": gate_results,
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gates_passed": gates_passed,
        "parallel_readonly_gates_enabled": True,
        "parallel_execution_limited_to_readonly_gates": True,
        "governed_self_evolution_enabled": True,
        "multi_phase_autonomous_continuation_enabled": True,
        "safe_repair_catalog_operator_loop_enabled": True,
        "unknown_failure_class_behavior": "stop_and_require_human_review_or_new_policy",
        "human_gated_actions": HUMAN_GATED_ACTIONS,
        "blocked_autonomous_actions": BLOCKED_AUTONOMOUS_ACTIONS,
        "human_approval_required_for_merge": True,
        "human_approval_required_for_tag": True,
        "human_approval_required_for_push": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_live_provider_calls": True,
        "human_approval_required_for_certification_claims": True,
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


def validate_autonomous_phase_discovery_and_planning(audit: JsonDict) -> list[str]:
    errors: list[str] = []
    if audit.get("schema_version") != SCHEMA_VERSION:
        errors.append("Unexpected schema_version")
    if audit.get("status") != READY_STATUS:
        errors.append("Unexpected status")
    if audit.get("discovered_next_phase") != "phase14v/autonomous-quality-gate-pipeline-hardening":
        errors.append("Next phase discovery must point to Phase 14V")
    if audit.get("end_phase_target") != "phase14z/v1-autonomous-readiness-pack":
        errors.append("End phase target must be Phase 14Z")
    if audit.get("parallel_execution_limited_to_readonly_gates") is not True:
        errors.append("Parallel execution must be limited to read-only gates")
    if audit.get("unknown_failure_class_behavior") != "stop_and_require_human_review_or_new_policy":
        errors.append("Unknown failure classes must stop for review/new policy")
    for field in (
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_push_performed",
        "auto_release_performed",
        "auto_promotion_performed",
        "auto_certification_performed",
        "live_provider_calls_performed",
        "destructive_cleanup_performed",
        "external_system_mutation_performed",
        "official_certification_claimed",
        "official_certification_granted_by_factory",
    ):
        if audit.get(field) is not False:
            errors.append(f"{field} must remain false")
    planned = audit.get("planned_phase_sequence")
    if not isinstance(planned, list) or len(planned) != 5:
        errors.append("Planned phase sequence must contain Phase 14V through Phase 14Z")
    if audit.get("read_only_gates_executed") is True:
        if audit.get("read_only_gates_passed") is not True:
            errors.append("Read-only gates were executed but did not all pass")
        results = audit.get("read_only_gate_results")
        if not isinstance(results, list) or not results:
            errors.append("Executed read-only gates must have result evidence")
        else:
            failing = [str(item.get("gate_id")) for item in results if isinstance(item, dict) and item.get("status") != "PASS"]
            if failing:
                errors.append("Failing read-only gates: " + ", ".join(failing))
    return errors


def _write_audit(audit: JsonDict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 14U autonomous phase discovery and endgame planning.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT_PATH)
    args = parser.parse_args()

    audit = build_autonomous_phase_discovery_and_planning(
        execute_readonly_gates=args.execute_readonly_gates,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout_seconds,
    )
    _write_audit(audit, args.audit_out)
    errors = validate_autonomous_phase_discovery_and_planning(audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
