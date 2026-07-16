from __future__ import annotations
from typing import Any

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase13b_generated_application.py"
APP_ROOT = ROOT / "workspace" / "factory_generated" / "upi_dispute_resolution" / "generated_application"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_phase13b_generated_application",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase13b_generated_application_validator_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)


def test_generated_application_pytest_suite_passes() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "tests"), str(APP_ROOT / "app")])
    env["PYTEST_PLUGINS"] = "conftest"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(APP_ROOT / "tests")],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
