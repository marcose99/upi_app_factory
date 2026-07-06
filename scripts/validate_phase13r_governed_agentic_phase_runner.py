#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
from typing import Any, cast

APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13r"
    / "governed_agentic_phase_runner_audit.json"
)
REQUIRED_NODES = {
    "preflight_agent",
    "phase_plan_agent",
    "implementation_agent",
    "validation_agent",
    "failure_diagnosis_agent",
    "bounded_repair_agent",
    "human_release_gate_agent",
    "evidence_agent",
}
REQUIRED_BLOCKED_ACTIONS = {"git push", "git tag", "git merge", "release publish"}


def load_audit() -> dict[str, Any]:
    if not AUDIT_PATH.is_file():
        raise AssertionError(f"Missing audit artifact: {AUDIT_PATH}")
    payload = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("Audit payload must be a JSON object.")
    return cast(dict[str, Any], payload)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_audit(audit: dict[str, Any]) -> None:
    require(audit.get("phase") == "Phase 13R", "Audit phase must be Phase 13R.")
    require(audit.get("passed") is True, "Phase 13R runner audit must pass.")
    require(
        audit.get("orchestration_framework") == "langgraph",
        "Runner must use LangGraph.",
    )
    require(audit.get("graph_type") == "StateGraph", "Runner must use StateGraph.")
    graph_nodes = set(cast(list[str], audit.get("graph_nodes", [])))
    require(
        REQUIRED_NODES.issubset(graph_nodes),
        f"Runner is missing required graph nodes: {sorted(REQUIRED_NODES - graph_nodes)}",
    )
    blocked_actions = set(cast(list[str], audit.get("blocked_actions", [])))
    require(
        REQUIRED_BLOCKED_ACTIONS.issubset(blocked_actions),
        "Runner must block merge/tag/push/release until human approval.",
    )
    require(
        audit.get("human_approval_required") is True,
        "Runner must stop at human release approval gate.",
    )
    require(audit.get("release_ready") is True, "Runner should be release-ready after gates.")
    require(audit.get("validation_passed") is True, "Runner validation must pass.")
    require(audit.get("max_repair_attempts") == 2, "Runner must have bounded repair attempts.")
    actions = audit.get("actions", [])
    require(isinstance(actions, list) and len(actions) >= 6, "Runner must record agent actions.")
    action_agents = [str(action.get("agent")) for action in actions if isinstance(action, dict)]
    require("evidence_agent" in action_agents, "Persisted audit must include evidence_agent action.")
    truth_boundary = str(audit.get("truth_boundary", ""))
    require("human approval" in truth_boundary, "Truth boundary must mention human approval.")
    require("simulated mocks only" in truth_boundary, "Truth boundary must preserve mock ecosystem boundary.")


def main() -> None:
    audit = load_audit()
    validate_audit(audit)
    result = {
        "passed": True,
        "phase": "Phase 13R",
        "orchestration_framework": audit.get("orchestration_framework"),
        "graph_type": audit.get("graph_type"),
        "graph_nodes": audit.get("graph_nodes"),
        "status": audit.get("status"),
        "human_approval_required": audit.get("human_approval_required"),
        "release_ready": audit.get("release_ready"),
        "max_repair_attempts": audit.get("max_repair_attempts"),
        "blocked_actions": audit.get("blocked_actions"),
        "audit_path": str(AUDIT_PATH),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
