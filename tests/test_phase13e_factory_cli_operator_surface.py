from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_COMMAND = "factoryctl"


def run_factoryctl(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src = str(ROOT / "src")
    old = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src if not old else src + os.pathsep + old
    return subprocess.run(
        [str(ROOT / ROOT_COMMAND), *args],
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_factory_operator_status_json() -> None:
    result = run_factoryctl("status", "--json")
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["app_id"] == "upi_dispute_resolution"
    assert payload["phase"] == "Phase 13E"
    assert payload["root_command"] == f"./{ROOT_COMMAND}"
    assert payload["default_execution"] == "local_deterministic"
    assert "policy-gated" in payload["truth_boundary"]


def test_factory_operator_handover_command() -> None:
    result = run_factoryctl("handover")
    assert result.returncode == 0, result.stdout
    assert f"./{ROOT_COMMAND} validate --quick" in result.stdout
    assert "Factory operator handover" in result.stdout


def test_factory_operator_logs_command() -> None:
    result = run_factoryctl("logs", "--limit", "1")
    assert result.returncode == 0, result.stdout
    assert "Run log directory:" in result.stdout


def test_phase13e_command_policy_document() -> None:
    policy_path = ROOT / "docs" / "phase13e" / "factory_cli_operator_commands.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    assert payload["root_command"] == f"./{ROOT_COMMAND}"
    command_names = {item["name"] for item in payload["commands"]}
    assert {
        "status",
        "adapters",
        "validate_quick",
        "validate_full",
        "portals",
        "handover",
        "logs",
    }.issubset(command_names)
