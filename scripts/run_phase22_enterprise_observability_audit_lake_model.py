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
DEFAULT_PHASE_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase22"


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


def build_event_taxonomy() -> dict[str, Any]:
    return {
        "schema_version": "phase22-observability-event-taxonomy.v1",
        "event_classes": [
            "requirement_intake",
            "policy_decision",
            "agent_plan",
            "tool_execution",
            "validation_gate",
            "self_healing_attempt",
            "human_approval_boundary",
            "release_evidence",
            "certification_boundary",
        ],
        "pii_allowed": False,
        "secret_values_allowed": False,
    }


def build_audit_lake_model() -> dict[str, Any]:
    return {
        "schema_version": "phase22-audit-lake-model.v1",
        "external_audit_lake_mutation_performed": False,
        "local_evidence_only": True,
        "suggested_partitions": ["app_id", "phase", "run_id", "event_date", "event_class"],
        "retention_classes": ["development", "audit", "release", "certification_review"],
    }


def build_retention_model() -> dict[str, Any]:
    return {
        "schema_version": "phase22-telemetry-retention-model.v1",
        "production_retention_activation_is_human_gated": True,
        "local_replay_evidence_retained_in_repo": True,
        "external_retention_policy_activated": False,
    }


def build_audit(execute_readonly_gates: bool) -> dict[str, Any]:
    gates: list[dict[str, Any]] = []
    if execute_readonly_gates:
        gates = [
            run_gate("phase21_secrets_identity_validator", [sys.executable, "scripts/validate_phase21_secrets_identity_governance.py"]),
            run_gate("phase20_environment_promotion_validator", [sys.executable, "scripts/validate_phase20_environment_promotion_governance.py"]),
        ]
    return {
        "schema_version": "phase22-enterprise-observability-audit-lake-audit.v1",
        "phase": "22",
        "app_id": APP_ID,
        "created_at_utc": utc_now(),
        "status": "ENTERPRISE_OBSERVABILITY_AUDIT_LAKE_MODEL_READY",
        "read_only_gates_executed": execute_readonly_gates,
        "read_only_gates_passed": all(gate["status"] == "PASS" for gate in gates),
        "read_only_gate_results": gates,
        "certification_ready_not_certified_boundary_preserved": True,
        "official_certification_claimed": False,
        "external_telemetry_published": False,
        "external_audit_lake_mutation_performed": False,
        "pii_in_observability_allowed": False,
        "secret_values_in_observability_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 22 enterprise observability and audit-lake evidence generation.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", type=Path, default=DEFAULT_PHASE_DIR / "enterprise_observability_audit_lake_audit.json")
    parser.add_argument("--taxonomy-out", type=Path, default=DEFAULT_PHASE_DIR / "observability_event_taxonomy.json")
    parser.add_argument("--lake-out", type=Path, default=DEFAULT_PHASE_DIR / "audit_lake_model.json")
    parser.add_argument("--retention-out", type=Path, default=DEFAULT_PHASE_DIR / "telemetry_retention_model.json")
    args = parser.parse_args()

    write_json(args.taxonomy_out, build_event_taxonomy())
    write_json(args.lake_out, build_audit_lake_model())
    write_json(args.retention_out, build_retention_model())
    audit = build_audit(args.execute_readonly_gates)
    write_json(args.audit_out, audit)
    print(json.dumps({"audit_path": str(args.audit_out), "status": audit["status"]}, indent=2, sort_keys=True))
    return 0 if audit["read_only_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
