from __future__ import annotations
from typing import Any

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase13a_first_governed_generation_run.py"


def load_validator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "validate_phase13a_first_governed_generation_run",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase13a_first_governed_generation_run_scaffold_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)


def test_phase13a_generation_manifest_is_ready_to_start() -> None:
    manifest = ROOT / "docs" / "phase13a" / "generation_run_manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["decision"] == "READY_TO_START_CONTROLLED_GENERATION"
    assert data["generation_scope"]["external_ecosystem"] == "mock/simulated only"
    assert data["generation_scope"]["no_real_customer_data"] is True


def test_phase13a_agent_execution_plan_reaches_portal_agent() -> None:
    plan = ROOT / "docs" / "phase13a" / "agent_execution_plan.json"
    data = json.loads(plan.read_text(encoding="utf-8"))
    agent_names = [agent["name"] for agent in data["agents"]]
    assert "developer_agent" in agent_names
    assert "audit_agent" in agent_names
    assert "portal_agent" in agent_names
