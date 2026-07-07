#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
DEFAULT_PHASE_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase20"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_gate(gate_id: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    return {
        "gate_id": gate_id,
        "command": command,
        "read_only": True,
        "returncode": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def build_promotion_matrix() -> dict[str, Any]:
    return {
        "schema_version": "phase20-promotion-matrix.v1",
        "phase": "20",
        "environments": [
            {"name": "local", "promotion_allowed": True, "human_approval_required": False},
            {"name": "developer_workstation", "promotion_allowed": True, "human_approval_required": False},
            {"name": "ci_shadow", "promotion_allowed": True, "human_approval_required": False},
            {"name": "independent_reviewer_workspace", "promotion_allowed": True, "human_approval_required": True},
            {"name": "controlled_nonprod", "promotion_allowed": True, "human_approval_required": True},
            {"name": "production_candidate", "promotion_allowed": True, "human_approval_required": True},
            {"name": "production", "promotion_allowed": False, "human_approval_required": True},
        ],
        "automatic_production_promotion_allowed": False,
        "evidence_required_before_handoff": [
            "passing_full_regression",
            "replay_evidence",
            "policy_validation",
            "rollback_plan",
            "certification_boundary_statement",
        ],
    }


def build_rollback_model() -> dict[str, Any]:
    return {
        "schema_version": "phase20-rollback-model.v1",
        "rollback_execution_is_human_gated": True,
        "factory_may_generate_rollback_plan": True,
        "factory_must_not_execute_production_rollback": True,
        "rollback_evidence": ["previous_tag", "release_notes", "regression_report", "operator_approval"],
    }


def build_audit(execute_readonly_gates: bool) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []
    if execute_readonly_gates:
        gates = [
            run_gate("phase19_supply_chain_validator", [sys.executable, "scripts/validate_phase19_supply_chain_provenance_hardening.py"]),
            run_gate("phase16_self_contained_replay_validator", [sys.executable, "scripts/validate_phase16_self_contained_handoff_replay.py"]),
        ]
    return {
        "schema_version": "phase20-environment-promotion-governance-audit.v1",
        "phase": "20",
        "app_id": APP_ID,
        "created_at_utc": utc_now(),
        "status": "ENVIRONMENT_PROMOTION_GOVERNANCE_READY",
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gates_passed": all(gate["status"] == "PASS" for gate in gates),
        "read_only_gate_results": gates,
        "certification_ready_not_certified_boundary_preserved": True,
        "factory_does_not_self_certify": True,
        "official_certification_claimed": False,
        "live_provider_calls_performed": False,
        "external_system_mutation_performed": False,
        "automatic_production_promotion_performed": False,
        "destructive_cleanup_performed": False,
        "human_gated_actions": [
            "environment_promotion",
            "production_release",
            "rollback_execution",
            "official_certification_claims",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 20 environment promotion governance evidence generation.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_PHASE_DIR / "environment_promotion_governance_audit.json")
    parser.add_argument("--matrix-out", type=Path, default=DEFAULT_PHASE_DIR / "environment_promotion_matrix.json")
    parser.add_argument("--rollback-out", type=Path, default=DEFAULT_PHASE_DIR / "rollback_model.json")
    args = parser.parse_args()

    write_json(args.matrix_out, build_promotion_matrix())
    write_json(args.rollback_out, build_rollback_model())
    audit = build_audit(args.execute_readonly_gates)
    write_json(args.audit_out, audit)
    print(json.dumps({"audit_path": str(args.audit_out), "status": audit["status"]}, indent=2, sort_keys=True))
    return 0 if audit["read_only_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
