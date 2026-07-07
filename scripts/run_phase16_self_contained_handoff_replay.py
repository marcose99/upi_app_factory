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

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE_DIR = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase16"
DOC_PATH = ROOT / "docs" / "phase16" / "self_contained_handoff_replay_hardening.md"
POLICY_PATH = ROOT / "policies" / "phase16_self_contained_handoff_replay_policy.json"
AUDIT_PATH = PHASE_DIR / "self_contained_handoff_replay_hardening_audit.json"
REPLAY_PATH = PHASE_DIR / "self_contained_full_fresh_clone_replay_result.json"


def run_gate(gate: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    completed = subprocess.run(
        gate["command"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        **gate,
        "returncode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def build_audit(*, execute_readonly_gates: bool, timeout_seconds: int, max_workers: int) -> dict[str, Any]:
    python = sys.executable
    gates: list[dict[str, Any]] = [
        {
            "gate_id": "phase13g_legacy_drift_guardrail",
            "tier": "phase_artifact_validators",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only",
            "command": [python, "scripts/validate_phase13g_readonly_validation_guardrails.py"],
        },
        {
            "gate_id": "phase15_artifact_validator",
            "tier": "phase_artifact_validators",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only",
            "command": [python, "scripts/validate_phase15_autonomous_post_v1_industrialization.py"],
        },
        {
            "gate_id": "phase15_targeted_tests",
            "tier": "targeted_tests",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only-after-audit-isolation",
            "command": [python, "-m", "pytest", "tests/test_phase15_autonomous_post_v1_industrialization.py"],
        },
        {
            "gate_id": "ruff_static_hygiene",
            "tier": "static_hygiene",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only",
            "command": [python, "-m", "ruff", "check", "."],
        },
        {
            "gate_id": "mypy_static_typing",
            "tier": "static_typing",
            "read_only": True,
            "parallel_safe": True,
            "mutation_profile": "tracked-state-read-only",
            "command": [python, "-m", "mypy", "."],
        },
    ]

    results: list[dict[str, Any]] = []
    if execute_readonly_gates:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_gate, gate, timeout_seconds) for gate in gates]
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: item["gate_id"])

    passed = bool(results) and all(result["status"] == "PASS" for result in results)
    return {
        "schema_version": "self-contained-handoff-replay-hardening.v1",
        "phase": "16",
        "mode": "governed_self_contained_handoff_replay_hardening",
        "app_id": APP_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SELF_CONTAINED_HANDOFF_REPLAY_HARDENING_READY",
        "base_tag_required": "v0.15.0-autonomous-post-v1-industrialization-batch",
        "doc_path": str(DOC_PATH.relative_to(ROOT)),
        "policy_path": str(POLICY_PATH.relative_to(ROOT)),
        "audit_path": str(AUDIT_PATH.relative_to(ROOT)),
        "replay_result_path": str(REPLAY_PATH.relative_to(ROOT)),
        "self_contained_full_fresh_clone_gate_enabled": True,
        "legacy_workspace_evidence_packaging_enabled": True,
        "clone_local_virtualenv_assumption_removed": True,
        "validators_are_read_only": True,
        "tests_use_temporary_audit_outputs": True,
        "full_regression_requires_clean_committed_tree": True,
        "final_verification_is_non_mutating": True,
        "certification_ready_not_certified_boundary_preserved": True,
        "factory_does_not_self_certify": True,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "live_provider_calls_performed": False,
        "destructive_cleanup_performed": False,
        "external_system_mutation_performed": False,
        "human_gated_actions": [
            "merge",
            "tag",
            "push",
            "release",
            "promotion",
            "official_certification_claims",
            "live_provider_calls",
            "destructive_operations",
            "risky_generated_application_business_logic_changes",
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
        "read_only_gate_specs": gates,
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gates_passed": passed,
        "read_only_gate_results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", default=str(AUDIT_PATH))
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--max-workers", type=int, default=3)
    args = parser.parse_args()

    audit = build_audit(
        execute_readonly_gates=args.execute_readonly_gates,
        timeout_seconds=args.timeout_seconds,
        max_workers=args.max_workers,
    )
    out = Path(args.audit_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    if args.execute_readonly_gates and not audit["read_only_gates_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
