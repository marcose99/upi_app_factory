#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13n"
)
AUDIT_PATH = ARTIFACT_DIR / "langgraph_factory_self_repair_supervisor_audit.json"
TARGET_PATH = ARTIFACT_DIR / "self_repair_target.md"
REQUIRED_BOUNDARY = "external ecosystem interfaces are simulated mocks only"


def load_audit() -> dict[str, Any]:
    if not AUDIT_PATH.is_file():
        raise AssertionError(f"Missing audit artifact: {AUDIT_PATH}")
    payload = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("Audit payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def validate_target() -> None:
    if not TARGET_PATH.is_file():
        raise AssertionError(f"Missing repair target: {TARGET_PATH}")
    content = TARGET_PATH.read_text(encoding="utf-8")
    if REQUIRED_BOUNDARY not in content:
        raise AssertionError("Repair target was not corrected with mock-boundary wording.")


def validate_audit(audit: dict[str, Any]) -> None:
    if audit.get("phase") != "Phase 13N":
        raise AssertionError("Audit phase is not Phase 13N.")
    if audit.get("orchestration_framework") != "langgraph":
        raise AssertionError("Audit does not record LangGraph orchestration.")
    if audit.get("graph_type") != "StateGraph":
        raise AssertionError("Audit does not record StateGraph graph type.")
    if audit.get("repair_applied") is not True:
        raise AssertionError("Supervisor did not apply a bounded repair.")
    if audit.get("final_validation_passed") is not True:
        raise AssertionError("Supervisor final validation did not pass.")
    attempts = audit.get("attempts_used")
    if not isinstance(attempts, int) or attempts < 1 or attempts > 2:
        raise AssertionError("Supervisor attempts_used must be between 1 and 2.")
    conditional_edges = audit.get("conditional_edges", [])
    if not any("diagnose_agent" in str(edge) for edge in conditional_edges):
        raise AssertionError("Audit does not capture diagnose route.")
    if not any("repair_agent" in str(edge) for edge in conditional_edges):
        raise AssertionError("Audit does not capture repair route.")
    steps = audit.get("steps", [])
    step_nodes = [str(step.get("node")) for step in steps if isinstance(step, dict)]
    for required_node in ["plan_agent", "validate_agent", "diagnose_agent", "repair_agent", "proof_gate_agent", "governance_evidence_agent"]:
        if required_node not in step_nodes:
            raise AssertionError(f"Missing supervisor step: {required_node}")
    command_results = audit.get("command_results", [])
    if not isinstance(command_results, list) or len(command_results) < 2:
        raise AssertionError("Expected Phase 13M proof command results.")
    for result in command_results:
        if not isinstance(result, dict) or result.get("return_code") != 0:
            raise AssertionError("One or more proof commands failed.")


def main() -> None:
    audit = load_audit()
    validate_target()
    validate_audit(audit)
    result = {
        "passed": True,
        "phase": "Phase 13N",
        "orchestration_framework": audit.get("orchestration_framework"),
        "graph_type": audit.get("graph_type"),
        "repair_applied": audit.get("repair_applied"),
        "attempts_used": audit.get("attempts_used"),
        "final_validation_passed": audit.get("final_validation_passed"),
        "audit_path": str(AUDIT_PATH),
        "target_path": str(TARGET_PATH),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
