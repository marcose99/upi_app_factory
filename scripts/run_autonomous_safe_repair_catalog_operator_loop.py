#!/usr/bin/env python3
"""Phase 14T governed autonomous safe-repair catalog operator loop."""

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

JsonDict = dict[str, Any]

PHASE = "14T"
SCHEMA_VERSION = "autonomous-safe-repair-catalog-operator-loop.v1"
STATUS = "AUTONOMOUS_SAFE_REPAIR_CATALOG_OPERATOR_LOOP_READY"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = Path("docs/phase14t/autonomous_safe_repair_catalog_operator_loop.md")
POLICY_PATH = Path("policies/phase14t_autonomous_safe_repair_catalog_policy.json")
DEFAULT_AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14t/"
    "autonomous_safe_repair_catalog_operator_loop_audit.json"
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

WHAT_SITS_BETWEEN_APP_AND_CERTIFICATION = [
    "certifying_authority_review",
    "independent_verification",
    "formal_audit_or_compliance_assessment",
    "regulatory_or_industry_standard_assessment",
    "production_environment_validation_where_required",
    "security_privacy_resilience_and_operational_review",
    "official_certification_decision",
]

SAFE_REPAIR_CATALOG: list[JsonDict] = [
    {
        "repair_id": "ruff_unused_variable_cleanup",
        "failure_signatures": ["F841", "local variable", "assigned to but never used"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Remove unused local variable when value has no side effect.",
    },
    {
        "repair_id": "ruff_unused_import_cleanup",
        "failure_signatures": ["F401", "imported but unused"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Remove unused import only when symbol is not referenced.",
    },
    {
        "repair_id": "mypy_test_typing_cast",
        "failure_signatures": ["object has no attribute", "not iterable", "attr-defined"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Add explicit typing or cast in tests without weakening production contracts.",
    },
    {
        "repair_id": "mypy_validator_json_object_cast",
        "failure_signatures": ["Returning Any", "no-any-return"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Narrow json.loads results with isinstance checks and cast.",
    },
    {
        "repair_id": "mypy_redundant_cast_cleanup",
        "failure_signatures": ["Redundant cast", "redundant-cast"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Remove redundant cast only when inferred type already satisfies the expected contract.",
    },
    {
        "repair_id": "ruff_e402_import_order_cleanup",
        "failure_signatures": ["E402", "Module level import not at top of file"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Keep imports at module top and use runner environment for PYTHONPATH.",
    },
    {
        "repair_id": "validator_direct_execution_pythonpath_environment",
        "failure_signatures": ["ModuleNotFoundError", "No module named 'scripts'"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Set PYTHONPATH in runner scripts instead of unsafe in-file path mutation.",
    },
    {
        "repair_id": "generated_app_runtime_cache_cleanup",
        "failure_signatures": ["__pycache__", ".pyc", "replay payload contains bytecode/cache"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Delete generated runtime cache files only, never source files.",
    },
    {
        "repair_id": "ignored_workspace_audit_artifact_forced_staging",
        "failure_signatures": ["ignored by one of your .gitignore files", "git add -f"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": False,
        "scope_limit": "Force-stage only explicitly named lifecycle audit evidence files.",
    },
    {
        "repair_id": "validator_rerun_ordering",
        "failure_signatures": ["validator failed before audit refresh", "stale audit"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Regenerate audit evidence before validator execution.",
    },
    {
        "repair_id": "adoption_gate_sample_runner_reference",
        "failure_signatures": ["does not use the governed runner", "uses_governed_runner: false"],
        "allowed_auto_apply_when_policy_cataloged": True,
        "requires_impacted_gate_rerun": True,
        "scope_limit": "Use scripts/governed_phase_runner.py in adoption gate samples.",
    },
]


@dataclass(frozen=True)
class GateSpec:
    gate_id: str
    command: list[str]
    read_only: bool = True
    parallel_safe: bool = True


def read_only_gate_specs() -> list[GateSpec]:
    python = sys.executable
    return [
        GateSpec("phase14s_artifact_validator", [python, "scripts/validate_phase14s_multi_phase_autonomous_continuation.py"]),
        GateSpec("phase14s_targeted_tests", [python, "-m", "pytest", "tests/test_phase14s_multi_phase_autonomous_continuation.py"]),
        GateSpec("phase14r_artifact_validator", [python, "scripts/validate_phase14r_governed_autonomous_self_evolving_mode.py"]),
        GateSpec("ruff_static_hygiene", [python, "-m", "ruff", "check", "."]),
        GateSpec("mypy_static_typing", [python, "-m", "mypy", "."]),
    ]


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if len(text) > limit else text


def _run_gate(spec: GateSpec, timeout_seconds: int) -> JsonDict:
    result = subprocess.run(
        spec.command,
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return {
        "gate_id": spec.gate_id,
        "command": spec.command,
        "read_only": spec.read_only,
        "parallel_safe": spec.parallel_safe,
        "returncode": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout_tail": _tail(result.stdout),
        "stderr_tail": _tail(result.stderr),
    }


def run_read_only_gates(max_workers: int, timeout_seconds: int) -> list[JsonDict]:
    specs = read_only_gate_specs()
    workers = max(1, min(max_workers, len(specs)))
    results: list[JsonDict] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_run_gate, spec, timeout_seconds): spec.gate_id for spec in specs}
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda item: str(item["gate_id"]))


def build_autonomous_safe_repair_catalog_operator_loop(
    *,
    execute_readonly_gates: bool = False,
    max_workers: int = 3,
    timeout_seconds: int = 240,
) -> JsonDict:
    gate_specs = [
        {
            "gate_id": spec.gate_id,
            "command": spec.command,
            "read_only": spec.read_only,
            "parallel_safe": spec.parallel_safe,
        }
        for spec in read_only_gate_specs()
    ]
    gate_results = run_read_only_gates(max_workers, timeout_seconds) if execute_readonly_gates else []
    gates_passed = bool(execute_readonly_gates) and all(result["status"] == "PASS" for result in gate_results)
    audit: JsonDict = {
        "schema_version": SCHEMA_VERSION,
        "phase": PHASE,
        "status": STATUS,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "governed_autonomous_safe_repair_catalog_operator_loop",
        "safe_repair_catalog_operator_loop_enabled": True,
        "governed_self_evolution_enabled": True,
        "policy_path": str(POLICY_PATH),
        "doc_path": str(DOC_PATH),
        "safe_repair_catalog": SAFE_REPAIR_CATALOG,
        "safe_repair_classes_known": [str(item["repair_id"]) for item in SAFE_REPAIR_CATALOG],
        "safe_repair_auto_apply_allowed_only_when_policy_cataloged": True,
        "safe_repairs_auto_applied_this_phase": [],
        "unknown_failure_class_behavior": "stop_and_require_human_review_or_new_policy",
        "operator_loop_steps": [
            "capture_failed_gate_evidence",
            "classify_failure_signature",
            "match_policy_cataloged_repair_class",
            "apply_bounded_low_risk_local_repair_when_allowed",
            "rerun_impacted_read_only_gates",
            "produce_repair_evidence",
            "stop_at_human_gated_boundaries",
        ],
        "parallel_readonly_gates_enabled": True,
        "parallel_execution_limited_to_readonly_gates": True,
        "read_only_gate_specs": gate_specs,
        "read_only_gate_results": gate_results,
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gates_passed": gates_passed,
        "max_parallel_workers": max_workers,
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
        "what_sits_between_generated_application_and_certification": WHAT_SITS_BETWEEN_APP_AND_CERTIFICATION,
        "supports_next_phase_goal": "autonomous_phase_discovery_and_planning",
    }
    return audit


def validate_autonomous_safe_repair_catalog_operator_loop(audit: JsonDict) -> list[str]:
    errors: list[str] = []
    if audit.get("schema_version") != SCHEMA_VERSION:
        errors.append("Unexpected schema version")
    if audit.get("status") != STATUS:
        errors.append("Unexpected Phase 14T status")
    if not audit.get("safe_repair_catalog_operator_loop_enabled"):
        errors.append("Safe-repair catalog operator loop is not enabled")
    if not audit.get("safe_repair_auto_apply_allowed_only_when_policy_cataloged"):
        errors.append("Safe repair auto-apply must be policy catalog bounded")
    if audit.get("unknown_failure_class_behavior") != "stop_and_require_human_review_or_new_policy":
        errors.append("Unknown failure classes must stop for review or policy")
    catalog = audit.get("safe_repair_catalog", [])
    if not isinstance(catalog, list) or len(catalog) < 10:
        errors.append("Safe repair catalog is incomplete")
    known = set(audit.get("safe_repair_classes_known", []))
    required = {
        "ruff_unused_variable_cleanup",
        "ruff_unused_import_cleanup",
        "mypy_validator_json_object_cast",
        "mypy_redundant_cast_cleanup",
        "generated_app_runtime_cache_cleanup",
        "ignored_workspace_audit_artifact_forced_staging",
    }
    missing = sorted(required - known)
    if missing:
        errors.append(f"Missing safe repair classes: {', '.join(missing)}")
    if not audit.get("parallel_execution_limited_to_readonly_gates"):
        errors.append("Parallel execution must be limited to read-only gates")
    if audit.get("auto_merge_performed") or audit.get("auto_tag_performed") or audit.get("auto_push_performed"):
        errors.append("Autonomous merge/tag/push must not be performed")
    if audit.get("live_provider_calls_performed") or audit.get("destructive_cleanup_performed"):
        errors.append("Live provider calls and destructive cleanup must not be performed")
    if audit.get("official_certification_claimed") or audit.get("official_certification_granted_by_factory"):
        errors.append("Factory must not claim or grant official certification")
    if audit.get("read_only_gates_executed") and not audit.get("read_only_gates_passed"):
        failing = [str(result.get("gate_id")) for result in audit.get("read_only_gate_results", []) if result.get("status") != "PASS"]
        errors.append(f"Failing read-only gates: {', '.join(failing)}")
    for path in (DOC_PATH, POLICY_PATH):
        if not (PROJECT_ROOT / path).exists():
            errors.append(f"Missing required artifact: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT_PATH)
    args = parser.parse_args()

    audit = build_autonomous_safe_repair_catalog_operator_loop(
        execute_readonly_gates=args.execute_readonly_gates,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout_seconds,
    )
    audit_path = PROJECT_ROOT / args.audit_out
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    errors = validate_autonomous_safe_repair_catalog_operator_loop(audit)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
