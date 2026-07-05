#!/usr/bin/env python3
"""Validate Phase 7 governed factory run manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = [
    "factory_run_manifest.json",
    "task_manifest.json",
    "agent_outputs.jsonl",
    "artifact_manifest.json",
    "validation_report.json",
    "known_limitations.md",
    "release_readiness_report.md",
    "audit_events.jsonl",
]

REQUIRED_HONESTY_LABELS = {
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
}

REQUIRED_MOCK_BOUNDARIES = {
    "mock_upi_switch",
    "mock_core_banking",
    "mock_customer_notification",
    "mock_dispute_evidence_store",
}


class ValidationError(Exception):
    """Raised when a run manifest file cannot be parsed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path}: {exc}") from exc


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSONL in {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValidationError(f"JSONL row must be an object in {path}:{line_number}")
        rows.append(value)
    return rows


def latest_run_dir(project_root: Path) -> Path:
    runs_root = project_root / "workspace" / "runs"
    candidates = [path for path in runs_root.iterdir() if path.is_dir()] if runs_root.exists() else []
    if not candidates:
        raise ValidationError(f"No run directories found under {runs_root}")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def require_non_empty_list(errors: list[str], owner: str, payload: dict[str, Any], field: str) -> None:
    value = payload.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        errors.append(f"{owner} must contain a non-empty string list field: {field}")


def validate_schema_versions(errors: list[str], manifests: dict[str, Any]) -> None:
    expected = {
        "factory_run_manifest.json": "factory.run_manifest.v1",
        "task_manifest.json": "factory.task_manifest.v1",
        "artifact_manifest.json": "factory.artifact_manifest.v1",
        "validation_report.json": "factory.validation_report.v1",
    }
    for filename, schema_version in expected.items():
        actual = manifests[filename].get("schema_version")
        if actual != schema_version:
            errors.append(f"{filename} schema_version must be {schema_version}; found {actual!r}")


def validate_run_dir(
    run_dir: Path,
    *,
    require_passed_validation: bool = True,
    ignore_artifact_manifest_self_hash: bool = False,
) -> list[str]:
    errors: list[str] = []
    run_dir = run_dir.resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        return [f"Run directory does not exist: {run_dir}"]

    for relative in REQUIRED_FILES:
        if not (run_dir / relative).is_file():
            errors.append(f"Missing required run artifact: {relative}")
    if errors:
        return errors

    try:
        manifests = {
            "factory_run_manifest.json": load_json(run_dir / "factory_run_manifest.json"),
            "task_manifest.json": load_json(run_dir / "task_manifest.json"),
            "artifact_manifest.json": load_json(run_dir / "artifact_manifest.json"),
            "validation_report.json": load_json(run_dir / "validation_report.json"),
        }
        agent_outputs = load_jsonl(run_dir / "agent_outputs.jsonl")
        audit_events = load_jsonl(run_dir / "audit_events.jsonl")
    except ValidationError as exc:
        return [str(exc)]

    validate_schema_versions(errors, manifests)

    factory_manifest = manifests["factory_run_manifest.json"]
    task_manifest = manifests["task_manifest.json"]
    artifact_manifest = manifests["artifact_manifest.json"]
    validation_report = manifests["validation_report.json"]

    if not factory_manifest.get("run_id"):
        errors.append("factory_run_manifest.json must contain run_id")
    if not factory_manifest.get("workspace"):
        errors.append("factory_run_manifest.json must contain workspace")
    if not factory_manifest.get("source", {}).get("head"):
        errors.append("factory_run_manifest.json must contain source.head")

    honesty_labels = set(factory_manifest.get("honesty_labels", []))
    missing_labels = REQUIRED_HONESTY_LABELS - honesty_labels
    if missing_labels:
        errors.append(f"factory_run_manifest.json missing honesty labels: {sorted(missing_labels)}")

    mock_boundaries = set(factory_manifest.get("mock_boundaries", []))
    missing_boundaries = REQUIRED_MOCK_BOUNDARIES - mock_boundaries
    if missing_boundaries:
        errors.append(f"factory_run_manifest.json missing mock boundaries: {sorted(missing_boundaries)}")

    requirements = factory_manifest.get("requirements", [])
    policies = factory_manifest.get("policies", [])
    if not isinstance(requirements, list) or not requirements:
        errors.append("factory_run_manifest.json must contain at least one requirement")
    if not isinstance(policies, list) or not policies:
        errors.append("factory_run_manifest.json must contain at least one policy")
    requirement_ids = {item.get("id") for item in requirements if isinstance(item, dict)}
    policy_ids = {item.get("id") for item in policies if isinstance(item, dict)}

    tasks = task_manifest.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        errors.append("task_manifest.json must contain tasks")
    task_ids: set[str] = set()
    for task in tasks if isinstance(tasks, list) else []:
        if not isinstance(task, dict):
            errors.append("Every task must be an object")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            errors.append("Every task must contain id")
            continue
        task_ids.add(task_id)
        require_non_empty_list(errors, f"task {task_id}", task, "requirement_ids")
        require_non_empty_list(errors, f"task {task_id}", task, "policy_ids")
        require_non_empty_list(errors, f"task {task_id}", task, "evidence_refs")
        for req_id in task.get("requirement_ids", []):
            if req_id not in requirement_ids:
                errors.append(f"task {task_id} references unknown requirement {req_id}")
        for policy_id in task.get("policy_ids", []):
            if policy_id not in policy_ids:
                errors.append(f"task {task_id} references unknown policy {policy_id}")

    if not agent_outputs:
        errors.append("agent_outputs.jsonl must contain at least one agent output")
    for index, output in enumerate(agent_outputs, start=1):
        require_non_empty_list(errors, f"agent output row {index}", output, "task_ids")
        require_non_empty_list(errors, f"agent output row {index}", output, "requirement_ids")
        if not output.get("agent_name"):
            errors.append(f"agent output row {index} must contain agent_name")

    if not audit_events:
        errors.append("audit_events.jsonl must contain at least one audit event")
    event_types = {event.get("event_type") for event in audit_events}
    if "RUN_STARTED" not in event_types:
        errors.append("audit_events.jsonl must include RUN_STARTED")

    artifacts = artifact_manifest.get("artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifact_manifest.json must contain artifacts")
    seen_paths: set[str] = set()
    generated_count = 0
    for artifact in artifacts if isinstance(artifacts, list) else []:
        if not isinstance(artifact, dict):
            errors.append("Every artifact must be an object")
            continue
        path_value = artifact.get("path")
        if not isinstance(path_value, str) or not path_value:
            errors.append("Every artifact must contain path")
            continue
        if path_value in seen_paths:
            errors.append(f"Duplicate artifact path: {path_value}")
        seen_paths.add(path_value)
        artifact_path = run_dir / path_value
        if not artifact_path.is_file():
            errors.append(f"Artifact path missing on disk: {path_value}")
            continue
        if not (ignore_artifact_manifest_self_hash and path_value == "artifact_manifest.json"):
            actual_hash = sha256_file(artifact_path)
            if artifact.get("sha256") != actual_hash:
                errors.append(f"Artifact hash mismatch for {path_value}")
        if path_value.startswith("generated/"):
            generated_count += 1
            owner = f"generated artifact {path_value}"
            require_non_empty_list(errors, owner, artifact, "requirement_ids")
            require_non_empty_list(errors, owner, artifact, "task_ids")
            require_non_empty_list(errors, owner, artifact, "policy_ids")
            require_non_empty_list(errors, owner, artifact, "evidence_refs")
            for req_id in artifact.get("requirement_ids", []):
                if req_id not in requirement_ids:
                    errors.append(f"{owner} references unknown requirement {req_id}")
            for task_id in artifact.get("task_ids", []):
                if task_id not in task_ids:
                    errors.append(f"{owner} references unknown task {task_id}")
            for policy_id in artifact.get("policy_ids", []):
                if policy_id not in policy_ids:
                    errors.append(f"{owner} references unknown policy {policy_id}")
    if generated_count == 0:
        errors.append("artifact_manifest.json must include at least one generated/ artifact")

    if require_passed_validation and validation_report.get("overall_status") != "passed":
        errors.append("validation_report.json overall_status must be passed")
    if factory_manifest.get("validation_status") not in {"passed", "pending"}:
        errors.append("factory_run_manifest.json validation_status must be passed or pending")

    limitations = (run_dir / "known_limitations.md").read_text(encoding="utf-8")
    for label in REQUIRED_HONESTY_LABELS:
        if label not in limitations:
            errors.append(f"known_limitations.md must mention {label}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Phase 7 governed factory run manifests.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-dir", help="Path to workspace/runs/<run_id>.")
    group.add_argument("--latest", action="store_true", help="Validate the latest run under workspace/runs.")
    parser.add_argument("--project-root", default=".", help="Repository root used with --latest.")
    parser.add_argument("--allow-pending-validation", action="store_true")
    parser.add_argument("--ignore-artifact-manifest-self-hash", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_dir = latest_run_dir(Path(args.project_root).resolve()) if args.latest else Path(args.run_dir).resolve()
        errors = validate_run_dir(
            run_dir,
            require_passed_validation=not args.allow_pending_validation,
            ignore_artifact_manifest_self_hash=args.ignore_artifact_manifest_self_hash,
        )
    except ValidationError as exc:
        errors = [str(exc)]
        run_dir = Path(args.project_root).resolve()

    payload = {"run_dir": str(run_dir), "passed": not errors, "errors": errors}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
