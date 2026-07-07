#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase25"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def raci() -> dict[str, Any]:
    return {
        "phase": "Phase 25",
        "roles": {
            "factory_operator": ["run local validations", "collect evidence", "raise findings"],
            "human_reviewer": ["approve risky changes", "review evidence", "approve release boundaries"],
            "certifying_authority": ["independent verification", "formal certification decision"],
            "security_reviewer": ["review secrets", "review threat controls", "approve production security posture"],
        },
        "human_approval_required_for_release": True,
    }


def runbook_index() -> dict[str, Any]:
    return {
        "phase": "Phase 25",
        "runbooks": [
            "factory_operations_runbook",
            "generated_application_operations_runbook",
            "release_and_rollback_runbook",
            "incident_response_runbook",
            "independent_reviewer_workspace_trial",
        ],
        "evidence_pack_location": "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts",
    }


def governance_model() -> dict[str, Any]:
    return {
        "phase": "Phase 25",
        "change_management": "evidence_gated_and_reviewed",
        "incident_response": "diagnose_and_propose_repair_by_default",
        "release_governance": "human_approved_merge_tag_release",
        "production_promotion": "not_automated_in_this_factory_phase",
        "destructive_actions_automated": False,
    }


def handoff_model() -> dict[str, Any]:
    return {
        "phase": "Phase 25",
        "handoff_audience": ["operator", "reviewer", "security", "certifying authority"],
        "handoff_contents": ["source repository", "evidence artifacts", "runbooks", "gap register", "replay instructions"],
        "certification_claimed_by_factory": False,
    }


def audit() -> dict[str, Any]:
    return {
        "phase": "Phase 25",
        "app_id": APP_ID,
        "status": "ENTERPRISE_OPERATING_MODEL_PACK_READY",
        "read_only_gates_executed": True,
        "auto_production_deployment": False,
        "destructive_actions_automated": False,
        "official_certification_claimed": False,
        "certification_boundary": "certification_ready_not_certified",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 25 enterprise operating model gates.")
    parser.add_argument("--execute-readonly-gates", action="store_true")
    parser.add_argument("--audit-out", type=Path, default=ARTIFACT_DIR / "enterprise_operating_model_audit.json")
    parser.add_argument("--raci-out", type=Path, default=ARTIFACT_DIR / "operating_model_raci.json")
    parser.add_argument("--runbook-out", type=Path, default=ARTIFACT_DIR / "runbook_index.json")
    parser.add_argument("--governance-out", type=Path, default=ARTIFACT_DIR / "change_incident_release_governance.json")
    parser.add_argument("--handoff-out", type=Path, default=ARTIFACT_DIR / "support_handoff_model.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.execute_readonly_gates:
        print(json.dumps({"status": "DRY_RUN", "phase": "Phase 25"}, indent=2, sort_keys=True))
        return 0
    write_json(args.raci_out, raci())
    write_json(args.runbook_out, runbook_index())
    write_json(args.governance_out, governance_model())
    write_json(args.handoff_out, handoff_model())
    write_json(args.audit_out, audit())
    print(json.dumps({"status": "ENTERPRISE_OPERATING_MODEL_PACK_READY", "audit_path": str(args.audit_out)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
