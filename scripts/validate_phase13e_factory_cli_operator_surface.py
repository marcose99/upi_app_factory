#!/usr/bin/env python3
"""Validate Phase 13E factory CLI operator command surface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
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


def env() -> dict[str, str]:
    merged = os.environ.copy()
    src = str(PROJECT_ROOT / "src")
    old = merged.get("PYTHONPATH")
    merged["PYTHONPATH"] = src if not old else src + os.pathsep + old
    return merged


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(PROJECT_ROOT),
        env=env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    required_files = [
        ROOT_COMMAND,
        "scripts/factory_cli.py",
        "scripts/generate_phase13e_factory_cli_operator_portal.py",
        "scripts/validate_phase13e_factory_cli_operator_surface.py",
        "tests/test_phase13e_factory_cli_operator_surface.py",
        "docs/phase13e/factory_cli_operator_commands.json",
        "docs/phase13e/factory_cli_architecture.json",
        "docs/phase13e/factory_cli_operator_surface.md",
    ]
    for relative_path in required_files:
        if not (PROJECT_ROOT / relative_path).exists():
            errors.append(f"Missing required file: {relative_path}")

    root_path = PROJECT_ROOT / ROOT_COMMAND
    if root_path.exists() and not os.access(root_path, os.X_OK):
        errors.append(f"Root command is not executable: {ROOT_COMMAND}")

    for relative_path in [
        "scripts/factory_cli.py",
        "scripts/generate_phase13e_factory_cli_operator_portal.py",
        "scripts/validate_phase13e_factory_cli_operator_surface.py",
        "tests/test_phase13e_factory_cli_operator_surface.py",
    ]:
        path = PROJECT_ROOT / relative_path
        if path.exists():
            compiled = run([str(PYTHON), "-m", "py_compile", str(path)])
            if compiled.returncode != 0:
                errors.append(f"Python compile failed for {relative_path}: {compiled.stdout.strip()}")

    commands_path = PROJECT_ROOT / "docs" / "phase13e" / "factory_cli_operator_commands.json"
    if commands_path.exists():
        try:
            commands_doc = load_json(commands_path)
            commands = commands_doc.get("commands", [])
            names = {item.get("name") for item in commands}
            expected = {"status", "adapters", "validate_quick", "validate_full", "portals", "handover", "logs"}
            missing = sorted(expected - names)
            if missing:
                errors.append(f"Missing command definitions: {missing}")
            if commands_doc.get("root_command") != f"./{ROOT_COMMAND}":
                errors.append("Command doc root_command mismatch.")
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Invalid commands JSON: {exc}")

    architecture_path = PROJECT_ROOT / "docs" / "phase13e" / "factory_cli_architecture.json"
    if architecture_path.exists():
        try:
            architecture = load_json(architecture_path)
            if architecture.get("phase") != PHASE:
                errors.append("Architecture JSON phase mismatch.")
            if "local deterministic" not in architecture.get("truth_boundary", ""):
                errors.append("Architecture JSON missing local deterministic truth boundary.")
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Invalid architecture JSON: {exc}")

    status_result = run([str(root_path), "status", "--json"])
    if status_result.returncode != 0:
        errors.append(f"{ROOT_COMMAND} status --json failed: {status_result.stdout}")
    else:
        try:
            payload = json.loads(status_result.stdout)
            if payload.get("root_command") != f"./{ROOT_COMMAND}":
                errors.append("Status payload root_command mismatch.")
            if payload.get("default_execution") != "local_deterministic":
                errors.append("Status payload default_execution mismatch.")
            if "policy-gated" not in payload.get("truth_boundary", ""):
                errors.append("Status payload truth boundary missing policy-gated wording.")
        except json.JSONDecodeError as exc:
            errors.append(f"Status output is not JSON: {exc}")

    logs_result = run([str(root_path), "logs", "--limit", "1"])
    if logs_result.returncode != 0:
        errors.append(f"{ROOT_COMMAND} logs failed: {logs_result.stdout}")

    portal_path = PROJECT_ROOT / "workspace" / "factory_generated" / APP_ID / "audit_portal" / "factory_cli_operator_portal.html"
    if not portal_path.exists():
        portal_result = run([str(PYTHON), str(PROJECT_ROOT / "scripts" / "generate_phase13e_factory_cli_operator_portal.py")])
        if portal_result.returncode != 0:
            errors.append(f"Portal generation failed: {portal_result.stdout}")
    if portal_path.exists():
        portal_text = portal_path.read_text(encoding="utf-8")
        for expected_text in ("Phase 13E", f"./{ROOT_COMMAND}", "Truth boundary"):
            if expected_text not in portal_text:
                errors.append(f"Portal missing expected text: {expected_text}")

    result = {
        "app_id": APP_ID,
        "errors": errors,
        "passed": not errors,
        "phase": PHASE,
        "root_command": f"./{ROOT_COMMAND}",
        "run_id": RUN_ID,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
