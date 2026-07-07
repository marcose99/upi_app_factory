from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE = "14V"
DOC_PATH = Path("docs/phase14v/autonomous_quality_gate_pipeline_hardening.md")
POLICY_PATH = Path("policies/phase14v_autonomous_quality_gate_pipeline_policy.json")
DEFAULT_AUDIT_PATH = Path(
    "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase14v/"
    "autonomous_quality_gate_pipeline_hardening_audit.json"
)

JsonDict = dict[str, Any]


@dataclass(frozen=True)
class GateSpec:
    gate_id: str
    command: list[str]
    read_only: bool
    parallel_safe: bool
    mutation_profile: str
    tier: str


def _python() -> str:
    return sys.executable


def read_only_gate_specs() -> list[GateSpec]:
    python = _python()
    return [
        GateSpec(
            gate_id="phase14u_artifact_validator",
            command=[python, "scripts/validate_phase14u_autonomous_phase_discovery.py"],
            read_only=True,
            parallel_safe=True,
            mutation_profile="tracked-state-read-only",
            tier="phase_artifact_validators",
        ),
        GateSpec(
            gate_id="phase14t_artifact_validator",
            command=[python, "scripts/validate_phase14t_autonomous_safe_repair_catalog_operator_loop.py"],
            read_only=True,
            parallel_safe=True,
            mutation_profile="tracked-state-read-only",
            tier="phase_artifact_validators",
        ),
        GateSpec(
            gate_id="phase14u_targeted_tests",
            command=[python, "-m", "pytest", "tests/test_phase14u_autonomous_phase_discovery.py"],
            read_only=True,
            parallel_safe=True,
            mutation_profile="tracked-state-read-only-after-phase14u-audit-fix",
            tier="targeted_tests",
        ),
        GateSpec(
            gate_id="ruff_static_hygiene",
            command=[python, "-m", "ruff", "check", "."],
            read_only=True,
            parallel_safe=True,
            mutation_profile="tracked-state-read-only",
            tier="static_hygiene",
        ),
        GateSpec(
            gate_id="mypy_static_typing",
            command=[python, "-m", "mypy", "."],
            read_only=True,
            parallel_safe=True,
            mutation_profile="tracked-state-read-only",
            tier="static_typing",
        ),
    ]


def _tail(value: str, limit: int = 4000) -> str:
    return value[-limit:]


def run_gate(spec: GateSpec, timeout_seconds: int) -> JsonDict:
    completed = subprocess.run(
        spec.command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "gate_id": spec.gate_id,
        "command": spec.command,
        "read_only": spec.read_only,
        "parallel_safe": spec.parallel_safe,
        "mutation_profile": spec.mutation_profile,
        "tier": spec.tier,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def execute_read_only_gates(max_workers: int, timeout_seconds: int) -> list[JsonDict]:
    specs = read_only_gate_specs()
    worker_count = max(1, min(max_workers, len(specs)))
    results: list[JsonDict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_spec = {
            executor.submit(run_gate, spec, timeout_seconds): spec for spec in specs
        }
        for future in concurrent.futures.as_completed(future_to_spec):
            results.append(future.result())
    return sorted(results, key=lambda item: str(item["gate_id"]))


def build_autonomous_quality_gate_pipeline_hardening(
    *,
    execute_gates: bool,
    max_workers: int,
    timeout_seconds: int,
) -> JsonDict:
    gate_specs = [asdict(spec) for spec in read_only_gate_specs()]
    gate_results = execute_read_only_gates(max_workers, timeout_seconds) if execute_gates else []
    gates_passed = bool(gate_results) and all(
        str(result.get("status")) == "PASS" for result in gate_results
    )
    return {
        "schema_version": "autonomous-quality-gate-pipeline-hardening.v1",
        "phase": PHASE,
        "mode": "governed_autonomous_quality_gate_pipeline_hardening",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "doc_path": str(DOC_PATH),
        "policy_path": str(POLICY_PATH),
        "quality_gate_pipeline_hardening_enabled": True,
        "parallel_readonly_gates_enabled": True,
        "parallel_execution_limited_to_readonly_gates": True,
        "read_only_gates_executed": execute_gates,
        "read_only_gates_passed": gates_passed if execute_gates else False,
        "read_only_gate_specs": gate_specs,
        "read_only_gate_results": gate_results,
        "full_regression_requires_clean_committed_tree": True,
        "audit_mutation_isolation_required": True,
        "targeted_tests_use_temporary_audit_outputs": True,
        "final_non_mutating_verification_only_after_final_audit_commit": True,
        "gate_tiers": [
            "syntax_compile",
            "phase_artifact_validators",
            "targeted_tests",
            "static_hygiene",
            "static_typing",
            "full_regression",
            "final_non_mutating_verification",
        ],
        "impacted_gate_rerun_required_after_repair": True,
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
        "supports_next_phase_goal": "generated_application_depth_roadmap_executor",
        "status": "AUTONOMOUS_QUALITY_GATE_PIPELINE_HARDENING_READY",
    }


def validate_autonomous_quality_gate_pipeline_hardening(audit: JsonDict) -> list[str]:
    errors: list[str] = []
    required_true = [
        "quality_gate_pipeline_hardening_enabled",
        "parallel_readonly_gates_enabled",
        "parallel_execution_limited_to_readonly_gates",
        "full_regression_requires_clean_committed_tree",
        "audit_mutation_isolation_required",
        "targeted_tests_use_temporary_audit_outputs",
        "final_non_mutating_verification_only_after_final_audit_commit",
        "safe_repair_catalog_operator_loop_enabled",
        "factory_does_not_self_certify",
        "certification_ready_not_certified_boundary_preserved",
    ]
    for key in required_true:
        if audit.get(key) is not True:
            errors.append(f"{key} must be true")
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
    for key in required_false:
        if audit.get(key) is not False:
            errors.append(f"{key} must be false")
    if audit.get("phase") != PHASE:
        errors.append("phase must be 14V")
    if not DOC_PATH.exists():
        errors.append(f"missing doc: {DOC_PATH}")
    if not POLICY_PATH.exists():
        errors.append(f"missing policy: {POLICY_PATH}")
    gate_tiers = audit.get("gate_tiers")
    if not isinstance(gate_tiers, list) or "full_regression" not in gate_tiers:
        errors.append("gate_tiers must include full_regression")
    gate_specs = audit.get("read_only_gate_specs")
    if not isinstance(gate_specs, list) or len(gate_specs) < 5:
        errors.append("expected at least five read-only gate specs")
    if audit.get("read_only_gates_executed") is True and audit.get("read_only_gates_passed") is not True:
        errors.append("read-only gates were executed but did not all pass")
    known_repairs = audit.get("safe_repair_classes_known")
    if not isinstance(known_repairs, list) or "legacy_drift_guardrail_clean_tree_regression" not in known_repairs:
        errors.append("legacy drift clean-tree repair class must be known")
    return errors


def write_audit(audit: JsonDict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_AUDIT_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    audit = build_autonomous_quality_gate_pipeline_hardening(
        execute_gates=bool(args.execute_readonly_gates),
        max_workers=int(args.max_workers),
        timeout_seconds=int(args.timeout_seconds),
    )
    write_audit(audit, args.audit_out)
    errors = validate_autonomous_quality_gate_pipeline_hardening(audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        failed_gates = [
            str(result.get("gate_id"))
            for result in audit.get("read_only_gate_results", [])
            if isinstance(result, dict) and result.get("status") != "PASS"
        ]
        if failed_gates:
            print("ERROR: Failing read-only gates: " + ", ".join(failed_gates), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
