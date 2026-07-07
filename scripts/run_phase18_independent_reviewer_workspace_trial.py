#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

PHASE = "18"
APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase18")


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
    pack_out = Path(cast(str, args.pack_out))
    checklist_out = Path(cast(str, args.checklist_out))
    gates: list[dict[str, Any]] = []
    if bool(args.execute_readonly_gates):
        gates = [
            run_gate([sys.executable, "scripts/validate_phase17_enterprise_autonomous_hardening.py"]),
            run_gate([sys.executable, "scripts/validate_phase16_self_contained_handoff_replay.py"]),
        ]

    pack = {
        "schema_version": "phase18-reviewer-workspace-pack.v1",
        "phase": PHASE,
        "app_id": APP_ID,
        "base_tag_required": "v0.17.0-enterprise-autonomous-hardening-batch",
        "reviewer_replay_commands": [
            "python -m pytest",
            "python scripts/validate_phase16_self_contained_handoff_replay.py",
            "python scripts/validate_phase17_enterprise_autonomous_hardening.py",
            "python scripts/validate_phase18_independent_reviewer_workspace_trial.py"
        ],
        "requires_external_provider": False,
        "requires_hidden_local_workspace_state": False,
        "requires_production_access": False,
    }
    checklist = {
        "schema_version": "phase18-independent-reviewer-checklist.v1",
        "phase": PHASE,
        "items": [
            "verify_repository_tag_and_commit",
            "run_local_dependency_install",
            "run_full_regression",
            "inspect_phase16_replay_evidence",
            "inspect_phase17_enterprise_hardening_evidence",
            "record_independent_findings",
            "do_not_treat_factory_output_as_certification"
        ],
    }
    audit = {
        "schema_version": "phase18-independent-reviewer-workspace-trial-audit.v1",
        "phase": PHASE,
        "app_id": APP_ID,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "INDEPENDENT_REVIEWER_WORKSPACE_TRIAL_READY",
        "factory_does_not_self_certify": True,
        "official_certification_claimed": False,
        "official_certification_granted_by_factory": False,
        "live_provider_calls_performed": False,
        "external_system_mutation_performed": False,
        "reviewer_pack_path": str(pack_out),
        "reviewer_checklist_path": str(checklist_out),
        "read_only_gates_executed": bool(args.execute_readonly_gates),
        "read_only_gates_passed": all(gate["returncode"] == 0 for gate in gates),
        "read_only_gate_results": gates,
    }
    write_json(pack_out, pack)
    write_json(checklist_out, checklist)
    write_json(audit_out, audit)
    return {"audit_path": str(audit_out), "status": audit["status"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 18 independent reviewer workspace evidence.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", default=str(ARTIFACT_DIR / "independent_reviewer_workspace_trial_audit.json"))
    parser.add_argument("--pack-out", default=str(ARTIFACT_DIR / "independent_reviewer_workspace_pack.json"))
    parser.add_argument("--checklist-out", default=str(ARTIFACT_DIR / "independent_reviewer_checklist.json"))
    return parser.parse_args()


def main() -> int:
    print(json.dumps(build(parse_args()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
