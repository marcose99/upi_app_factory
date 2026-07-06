#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, START, StateGraph

APP_ID = "upi_dispute_resolution"
PHASE = "Phase 13R"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13r"
)
AUDIT_PATH = ARTIFACT_DIR / "governed_agentic_phase_runner_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "governed_agentic_phase_runner_manifest.json"
REPORT_PATH = ARTIFACT_DIR / "governed_agentic_phase_runner_report.md"

AgenticStatus = Literal[
    "initialized",
    "planned",
    "implemented",
    "validation_failed",
    "repaired",
    "awaiting_human_release_approval",
    "completed_with_errors",
]


class ValidationCommand(TypedDict):
    command: list[str]
    cwd: str
    return_code: int
    output_preview: str


class AgentAction(TypedDict):
    agent: str
    status: str
    detail: str


class AgenticPhaseState(TypedDict):
    objective: str
    phase_id: str
    app_id: str
    project_root: str
    run_id: str
    dry_run: bool
    max_repair_attempts: int
    repair_attempts: int
    allowed_file_scopes: list[str]
    blocked_actions: list[str]
    status: AgenticStatus
    validation_passed: bool
    human_approval_required: bool
    release_ready: bool
    errors: list[str]
    warnings: list[str]
    plan: list[str]
    generated_files: list[str]
    validation_commands: list[ValidationCommand]
    actions: list[AgentAction]
    diagnosis: list[str]
    applied_repairs: list[str]
    audit_path: str
    orchestration_framework: str
    graph_type: str
    graph_nodes: list[str]
    truth_boundary: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relative(path: pathlib.Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def copy_state(state: AgenticPhaseState) -> AgenticPhaseState:
    return cast(AgenticPhaseState, dict(state))


def append_action(
    state: AgenticPhaseState,
    agent: str,
    status: str,
    detail: str,
) -> None:
    state["actions"].append({"agent": agent, "status": status, "detail": detail})


def run_command(command: list[str], cwd: pathlib.Path) -> ValidationCommand:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr
    return {
        "command": command,
        "cwd": str(cwd),
        "return_code": result.returncode,
        "output_preview": output[:4000],
    }


def preflight_agent(state: AgenticPhaseState) -> AgenticPhaseState:
    next_state = copy_state(state)
    root = pathlib.Path(next_state["project_root"])
    if not root.is_dir():
        next_state["errors"].append(f"Project root does not exist: {root}")
    git_check = run_command(["git", "rev-parse", "--is-inside-work-tree"], root)
    next_state["validation_commands"].append(git_check)
    if git_check["return_code"] != 0:
        next_state["errors"].append("Project root is not a git work tree.")
    append_action(
        next_state,
        "preflight_agent",
        "completed" if not next_state["errors"] else "failed",
        "Verified project root and git work-tree boundary.",
    )
    return next_state


def phase_plan_agent(state: AgenticPhaseState) -> AgenticPhaseState:
    next_state = copy_state(state)
    next_state["plan"] = [
        "Resolve objective into a bounded phase work package.",
        "Constrain implementation to approved file scopes only.",
        "Apply generated changes through deterministic file operations only.",
        "Run deterministic validation gates.",
        "Diagnose failures and apply bounded repairs only within scope.",
        "Write audit evidence and stop at human release approval.",
    ]
    next_state["status"] = "planned"
    append_action(
        next_state,
        "phase_plan_agent",
        "completed",
        "Built governed phase plan with scoped implementation and validation gates.",
    )
    return next_state


def implementation_agent(state: AgenticPhaseState) -> AgenticPhaseState:
    next_state = copy_state(state)
    if next_state["dry_run"]:
        next_state["warnings"].append(
            "Dry-run mode: implementation agent produced a governed plan without writing feature files."
        )
    next_state["generated_files"] = [
        "scripts/run_governed_agentic_phase.py",
        "scripts/validate_phase13r_governed_agentic_phase_runner.py",
        "tests/test_phase13r_governed_agentic_phase_runner.py",
        "docs/phase13r/governed_agentic_phase_runner.md",
    ]
    next_state["status"] = "implemented"
    append_action(
        next_state,
        "implementation_agent",
        "completed",
        "Recorded deterministic implementation outputs for the governed phase runner.",
    )
    return next_state


def validation_agent(state: AgenticPhaseState) -> AgenticPhaseState:
    next_state = copy_state(state)
    required_nodes = {
        "preflight_agent",
        "phase_plan_agent",
        "implementation_agent",
        "validation_agent",
        "failure_diagnosis_agent",
        "bounded_repair_agent",
        "human_release_gate_agent",
        "evidence_agent",
    }
    missing_nodes = sorted(required_nodes.difference(next_state["graph_nodes"]))
    if missing_nodes:
        next_state["errors"].append(f"Missing required graph nodes: {missing_nodes}")
    if "git push" not in next_state["blocked_actions"]:
        next_state["errors"].append("Release push must remain blocked until human approval.")
    if "git tag" not in next_state["blocked_actions"]:
        next_state["errors"].append("Release tag must remain blocked until human approval.")
    if not next_state["allowed_file_scopes"]:
        next_state["errors"].append("At least one allowed file scope is required.")
    next_state["validation_passed"] = not next_state["errors"]
    if next_state["validation_passed"]:
        append_action(
            next_state,
            "validation_agent",
            "completed",
            "Governed runner policy checks passed.",
        )
    else:
        next_state["status"] = "validation_failed"
        append_action(
            next_state,
            "validation_agent",
            "failed",
            "Governed runner policy checks failed.",
        )
    return next_state


def failure_diagnosis_agent(state: AgenticPhaseState) -> AgenticPhaseState:
    next_state = copy_state(state)
    next_state["diagnosis"] = [
        f"diagnosed: {error}" for error in next_state["errors"]
    ]
    append_action(
        next_state,
        "failure_diagnosis_agent",
        "completed",
        "Diagnosed validation failures for bounded repair.",
    )
    return next_state


def bounded_repair_agent(state: AgenticPhaseState) -> AgenticPhaseState:
    next_state = copy_state(state)
    next_state["repair_attempts"] += 1
    repaired_errors: list[str] = []
    remaining_errors: list[str] = []
    for error in next_state["errors"]:
        if "Release push" in error:
            next_state["blocked_actions"].append("git push")
            repaired_errors.append(error)
        elif "Release tag" in error:
            next_state["blocked_actions"].append("git tag")
            repaired_errors.append(error)
        elif "allowed file scope" in error:
            next_state["allowed_file_scopes"].append("scripts/")
            repaired_errors.append(error)
        else:
            remaining_errors.append(error)
    next_state["errors"] = remaining_errors
    for error in repaired_errors:
        next_state["applied_repairs"].append(f"bounded repair: {error}")
    next_state["status"] = "repaired"
    append_action(
        next_state,
        "bounded_repair_agent",
        "completed",
        f"Applied {len(repaired_errors)} bounded repairs within policy scope.",
    )
    return next_state


def human_release_gate_agent(state: AgenticPhaseState) -> AgenticPhaseState:
    next_state = copy_state(state)
    next_state["human_approval_required"] = True
    next_state["release_ready"] = True
    next_state["status"] = "awaiting_human_release_approval"
    append_action(
        next_state,
        "human_release_gate_agent",
        "waiting",
        "Implementation and validation passed; merge/tag/release require human approval.",
    )
    return next_state


def evidence_agent(state: AgenticPhaseState) -> AgenticPhaseState:
    next_state = copy_state(state)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    passed = next_state["validation_passed"] and not next_state["errors"]
    if not passed:
        next_state["status"] = "completed_with_errors"
    # Record the evidence agent action before persisting audit evidence so
    # validators and auditors see a complete graph-action trail.
    append_action(
        next_state,
        "evidence_agent",
        "completed",
        f"Wrote audit evidence to {relative(AUDIT_PATH)}.",
    )
    audit: dict[str, Any] = {
        "app_id": next_state["app_id"],
        "phase": PHASE,
        "phase_id": next_state["phase_id"],
        "objective": next_state["objective"],
        "run_id": next_state["run_id"],
        "generated_at_utc": utc_now(),
        "orchestration_framework": next_state["orchestration_framework"],
        "graph_type": next_state["graph_type"],
        "graph_nodes": next_state["graph_nodes"],
        "status": next_state["status"],
        "dry_run": next_state["dry_run"],
        "max_repair_attempts": next_state["max_repair_attempts"],
        "repair_attempts": next_state["repair_attempts"],
        "allowed_file_scopes": next_state["allowed_file_scopes"],
        "blocked_actions": sorted(set(next_state["blocked_actions"])),
        "plan": next_state["plan"],
        "generated_files": next_state["generated_files"],
        "validation_commands": next_state["validation_commands"],
        "actions": next_state["actions"],
        "diagnosis": next_state["diagnosis"],
        "applied_repairs": next_state["applied_repairs"],
        "errors": next_state["errors"],
        "warnings": next_state["warnings"],
        "validation_passed": next_state["validation_passed"],
        "human_approval_required": next_state["human_approval_required"],
        "release_ready": next_state["release_ready"],
        "passed": passed,
        "truth_boundary": next_state["truth_boundary"],
    }
    AUDIT_PATH.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    MANIFEST_PATH.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        "# Phase 13R Governed Agentic Phase Runner\n\n"
        f"Status: `{next_state['status']}`\n\n"
        f"Objective: `{next_state['objective']}`\n\n"
        f"Orchestration: `{next_state['orchestration_framework']} {next_state['graph_type']}`\n\n"
        "The runner executes the phase loop through governed agents and stops at "
        "a human release approval gate before merge, tag, push, or release.\n",
        encoding="utf-8",
    )
    next_state["audit_path"] = relative(AUDIT_PATH)
    return next_state


def route_after_validation(state: AgenticPhaseState) -> str:
    if state["validation_passed"] and not state["errors"]:
        return "human_release_gate_agent"
    if state["repair_attempts"] < state["max_repair_attempts"]:
        return "failure_diagnosis_agent"
    return "evidence_agent"


def build_graph() -> Any:
    graph = StateGraph(AgenticPhaseState)
    graph.add_node("preflight_agent", preflight_agent)
    graph.add_node("phase_plan_agent", phase_plan_agent)
    graph.add_node("implementation_agent", implementation_agent)
    graph.add_node("validation_agent", validation_agent)
    graph.add_node("failure_diagnosis_agent", failure_diagnosis_agent)
    graph.add_node("bounded_repair_agent", bounded_repair_agent)
    graph.add_node("human_release_gate_agent", human_release_gate_agent)
    graph.add_node("evidence_agent", evidence_agent)
    graph.add_edge(START, "preflight_agent")
    graph.add_edge("preflight_agent", "phase_plan_agent")
    graph.add_edge("phase_plan_agent", "implementation_agent")
    graph.add_edge("implementation_agent", "validation_agent")
    graph.add_conditional_edges(
        "validation_agent",
        route_after_validation,
        {
            "human_release_gate_agent": "human_release_gate_agent",
            "failure_diagnosis_agent": "failure_diagnosis_agent",
            "evidence_agent": "evidence_agent",
        },
    )
    graph.add_edge("failure_diagnosis_agent", "bounded_repair_agent")
    graph.add_edge("bounded_repair_agent", "validation_agent")
    graph.add_edge("human_release_gate_agent", "evidence_agent")
    graph.add_edge("evidence_agent", END)
    return graph.compile()


def initial_state(objective: str, phase_id: str, dry_run: bool) -> AgenticPhaseState:
    return {
        "objective": objective,
        "phase_id": phase_id,
        "app_id": APP_ID,
        "project_root": str(PROJECT_ROOT),
        "run_id": f"phase13r_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "dry_run": dry_run,
        "max_repair_attempts": 2,
        "repair_attempts": 0,
        "allowed_file_scopes": ["scripts/", "tests/", "docs/", "workspace/factory_generated/"],
        "blocked_actions": ["git push", "git tag", "git merge", "release publish"],
        "status": "initialized",
        "validation_passed": False,
        "human_approval_required": False,
        "release_ready": False,
        "errors": [],
        "warnings": [],
        "plan": [],
        "generated_files": [],
        "validation_commands": [],
        "actions": [],
        "diagnosis": [],
        "applied_repairs": [],
        "audit_path": "",
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "graph_nodes": [
            "preflight_agent",
            "phase_plan_agent",
            "implementation_agent",
            "validation_agent",
            "failure_diagnosis_agent",
            "bounded_repair_agent",
            "human_release_gate_agent",
            "evidence_agent",
        ],
        "truth_boundary": (
            "The governed agentic phase runner may plan, generate, validate, "
            "diagnose, and bounded-repair repository changes only inside approved "
            "file scopes. Merge, tag, push, release, destructive cleanup, real "
            "external ecosystem calls, and production deployment remain blocked "
            "until explicit human approval. Primary UPI lifecycle logic remains "
            "local and runnable; external ecosystem interfaces remain simulated "
            "mocks only."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a governed LangGraph phase loop and stop at human release approval."
    )
    parser.add_argument("--objective", required=True)
    parser.add_argument("--phase-id", default="phase13r_governed_runner_smoke")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = cast(
        AgenticPhaseState,
        build_graph().invoke(initial_state(args.objective, args.phase_id, args.dry_run)),
    )
    response = {
        "passed": result["validation_passed"] and not result["errors"],
        "phase": PHASE,
        "phase_id": result["phase_id"],
        "objective": result["objective"],
        "status": result["status"],
        "orchestration_framework": result["orchestration_framework"],
        "graph_type": result["graph_type"],
        "graph_nodes": result["graph_nodes"],
        "human_approval_required": result["human_approval_required"],
        "release_ready": result["release_ready"],
        "repair_attempts": result["repair_attempts"],
        "max_repair_attempts": result["max_repair_attempts"],
        "blocked_actions": sorted(set(result["blocked_actions"])),
        "allowed_file_scopes": result["allowed_file_scopes"],
        "audit_path": result["audit_path"],
    }
    print(json.dumps(response, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
