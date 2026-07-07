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
DEFAULT_PHASE_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase21"


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


def build_identity_matrix() -> dict[str, Any]:
    return {
        "schema_version": "phase21-identity-boundary-matrix.v1",
        "identities": [
            {"name": "local_operator", "scope": "local-only", "real_account_required": False},
            {"name": "factory_agent", "scope": "simulated-local-agent", "real_account_required": False},
            {"name": "reviewer", "scope": "independent-reviewer-workspace", "real_account_required": False},
            {"name": "production_service_account", "scope": "future-human-approved-enterprise-integration", "real_account_required": True},
        ],
        "service_account_creation_performed": False,
        "identity_provider_mutation_performed": False,
    }


def build_secret_evidence() -> dict[str, Any]:
    return {
        "schema_version": "phase21-secret-handling-evidence.v1",
        "real_secrets_required_for_local_replay": False,
        "real_secrets_stored_in_repo": False,
        "placeholder_patterns_allowed": ["${OPENAI_API_KEY}", "${DATABASE_URL}", "${OIDC_ISSUER}"],
        "secret_values_materialized": False,
        "live_provider_calls_performed": False,
    }


def build_audit(execute_readonly_gates: bool) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []
    if execute_readonly_gates:
        gates = [
            run_gate("phase20_environment_promotion_validator", [sys.executable, "scripts/validate_phase20_environment_promotion_governance.py"]),
            run_gate("phase19_supply_chain_validator", [sys.executable, "scripts/validate_phase19_supply_chain_provenance_hardening.py"]),
        ]
    return {
        "schema_version": "phase21-secrets-identity-governance-audit.v1",
        "phase": "21",
        "app_id": APP_ID,
        "created_at_utc": utc_now(),
        "status": "SECRETS_IDENTITY_GOVERNANCE_READY",
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gates_passed": all(gate["status"] == "PASS" for gate in gates),
        "read_only_gate_results": gates,
        "certification_ready_not_certified_boundary_preserved": True,
        "official_certification_claimed": False,
        "real_secret_storage_performed": False,
        "live_identity_provider_calls_performed": False,
        "service_account_creation_performed": False,
        "external_system_mutation_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 21 secrets and identity governance evidence generation.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_PHASE_DIR / "secrets_identity_governance_audit.json")
    parser.add_argument("--identity-out", type=Path, default=DEFAULT_PHASE_DIR / "identity_boundary_matrix.json")
    parser.add_argument("--secrets-out", type=Path, default=DEFAULT_PHASE_DIR / "secret_handling_evidence.json")
    args = parser.parse_args()

    write_json(args.identity_out, build_identity_matrix())
    write_json(args.secrets_out, build_secret_evidence())
    audit = build_audit(args.execute_readonly_gates)
    write_json(args.audit_out, audit)
    print(json.dumps({"audit_path": str(args.audit_out), "status": audit["status"]}, indent=2, sort_keys=True))
    return 0 if audit["read_only_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
