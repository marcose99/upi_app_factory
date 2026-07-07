#!/usr/bin/env python3
"""Build read-only status data for the local Factory Operator Portal."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_ID = "upi_dispute_resolution"
PORTAL_STATUS = "LOCAL_OPERATOR_PORTAL_STATUS_READY"

PHASES: tuple[str, ...] = (
    "phase13aq",
    "phase13ar",
    "phase13as",
    "phase13at",
    "phase13au",
    "phase13av",
    "phase13aw",
)

PORTAL_SECTIONS: tuple[str, ...] = (
    "factory_health",
    "phase_status",
    "evidence_summary",
    "standards_summary",
    "self_healing_summary",
    "agentic_threat_summary",
    "handover_summary",
    "safe_command_catalog",
)


@dataclass(frozen=True)
class SafeCommand:
    """Display-only safe command description."""

    command_id: str
    title: str
    command: str
    execution_enabled_in_portal: bool
    requires_human_terminal_execution: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "command_id": self.command_id,
            "execution_enabled_in_portal": self.execution_enabled_in_portal,
            "requires_human_terminal_execution": self.requires_human_terminal_execution,
            "title": self.title,
        }


def _run_git(args: list[str], project_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"

    if completed.returncode != 0:
        return "unavailable"
    return completed.stdout.strip() or "unavailable"


def _exists(path: Path) -> bool:
    return path.exists()


def _artifact_path(project_root: Path, phase: str, filename: str) -> Path:
    return (
        project_root
        / "workspace"
        / "factory_generated"
        / APP_ID
        / "lifecycle_artifacts"
        / phase
        / filename
    )


def _evidence_summary(project_root: Path) -> dict[str, object]:
    evidence_files = {
        "phase13aq": "fresh_recipient_handover_replay_audit.json",
        "phase13ar": "governed_self_healing_repair_catalog_audit.json",
        "phase13as": "local_industry_standards_control_matrix_audit.json",
        "phase13at": "autonomous_phase_engineering_runner_audit.json",
        "phase13au": "low_risk_autonomous_repair_audit.json",
        "phase13av": "local_agentic_ai_threat_test_audit.json",
        "phase13aw": "local_operator_portal_audit.json",
    }
    items = {
        phase: {
            "path": str(_artifact_path(project_root, phase, filename).relative_to(project_root)),
            "present": _exists(_artifact_path(project_root, phase, filename)),
        }
        for phase, filename in evidence_files.items()
    }
    return {
        "all_required_evidence_present": all(
            bool(item["present"]) for item in items.values()
        ),
        "items": items,
    }


def _phase_status(project_root: Path) -> dict[str, object]:
    validators = {
        "phase13aq": "scripts/validate_phase13aq_fresh_recipient_replay.py",
        "phase13ar": "scripts/validate_phase13ar_self_healing_repair_catalog.py",
        "phase13as": "scripts/validate_phase13as_standards_control_matrix.py",
        "phase13at": "scripts/validate_phase13at_autonomous_runner.py",
        "phase13au": "scripts/validate_phase13au_low_risk_repair_applier.py",
        "phase13av": "scripts/validate_phase13av_agentic_ai_threat_tests.py",
        "phase13aw": "scripts/validate_phase13aw_operator_portal.py",
    }
    return {
        phase: {
            "validator": validator,
            "validator_present": _exists(project_root / validator),
            "test_present": bool(list((project_root / "tests").glob(f"test_{phase}*.py"))),
        }
        for phase, validator in validators.items()
    }


def _safe_commands() -> tuple[SafeCommand, ...]:
    return (
        SafeCommand(
            command_id="VALIDATE_PHASE13AV",
            title="Validate agentic-AI threat tests",
            command="python scripts/validate_phase13av_agentic_ai_threat_tests.py",
            execution_enabled_in_portal=False,
            requires_human_terminal_execution=True,
        ),
        SafeCommand(
            command_id="VALIDATE_PHASE13AW",
            title="Validate local operator portal",
            command="python scripts/validate_phase13aw_operator_portal.py",
            execution_enabled_in_portal=False,
            requires_human_terminal_execution=True,
        ),
        SafeCommand(
            command_id="RUN_FULL_TESTS",
            title="Run full test suite",
            command="python -m pytest",
            execution_enabled_in_portal=False,
            requires_human_terminal_execution=True,
        ),
        SafeCommand(
            command_id="RUN_RUFF",
            title="Run Ruff checks",
            command="python -m ruff check .",
            execution_enabled_in_portal=False,
            requires_human_terminal_execution=True,
        ),
        SafeCommand(
            command_id="RUN_MYPY",
            title="Run MyPy checks",
            command="python -m mypy .",
            execution_enabled_in_portal=False,
            requires_human_terminal_execution=True,
        ),
    )


def build_local_operator_portal_status(project_root: Path) -> dict[str, Any]:
    """Build read-only local operator portal status."""

    root = project_root.resolve()
    evidence = _evidence_summary(root)
    phase_status = _phase_status(root)

    return {
        "app_id": APP_ID,
        "arbitrary_shell_execution_exposed_from_ui": False,
        "auto_merge_enabled_from_ui": False,
        "auto_release_enabled_from_ui": False,
        "auto_tag_enabled_from_ui": False,
        "external_system_calls_enabled": False,
        "factory_health": {
            "current_branch": _run_git(["branch", "--show-current"], root),
            "latest_tag": _run_git(["describe", "--tags", "--abbrev=0"], root),
            "portal_status": PORTAL_STATUS,
            "project_root": str(root),
            "python_required": "3.10.x",
        },
        "phase_status": phase_status,
        "evidence_summary": evidence,
        "standards_summary": {
            "control_matrix_present": _exists(root / "scripts/build_local_industry_standards_control_matrix.py"),
            "validator_present": _exists(root / "scripts/validate_phase13as_standards_control_matrix.py"),
            "evidence_present": bool(
                evidence["items"]["phase13as"]["present"]  # type: ignore[index]
            ),
        },
        "self_healing_summary": {
            "repair_catalog_present": _exists(root / "scripts/build_governed_self_healing_repair_catalog.py"),
            "low_risk_repair_applier_present": _exists(root / "scripts/apply_governed_low_risk_repair.py"),
            "worktree_auto_repair_enabled": False,
        },
        "agentic_threat_summary": {
            "threat_suite_present": _exists(root / "scripts/build_local_agentic_ai_threat_tests.py"),
            "validator_present": _exists(root / "scripts/validate_phase13av_agentic_ai_threat_tests.py"),
            "live_provider_calls_enabled": False,
        },
        "handover_summary": {
            "fresh_recipient_replay_present": _exists(root / "scripts/build_fresh_recipient_handover_replay_pack.py"),
            "handover_replay_validator_present": _exists(root / "scripts/validate_phase13aq_fresh_recipient_replay.py"),
            "local_only": True,
        },
        "safe_command_catalog": [command.to_dict() for command in _safe_commands()],
        "schema_version": "local-operator-portal-status.v1",
        "sections": list(PORTAL_SECTIONS),
    }


def write_local_operator_portal_status(status: dict[str, Any], audit_out: Path) -> None:
    """Write deterministic portal status JSON."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_local_operator_portal_status(status: dict[str, Any]) -> list[str]:
    """Validate portal status safety and completeness."""

    failures: list[str] = []

    if status.get("schema_version") != "local-operator-portal-status.v1":
        failures.append("Invalid portal status schema")
    if status.get("app_id") != APP_ID:
        failures.append("Unexpected app_id")
    if set(status.get("sections", [])) != set(PORTAL_SECTIONS):
        failures.append("Portal must include every required section")

    for key in [
        "arbitrary_shell_execution_exposed_from_ui",
        "auto_merge_enabled_from_ui",
        "auto_tag_enabled_from_ui",
        "auto_release_enabled_from_ui",
        "external_system_calls_enabled",
    ]:
        if status.get(key) is not False:
            failures.append(f"{key} must be false")

    commands = status.get("safe_command_catalog", [])
    if not isinstance(commands, list) or not commands:
        failures.append("Safe command catalog is required")
    else:
        for command in commands:
            if not isinstance(command, dict):
                failures.append("Safe command entries must be objects")
                continue
            if command.get("execution_enabled_in_portal") is not False:
                failures.append("Portal command execution must remain disabled")
            if command.get("requires_human_terminal_execution") is not True:
                failures.append("Safe commands must require human terminal execution")

    evidence_summary = status.get("evidence_summary", {})
    if not isinstance(evidence_summary, dict):
        failures.append("Evidence summary must be an object")
    elif "items" not in evidence_summary:
        failures.append("Evidence summary must include items")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local operator portal status.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    status = build_local_operator_portal_status(args.project_root)

    if args.audit_out is not None:
        write_local_operator_portal_status(status, args.audit_out)

    print(json.dumps(status, indent=2, sort_keys=True))

    failures = validate_local_operator_portal_status(status)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
