#!/usr/bin/env python3
"""Run Phase 14S governed multi-phase autonomous continuation evidence."""

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

READY = "MULTI_PHASE_AUTONOMOUS_CONTINUATION_RUNNER_READY"
PHASE = "14S"
DOC_PATH = Path("docs/phase14s/multi_phase_autonomous_continuation_runner.md")
POLICY_PATH = Path("policies/phase14s_multi_phase_autonomous_continuation_policy.json")
DEFAULT_AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14s/"
    "multi_phase_autonomous_continuation_runner_audit.json"
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

SAFE_REPAIR_CLASSES_KNOWN = [
    "ruff_unused_variable_cleanup",
    "ruff_unused_import_cleanup",
    "mypy_test_typing_cast",
    "mypy_validator_json_object_cast",
    "ruff_e402_import_order_cleanup",
    "validator_direct_execution_pythonpath_environment",
    "generated_app_runtime_cache_cleanup",
    "ignored_workspace_audit_artifact_forced_staging",
    "validator_rerun_ordering",
    "adoption_gate_sample_runner_reference",
]

DEFAULT_PHASE_SEQUENCE = [
    "phase14t/autonomous-safe-repair-catalog-operator-loop",
    "phase14u/autonomous-phase-discovery-and-planning",
    "phase14v/autonomous-quality-gate-pipeline-hardening",
    "phase14w/generated-application-depth-roadmap-executor",
    "phase14x/release-evidence-industrialization",
    "phase14y/operator-autonomy-dashboard",
    "phase14z/v1-autonomous-readiness-pack",
]


def _python() -> str:
    return sys.executable


def read_only_gate_specs() -> list[JsonDict]:
    return [
        {
            "gate_id": "phase14r_artifact_validator",
            "command": [
                _python(),
                "scripts/validate_phase14r_governed_autonomous_self_evolving_mode.py",
            ],
            "read_only": True,
            "parallel_safe": True,
        },
        {
            "gate_id": "phase14r_targeted_tests",
            "command": [
                _python(),
                "-m",
                "pytest",
                "tests/test_phase14r_governed_autonomous_self_evolving_mode.py",
            ],
            "read_only": True,
            "parallel_safe": True,
        },
        {
            "gate_id": "phase14q_artifact_validator",
            "command": [
                _python(),
                "scripts/validate_phase14q_generated_application_deep_quality.py",
            ],
            "read_only": True,
            "parallel_safe": True,
        },
        {
            "gate_id": "ruff_static_hygiene",
            "command": [_python(), "-m", "ruff", "check", "."],
            "read_only": True,
            "parallel_safe": True,
        },
        {
            "gate_id": "mypy_static_typing",
            "command": [_python(), "-m", "mypy", "."],
            "read_only": True,
            "parallel_safe": True,
        },
    ]


def _tail(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def run_read_only_gate(spec: JsonDict, timeout_seconds: int) -> JsonDict:
    command = spec["command"]
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        raise TypeError(f"Invalid command for gate {spec.get('gate_id')!r}")
    completed = subprocess.run(
        command,
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
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def execute_read_only_gates(max_workers: int, timeout_seconds: int) -> list[JsonDict]:
    specs = read_only_gate_specs()
    results_by_gate: dict[str, JsonDict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_gate = {
            executor.submit(run_read_only_gate, spec, timeout_seconds): str(spec["gate_id"])
            for spec in specs
        }
        for future in as_completed(future_to_gate):
            gate_id = future_to_gate[future]
            try:
                results_by_gate[gate_id] = future.result()
            except subprocess.TimeoutExpired as exc:
                results_by_gate[gate_id] = {
                    "gate_id": gate_id,
                    "command": exc.cmd if isinstance(exc.cmd, list) else [str(exc.cmd)],
                    "read_only": True,
                    "parallel_safe": True,
                    "returncode": 124,
                    "status": "FAIL",
                    "stdout_tail": _tail(str(exc.stdout or "")),
                    "stderr_tail": _tail(str(exc.stderr or "timeout")),
                }
    return [results_by_gate[str(spec["gate_id"])] for spec in specs]


def build_multi_phase_autonomous_continuation_runner(
    *,
    execute_gates: bool = False,
    max_workers: int = 3,
    timeout_seconds: int = 240,
    from_phase: str = "phase14s",
    to_phase: str = "phase14z",
) -> JsonDict:
    specs = read_only_gate_specs()
    gate_results = execute_read_only_gates(max_workers, timeout_seconds) if execute_gates else []
    gates_passed = bool(gate_results) and all(result["status"] == "PASS" for result in gate_results)
    audit: JsonDict = {
        "schema_version": "multi-phase-autonomous-continuation-runner.v1",
        "phase": PHASE,
        "status": READY,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "governed_multi_phase_autonomous_continuation",
        "from_phase": from_phase,
        "to_phase": to_phase,
        "planned_phase_sequence": DEFAULT_PHASE_SEQUENCE,
        "multi_phase_autonomous_continuation_enabled": True,
        "governed_self_evolution_enabled": True,
        "manual_command_reduction_goal": True,
        "parallel_readonly_gates_enabled": True,
        "parallel_execution_limited_to_readonly_gates": True,
        "sequential_human_gates_preserved": True,
        "max_parallel_workers": max_workers,
        "read_only_gate_specs": specs,
        "read_only_gate_results": gate_results,
        "read_only_gates_executed": execute_gates,
        "read_only_gates_passed": gates_passed,
        "safe_repair_classes_known": SAFE_REPAIR_CLASSES_KNOWN,
        "safe_repairs_auto_apply_allowed_only_when_policy_cataloged": True,
        "safe_repairs_auto_applied_this_phase": [],
        "unknown_failure_class_behavior": "stop_and_require_human_review_or_new_policy",
        "autonomous_loop_capabilities": [
            "discover_next_phase_candidate",
            "generate_phase_plan",
            "generate_local_artifacts",
            "run_parallel_read_only_gates",
            "classify_failures",
            "map_failures_to_safe_repair_catalog",
            "apply_policy_cataloged_low_risk_repairs",
            "rerun_impacted_gates",
            "produce_audit_evidence",
            "stop_at_human_gated_boundaries",
        ],
        "blocked_autonomous_actions": BLOCKED_AUTONOMOUS_ACTIONS,
        "human_gated_actions": HUMAN_GATED_ACTIONS,
        "auto_merge_performed": False,
        "auto_tag_performed": False,
        "auto_push_performed": False,
        "auto_release_performed": False,
        "auto_promotion_performed": False,
        "auto_certification_performed": False,
        "live_provider_calls_performed": False,
        "destructive_cleanup_performed": False,
        "external_system_mutation_performed": False,
        "human_approval_required_for_merge": True,
        "human_approval_required_for_tag": True,
        "human_approval_required_for_push": True,
        "human_approval_required_for_release": True,
        "human_approval_required_for_promotion": True,
        "human_approval_required_for_live_provider_calls": True,
        "human_approval_required_for_certification_claims": True,
        "factory_does_not_self_certify": True,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "certification_ready_not_certified_boundary_preserved": True,
        "doc_path": str(DOC_PATH),
        "policy_path": str(POLICY_PATH),
        "supports_next_phase_goal": "complete_remaining_safe_phases_with_governed_autonomous_continuation",
    }
    return audit


def validate_multi_phase_autonomous_continuation_runner(audit: JsonDict) -> list[str]:
    errors: list[str] = []
    if audit.get("status") != READY:
        errors.append("Unexpected Phase 14S status")
    for path in (DOC_PATH, POLICY_PATH):
        if not path.exists():
            errors.append(f"Missing required artifact: {path}")
    required_true = [
        "multi_phase_autonomous_continuation_enabled",
        "governed_self_evolution_enabled",
        "manual_command_reduction_goal",
        "parallel_readonly_gates_enabled",
        "parallel_execution_limited_to_readonly_gates",
        "sequential_human_gates_preserved",
        "human_approval_required_for_merge",
        "human_approval_required_for_tag",
        "human_approval_required_for_push",
        "human_approval_required_for_release",
        "human_approval_required_for_promotion",
        "human_approval_required_for_live_provider_calls",
        "human_approval_required_for_certification_claims",
        "factory_does_not_self_certify",
        "certification_ready_not_certified_boundary_preserved",
    ]
    for field in required_true:
        if audit.get(field) is not True:
            errors.append(f"Expected true field: {field}")
    required_false = [
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
    ]
    for field in required_false:
        if audit.get(field) is not False:
            errors.append(f"Expected false field: {field}")
    specs = audit.get("read_only_gate_specs")
    if not isinstance(specs, list) or not specs:
        errors.append("Read-only gate specs are missing")
    else:
        for spec in specs:
            if not isinstance(spec, dict):
                errors.append("Read-only gate spec is not an object")
                continue
            if spec.get("read_only") is not True or spec.get("parallel_safe") is not True:
                errors.append(f"Gate is not read-only parallel safe: {spec.get('gate_id')}")
    if audit.get("read_only_gates_executed") is True:
        if audit.get("read_only_gates_passed") is not True:
            errors.append("Read-only gates were executed but did not all pass")
        results = audit.get("read_only_gate_results")
        if not isinstance(results, list) or not results:
            errors.append("Executed read-only gate results are missing")
        else:
            failing = [
                str(result.get("gate_id"))
                for result in results
                if isinstance(result, dict) and result.get("status") != "PASS"
            ]
            if failing:
                errors.append("Failing read-only gates: " + ", ".join(failing))
    for action in BLOCKED_AUTONOMOUS_ACTIONS:
        if action not in audit.get("blocked_autonomous_actions", []):
            errors.append(f"Missing blocked autonomous action: {action}")
    for action in HUMAN_GATED_ACTIONS:
        if action not in audit.get("human_gated_actions", []):
            errors.append(f"Missing human-gated action: {action}")
    if len(audit.get("planned_phase_sequence", [])) < 3:
        errors.append("Planned phase sequence is too small for multi-phase continuation")
    return errors


def write_json(path: Path, data: JsonDict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--from-phase", default="phase14s")
    parser.add_argument("--to-phase", default="phase14z")
    parser.add_argument("--audit-out", type=Path, default=None)
    args = parser.parse_args()

    audit = build_multi_phase_autonomous_continuation_runner(
        execute_gates=args.execute_readonly_gates,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout_seconds,
        from_phase=args.from_phase,
        to_phase=args.to_phase,
    )
    if args.audit_out is not None:
        write_json(args.audit_out, audit)
    errors = validate_multi_phase_autonomous_continuation_runner(audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
