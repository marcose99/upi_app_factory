from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

from typing import Protocol, Sequence, cast
import pytest


MODULE = "scripts.run_portal_requirements_driven_application_engineering"


class AdapterModule(Protocol):
    def main(self, argv: Sequence[str] | None = None) -> int: ...


def _module() -> AdapterModule:
    return cast(AdapterModule, importlib.import_module(MODULE))


def _requirements(tmp_path: Path) -> Path:
    path = tmp_path / "requirements.md"
    path.write_text(
        """# UPI Dispute Resolution

Build a local mock-safe UPI dispute resolution API.

## Required contracts

- Implement health and readiness endpoints.
- Enforce idempotent dispute creation.
- Generate unit and API contract tests.
- Never call live payment providers.
""",
        encoding="utf-8",
    )
    return path


def _environment(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setenv("UPI_APP_FACTORY_ROOT", str(root))
    monkeypatch.setenv(
        "UPI_APP_FACTORY_WORKSPACE_ROOT",
        str(root / "workspace"),
    )
    monkeypatch.setenv("FACTORY_LLM_ENABLED", "0")
    monkeypatch.setenv("REAL_PAYMENT_CALLS", "disabled")
    monkeypatch.setenv("MOCK_BOUNDARY", "1")


def test_plan_only_hashes_requirements_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root = tmp_path / "factory"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    requirements = _requirements(tmp_path)
    output = workspace / "factory_generated" / "upi_dispute_resolution" / "generated_application"
    evidence = workspace / "evidence"
    _environment(monkeypatch, root)

    rc = module.main(
        [
            "--requirements",
            str(requirements),
            "--app-id",
            "upi_dispute_resolution",
            "--output-root",
            str(output),
            "--evidence-root",
            str(evidence),
            "--approval-mode",
            "proposal-only",
            "--mock-safe",
            "--plan-only",
        ]
    )

    assert rc == 0
    assert not output.exists()
    assert hashlib.sha256(requirements.read_bytes()).hexdigest()


def test_execution_requires_exact_human_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root = tmp_path / "factory"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    requirements = _requirements(tmp_path)
    _environment(monkeypatch, root)

    rc = module.main(
        [
            "--requirements",
            str(requirements),
            "--output-root",
            str(workspace / "generated"),
            "--evidence-root",
            str(workspace / "evidence"),
            "--approval-mode",
            "human-gated",
            "--mock-safe",
        ]
    )

    assert rc == 2
    assert not (workspace / "generated").exists()


def test_approved_execution_creates_demo_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    root = tmp_path / "factory"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    requirements = _requirements(tmp_path)
    output = workspace / "factory_generated" / "upi_dispute_resolution" / "generated_application"
    evidence = workspace / "portal_generation_evidence"
    _environment(monkeypatch, root)

    rc = module.main(
        [
            "--requirements",
            str(requirements),
            "--app-id",
            "upi_dispute_resolution",
            "--output-root",
            str(output),
            "--evidence-root",
            str(evidence),
            "--approval-mode",
            "human-gated",
            "--approval-token",
            "APPROVE_PORTAL_APPLICATION_ENGINEERING",
            "--mock-safe",
        ]
    )

    assert rc == 0
    assert (output / "pyproject.toml").is_file()
    assert (output / "Dockerfile").is_file()
    assert (output / "app" / "__init__.py").is_file()
    assert (output / "tests" / "__init__.py").is_file()
    assert (output / "tests" / "test_service.py").is_file()
    assert (output / "tests" / "test_api_contract.py").is_file()

    api = (output / "app" / "upi_dispute_resolution" / "interfaces" / "api" / "main.py").read_text(
        encoding="utf-8"
    )
    assert '"/health"' in api
    assert '"/ready"' in api

    metadata = json.loads((output / "generation_metadata.json").read_text(encoding="utf-8"))
    assert metadata["requirements_sha256"] == hashlib.sha256(requirements.read_bytes()).hexdigest()
    assert metadata["real_payment_calls"] == "disabled"
    assert metadata["llm_calls"] == 0

    result_files = list(evidence.glob("portal_*/result.json"))
    assert len(result_files) == 1
    result = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert result["status"] == ("PORTAL_REQUIREMENTS_DRIVEN_APPLICATION_ENGINEERING_COMPLETED")
    assert result["health_contract"] is True
    assert result["ready_contract"] is True

    generated_env = os.environ.copy()
    generated_env.update(
        {
            "PYTHONPATH": str(output),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "REAL_PAYMENT_CALLS": "disabled",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests"],
        cwd=output,
        env=generated_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"generated tests failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )


def test_portal_config_points_to_adapter() -> None:
    config_path = Path("config/operator_portal/generate_command.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "1.0"
    assert "scripts.run_portal_requirements_driven_application_engineering" in payload["command"]
    assert payload["approval"]["required"] is True
    assert payload["environment"]["FACTORY_LLM_ENABLED"] == "0"
    assert payload["environment"]["REAL_PAYMENT_CALLS"] == "disabled"
    assert set(payload["required_placeholders"]) == {
        "requirements_path",
        "app_id",
        "output_root",
        "evidence_root",
    }
