from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
PHASE = "phase43_one_command_demo_reviewer_pack"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_APP_ROOT = PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "generated_application"
ARTIFACT_DIR = (
    PROJECT_ROOT / "workspace/factory_generated" / APP_ID / "lifecycle_artifacts" / "phase43"
)
DEFAULT_REPORT_PATH = ARTIFACT_DIR / "one_command_demo_report.json"
STDIO_PREVIEW_CHARS = 4000


@dataclass(frozen=True)
class DemoCommand:
    command_id: str
    description: str
    argv: tuple[str, ...]
    working_directory: Path = PROJECT_ROOT
    execution_mode: str = "staged"

    def as_report_entry(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "description": self.description,
            "command": list(self.argv),
            "command_display": " ".join(self.argv),
            "working_directory": str(self.working_directory),
            "execution_mode": self.execution_mode,
        }


STAGED_COMMANDS: tuple[DemoCommand, ...] = (
    DemoCommand(
        command_id="validate_phase43_reviewer_pack",
        description="Validate Phase 43 governance, artifacts, and reviewer-pack boundaries.",
        argv=(sys.executable, "scripts/validate_phase43_one_command_demo_reviewer_pack.py"),
    ),
    DemoCommand(
        command_id="validate_generated_app_local_run_pack",
        description="Run the generated app local run-pack validation using mock-only ASGI checks.",
        argv=(
            sys.executable,
            "workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/"
            "validate_local_run_pack.py",
        ),
    ),
    DemoCommand(
        command_id="start_generated_app_local_server",
        description="Start the local generated FastAPI app with mocked external ecosystem mode.",
        argv=(
            "workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/"
            "start_local.sh",
        ),
    ),
    DemoCommand(
        command_id="run_generated_app_smoke_test",
        description="Run the generated app smoke test against the mock-only local application flow.",
        argv=(
            sys.executable,
            "workspace/factory_generated/upi_dispute_resolution/generated_application/scripts/"
            "smoke_test.py",
        ),
    ),
    DemoCommand(
        command_id="inspect_reviewer_pack",
        description="Inspect the reviewer pack and lifecycle evidence before interview review.",
        argv=(
            "sed",
            "-n",
            "1,220p",
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase43/"
            "reviewer_pack.md",
        ),
    ),
)

SAFE_AUTOMATED_COMMAND_IDS = (
    "validate_generated_app_local_run_pack",
    "run_generated_app_smoke_test",
)


def safety_boundaries() -> dict[str, Any]:
    return {
        "certification_boundary": "certification_ready_not_certified",
        "official_certification_claimed": False,
        "official_certification_granted": False,
        "production_readiness_claimed": False,
        "production_readiness_scope": "not_claimed; local-readiness checks only",
        "live_provider_calls_allowed": False,
        "real_secrets_allowed": False,
        "deployment_allowed": False,
        "merge_allowed": False,
        "tag_allowed": False,
        "push_allowed": False,
        "external_ecosystem_integrations": "mocked_or_simulated_only",
        "real_payment_rails_enabled": False,
        "long_running_server_auto_start_allowed": False,
    }


def reviewer_pack_sections() -> dict[str, str]:
    return {
        "what_the_factory_does": (
            "UPI App Factory assembles governed software-factory artifacts and a locally "
            "runnable generated UPI dispute-resolution application. The generated application "
            "supports synthetic dispute intake, mock ecosystem checks, local persistence, audit "
            "events, and reviewer-facing validation evidence."
        ),
        "how_to_run_it": (
            "Use `make phase43-demo-reviewer-pack` from the repository root to print exact "
            "staged reviewer commands. Use `scripts/run_phase43_one_command_demo_reviewer_pack.py "
            "--run-safe-checks` for bounded mock-only checks that do not start a long-running "
            "server."
        ),
        "what_evidence_to_inspect": (
            "Inspect the Phase 43 reviewer pack, one-command demo manifest, gate, audit, "
            "policy, prompt, Phase 34 validation runner report, and the generated app local "
            "run-pack smoke/validation outputs."
        ),
        "what_is_intentionally_mocked": (
            "UPI rails, NPCI/RBI interfaces, banks, PSPs, payment rails, ODR systems, "
            "notifications, customer systems, upstream/downstream integrations, and third-party "
            "services remain mocked or simulated."
        ),
        "certification_ready_not_certified_boundary": (
            "The posture is certification_ready_not_certified. The pack does not claim official "
            "certification, approval, live payment capability, legal sufficiency, or broad "
            "production readiness."
        ),
        "known_limitations": (
            "The demo is local and synthetic, does not connect to external ecosystems, does not "
            "create real credentials, does not deploy, and does not replace formal compliance, "
            "security, performance, or certification review."
        ),
    }


def build_staged_command_report() -> dict[str, Any]:
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "status": "staged_commands",
        "one_command": "make phase43-demo-reviewer-pack",
        "script_command": (
            f"{sys.executable} scripts/run_phase43_one_command_demo_reviewer_pack.py"
        ),
        "reason_for_staged_commands": (
            "A fully automated demo would need to start a long-running local web server. "
            "The reviewer command therefore prints exact staged commands by default."
        ),
        "staged_commands": [command.as_report_entry() for command in STAGED_COMMANDS],
        "safe_automated_command_ids": list(SAFE_AUTOMATED_COMMAND_IDS),
        "reviewer_pack_sections": reviewer_pack_sections(),
        "safety_boundaries": safety_boundaries(),
    }


def run_safe_checks(*, report_path: Path = DEFAULT_REPORT_PATH) -> dict[str, Any]:
    started = time.monotonic()
    selected = {
        command.command_id: command
        for command in STAGED_COMMANDS
        if command.command_id in SAFE_AUTOMATED_COMMAND_IDS
    }
    results = [_execute(selected[command_id]) for command_id in SAFE_AUTOMATED_COMMAND_IDS]
    status = "passed" if all(result["status"] == "passed" for result in results) else "failed"
    report = {
        **build_staged_command_report(),
        "status": status,
        "dry_run": False,
        "executed_command_results": results,
        "duration_seconds": round(time.monotonic() - started, 6),
        "report_path": _report_path_for_payload(report_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _report_path_for_payload(report_path: Path) -> str:
    try:
        return str(report_path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(report_path)


def _execute(command: DemoCommand) -> dict[str, Any]:
    started = time.monotonic()
    result = subprocess.run(
        list(command.argv),
        cwd=command.working_directory,
        check=False,
        text=True,
        capture_output=True,
    )
    return {
        **command.as_report_entry(),
        "return_code": result.returncode,
        "status": "passed" if result.returncode == 0 else "failed",
        "duration_seconds": round(time.monotonic() - started, 6),
        "stdout_preview": result.stdout[:STDIO_PREVIEW_CHARS],
        "stderr_preview": result.stderr[:STDIO_PREVIEW_CHARS],
    }
