#!/usr/bin/env python3
"""Validate a governed deterministic multi-agent run workspace.

The validator is intentionally beginner-readable and debug-friendly.  It can
validate normal workspaces under ``workspace/agent_runs/<run_id>`` and temporary
pytest workspaces by reading ``project_root`` from the run manifest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, cast

from factory.agents.contracts import AGENT_SEQUENCE, HONESTY_LABELS

REQUIRED_FILES = (
    "agent_run_manifest.json",
    "agent_execution_plan.json",
    "agent_outputs.jsonl",
    "agent_decisions.jsonl",
    "agent_handoffs.jsonl",
    "agent_validation_report.json",
    "agent_audit_events.jsonl",
)

REQUIRED_OUTPUT_FIELDS = (
    "agent_id",
    "agent_role",
    "prompt_path",
    "input_refs",
    "output_refs",
    "requirement_ids",
    "task_ids",
    "policy_ids",
    "evidence_refs",
    "honesty_labels",
    "validation_status",
    "summary",
    "debug_notes",
)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    """Load a JSON object and collect actionable errors."""

    if not path.exists():
        errors.append(f"Missing JSON file: {path}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"Expected JSON object in {path}")
        return {}
    return cast(dict[str, Any], data)


def load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    """Load JSONL rows and collect line-specific errors."""

    rows: list[dict[str, Any]] = []
    if not path.exists():
        errors.append(f"Missing JSONL file: {path}")
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"Invalid JSONL in {path}:{line_number}: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"Expected JSON object in {path}:{line_number}")
            continue
        rows.append(cast(dict[str, Any], data))
    return rows


def is_non_empty_list(value: object) -> bool:
    """Return True when value is a non-empty list."""

    return isinstance(value, list) and bool(value)


def latest_run_dir(project_root: Path) -> Path:
    """Return the newest agent-run workspace under the repository."""

    runs_root = project_root / "workspace" / "agent_runs"
    if not runs_root.exists():
        raise FileNotFoundError(f"No agent run directory exists: {runs_root}")
    candidates = [path for path in runs_root.iterdir() if path.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No agent run workspaces found under: {runs_root}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def require_files(run_dir: Path, errors: list[str]) -> None:
    """Ensure all required run artifacts exist."""

    for filename in REQUIRED_FILES:
        if not (run_dir / filename).exists():
            errors.append(f"Missing required run artifact: {filename}")


def resolve_project_root(run_dir: Path, manifest: dict[str, Any], errors: list[str]) -> Path:
    """Resolve the repository root used to validate project-relative paths.

    Normal runs live under ``<project>/workspace/agent_runs/<run_id>``.  Tests
    may use a temporary output directory.  Therefore the safest source of truth
    is the ``project_root`` recorded in ``agent_run_manifest.json``.
    """

    project_root_value = manifest.get("project_root")
    if isinstance(project_root_value, str) and project_root_value.strip():
        project_root = Path(project_root_value).resolve()
        if not project_root.exists():
            errors.append(f"agent_run_manifest project_root does not exist: {project_root}")
        return project_root

    fallback_root = run_dir.parents[2] if len(run_dir.parents) >= 3 else run_dir.parent
    errors.append(
        "agent_run_manifest is missing project_root; "
        f"using fallback root for validation: {fallback_root}"
    )
    return fallback_root.resolve()


def validate_required_agents(outputs: Iterable[dict[str, Any]], errors: list[str]) -> None:
    """Confirm every required governed agent produced an output."""

    output_by_agent = {str(row.get("agent_id")): row for row in outputs}
    for agent_id in AGENT_SEQUENCE:
        if agent_id not in output_by_agent:
            errors.append(f"Missing agent output: {agent_id}")


def validate_agent_output(row: dict[str, Any], project_root: Path, errors: list[str]) -> None:
    """Validate one role-agent output row."""

    agent_id = str(row.get("agent_id", "<missing-agent-id>"))
    for field in REQUIRED_OUTPUT_FIELDS:
        if field not in row:
            errors.append(f"{agent_id} missing field: {field}")

    for list_field in (
        "input_refs",
        "output_refs",
        "requirement_ids",
        "task_ids",
        "policy_ids",
        "evidence_refs",
        "honesty_labels",
        "debug_notes",
    ):
        if not is_non_empty_list(row.get(list_field)):
            errors.append(f"{agent_id} field must be a non-empty list: {list_field}")

    honesty_labels = row.get("honesty_labels")
    if isinstance(honesty_labels, list):
        missing = set(HONESTY_LABELS) - {str(label) for label in honesty_labels}
        if missing:
            errors.append(f"{agent_id} missing honesty labels: {sorted(missing)}")

    if row.get("validation_status") != "passed":
        errors.append(f"{agent_id} validation_status must be passed")

    prompt_path = row.get("prompt_path")
    if isinstance(prompt_path, str):
        if Path(prompt_path).is_absolute():
            errors.append(f"{agent_id} prompt_path must be project-relative: {prompt_path}")
        elif not (project_root / prompt_path).exists():
            errors.append(f"{agent_id} prompt_path does not exist: {prompt_path}")
    else:
        errors.append(f"{agent_id} prompt_path must be a string")


def validate_run(run_dir: Path) -> list[str]:
    """Validate one governed multi-agent run workspace."""

    errors: list[str] = []
    require_files(run_dir, errors)

    manifest = load_json(run_dir / "agent_run_manifest.json", errors)
    execution_plan = load_json(run_dir / "agent_execution_plan.json", errors)
    validation_report = load_json(run_dir / "agent_validation_report.json", errors)
    outputs = load_jsonl(run_dir / "agent_outputs.jsonl", errors)
    decisions = load_jsonl(run_dir / "agent_decisions.jsonl", errors)
    handoffs = load_jsonl(run_dir / "agent_handoffs.jsonl", errors)
    audit_events = load_jsonl(run_dir / "agent_audit_events.jsonl", errors)

    project_root = resolve_project_root(run_dir, manifest, errors)

    if manifest.get("validation_status") != "passed":
        errors.append("agent_run_manifest validation_status must be passed")
    if manifest.get("agent_count") != len(AGENT_SEQUENCE):
        errors.append("agent_run_manifest agent_count does not match required sequence")
    if validation_report.get("overall_status") != "passed":
        errors.append("agent_validation_report overall_status must be passed")

    plan_agents = execution_plan.get("agents")
    if not isinstance(plan_agents, list) or len(plan_agents) != len(AGENT_SEQUENCE):
        errors.append("agent_execution_plan must include all required agents")

    validate_required_agents(outputs, errors)
    for output in outputs:
        validate_agent_output(output, project_root, errors)

    if len(decisions) != len(AGENT_SEQUENCE):
        errors.append("agent_decisions.jsonl must contain one decision record per agent")
    if len(handoffs) != len(AGENT_SEQUENCE) - 1:
        errors.append("agent_handoffs.jsonl must contain one handoff between each agent")
    if len(audit_events) < (2 * len(AGENT_SEQUENCE)) + 2:
        errors.append("agent_audit_events.jsonl has too few audit events")

    return errors


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Validate a governed multi-agent run.")
    parser.add_argument("--run-dir", help="Run directory to validate.")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Validate the latest workspace under workspace/agent_runs.",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root. Defaults to the current working directory.",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""

    args = parse_args()
    project_root = Path(args.project_root).resolve()
    if args.latest:
        try:
            run_dir = latest_run_dir(project_root)
            errors = validate_run(run_dir)
        except FileNotFoundError as exc:
            run_dir = project_root / "workspace" / "agent_runs"
            errors = [str(exc)]
    elif args.run_dir:
        run_dir = Path(args.run_dir).resolve()
        errors = validate_run(run_dir)
    else:
        run_dir = project_root / "workspace" / "agent_runs"
        errors = ["Provide --run-dir or --latest."]

    result = {"errors": errors, "passed": not errors, "run_dir": str(run_dir)}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
