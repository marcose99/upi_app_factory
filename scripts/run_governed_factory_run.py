#!/usr/bin/env python3
"""Create a deterministic governed factory run workspace.

Phase 7 intentionally models factory agents as deterministic governed roles.
It does not claim autonomous LLM execution. The point of this phase is to make
run evidence, artifact traceability, validation, and limitations machine-checkable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


def _phase11a2_stringify_dict_key(value: object) -> str:
    """Return a stable string key for manifest/prompt dictionaries."""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "/".join(str(item) for item in value)
    return str(value)

REQUIRED_HONESTY_LABELS = [
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
]

DEFAULT_REQUIREMENTS = [
    {
        "id": "REQ-P7-001",
        "title": "Create deterministic run workspace",
        "description": "Every governed factory execution must create an isolated workspace under workspace/runs/<run_id>/.",
    },
    {
        "id": "REQ-P7-002",
        "title": "Emit run-level manifests",
        "description": "Each run must emit factory, task, agent output, artifact, validation, limitation, release readiness, and audit evidence files.",
    },
    {
        "id": "REQ-P7-003",
        "title": "Preserve artifact traceability",
        "description": "Every generated artifact must link to requirement, task, policy, and evidence references.",
    },
    {
        "id": "REQ-P7-004",
        "title": "Reuse deterministic regeneration",
        "description": "The Phase 6 deterministic regeneration flow must be executed or explicitly recorded as skipped.",
    },
    {
        "id": "REQ-P7-005",
        "title": "Validate run completeness",
        "description": "A deterministic validator must fail incomplete, untraceable, or hash-mismatched factory runs.",
    },
]

DEFAULT_POLICIES = [
    {
        "id": "POL-MOCK-BOUNDARY",
        "title": "Mock boundary policy",
        "description": "Out-of-scope systems must remain explicit mocks.",
    },
    {
        "id": "POL-HONESTY-LABELS",
        "title": "Honesty label preservation policy",
        "description": "Known honesty labels must be preserved in run evidence.",
    },
    {
        "id": "POL-EVIDENCE-LEDGER",
        "title": "Evidence ledger policy",
        "description": "Run decisions and generated artifacts must be auditable.",
    },
    {
        "id": "POL-REGENERATION-READINESS",
        "title": "Regeneration readiness policy",
        "description": "Generated application artifacts must be reproducible through the deterministic regeneration path.",
    },
    {
        "id": "POL-BASELINE-PROVENANCE",
        "title": "Baseline provenance policy",
        "description": "The governed baseline source must remain hashed, preserved, and validated.",
    },
]

DEFAULT_TASKS = [
    {
        "id": "TASK-P7-001",
        "title": "Initialize governed factory run workspace",
        "requirement_ids": ["REQ-P7-001"],
        "policy_ids": ["POL-EVIDENCE-LEDGER"],
        "evidence_refs": ["factory_run_manifest.json", "audit_events.jsonl"],
    },
    {
        "id": "TASK-P7-002",
        "title": "Execute deterministic mock dispute app regeneration",
        "requirement_ids": ["REQ-P7-004"],
        "policy_ids": ["POL-REGENERATION-READINESS", "POL-MOCK-BOUNDARY"],
        "evidence_refs": ["generated/", "agent_outputs.jsonl", "audit_events.jsonl"],
    },
    {
        "id": "TASK-P7-003",
        "title": "Collect generated artifacts and hashes",
        "requirement_ids": ["REQ-P7-003"],
        "policy_ids": ["POL-EVIDENCE-LEDGER"],
        "evidence_refs": ["artifact_manifest.json"],
    },
    {
        "id": "TASK-P7-004",
        "title": "Emit traceable run evidence artifacts",
        "requirement_ids": ["REQ-P7-002", "REQ-P7-003"],
        "policy_ids": ["POL-EVIDENCE-LEDGER", "POL-HONESTY-LABELS"],
        "evidence_refs": [
            "factory_run_manifest.json",
            "task_manifest.json",
            "agent_outputs.jsonl",
            "artifact_manifest.json",
            "known_limitations.md",
            "release_readiness_report.md",
        ],
    },
    {
        "id": "TASK-P7-005",
        "title": "Run deterministic validation gates",
        "requirement_ids": ["REQ-P7-005"],
        "policy_ids": [
            "POL-MOCK-BOUNDARY",
            "POL-EVIDENCE-LEDGER",
            "POL-REGENERATION-READINESS",
            "POL-BASELINE-PROVENANCE",
        ],
        "evidence_refs": ["validation_report.json"],
    },
]

VALIDATION_COMMANDS = [
    ["make", "validate"],
    ["make", "validate-combined-phases"],
    ["make", "validate-regeneration"],
    ["make", "validate-baseline-provenance"],
]

RUN_LEVEL_ARTIFACTS = [
    "factory_run_manifest.json",
    "task_manifest.json",
    "agent_outputs.jsonl",
    "artifact_manifest.json",
    "validation_report.json",
    "known_limitations.md",
    "release_readiness_report.md",
    "audit_events.jsonl",
]


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    started_at_utc: str
    finished_at_utc: str


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def run_command(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> CommandResult:
    started = utc_now()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        started_at_utc=started,
        finished_at_utc=utc_now(),
    )


def git_value(repo_root: Path, args: list[str], fallback: str = "UNKNOWN") -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    value = result.stdout.strip()
    return value or fallback


def safe_run_id(candidate: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    cleaned = "".join(ch if ch in allowed else "-" for ch in candidate.strip())
    return cleaned or dt.datetime.now(dt.timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_generated_artifacts(repo_root: Path, run_id: str, run_dir: Path, skip_regeneration: bool) -> tuple[list[CommandResult], str]:
    generated_dir = run_dir / "generated"
    ensure_clean_dir(generated_dir)

    if skip_regeneration:
        placeholder = generated_dir / "SKIPPED_REGENERATION.md"
        placeholder.write_text(
            "# Skipped Regeneration\n\n"
            "Regeneration was explicitly skipped for this factory run. "
            "This is acceptable only for validator or dry-run testing.\n",
            encoding="utf-8",
        )
        return [], "skipped"

    script_path = repo_root / "scripts" / "regenerate_mock_dispute_app.sh"
    if not script_path.exists():
        placeholder = generated_dir / "MISSING_REGENERATION_SCRIPT.md"
        placeholder.write_text(
            "# Missing Regeneration Script\n\n"
            "scripts/regenerate_mock_dispute_app.sh was not found. "
            "The Phase 7 run workspace was still created so the missing dependency is auditable.\n",
            encoding="utf-8",
        )
        return [], "missing_regeneration_script"

    regeneration_run_id = f"{run_id}_regeneration"
    env = dict(os.environ)
    env["RUN_ID"] = regeneration_run_id
    command_result = run_command([str(script_path)], cwd=repo_root, env=env)

    source_generated_dir = repo_root / "workspace" / "regeneration_runs" / regeneration_run_id / "generated"
    if command_result.returncode == 0 and source_generated_dir.exists():
        shutil.rmtree(generated_dir)
        shutil.copytree(source_generated_dir, generated_dir)
        status = "completed"
    else:
        failure_file = generated_dir / "REGENERATION_FAILED.md"
        failure_file.write_text(
            "# Regeneration Failed\n\n"
            f"Command: `{script_path}`\n\n"
            f"Return code: `{command_result.returncode}`\n\n"
            "The command output is captured in agent_outputs.jsonl and validation_report.json.\n",
            encoding="utf-8",
        )
        status = "failed"

    return [command_result], status


def task_index() -> dict[str, dict[str, Any]]:
    return {_phase11a2_stringify_dict_key(task["id"]): task for task in DEFAULT_TASKS}


def artifact_trace_for(relative_path: str) -> dict[str, list[str]]:
    # Phase 7 applies broad traceability at this maturity level. Later phases can
    # replace this with fine-grained per-file task mapping from real agent plans.
    if relative_path.startswith("generated/"):
        return {
            "requirement_ids": ["REQ-P7-003", "REQ-P7-004"],
            "task_ids": ["TASK-P7-002", "TASK-P7-003"],
            "policy_ids": ["POL-MOCK-BOUNDARY", "POL-REGENERATION-READINESS", "POL-EVIDENCE-LEDGER"],
            "evidence_refs": ["agent_outputs.jsonl", "audit_events.jsonl", "artifact_manifest.json"],
        }
    if relative_path == "validation_report.json":
        return {
            "requirement_ids": ["REQ-P7-005"],
            "task_ids": ["TASK-P7-005"],
            "policy_ids": ["POL-EVIDENCE-LEDGER"],
            "evidence_refs": ["validation_report.json", "audit_events.jsonl"],
        }
    return {
        "requirement_ids": ["REQ-P7-002", "REQ-P7-003"],
        "task_ids": ["TASK-P7-004"],
        "policy_ids": ["POL-EVIDENCE-LEDGER", "POL-HONESTY-LABELS"],
        "evidence_refs": ["factory_run_manifest.json", "task_manifest.json", "audit_events.jsonl"],
    }


def discover_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(run_dir).as_posix()
        if relative_path == "artifact_manifest.json":
            continue
        trace = artifact_trace_for(relative_path)
        artifacts.append(
            {
                "path": relative_path,
                "artifact_type": "generated" if relative_path.startswith("generated/") else "run_evidence",
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                **trace,
            }
        )
    return artifacts


def make_task_manifest(status: str) -> dict[str, Any]:
    tasks = []
    for task in DEFAULT_TASKS:
        task_copy = dict(task)
        task_copy["status"] = status
        tasks.append(task_copy)
    return cast(dict[str, Any], {
        "schema_version": "factory.task_manifest.v1",
        "honesty_labels": REQUIRED_HONESTY_LABELS,
        "tasks": tasks,
    })


def write_agent_outputs(path: Path, run_id: str, regeneration_results: list[CommandResult], regeneration_status: str) -> None:
    if path.exists():
        path.unlink()
    outputs = [
        {
            "run_id": run_id,
            "agent_name": "run_intake_agent",
            "agent_execution_model": "deterministic_role_agent",
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL"],
            "task_ids": ["TASK-P7-001"],
            "requirement_ids": ["REQ-P7-001"],
            "summary": "Created governed run workspace and initialized run evidence model.",
        },
        {
            "run_id": run_id,
            "agent_name": "regeneration_agent",
            "agent_execution_model": "deterministic_role_agent",
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL", "MOCK_BOUNDARY", "SYNTHETIC_DATA"],
            "task_ids": ["TASK-P7-002"],
            "requirement_ids": ["REQ-P7-004"],
            "summary": f"Deterministic regeneration status: {regeneration_status}.",
            "commands": [result.__dict__ for result in regeneration_results],
        },
        {
            "run_id": run_id,
            "agent_name": "traceability_agent",
            "agent_execution_model": "deterministic_role_agent",
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL"],
            "task_ids": ["TASK-P7-003", "TASK-P7-004"],
            "requirement_ids": ["REQ-P7-002", "REQ-P7-003"],
            "summary": "Mapped artifacts to requirement, task, policy, and evidence references.",
        },
        {
            "run_id": run_id,
            "agent_name": "validation_agent",
            "agent_execution_model": "deterministic_role_agent",
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL"],
            "task_ids": ["TASK-P7-005"],
            "requirement_ids": ["REQ-P7-005"],
            "summary": "Prepared deterministic validation gates for this run.",
        },
    ]
    for output in outputs:
        append_jsonl(path, cast(dict[str, Any], output))


def write_known_limitations(path: Path, run_id: str, regeneration_status: str) -> None:
    path.write_text(
        f"# Known Limitations for Factory Run `{run_id}`\n\n"
        "## Honesty labels preserved\n\n"
        "- MISSING_OFFICIAL_SOURCE\n"
        "- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL\n"
        "- MOCK_BOUNDARY\n"
        "- SYNTHETIC_DATA\n\n"
        "## Current Phase 7 limitations\n\n"
        "1. Phase 7 uses deterministic role-agents, not autonomous LLM agents.\n"
        "2. Generated UPI ecosystem dependencies remain explicit mocks.\n"
        "3. Official NPCI/RBI dispute workflow sources remain outside this baseline unless separately supplied and cited.\n"
        "4. Artifact traceability is run-level and task-level; later phases can add finer-grained design-to-code mappings.\n"
        f"5. Regeneration status for this run: `{regeneration_status}`.\n",
        encoding="utf-8",
    )


def write_release_readiness(path: Path, run_id: str, overall_status: str, regeneration_status: str) -> None:
    recommendation = "ready for branch review" if overall_status == "passed" else "not ready for merge"
    path.write_text(
        f"# Release Readiness Report for Factory Run `{run_id}`\n\n"
        f"Overall status: **{overall_status}**\n\n"
        f"Regeneration status: **{regeneration_status}**\n\n"
        f"Recommendation: **{recommendation}**\n\n"
        "## Required review points\n\n"
        "- Confirm `validation_report.json` shows all required gates passing.\n"
        "- Confirm `artifact_manifest.json` hashes all generated artifacts.\n"
        "- Confirm every generated artifact has requirement, task, policy, and evidence links.\n"
        "- Confirm mock boundaries and honesty labels remain visible to reviewers.\n",
        encoding="utf-8",
    )


def run_validations(repo_root: Path, run_dir: Path, skip_project_validations: bool) -> dict[str, Any]:
    validation_results: list[dict[str, Any]] = []
    if skip_project_validations:
        validation_results.append(
            {
                "command": ["project_validations"],
                "returncode": 0,
                "status": "skipped",
                "reason": "Skipped by --skip-project-validations.",
                "started_at_utc": utc_now(),
                "finished_at_utc": utc_now(),
                "stdout": "",
                "stderr": "",
            }
        )
    else:
        for command in VALIDATION_COMMANDS:
            result = run_command(command, cwd=repo_root)
            validation_results.append({**result.__dict__, "status": "passed" if result.returncode == 0 else "failed"})

    validator_result = run_command(
        [
            sys.executable,
            "scripts/validate_factory_run_manifest.py",
            "--run-dir",
            str(run_dir),
            "--allow-pending-validation",
        ],
        cwd=repo_root,
    )
    validation_results.append(
        {**validator_result.__dict__, "status": "passed" if validator_result.returncode == 0 else "failed"}
    )

    overall_status = "passed" if all(item.get("returncode", 1) == 0 for item in validation_results) else "failed"
    return cast(dict[str, Any], {
        "schema_version": "factory.validation_report.v1",
        "overall_status": overall_status,
        "generated_at_utc": utc_now(),
        "results": validation_results,
    })


def create_initial_validation_report(path: Path) -> None:
    write_json(
        path,
        {
            "schema_version": "factory.validation_report.v1",
            "overall_status": "pending",
            "generated_at_utc": utc_now(),
            "results": [],
        },
    )


def build_factory_run(args: argparse.Namespace) -> int:
    repo_root = Path(args.project_root).resolve()
    run_id = safe_run_id(args.run_id or os.environ.get("RUN_ID", ""))
    if not run_id:
        run_id = dt.datetime.now(dt.timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")

    run_dir = repo_root / "workspace" / "runs" / run_id
    if run_dir.exists() and not args.force:
        print(f"ERROR: Run directory already exists: {run_dir}", file=sys.stderr)
        return 2
    ensure_clean_dir(run_dir)

    audit_path = run_dir / "audit_events.jsonl"
    append_jsonl(
        audit_path,
        cast(dict[str, Any], {
            "event_type": "RUN_STARTED",
            "run_id": run_id,
            "occurred_at_utc": utc_now(),
            "workspace": str(run_dir),
        }),
    )

    regeneration_results, regeneration_status = copy_generated_artifacts(
        repo_root=repo_root,
        run_id=run_id,
        run_dir=run_dir,
        skip_regeneration=args.skip_regeneration,
    )
    append_jsonl(
        audit_path,
        cast(dict[str, Any], {
            "event_type": "REGENERATION_STATUS_RECORDED",
            "run_id": run_id,
            "occurred_at_utc": utc_now(),
            "regeneration_status": regeneration_status,
        }),
    )

    task_status = "completed" if regeneration_status in {"completed", "skipped"} else "completed_with_limitations"
    write_json(run_dir / "task_manifest.json", make_task_manifest(task_status))
    write_agent_outputs(run_dir / "agent_outputs.jsonl", run_id, regeneration_results, regeneration_status)
    create_initial_validation_report(run_dir / "validation_report.json")
    write_known_limitations(run_dir / "known_limitations.md", run_id, regeneration_status)
    write_release_readiness(run_dir / "release_readiness_report.md", run_id, "pending", regeneration_status)

    factory_manifest = {
        "schema_version": "factory.run_manifest.v1",
        "run_id": run_id,
        "created_at_utc": utc_now(),
        "workspace": run_dir.relative_to(repo_root).as_posix(),
        "source": {
            "branch": git_value(repo_root, ["branch", "--show-current"]),
            "head": git_value(repo_root, ["rev-parse", "HEAD"]),
            "head_short": git_value(repo_root, ["rev-parse", "--short", "HEAD"]),
            "restore_point": args.restore_point,
        },
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "requirements": DEFAULT_REQUIREMENTS,
        "policies": DEFAULT_POLICIES,
        "honesty_labels": REQUIRED_HONESTY_LABELS,
        "mock_boundaries": [
            "mock_upi_switch",
            "mock_core_banking",
            "mock_customer_notification",
            "mock_dispute_evidence_store",
        ],
        "required_run_artifacts": RUN_LEVEL_ARTIFACTS,
        "regeneration_status": regeneration_status,
        "validation_status": "pending",
    }
    write_json(run_dir / "factory_run_manifest.json", factory_manifest)

    artifacts = discover_artifacts(run_dir)
    write_json(
        run_dir / "artifact_manifest.json",
        {
            "schema_version": "factory.artifact_manifest.v1",
            "run_id": run_id,
            "created_at_utc": utc_now(),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        },
    )

    # Re-discover so artifact_manifest itself is included and hash-current.
    artifacts = discover_artifacts(run_dir)
    write_json(
        run_dir / "artifact_manifest.json",
        {
            "schema_version": "factory.artifact_manifest.v1",
            "run_id": run_id,
            "created_at_utc": utc_now(),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        },
    )

    validation_report = run_validations(repo_root, run_dir, args.skip_project_validations)
    write_json(run_dir / "validation_report.json", validation_report)
    factory_manifest["validation_status"] = validation_report["overall_status"]
    write_json(run_dir / "factory_run_manifest.json", factory_manifest)
    write_release_readiness(
        run_dir / "release_readiness_report.md",
        run_id,
        validation_report["overall_status"],
        regeneration_status,
    )

    artifacts = discover_artifacts(run_dir)
    write_json(
        run_dir / "artifact_manifest.json",
        {
            "schema_version": "factory.artifact_manifest.v1",
            "run_id": run_id,
            "created_at_utc": utc_now(),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        },
    )
    # Final validation after final hashes have been written. This updates the validation report once more,
    # then artifact_manifest once more to avoid stale hashes for validation_report and factory_run_manifest.
    final_validator_result = run_command(
        [sys.executable, "scripts/validate_factory_run_manifest.py", "--run-dir", str(run_dir), "--ignore-artifact-manifest-self-hash"],
        cwd=repo_root,
    )
    validation_report["results"].append(
        {
            **final_validator_result.__dict__,
            "status": "passed" if final_validator_result.returncode == 0 else "failed",
            "phase": "final_manifest_validation",
        }
    )
    validation_report["overall_status"] = (
        "passed" if all(item.get("returncode", 1) == 0 for item in validation_report["results"]) else "failed"
    )
    write_json(run_dir / "validation_report.json", validation_report)
    factory_manifest["validation_status"] = validation_report["overall_status"]
    write_json(run_dir / "factory_run_manifest.json", factory_manifest)
    write_release_readiness(
        run_dir / "release_readiness_report.md",
        run_id,
        validation_report["overall_status"],
        regeneration_status,
    )
    append_jsonl(
        audit_path,
        cast(dict[str, Any], {
            "event_type": "RUN_COMPLETED",
            "run_id": run_id,
            "occurred_at_utc": utc_now(),
            "validation_status": validation_report["overall_status"],
            "workspace": str(run_dir),
        }),
    )

    artifacts = discover_artifacts(run_dir)
    write_json(
        run_dir / "artifact_manifest.json",
        {
            "schema_version": "factory.artifact_manifest.v1",
            "run_id": run_id,
            "created_at_utc": utc_now(),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        },
    )

    print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "status": validation_report["overall_status"]}, indent=2))
    return 0 if validation_report["overall_status"] == "passed" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a governed factory run workspace.")
    parser.add_argument("--project-root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--run-id", default="", help="Run id. Defaults to RUN_ID env var or timestamp.")
    parser.add_argument("--restore-point", default="v0.6.0-regeneration-automation")
    parser.add_argument("--force", action="store_true", help="Replace existing workspace/runs/<run_id>.")
    parser.add_argument("--skip-regeneration", action="store_true", help="Create run evidence without executing regeneration.")
    parser.add_argument("--skip-project-validations", action="store_true", help="Skip existing project make validation gates.")
    return parser.parse_args()


def main() -> int:
    return build_factory_run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
