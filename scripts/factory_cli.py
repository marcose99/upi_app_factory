#!/usr/bin/env python3
"""Operator command surface for the governed UPI dispute factory."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"
PHASE = "Phase 13E"
ROOT_COMMAND = "factoryctl"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python3"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
GENERATED_ROOT = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID
AUDIT_PORTAL = GENERATED_ROOT / "audit_portal"
RUN_LOGS = GENERATED_ROOT / "run_logs"


def env() -> dict[str, str]:
    merged = os.environ.copy()
    src = str(PROJECT_ROOT / "src")
    old = merged.get("PYTHONPATH")
    merged["PYTHONPATH"] = src if not old else src + os.pathsep + old
    return merged


def run_command(args: list[str], *, check: bool = True) -> int:
    print("+ " + " ".join(args))
    completed = subprocess.run(
        args,
        cwd=str(PROJECT_ROOT),
        env=env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if check and completed.returncode != 0:
        return completed.returncode
    return completed.returncode


def current_branch() -> str:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip() or "unknown"


def latest_tag() -> str:
    completed = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip() or "unknown"


def status_payload() -> dict[str, Any]:
    return {
        "app_id": APP_ID,
        "phase": PHASE,
        "run_id": RUN_ID,
        "root_command": f"./{ROOT_COMMAND}",
        "current_branch": current_branch(),
        "latest_tag": latest_tag(),
        "default_execution": "local_deterministic",
        "truth_boundary": (
            "The operator CLI does not claim active LangGraph/OpenAI execution. "
            "The default execution path remains local deterministic. "
            "External adapters remain detected and policy-gated."
        ),
        "key_commands": [
            f"./{ROOT_COMMAND} status",
            f"./{ROOT_COMMAND} adapters",
            f"./{ROOT_COMMAND} validate --quick",
            f"./{ROOT_COMMAND} validate",
            f"./{ROOT_COMMAND} portals",
            f"./{ROOT_COMMAND} handover",
            f"./{ROOT_COMMAND} logs",
        ],
        "portals": {
            "phase13b_progress": str(AUDIT_PORTAL / "factory_generation_progress_portal.html"),
            "phase13c_runtime": str(AUDIT_PORTAL / "factory_agent_runtime_portal.html"),
            "phase13d_adapters": str(AUDIT_PORTAL / "factory_agent_adapter_portal.html"),
            "phase13e_cli": str(AUDIT_PORTAL / "factory_cli_operator_portal.html"),
        },
    }


def command_status(args: argparse.Namespace) -> int:
    payload = status_payload()
    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print("UPI App Factory operator status")
    print(f"App ID        : {payload['app_id']}")
    print(f"Phase         : {payload['phase']}")
    print(f"Run ID        : {payload['run_id']}")
    print(f"Root command  : {payload['root_command']}")
    print(f"Branch        : {payload['current_branch']}")
    print(f"Latest tag    : {payload['latest_tag']}")
    print(f"Default mode  : {payload['default_execution']}")
    print()
    print(payload["truth_boundary"])
    return 0


def command_adapters(_args: argparse.Namespace) -> int:
    script = PROJECT_ROOT / "scripts" / "run_phase13d_agent_adapter_execution.py"
    if not script.exists():
        print(f"ERROR: missing {script.relative_to(PROJECT_ROOT)}")
        return 1
    return run_command([str(PYTHON), str(script)])


def validator_scripts(quick: bool) -> list[str]:
    quick_scripts = [
        "scripts/validate_phase13e_factory_cli_operator_surface.py",
        "scripts/validate_phase13d_agent_adapter_execution.py",
    ]
    if quick:
        return quick_scripts
    return quick_scripts + [
        "scripts/validate_phase13c_self_correction_governance.py",
        "scripts/validate_phase13c_agent_runtime_foundation.py",
        "scripts/validate_phase13c_handover_documentation.py",
        "scripts/validate_phase13b_generated_application.py",
        "scripts/validate_phase13b_progress_portal_observability.py",
        "scripts/validate_phase13a_generated_application_regeneration.py",
        "scripts/validate_phase13a_first_governed_generation_run.py",
        "scripts/validate_phase12b_operations_remediation_loop.py",
        "scripts/validate_phase12a_independent_audit_foundation.py",
        "scripts/validate_phase11d_pre_agent_generation_readiness.py",
        "scripts/validate_phase11c_llm_call_metrics_prompt_policy.py",
        "scripts/validate_phase11c_agentic_prompt_best_practices.py",
        "scripts/validate_phase11c_upi_domain_safety_regulatory_guardrails.py",
    ]


def command_validate(args: argparse.Namespace) -> int:
    for relative_script in validator_scripts(args.quick):
        script = PROJECT_ROOT / relative_script
        if not script.exists():
            print(f"SKIP missing validator: {relative_script}")
            continue
        status = run_command([str(PYTHON), str(script)])
        if status != 0:
            return status
    if not args.quick:
        generated_tests = GENERATED_ROOT / "generated_application" / "tests"
        if generated_tests.exists():
            status = run_command([str(PYTHON), "-m", "pytest", "-q", str(generated_tests)])
            if status != 0:
                return status
        for quality_command in (
            [str(PYTHON), "-m", "ruff", "check", "."],
            [str(PYTHON), "-m", "mypy", "src"],
            [str(PYTHON), "-m", "pytest", "-q"],
        ):
            status = run_command(quality_command)
            if status != 0:
                return status
    return 0


def command_portals(_args: argparse.Namespace) -> int:
    for relative_script in (
        "scripts/generate_phase13e_factory_cli_operator_portal.py",
        "scripts/generate_phase13d_agent_adapter_portal.py",
    ):
        script = PROJECT_ROOT / relative_script
        if script.exists():
            status = run_command([str(PYTHON), str(script)])
            if status != 0:
                return status
        else:
            print(f"SKIP missing portal generator: {relative_script}")
    return 0


def command_handover(_args: argparse.Namespace) -> int:
    docs = [
        "docs/phase13e/factory_cli_operator_surface.md",
        "docs/phase13e/factory_cli_operator_commands.json",
        "docs/phase13e/factory_cli_architecture.json",
        "docs/phase13d/agent_adapter_execution_layer.md",
        "docs/phase13c/agent_runtime_handover.md",
    ]
    print("Factory operator handover")
    print()
    print("Primary commands:")
    for command in status_payload()["key_commands"]:
        print(f"- {command}")
    print()
    print("Useful documents:")
    for relative_doc in docs:
        marker = "OK" if (PROJECT_ROOT / relative_doc).exists() else "MISSING"
        print(f"- [{marker}] {relative_doc}")
    return 0


def command_logs(args: argparse.Namespace) -> int:
    print(f"Run log directory: {RUN_LOGS}")
    if not RUN_LOGS.exists():
        print("No run log directory found yet.")
        return 0
    logs = sorted(RUN_LOGS.glob("*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in logs[: args.limit]:
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        print(f"{modified}  {path}")
    return 0


def command_token_economics(args: argparse.Namespace) -> int:
    script = PROJECT_ROOT / "scripts" / "token_economics_cli.py"
    if not script.exists():
        print(f"ERROR: missing {script.relative_to(PROJECT_ROOT)}")
        return 1
    return run_command([str(PYTHON), str(script), *args.cli_args], check=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"./{ROOT_COMMAND}",
        description="Governed factory operator command surface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true", dest="as_json")
    status_parser.set_defaults(func=command_status)

    adapters_parser = subparsers.add_parser("adapters")
    adapters_parser.set_defaults(func=command_adapters)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--quick", action="store_true")
    validate_parser.set_defaults(func=command_validate)

    portals_parser = subparsers.add_parser("portals")
    portals_parser.set_defaults(func=command_portals)

    handover_parser = subparsers.add_parser("handover")
    handover_parser.set_defaults(func=command_handover)

    logs_parser = subparsers.add_parser("logs")
    logs_parser.add_argument("--limit", type=int, default=10)
    logs_parser.set_defaults(func=command_logs)

    token_parser = subparsers.add_parser("token-economics")
    token_parser.add_argument("cli_args", nargs=argparse.REMAINDER)
    token_parser.set_defaults(func=command_token_economics)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
