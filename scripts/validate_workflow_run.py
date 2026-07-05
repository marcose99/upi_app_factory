#!/usr/bin/env python3
"""Validate Phase 9 governed workflow run evidence.

The validator is intentionally strict about traceability fields and deliberately
simple to debug: each missing condition becomes one explicit error string.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = [
    "workflow_run_manifest.json",
    "workflow_execution_plan.json",
    "workflow_state.json",
    "workflow_checkpoints.jsonl",
    "workflow_audit_events.jsonl",
    "workflow_validation_report.json",
    "workflow_resume_report.json",
]

REQUIRED_HONESTY_LABELS = {
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
}

REQUIRED_TRACEABILITY_FIELDS = ["requirement_ids", "task_ids", "policy_ids", "evidence_refs"]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} line {line_number} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path} line {line_number} is not a JSON object")
        records.append(payload)
    return records


def latest_run_dir(project_root: Path) -> Path:
    runs_root = project_root / "workspace" / "workflow_runs"
    if not runs_root.exists():
        raise FileNotFoundError(f"No workflow runs directory found: {runs_root}")
    candidates = [path for path in runs_root.iterdir() if path.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No workflow run directories found under: {runs_root}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def validate_run(run_dir: Path) -> list[str]:
    errors: list[str] = []

    for file_name in REQUIRED_FILES:
        if not (run_dir / file_name).exists():
            errors.append(f"Missing required workflow artifact: {file_name}")

    if errors:
        return errors

    try:
        manifest = read_json(run_dir / "workflow_run_manifest.json")
        plan = read_json(run_dir / "workflow_execution_plan.json")
        state = read_json(run_dir / "workflow_state.json")
        validation_report = read_json(run_dir / "workflow_validation_report.json")
        resume_report = read_json(run_dir / "workflow_resume_report.json")
        checkpoints = read_jsonl(run_dir / "workflow_checkpoints.jsonl")
        audit_events = read_jsonl(run_dir / "workflow_audit_events.jsonl")
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"Invalid JSON evidence: {exc}"]

    if manifest.get("schema_version") != "factory.workflow_run_manifest.v1":
        errors.append("workflow_run_manifest.json has wrong schema_version")

    if plan.get("schema_version") != "factory.workflow_execution_plan.v1":
        errors.append("workflow_execution_plan.json has wrong schema_version")

    if state.get("schema_version") != "factory.workflow_state.v1":
        errors.append("workflow_state.json has wrong schema_version")

    if validation_report.get("overall_status") != "passed":
        errors.append("workflow_validation_report.json overall_status is not passed")

    if resume_report.get("schema_version") != "factory.workflow_resume_report.v1":
        errors.append("workflow_resume_report.json has wrong schema_version")

    if not REQUIRED_HONESTY_LABELS.issubset(set(manifest.get("honesty_labels", []))):
        errors.append("workflow manifest does not preserve all required honesty labels")

    steps = plan.get("steps", [])
    if not isinstance(steps, list) or not steps:
        errors.append("workflow_execution_plan.json has no steps")
    else:
        for step in steps:
            if not isinstance(step, dict):
                errors.append("workflow step is not a JSON object")
                continue
            for field in ["step_id", "title", "agent_id", *REQUIRED_TRACEABILITY_FIELDS]:
                if field not in step:
                    errors.append(f"Workflow step is missing field: {field}")
            for field in REQUIRED_TRACEABILITY_FIELDS:
                value = step.get(field)
                if not isinstance(value, list) or not value:
                    errors.append(f"Workflow step {step.get('step_id', '<unknown>')} has empty {field}")

    completed_step_count = state.get("completed_step_count")
    if completed_step_count != len(checkpoints):
        errors.append("workflow_state completed_step_count does not match checkpoint count")

    if not checkpoints:
        errors.append("workflow_checkpoints.jsonl has no checkpoints")
    for checkpoint in checkpoints:
        for field in ["checkpoint_id", "step_id", "agent_id", "status", *REQUIRED_TRACEABILITY_FIELDS]:
            if field not in checkpoint:
                errors.append(f"Workflow checkpoint is missing field: {field}")
        if checkpoint.get("status") != "completed":
            errors.append(f"Workflow checkpoint {checkpoint.get('checkpoint_id', '<unknown>')} is not completed")
        if not REQUIRED_HONESTY_LABELS.issubset(set(checkpoint.get("honesty_labels", []))):
            errors.append(f"Workflow checkpoint {checkpoint.get('checkpoint_id', '<unknown>')} misses honesty labels")

    event_types = {event.get("event_type") for event in audit_events}
    if "WORKFLOW_RUN_STARTED" not in event_types:
        errors.append("workflow_audit_events.jsonl is missing WORKFLOW_RUN_STARTED")
    if not ({"WORKFLOW_RUN_COMPLETED", "WORKFLOW_RUN_RECORDED"} & event_types):
        errors.append("workflow_audit_events.jsonl is missing final workflow event")
    if "WORKFLOW_STEP_STARTED" not in event_types:
        errors.append("workflow_audit_events.jsonl is missing WORKFLOW_STEP_STARTED")
    if "WORKFLOW_STEP_COMPLETED" not in event_types:
        errors.append("workflow_audit_events.jsonl is missing WORKFLOW_STEP_COMPLETED")

    project_root = manifest.get("project_root")
    if not isinstance(project_root, str) or not project_root:
        errors.append("workflow manifest is missing project_root")
    elif not Path(project_root).exists():
        errors.append(f"workflow manifest project_root does not exist: {project_root}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate governed workflow run evidence.")
    parser.add_argument("--run-dir", default=None, help="Path to workflow run directory.")
    parser.add_argument("--latest", action="store_true", help="Validate the latest workspace/workflow_runs entry.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]

    if args.latest:
        run_dir = latest_run_dir(project_root)
    elif args.run_dir:
        run_dir = Path(args.run_dir).resolve()
    else:
        raise SystemExit("Use --run-dir <path> or --latest")

    errors = validate_run(run_dir)
    print(json.dumps({"passed": errors == [], "errors": errors, "run_dir": str(run_dir)}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
