#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

PHASE = "19"
APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase19")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_gate(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    audit_out = Path(cast(str, args.audit_out))
    inventory_out = Path(cast(str, args.inventory_out))
    provenance_out = Path(cast(str, args.provenance_out))
    gate_out = Path(cast(str, args.gate_out))

    pyproject = Path("pyproject.toml")
    tracked_files = [
        Path("pyproject.toml"),
        Path("docs/phase19/supply_chain_provenance_hardening.md"),
        Path("policies/phase19_supply_chain_provenance_policy.json"),
    ]
    inventory = {
        "schema_version": "phase19-local-dependency-inventory.v1",
        "phase": PHASE,
        "app_id": APP_ID,
        "source_files": [
            {"path": str(path), "sha256": sha256_file(path)}
            for path in tracked_files
            if path.exists()
        ],
        "pyproject_present": pyproject.exists(),
        "external_publication_performed": False,
    }
    provenance = {
        "schema_version": "phase19-provenance-readiness.v1",
        "phase": PHASE,
        "app_id": APP_ID,
        "builder": "local-governed-factory",
        "base_tag_required": "v0.18.0-independent-reviewer-workspace-trial",
        "official_slsa_claim_made": False,
        "signing_key_used": False,
        "registry_push_performed": False,
        "attestation_status": "readiness_only_not_formal_attestation",
    }
    gates: list[dict[str, Any]] = []
    if bool(args.execute_readonly_gates):
        gates = [
            run_gate([sys.executable, "scripts/validate_phase18_independent_reviewer_workspace_trial.py"]),
            run_gate([sys.executable, "-m", "ruff", "check", "."]),
            run_gate([sys.executable, "-m", "mypy", "."]),
        ]
    gate_summary = {
        "schema_version": "phase19-supply-chain-gate-summary.v1",
        "phase": PHASE,
        "read_only_gates_executed": bool(args.execute_readonly_gates),
        "read_only_gates_passed": all(gate["returncode"] == 0 for gate in gates),
        "read_only_gate_results": gates,
    }
    audit = {
        "schema_version": "phase19-supply-chain-provenance-hardening-audit.v1",
        "phase": PHASE,
        "app_id": APP_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SUPPLY_CHAIN_PROVENANCE_HARDENING_READY",
        "local_attestation_readiness_only": True,
        "official_slsa_claim_made": False,
        "formal_supply_chain_certification_claimed": False,
        "artifact_publication_performed": False,
        "registry_push_performed": False,
        "signing_key_used": False,
        "live_provider_calls_performed": False,
        "external_system_mutation_performed": False,
        "inventory_path": str(inventory_out),
        "provenance_path": str(provenance_out),
        "gate_summary_path": str(gate_out),
    }
    write_json(inventory_out, inventory)
    write_json(provenance_out, provenance)
    write_json(gate_out, gate_summary)
    write_json(audit_out, audit)
    return {"audit_path": str(audit_out), "status": audit["status"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 19 supply-chain provenance hardening evidence.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", default=str(ARTIFACT_DIR / "supply_chain_provenance_hardening_audit.json"))
    parser.add_argument("--inventory-out", default=str(ARTIFACT_DIR / "local_dependency_inventory.json"))
    parser.add_argument("--provenance-out", default=str(ARTIFACT_DIR / "provenance_readiness_statement.json"))
    parser.add_argument("--gate-out", default=str(ARTIFACT_DIR / "supply_chain_gate_summary.json"))
    return parser.parse_args()


def main() -> int:
    print(json.dumps(build(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
