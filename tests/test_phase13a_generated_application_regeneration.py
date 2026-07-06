from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase13a_generated_application_regeneration.py"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_phase13a_generated_application_regeneration",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase13a_generated_application_regeneration_contract_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)


def test_reset_script_dry_run_writes_manifest() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "reset_generated_application_workspace.py"),
            "--run-id",
            "first_governed_generation_run_001",
            "--dry-run",
        ],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(completed.stdout)
    manifest = ROOT / result["manifest"]
    assert result["dry_run"] is True
    assert manifest.exists()
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_data["target"] == "workspace/factory_generated/upi_dispute_resolution/generated_application"
    assert "workspace/run_logs" in manifest_data["protected_paths"]


def test_reset_contract_protects_factory_paths() -> None:
    contract = ROOT / "docs" / "phase13a" / "generated_application_delete_recreate_contract.json"
    data = json.loads(contract.read_text(encoding="utf-8"))
    assert "docs" in data["protected_paths"]
    assert "factory_governance" in data["protected_paths"]
    assert "prompts" in data["protected_paths"]
    assert "workspace/run_logs" in data["protected_paths"]
