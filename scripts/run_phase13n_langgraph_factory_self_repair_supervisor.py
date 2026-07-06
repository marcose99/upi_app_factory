#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

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
TARGET_PATH = ARTIFACT_DIR / "self_repair_target.md"
AUDIT_PATH = ARTIFACT_DIR / "langgraph_factory_self_repair_supervisor_audit.json"
REPORT_PATH = ARTIFACT_DIR / "langgraph_factory_self_repair_supervisor_report.md"
REQUIRED_BOUNDARY = "external ecosystem interfaces are simulated mocks only"
MAX_ATTEMPTS = 2


class RepairStep(TypedDict):
    node: str
    status: str
    detail: str


class CommandResult(TypedDict):
    command: list[str]
    return_code: int
    output_preview: str


class SupervisorState(TypedDict, total=False):
    run_id: str
    attempt: int
    max_attempts: int
    target_path: str
    validation_passed: bool
    validation_errors: list[str]
    repair_applied: bool
    steps: list[RepairStep]
    command_results: list[CommandResult]
    audit: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relative(path: pathlib.Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def add_step(state: SupervisorState, node: str, status: str, detail: str) -> list[RepairStep]:
    steps = list(state.get("steps", []))
    steps.append({"node": node, "status": status, "detail": detail})
    return steps


def run_command(command: list[str]) -> CommandResult:
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(
        [
            str(PROJECT_ROOT / "src"),
            str(PROJECT_ROOT / "scripts"),
            str(PROJECT_ROOT),
            env.get("PYTHONPATH", ""),
        ]
    )
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (result.stdout + result.stderr)[:4000]
    return {"command": command, "return_code": result.returncode, "output_preview": output}


def plan_agent(state: SupervisorState) -> SupervisorState:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    TARGET_PATH.write_text(
        "# Phase 13N self-repair target\n\n"
        "This intentionally incomplete artifact is created by the supervisor to prove "
        "that the factory can diagnose a failed governance check, apply a bounded "
        "repair, and rerun validation without manual patching.\n\n"
        "Primary generated UPI dispute logic is local and runnable.\n",
        encoding="utf-8",
    )
    return {
        **state,
        "attempt": 0,
        "max_attempts": MAX_ATTEMPTS,
        "target_path": relative(TARGET_PATH),
        "repair_applied": False,
        "steps": add_step(
            state,
            "plan_agent",
            "completed",
            "Created intentionally incomplete governance artifact for bounded repair.",
        ),
    }


def validate_agent(state: SupervisorState) -> SupervisorState:
    content = TARGET_PATH.read_text(encoding="utf-8")
    errors: list[str] = []
    if REQUIRED_BOUNDARY not in content:
        errors.append("missing_required_mock_boundary_statement")
    passed = not errors
    return {
        **state,
        "validation_passed": passed,
        "validation_errors": errors,
        "steps": add_step(
            state,
            "validate_agent",
            "passed" if passed else "failed",
            "Governance target validation passed."
            if passed
            else ",".join(errors),
        ),
    }


def route_after_validation(state: SupervisorState) -> str:
    if state.get("validation_passed") is True:
        return "proof_gate_agent"
    if int(state.get("attempt", 0)) < int(state.get("max_attempts", MAX_ATTEMPTS)):
        return "diagnose_agent"
    return "governance_evidence_agent"


def diagnose_agent(state: SupervisorState) -> SupervisorState:
    errors = ",".join(state.get("validation_errors", []))
    return {
        **state,
        "steps": add_step(
            state,
            "diagnose_agent",
            "completed",
            f"Diagnosed bounded repair requirement: {errors}",
        ),
    }


def repair_agent(state: SupervisorState) -> SupervisorState:
    attempt = int(state.get("attempt", 0)) + 1
    content = TARGET_PATH.read_text(encoding="utf-8")
    if REQUIRED_BOUNDARY not in content:
        content += "\nGovernance boundary: external ecosystem interfaces are simulated mocks only.\n"
        TARGET_PATH.write_text(content, encoding="utf-8")
    return {
        **state,
        "attempt": attempt,
        "repair_applied": True,
        "steps": add_step(
            state,
            "repair_agent",
            "completed",
            f"Applied bounded repair attempt {attempt} of {MAX_ATTEMPTS}.",
        ),
    }


def proof_gate_agent(state: SupervisorState) -> SupervisorState:
    commands = [
        [sys.executable, "scripts/run_phase13m_langgraph_agentic_lifecycle_generation.py", "--quiet"],
        [sys.executable, "scripts/validate_phase13m_langgraph_agentic_lifecycle_generation.py"],
    ]
    results = [run_command(command) for command in commands]
    passed = all(result["return_code"] == 0 for result in results)
    return {
        **state,
        "command_results": results,
        "validation_passed": passed,
        "steps": add_step(
            state,
            "proof_gate_agent",
            "passed" if passed else "failed",
            "Phase 13M generator and validator proof commands passed."
            if passed
            else "One or more proof commands failed.",
        ),
    }


def governance_evidence_agent(state: SupervisorState) -> SupervisorState:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    steps = add_step(
        state,
        "governance_evidence_agent",
        "completed",
        "Governance evidence audit and report written after bounded repair proof.",
    )
    audit: dict[str, Any] = {
        "app_id": APP_ID,
        "phase": "Phase 13N",
        "run_id": state["run_id"],
        "generated_at_utc": utc_now(),
        "orchestration_framework": "langgraph",
        "graph_type": "StateGraph",
        "adapter_mode": "local_langgraph_deterministic",
        "purpose": "factory_supervisor_bounded_self_repair",
        "graph_nodes": [
            "plan_agent",
            "validate_agent",
            "diagnose_agent",
            "repair_agent",
            "proof_gate_agent",
            "governance_evidence_agent",
        ],
        "conditional_edges": [
            "validate_agent -> proof_gate_agent when validation passes",
            "validate_agent -> diagnose_agent when validation fails and attempts remain",
            "diagnose_agent -> repair_agent -> validate_agent",
        ],
        "target_path": state.get("target_path"),
        "max_attempts": state.get("max_attempts"),
        "attempts_used": state.get("attempt"),
        "repair_applied": state.get("repair_applied") is True,
        "final_validation_passed": state.get("validation_passed") is True,
        "validation_errors": state.get("validation_errors", []),
        "steps": steps,
        "command_results": state.get("command_results", []),
        "truth_boundary": (
            "Primary generated UPI dispute logic remains local and runnable; "
            "external banks, rails, NPCI-style, RBI-style, upstream, and "
            "downstream interfaces remain simulated mocks only."
        ),
    }
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "# Phase 13N LangGraph Factory Self-Repair Supervisor\n\n"
        "Status: `completed`\n\n"
        f"Run ID: `{state['run_id']}`\n\n"
        "This phase proves the factory can run a bounded LangGraph diagnose/repair/"
        "retry loop instead of relying on manual one-off repair scripts.\n\n"
        f"Repair applied: `{audit['repair_applied']}`\n\n"
        f"Attempts used: `{audit['attempts_used']}`\n\n"
        f"Final validation passed: `{audit['final_validation_passed']}`\n\n"
        f"Truth boundary: {audit['truth_boundary']}\n",
        encoding="utf-8",
    )
    return {**state, "audit": audit, "steps": steps}


def build_graph() -> Any:
    graph = StateGraph(SupervisorState)
    graph.add_node("plan_agent", plan_agent)
    graph.add_node("validate_agent", validate_agent)
    graph.add_node("diagnose_agent", diagnose_agent)
    graph.add_node("repair_agent", repair_agent)
    graph.add_node("proof_gate_agent", proof_gate_agent)
    graph.add_node("governance_evidence_agent", governance_evidence_agent)
    graph.add_edge(START, "plan_agent")
    graph.add_edge("plan_agent", "validate_agent")
    graph.add_conditional_edges(
        "validate_agent",
        route_after_validation,
        {
            "proof_gate_agent": "proof_gate_agent",
            "diagnose_agent": "diagnose_agent",
            "governance_evidence_agent": "governance_evidence_agent",
        },
    )
    graph.add_edge("diagnose_agent", "repair_agent")
    graph.add_edge("repair_agent", "validate_agent")
    graph.add_edge("proof_gate_agent", "governance_evidence_agent")
    graph.add_edge("governance_evidence_agent", END)
    return graph.compile()


def run_supervisor() -> dict[str, Any]:
    app = build_graph()
    final_state = app.invoke(
        {
            "run_id": "phase13n_langgraph_factory_self_repair_supervisor_001",
            "steps": [],
            "command_results": [],
        }
    )
    audit = final_state.get("audit")
    if not isinstance(audit, dict):
        raise SystemExit("Supervisor did not produce an audit payload.")
    if audit.get("final_validation_passed") is not True:
        print(json.dumps(audit, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    audit = run_supervisor()
    result = {
        "passed": True,
        "phase": "Phase 13N",
        "orchestration_framework": audit["orchestration_framework"],
        "graph_type": audit["graph_type"],
        "repair_applied": audit["repair_applied"],
        "attempts_used": audit["attempts_used"],
        "final_validation_passed": audit["final_validation_passed"],
        "audit_path": relative(AUDIT_PATH),
        "target_path": audit["target_path"],
    }
    if not args.quiet:
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
