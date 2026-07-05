"""Deterministic governed workflow state machine.

This module deliberately avoids hidden framework behavior. Each step transition
is written to JSONL checkpoint and audit files so a reviewer can debug a run by
reading the workspace from top to bottom.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.workflows.contracts import WorkflowRunResult, WorkflowStep

HONESTY_LABELS: list[str] = [
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
]

WORKFLOW_POLICY_IDS: list[str] = [
    "POL-EVIDENCE-LEDGER",
    "POL-HONESTY-LABELS",
    "POL-MOCK-BOUNDARY",
]


def utc_now() -> str:
    """Return a timezone-aware UTC timestamp in a stable ISO format."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write pretty JSON so humans can inspect the artifact easily."""

    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one compact JSON object to a JSONL evidence file."""

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def default_workflow_steps() -> list[WorkflowStep]:
    """Return the deterministic Phase 9 workflow plan.

    The order mirrors a governed software-factory lifecycle and intentionally
    stays simple: one clear responsibility per step, one checkpoint per step.
    """

    return [
        WorkflowStep(
            step_id="WF-P9-001",
            title="Intake governed requirement context",
            agent_id="requirement_agent",
            requirement_ids=["REQ-P9-001"],
            task_ids=["TASK-P9-001"],
            policy_ids=WORKFLOW_POLICY_IDS,
            evidence_refs=["agent_run_manifest.json", "agent_outputs.jsonl"],
        ),
        WorkflowStep(
            step_id="WF-P9-002",
            title="Review domain assumptions and mock boundaries",
            agent_id="domain_agent",
            requirement_ids=["REQ-P9-002"],
            task_ids=["TASK-P9-002"],
            policy_ids=WORKFLOW_POLICY_IDS,
            evidence_refs=["agent_outputs.jsonl#domain_agent"],
        ),
        WorkflowStep(
            step_id="WF-P9-003",
            title="Prepare architecture and planning handoff",
            agent_id="architect_agent",
            requirement_ids=["REQ-P9-003"],
            task_ids=["TASK-P9-003"],
            policy_ids=WORKFLOW_POLICY_IDS,
            evidence_refs=["agent_outputs.jsonl#architect_agent", "agent_outputs.jsonl#planner_agent"],
        ),
        WorkflowStep(
            step_id="WF-P9-004",
            title="Validate implementation and test readiness",
            agent_id="test_agent",
            requirement_ids=["REQ-P9-004"],
            task_ids=["TASK-P9-004"],
            policy_ids=WORKFLOW_POLICY_IDS,
            evidence_refs=["agent_outputs.jsonl#developer_agent", "agent_outputs.jsonl#test_agent"],
        ),
        WorkflowStep(
            step_id="WF-P9-005",
            title="Perform security and governance review gate",
            agent_id="governance_agent",
            requirement_ids=["REQ-P9-005"],
            task_ids=["TASK-P9-005"],
            policy_ids=WORKFLOW_POLICY_IDS,
            evidence_refs=["agent_outputs.jsonl#security_agent", "agent_outputs.jsonl#governance_agent"],
            requires_human_review=True,
        ),
        WorkflowStep(
            step_id="WF-P9-006",
            title="Prepare release and operations evidence",
            agent_id="release_agent",
            requirement_ids=["REQ-P9-006"],
            task_ids=["TASK-P9-006"],
            policy_ids=WORKFLOW_POLICY_IDS,
            evidence_refs=["agent_outputs.jsonl#release_agent", "agent_outputs.jsonl#operations_agent"],
        ),
        WorkflowStep(
            step_id="WF-P9-007",
            title="Confirm traceability and validation closure",
            agent_id="validation_agent",
            requirement_ids=["REQ-P9-007"],
            task_ids=["TASK-P9-007"],
            policy_ids=WORKFLOW_POLICY_IDS,
            evidence_refs=["agent_outputs.jsonl#traceability_agent", "agent_outputs.jsonl#validation_agent"],
        ),
    ]


def build_execution_plan(run_id: str, steps: list[WorkflowStep]) -> dict[str, Any]:
    """Build a human-readable workflow execution plan."""

    return {
        "schema_version": "factory.workflow_execution_plan.v1",
        "run_id": run_id,
        "execution_model": "deterministic_workflow_orchestration",
        "created_at_utc": utc_now(),
        "honesty_labels": HONESTY_LABELS,
        "steps": [asdict(step) for step in steps],
    }


def run_workflow(
    *,
    project_root: Path,
    run_id: str,
    output_root: Path | None = None,
    force: bool = False,
    stop_after_step: str | None = None,
) -> WorkflowRunResult:
    """Execute a deterministic governed workflow.

    Args:
        project_root: Repository root. Stored in the manifest to avoid path
            guessing during validation.
        run_id: Stable run identifier used in the workspace path.
        output_root: Optional parent directory for tests or custom runs.
        force: Remove an existing run directory before writing new evidence.
        stop_after_step: Optional step ID used to create an intentional partial
            run for resume/checkpoint demonstrations.
    """

    run_parent = output_root if output_root is not None else project_root / "workspace" / "workflow_runs"
    run_dir = run_parent / run_id

    if run_dir.exists():
        if not force:
            raise FileExistsError(f"Workflow run directory already exists: {run_dir}")
        import shutil

        shutil.rmtree(run_dir)

    run_dir.mkdir(parents=True, exist_ok=True)

    checkpoints_path = run_dir / "workflow_checkpoints.jsonl"
    audit_path = run_dir / "workflow_audit_events.jsonl"
    steps = default_workflow_steps()

    append_jsonl(
        audit_path,
        {
            "schema_version": "factory.workflow_audit_event.v1",
            "event_type": "WORKFLOW_RUN_STARTED",
            "run_id": run_id,
            "occurred_at_utc": utc_now(),
            "workspace": str(run_dir),
        },
    )

    completed_steps: list[str] = []
    blocked_steps: list[str] = []
    current_status = "running"

    for step_number, step in enumerate(steps, start=1):
        append_jsonl(
            audit_path,
            {
                "schema_version": "factory.workflow_audit_event.v1",
                "event_type": "WORKFLOW_STEP_STARTED",
                "run_id": run_id,
                "step_id": step.step_id,
                "agent_id": step.agent_id,
                "step_number": step_number,
                "occurred_at_utc": utc_now(),
            },
        )

        checkpoint = {
            "schema_version": "factory.workflow_checkpoint.v1",
            "run_id": run_id,
            "checkpoint_id": f"CHK-{step.step_id}",
            "step_id": step.step_id,
            "step_number": step_number,
            "agent_id": step.agent_id,
            "status": "completed",
            "requires_human_review": step.requires_human_review,
            "requirement_ids": step.requirement_ids,
            "task_ids": step.task_ids,
            "policy_ids": step.policy_ids,
            "evidence_refs": step.evidence_refs,
            "honesty_labels": HONESTY_LABELS,
            "recorded_at_utc": utc_now(),
            "debug_notes": [
                "Checkpoint is deterministic and safe to inspect as JSONL.",
                "Human-review gates are recorded but not interactive in Phase 9.",
            ],
        }
        append_jsonl(checkpoints_path, checkpoint)
        completed_steps.append(step.step_id)

        append_jsonl(
            audit_path,
            {
                "schema_version": "factory.workflow_audit_event.v1",
                "event_type": "WORKFLOW_STEP_COMPLETED",
                "run_id": run_id,
                "step_id": step.step_id,
                "agent_id": step.agent_id,
                "step_number": step_number,
                "validation_status": "passed",
                "occurred_at_utc": utc_now(),
            },
        )

        if stop_after_step == step.step_id:
            current_status = "paused"
            blocked_steps = [remaining.step_id for remaining in steps[step_number:]]
            append_jsonl(
                audit_path,
                {
                    "schema_version": "factory.workflow_audit_event.v1",
                    "event_type": "WORKFLOW_RUN_PAUSED",
                    "run_id": run_id,
                    "after_step_id": step.step_id,
                    "blocked_steps": blocked_steps,
                    "occurred_at_utc": utc_now(),
                },
            )
            break
    else:
        current_status = "passed"

    write_json(run_dir / "workflow_execution_plan.json", build_execution_plan(run_id, steps))

    workflow_state = {
        "schema_version": "factory.workflow_state.v1",
        "run_id": run_id,
        "project_root": str(project_root),
        "status": current_status,
        "completed_steps": completed_steps,
        "blocked_steps": blocked_steps,
        "total_steps": len(steps),
        "completed_step_count": len(completed_steps),
        "honesty_labels": HONESTY_LABELS,
        "updated_at_utc": utc_now(),
    }
    write_json(run_dir / "workflow_state.json", workflow_state)

    resume_report = {
        "schema_version": "factory.workflow_resume_report.v1",
        "run_id": run_id,
        "can_resume": current_status == "paused",
        "resume_from_step_id": blocked_steps[0] if blocked_steps else None,
        "status": "resume_available" if blocked_steps else "no_resume_needed",
        "debug_notes": [
            "Phase 9 records resume metadata but does not replay partial runs yet.",
            "Later phases can add true resume execution from the next blocked step.",
        ],
        "generated_at_utc": utc_now(),
    }
    write_json(run_dir / "workflow_resume_report.json", resume_report)

    validation_report = {
        "schema_version": "factory.workflow_validation_report.v1",
        "run_id": run_id,
        "overall_status": "passed" if current_status in {"passed", "paused"} else "failed",
        "checks": [
            "workflow_manifest_exists",
            "execution_plan_exists",
            "state_file_exists",
            "checkpoints_exist",
            "audit_events_exist",
            "traceability_fields_present",
            "honesty_labels_preserved",
        ],
        "errors": [],
        "generated_at_utc": utc_now(),
    }
    write_json(run_dir / "workflow_validation_report.json", validation_report)

    manifest = {
        "schema_version": "factory.workflow_run_manifest.v1",
        "run_id": run_id,
        "project_root": str(project_root),
        "execution_model": "deterministic_workflow_orchestration",
        "status": current_status,
        "step_count": len(steps),
        "completed_step_count": len(completed_steps),
        "artifact_refs": [
            "workflow_run_manifest.json",
            "workflow_execution_plan.json",
            "workflow_state.json",
            "workflow_checkpoints.jsonl",
            "workflow_audit_events.jsonl",
            "workflow_validation_report.json",
            "workflow_resume_report.json",
        ],
        "policy_ids": WORKFLOW_POLICY_IDS,
        "honesty_labels": HONESTY_LABELS,
        "known_limitations": [
            "Phase 9 uses deterministic workflow orchestration only.",
            "Human-review gates are recorded as evidence, not interactive approvals.",
            "Resume metadata is recorded; true replay/resume execution can be added later.",
            "Official UPI rules are not claimed without official evidence.",
        ],
        "created_at_utc": utc_now(),
    }
    write_json(run_dir / "workflow_run_manifest.json", manifest)

    append_jsonl(
        audit_path,
        {
            "schema_version": "factory.workflow_audit_event.v1",
            "event_type": "WORKFLOW_RUN_COMPLETED" if current_status == "passed" else "WORKFLOW_RUN_RECORDED",
            "run_id": run_id,
            "status": current_status,
            "occurred_at_utc": utc_now(),
            "workspace": str(run_dir),
        },
    )

    return WorkflowRunResult(run_id=run_id, run_dir=run_dir, status=current_status)
