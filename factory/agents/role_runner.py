"""Deterministic governed multi-agent role simulation.

This module does not call an LLM.  It simulates role-agent execution in a
repeatable way so the factory can prove agent contracts, handoffs, decisions,
and audit events before real model/tool execution is introduced.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.agents.contracts import (
    AGENT_SEQUENCE,
    COMMON_POLICY_IDS,
    HONESTY_LABELS,
    AgentDefinition,
    AgentOutput,
)
from factory.agents.prompt_loader import (
    load_agent_prompt,
    prompt_path_for_agent,
    validate_prompt_pack_files,
)

SCHEMA_AGENT_RUN_MANIFEST = "factory.agent_run_manifest.v1"
SCHEMA_AGENT_EXECUTION_PLAN = "factory.agent_execution_plan.v1"
SCHEMA_AGENT_OUTPUT = "factory.agent_output.v1"
SCHEMA_AGENT_DECISION = "factory.agent_decision.v1"
SCHEMA_AGENT_HANDOFF = "factory.agent_handoff.v1"
SCHEMA_AGENT_AUDIT_EVENT = "factory.agent_audit_event.v1"
SCHEMA_AGENT_VALIDATION_REPORT = "factory.agent_validation_report.v1"

ROLE_RESPONSIBILITIES: dict[str, str] = {
    "requirement_agent": "Clarify requirements and preserve missing-source limits.",
    "domain_agent": "Explain domain assumptions without inventing official rules.",
    "architect_agent": "Compare architecture choices and select a justified option.",
    "planner_agent": "Break work into traceable, reviewable tasks.",
    "developer_agent": "Plan beginner-readable, debug-friendly implementation work.",
    "test_agent": "Define positive, negative, boundary, and regression validation.",
    "security_agent": "Identify secure-development and LLM-risk checkpoints.",
    "governance_agent": "Check policies, honesty labels, and mock boundaries.",
    "evidence_agent": "Map artifacts and decisions to evidence references.",
    "reviewer_agent": "Review outputs for clarity, gaps, and validation readiness.",
    "release_agent": "Prepare release-readiness recommendation from evidence.",
    "operations_agent": "Define supportability, logging, and troubleshooting expectations.",
    "regeneration_agent": "Confirm deterministic regeneration expectations.",
    "traceability_agent": "Confirm requirement/task/policy/evidence traceability.",
    "validation_agent": "Confirm that required validation gates are represented.",
}


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with second precision."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write stable, human-readable JSON."""

    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one JSON object to a JSONL file."""

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def build_agent_definitions(project_root: Path) -> list[AgentDefinition]:
    """Build deterministic agent definitions from the governed prompt pack."""

    definitions: list[AgentDefinition] = []
    for agent_id in AGENT_SEQUENCE:
        prompt_path = prompt_path_for_agent(project_root, agent_id)
        definitions.append(
            AgentDefinition(
                agent_id=agent_id,
                agent_role=agent_id.replace("_", " ").title(),
                prompt_path=str(prompt_path.relative_to(project_root)),
                responsibility=ROLE_RESPONSIBILITIES[agent_id],
            )
        )
    return definitions


def make_agent_output(
    *,
    run_id: str,
    definition: AgentDefinition,
    previous_agent_id: str | None,
) -> AgentOutput:
    """Create one deterministic, traceable agent output."""

    input_refs = [definition.prompt_path, "factory_governance/agent_prompts/common_governed_agent_contract.md"]
    if previous_agent_id is not None:
        input_refs.append(f"agent_outputs.jsonl#{previous_agent_id}")

    output_refs = [f"agent_outputs.jsonl#{definition.agent_id}"]
    requirement_suffix = definition.agent_id.upper().replace("_", "-")

    return AgentOutput(
        schema_version=SCHEMA_AGENT_OUTPUT,
        run_id=run_id,
        agent_id=definition.agent_id,
        agent_role=definition.agent_role,
        prompt_path=definition.prompt_path,
        input_refs=input_refs,
        output_refs=output_refs,
        requirement_ids=["REQ-P8-001", f"REQ-P8-{requirement_suffix}"],
        task_ids=["TASK-P8-001", f"TASK-P8-{requirement_suffix}"],
        policy_ids=list(COMMON_POLICY_IDS),
        evidence_refs=[
            "agent_run_manifest.json",
            "agent_execution_plan.json",
            "agent_audit_events.jsonl",
            definition.prompt_path,
        ],
        assumptions=[
            "Phase 8 uses deterministic role-agent simulation, not autonomous LLM execution.",
            "Official UPI dispute rules are not claimed without approved evidence.",
        ],
        decisions=[
            f"{definition.agent_id} followed the governed prompt contract.",
            "Preserved mock boundaries and honesty labels in the simulated output.",
        ],
        known_limitations=[
            "No real LLM tool-calling is executed in Phase 8.",
            "Outputs are deterministic simulation artifacts for governance validation.",
        ],
        honesty_labels=list(HONESTY_LABELS),
        validation_status="passed",
        summary=definition.responsibility,
        debug_notes=[
            "Output is deterministic and can be reproduced from the prompt pack.",
            "All traceability fields are explicit to simplify review and debugging.",
        ],
        produced_at_utc=utc_now(),
    )


def validate_outputs_locally(outputs: list[AgentOutput]) -> list[str]:
    """Run lightweight validation before writing the validation report."""

    errors: list[str] = []
    seen_agents = {output.agent_id for output in outputs}

    for agent_id in AGENT_SEQUENCE:
        if agent_id not in seen_agents:
            errors.append(f"Missing output for agent: {agent_id}")

    for output in outputs:
        if not output.requirement_ids:
            errors.append(f"{output.agent_id} has no requirement_ids")
        if not output.task_ids:
            errors.append(f"{output.agent_id} has no task_ids")
        if not output.policy_ids:
            errors.append(f"{output.agent_id} has no policy_ids")
        if not output.evidence_refs:
            errors.append(f"{output.agent_id} has no evidence_refs")
        if set(HONESTY_LABELS) - set(output.honesty_labels):
            errors.append(f"{output.agent_id} does not preserve all honesty labels")
        if output.validation_status != "passed":
            errors.append(f"{output.agent_id} validation_status is not passed")

    return errors


def run_multi_agent_simulation(
    *,
    project_root: Path,
    run_id: str,
    output_root: Path | None = None,
    force: bool = False,
) -> Path:
    """Run a deterministic governed multi-agent simulation.

    Args:
        project_root: Repository root.
        run_id: Stable run identifier for the output workspace.
        output_root: Optional parent directory for testability.
        force: Remove an existing run directory with the same run_id.

    Returns:
        The created run directory.
    """

    prompt_errors = validate_prompt_pack_files(project_root)
    if prompt_errors:
        joined = "; ".join(prompt_errors)
        raise RuntimeError(f"Prompt pack is incomplete: {joined}")

    for agent_id in AGENT_SEQUENCE:
        # Load prompts now so missing or unreadable prompt files fail early.
        load_agent_prompt(project_root, agent_id)

    runs_root = output_root if output_root is not None else project_root / "workspace" / "agent_runs"
    run_dir = runs_root / run_id
    if run_dir.exists():
        if not force:
            raise RuntimeError(f"Run directory already exists: {run_dir}. Use --force to replace it.")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    audit_path = run_dir / "agent_audit_events.jsonl"
    outputs_path = run_dir / "agent_outputs.jsonl"
    decisions_path = run_dir / "agent_decisions.jsonl"
    handoffs_path = run_dir / "agent_handoffs.jsonl"

    append_jsonl(
        audit_path,
        {
            "schema_version": SCHEMA_AGENT_AUDIT_EVENT,
            "event_type": "AGENT_RUN_STARTED",
            "occurred_at_utc": utc_now(),
            "run_id": run_id,
            "workspace": str(run_dir),
        },
    )

    definitions = build_agent_definitions(project_root)
    write_json(
        run_dir / "agent_execution_plan.json",
        {
            "schema_version": SCHEMA_AGENT_EXECUTION_PLAN,
            "run_id": run_id,
            "created_at_utc": utc_now(),
            "execution_model": "deterministic_role_agent_simulation",
            "project_root": str(project_root),
            "agents": [definition.to_dict() for definition in definitions],
            "honesty_labels": list(HONESTY_LABELS),
        },
    )

    outputs: list[AgentOutput] = []
    previous_agent_id: str | None = None
    for step_number, definition in enumerate(definitions, start=1):
        append_jsonl(
            audit_path,
            {
                "schema_version": SCHEMA_AGENT_AUDIT_EVENT,
                "event_type": "AGENT_STARTED",
                "occurred_at_utc": utc_now(),
                "run_id": run_id,
                "agent_id": definition.agent_id,
                "step_number": step_number,
            },
        )

        output = make_agent_output(
            run_id=run_id,
            definition=definition,
            previous_agent_id=previous_agent_id,
        )
        outputs.append(output)
        append_jsonl(outputs_path, output.to_dict())
        append_jsonl(
            decisions_path,
            {
                "schema_version": SCHEMA_AGENT_DECISION,
                "run_id": run_id,
                "agent_id": definition.agent_id,
                "decision_ids": output.task_ids,
                "decisions": output.decisions,
                "evidence_refs": output.evidence_refs,
                "recorded_at_utc": utc_now(),
            },
        )

        if previous_agent_id is not None:
            append_jsonl(
                handoffs_path,
                {
                    "schema_version": SCHEMA_AGENT_HANDOFF,
                    "run_id": run_id,
                    "from_agent_id": previous_agent_id,
                    "to_agent_id": definition.agent_id,
                    "handoff_summary": "Previous governed output becomes input context.",
                    "evidence_refs": [
                        f"agent_outputs.jsonl#{previous_agent_id}",
                        f"agent_outputs.jsonl#{definition.agent_id}",
                    ],
                    "occurred_at_utc": utc_now(),
                },
            )

        append_jsonl(
            audit_path,
            {
                "schema_version": SCHEMA_AGENT_AUDIT_EVENT,
                "event_type": "AGENT_COMPLETED",
                "occurred_at_utc": utc_now(),
                "run_id": run_id,
                "agent_id": definition.agent_id,
                "step_number": step_number,
                "validation_status": output.validation_status,
            },
        )
        previous_agent_id = definition.agent_id

    validation_errors = validate_outputs_locally(outputs)
    overall_status = "passed" if not validation_errors else "failed"
    write_json(
        run_dir / "agent_validation_report.json",
        {
            "schema_version": SCHEMA_AGENT_VALIDATION_REPORT,
            "run_id": run_id,
            "generated_at_utc": utc_now(),
            "overall_status": overall_status,
            "errors": validation_errors,
            "checks": [
                "all_required_agents_have_outputs",
                "outputs_have_requirement_task_policy_evidence_links",
                "honesty_labels_preserved",
                "validation_status_passed",
            ],
        },
    )

    write_json(
        run_dir / "agent_run_manifest.json",
        {
            "schema_version": SCHEMA_AGENT_RUN_MANIFEST,
            "run_id": run_id,
            "created_at_utc": utc_now(),
            "execution_model": "deterministic_role_agent_simulation",
            "project_root": str(project_root),
            "agent_count": len(definitions),
            "agents": [definition.agent_id for definition in definitions],
            "artifact_refs": [
                "agent_run_manifest.json",
                "agent_execution_plan.json",
                "agent_outputs.jsonl",
                "agent_decisions.jsonl",
                "agent_handoffs.jsonl",
                "agent_validation_report.json",
                "agent_audit_events.jsonl",
            ],
            "policy_ids": list(COMMON_POLICY_IDS),
            "honesty_labels": list(HONESTY_LABELS),
            "validation_status": overall_status,
            "known_limitations": [
                "Phase 8 is deterministic simulation only.",
                "No autonomous LLM execution is performed.",
                "Official UPI rules are not claimed without official evidence.",
            ],
        },
    )

    append_jsonl(
        audit_path,
        {
            "schema_version": SCHEMA_AGENT_AUDIT_EVENT,
            "event_type": "AGENT_RUN_COMPLETED",
            "occurred_at_utc": utc_now(),
            "run_id": run_id,
            "workspace": str(run_dir),
            "validation_status": overall_status,
        },
    )

    if validation_errors:
        raise RuntimeError(f"Multi-agent simulation failed validation: {validation_errors}")
    return run_dir
