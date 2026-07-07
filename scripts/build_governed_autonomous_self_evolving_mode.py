#!/usr/bin/env python3
"""Build Phase 14R governed autonomous self-evolving mode evidence."""

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

READY = "GOVERNED_AUTONOMOUS_SELF_EVOLVING_MODE_READY"
POLICY_PATH = Path("policies/phase14r_governed_autonomous_self_evolving_policy.json")
DOC_PATH = Path("docs/phase14r/governed_autonomous_self_evolving_mode.md")
DEFAULT_AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14r/"
    "governed_autonomous_self_evolving_mode_audit.json"
)

BLOCKED_ACTIONS = [
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

SELF_EVOLUTION_CAPABILITIES = [
    "propose_prompt_improvements",
    "propose_policy_improvements",
    "propose_script_improvements",
    "propose_test_improvements",
    "propose_documentation_improvements",
    "classify_validation_failures",
    "map_failures_to_repair_catalog",
    "produce_audit_evidence",
    "preserve_certification_boundary",
]

SAFE_REPAIR_CLASSES = [
    "ruff_unused_variable_cleanup",
    "mypy_test_typing_cast",
        "ruff_e402_import_order_cleanup",
        "validator_direct_execution_pythonpath_environment",
        "validator_direct_script_import_path_bootstrap",
        "mypy_validator_json_object_cast",
    "generated_app_runtime_cache_cleanup",
    "ignored_workspace_audit_artifact_forced_staging",
    "validator_rerun_ordering",
    "adoption_gate_sample_runner_reference",
]

CERTIFICATION_BOUNDARY = [
    "certifying_authority_review",
    "independent_verification",
    "formal_audit_or_compliance_assessment",
    "regulatory_or_industry_standard_assessment",
    "production_environment_validation_where_required",
    "security_privacy_resilience_and_operational_review",
    "official_certification_decision",
]


def _python_command(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def readonly_gate_specs() -> list[JsonDict]:
    return [
        {
            "gate_id": "phase14q_artifact_validator",
            "command": _python_command(
                "scripts/validate_phase14q_generated_application_deep_quality.py"
            ),
            "parallel_safe": True,
            "read_only": True,
        },
        {
            "gate_id": "phase14q_targeted_tests",
            "command": _python_command(
                "-m", "pytest", "tests/test_phase14q_generated_application_deep_quality.py"
            ),
            "parallel_safe": True,
            "read_only": True,
        },
        {
            "gate_id": "ruff_static_hygiene",
            "command": _python_command("-m", "ruff", "check", "."),
            "parallel_safe": True,
            "read_only": True,
        },
        {
            "gate_id": "mypy_static_typing",
            "command": _python_command("-m", "mypy", "."),
            "parallel_safe": True,
            "read_only": True,
        },
    ]


def _run_command(gate: JsonDict, timeout_seconds: int) -> JsonDict:
    command = gate["command"]
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        raise TypeError(f"Invalid command for gate {gate['gate_id']}")
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return {
        "gate_id": gate["gate_id"],
        "command": command,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
        "parallel_safe": gate["parallel_safe"],
        "read_only": gate["read_only"],
    }


def execute_parallel_readonly_gates(
    gates: list[JsonDict], max_workers: int, timeout_seconds: int
) -> list[JsonDict]:
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    safe_gates = [gate for gate in gates if gate.get("parallel_safe") and gate.get("read_only")]
    unsafe_gates = [gate for gate in gates if gate not in safe_gates]
    if unsafe_gates:
        unsafe_ids = ", ".join(str(gate.get("gate_id", "unknown")) for gate in unsafe_gates)
        raise ValueError(f"Only read-only parallel-safe gates may execute here: {unsafe_ids}")

    worker_count = min(max_workers, len(safe_gates)) or 1
    results: list[JsonDict] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_gate = {
            executor.submit(_run_command, gate, timeout_seconds): gate for gate in safe_gates
        }
        for future in as_completed(future_to_gate):
            try:
                results.append(future.result())
            except Exception as exc:  # pragma: no cover - defensive audit path
                gate = future_to_gate[future]
                results.append(
                    {
                        "gate_id": gate["gate_id"],
                        "command": gate["command"],
                        "returncode": 1,
                        "status": "FAIL",
                        "stdout_tail": "",
                        "stderr_tail": repr(exc),
                        "parallel_safe": gate["parallel_safe"],
                        "read_only": gate["read_only"],
                    }
                )
    return sorted(results, key=lambda result: str(result["gate_id"]))


def build_governed_autonomous_self_evolving_mode(
    *,
    execute_readonly_gates: bool = False,
    max_workers: int = 3,
    timeout_seconds: int = 180,
) -> JsonDict:
    gates = readonly_gate_specs()
    gate_results: list[JsonDict] = []
    if execute_readonly_gates:
        gate_results = execute_parallel_readonly_gates(gates, max_workers, timeout_seconds)

    return {
        "schema_version": "governed-autonomous-self-evolving-mode.v1",
        "phase": "14R",
        "status": READY,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "governed_autonomous_self_evolving",
        "self_evolving_mode_enabled": True,
        "governed_autonomy_enabled": True,
        "parallel_readonly_gates_enabled": True,
        "parallel_execution_limited_to_readonly_gates": True,
        "read_only_gate_specs": gates,
        "read_only_gate_results": gate_results,
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gates_passed": all(result["status"] == "PASS" for result in gate_results),
        "max_parallel_workers": max_workers,
        "safe_repair_classes_known": SAFE_REPAIR_CLASSES,
        "safe_repairs_auto_applied_this_phase": [],
        "safe_repairs_auto_apply_allowed_without_policy": False,
        "self_evolution_capabilities": SELF_EVOLUTION_CAPABILITIES,
        "self_modification_requires_policy_and_evidence": True,
        "blocked_autonomous_actions": BLOCKED_ACTIONS,
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
        "what_sits_between_generated_application_and_certification": CERTIFICATION_BOUNDARY,
        "supports_next_phase_goal": "parallel_read_only_gates_with_governed_self_evolution",
        "policy_path": str(POLICY_PATH),
        "doc_path": str(DOC_PATH),
    }


def validate_governed_autonomous_self_evolving_mode(audit: JsonDict) -> list[str]:
    errors: list[str] = []
    if audit.get("status") != READY:
        errors.append("Phase 14R audit status is not ready")
    if audit.get("mode") != "governed_autonomous_self_evolving":
        errors.append("Governed autonomous self-evolving mode is not declared")
    if audit.get("self_evolving_mode_enabled") is not True:
        errors.append("Self-evolving mode is not enabled")
    if audit.get("parallel_execution_limited_to_readonly_gates") is not True:
        errors.append("Parallel execution is not limited to read-only gates")
    for action in BLOCKED_ACTIONS:
        if action not in audit.get("blocked_autonomous_actions", []):
            errors.append(f"Blocked autonomous action missing: {action}")
    for action in HUMAN_GATED_ACTIONS:
        if action not in audit.get("human_gated_actions", []):
            errors.append(f"Human-gated action missing: {action}")
    forbidden_flags = [
        "auto_merge_performed",
        "auto_tag_performed",
        "auto_push_performed",
        "auto_release_performed",
        "auto_promotion_performed",
        "auto_certification_performed",
        "live_provider_calls_performed",
        "destructive_cleanup_performed",
        "external_system_mutation_performed",
    ]
    for flag in forbidden_flags:
        if audit.get(flag) is not False:
            errors.append(f"Forbidden autonomous side effect detected: {flag}")
    required_true_flags = [
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
    for flag in required_true_flags:
        if audit.get(flag) is not True:
            errors.append(f"Required governance flag is not true: {flag}")
    if audit.get("official_certification_claimed") is not False:
        errors.append("Factory claimed official certification")
    if audit.get("official_certification_granted_by_factory") is not False:
        errors.append("Factory granted certification to itself")
    gate_specs = audit.get("read_only_gate_specs", [])
    if not isinstance(gate_specs, list) or len(gate_specs) < 4:
        errors.append("Expected at least four read-only gate specs")
    else:
        for gate in gate_specs:
            if not isinstance(gate, dict):
                errors.append("Read-only gate spec is not an object")
                continue
            if gate.get("read_only") is not True or gate.get("parallel_safe") is not True:
                errors.append(f"Gate is not safely parallel read-only: {gate.get('gate_id')}")
    if audit.get("read_only_gates_executed") is True:
        results = audit.get("read_only_gate_results", [])
        if not isinstance(results, list) or not results:
            errors.append("Read-only gates were marked executed without results")
        else:
            failing = [str(result.get("gate_id")) for result in results if result.get("status") != "PASS"]
            if failing:
                errors.append("Failing read-only gates: " + ", ".join(failing))
    return errors


def _write_audit(audit: JsonDict, audit_out: Path) -> None:
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT_PATH)
    args = parser.parse_args()

    audit = build_governed_autonomous_self_evolving_mode(
        execute_readonly_gates=args.execute_readonly_gates,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout_seconds,
    )
    _write_audit(audit, args.audit_out)
    print(json.dumps(audit, indent=2, sort_keys=True))
    errors = validate_governed_autonomous_self_evolving_mode(audit)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
