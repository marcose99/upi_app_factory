from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_ID = "upi_dispute_resolution"
PHASE = "phase34_operator_portal_governed_validation_runner"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase34"
)
DEFAULT_REPORT_PATH = ARTIFACT_DIR / "operator_portal_validation_run_report.json"
STDIO_PREVIEW_CHARS = 4000


@dataclass(frozen=True)
class AllowedValidationCommand:
    command_id: str
    description: str
    argv: tuple[str, ...]
    working_directory: Path = PROJECT_ROOT

    def as_report_entry(self) -> dict[str, Any]:
        command = [_portable_command_part(part) for part in self.argv]
        return {
            "command_id": self.command_id,
            "description": self.description,
            "command": command,
            "command_display": " ".join(command),
            "working_directory": _portable_working_directory(self.working_directory),
        }


ALLOWLIST: tuple[AllowedValidationCommand, ...] = (
    AllowedValidationCommand(
        "phase34_runner_self_check",
        "Small safe self-check used by the Phase 34 validator.",
        (sys.executable, "-c", "print('phase34 validation runner self-check')"),
    ),
    AllowedValidationCommand(
        "phase34_validator",
        "Validate the Phase 34 governed validation runner.",
        (sys.executable, "scripts/validate_phase34_operator_portal_validation_runner.py"),
    ),
    AllowedValidationCommand(
        "phase33_validator",
        "Validate the Phase 33 operator portal evidence dashboard.",
        (sys.executable, "scripts/validate_phase33_operator_portal_evidence_dashboard.py"),
    ),
    AllowedValidationCommand(
        "phase32_validator",
        "Validate the Phase 32 operator portal download center.",
        (sys.executable, "scripts/validate_phase32_operator_portal_download_center.py"),
    ),
    AllowedValidationCommand(
        "phase31_validator",
        "Validate the Phase 31 export/download center.",
        (sys.executable, "scripts/validate_phase31_deep_generated_application_export_download_center.py"),
    ),
    AllowedValidationCommand(
        "phase30_validator",
        "Validate the Phase 30 deep generated application regeneration.",
        (sys.executable, "scripts/validate_phase30_deep_generated_application_regeneration.py"),
    ),
    AllowedValidationCommand(
        "phase29_validator",
        "Validate the Phase 29 generated application deep structure generator.",
        (sys.executable, "scripts/validate_phase29_generated_application_deep_structure_generator.py"),
    ),
    AllowedValidationCommand(
        "phase28_validator",
        "Validate the Phase 28 generated application architecture depth blueprint.",
        (sys.executable, "scripts/validate_phase28_generated_application_architecture_depth_blueprint.py"),
    ),
)

DEFAULT_COMMAND_IDS = tuple(command.command_id for command in ALLOWLIST if command.command_id != "phase34_runner_self_check")


class CommandNotAllowedError(ValueError):
    """Raised when a caller requests a command outside the governed allowlist."""


def _portable_command_part(part: str) -> str:
    if part == sys.executable:
        return "python"
    try:
        path = Path(part)
        if path.is_absolute():
            return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        pass
    return part


def _portable_working_directory(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        home = Path.home().resolve()
        try:
            return "${HOME}/" + resolved.relative_to(home).as_posix()
        except ValueError:
            return "${WORKSPACE_ROOT}"
    return "." if relative == Path(".") else relative.as_posix()


class ValidationRunnerService:
    """Local-only governed validation runner for operator portal use."""

    def __init__(
        self,
        project_root: Path | None = None,
        report_path: Path | None = None,
        allowlist: tuple[AllowedValidationCommand, ...] = ALLOWLIST,
    ) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self.report_path = report_path or DEFAULT_REPORT_PATH
        self._allowlist = {command.command_id: command for command in allowlist}

    def list_allowed_commands(self) -> dict[str, Any]:
        return self._base_report(
            status="dry_run",
            dry_run=True,
            command_results=[
                self._command_for_id(command_id).as_report_entry()
                for command_id in DEFAULT_COMMAND_IDS
            ],
        )

    def run(
        self,
        command_ids: tuple[str, ...] | None = None,
        *,
        dry_run: bool = False,
        collect_all: bool = False,
        write_report: bool = True,
    ) -> dict[str, Any]:
        selected_ids = command_ids or DEFAULT_COMMAND_IDS
        selected = [self._command_for_id(command_id) for command_id in selected_ids]

        if dry_run:
            report = self._base_report(
                status="dry_run",
                dry_run=True,
                collect_all=collect_all,
                command_results=[command.as_report_entry() for command in selected],
            )
            if write_report:
                self._write_report(report)
            return report

        started = time.monotonic()
        results: list[dict[str, Any]] = []
        overall_status = "passed"
        for command in selected:
            result = self._execute(command)
            results.append(result)
            if result["status"] != "passed":
                overall_status = "failed"
                if not collect_all:
                    break

        report = self._base_report(
            status=overall_status,
            dry_run=False,
            collect_all=collect_all,
            command_results=results,
            duration_seconds=round(time.monotonic() - started, 6),
        )
        if write_report:
            self._write_report(report)
        return report

    def reject_unapproved_command(self, command_id: str) -> None:
        self._command_for_id(command_id)

    def _command_for_id(self, command_id: str) -> AllowedValidationCommand:
        if command_id not in self._allowlist:
            raise CommandNotAllowedError(f"Command is not approved for Phase 34: {command_id}")
        command = self._allowlist[command_id]
        if command.working_directory != PROJECT_ROOT:
            raise CommandNotAllowedError(f"Command has an unapproved working directory: {command_id}")
        return command

    def _execute(self, command: AllowedValidationCommand) -> dict[str, Any]:
        started = time.monotonic()
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(PROJECT_ROOT)
            if not existing_pythonpath
            else f"{PROJECT_ROOT}{os.pathsep}{existing_pythonpath}"
        )
        result = subprocess.run(
            list(command.argv),
            cwd=command.working_directory,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )
        duration = round(time.monotonic() - started, 6)
        return {
            **command.as_report_entry(),
            "return_code": result.returncode,
            "status": "passed" if result.returncode == 0 else "failed",
            "duration_seconds": duration,
            "stdout_preview": result.stdout[:STDIO_PREVIEW_CHARS],
            "stderr_preview": result.stderr[:STDIO_PREVIEW_CHARS],
        }

    def _base_report(
        self,
        *,
        status: str,
        dry_run: bool,
        command_results: list[dict[str, Any]],
        collect_all: bool = False,
        duration_seconds: float | None = None,
    ) -> dict[str, Any]:
        report: dict[str, Any] = {
            "app_id": APP_ID,
            "phase": PHASE,
            "status": status,
            "dry_run": dry_run,
            "collect_all": collect_all,
            "stop_on_first_failure": not collect_all,
            "command_results": command_results,
            "approved_command_ids": list(DEFAULT_COMMAND_IDS),
            "report_path": self._report_path_for_payload(),
            "safety_boundaries": {
                "certification_boundary": "certification_ready_not_certified",
                "official_certification_claimed": False,
                "official_certification_granted": False,
                "production_readiness_claimed": False,
                "live_provider_calls_allowed": False,
                "real_secrets_allowed": False,
                "deployment_allowed": False,
                "merge_allowed": False,
                "tag_allowed": False,
                "push_allowed": False,
                "external_ecosystem_integrations": "mocked_or_simulated_only",
                "arbitrary_shell_text_allowed": False,
                "shell_true_used": False,
            },
        }
        if duration_seconds is not None:
            report["duration_seconds"] = duration_seconds
        return report

    def _write_report(self, report: dict[str, Any]) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _report_path_for_payload(self) -> str:
        try:
            return str(self.report_path.relative_to(self.project_root))
        except ValueError:
            return str(self.report_path)


def list_allowed_commands() -> dict[str, Any]:
    return ValidationRunnerService().list_allowed_commands()


def run_validation(
    *,
    dry_run: bool = False,
    collect_all: bool = False,
    command_ids: tuple[str, ...] | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    return ValidationRunnerService().run(
        command_ids=command_ids,
        dry_run=dry_run,
        collect_all=collect_all,
        write_report=write_report,
    )
