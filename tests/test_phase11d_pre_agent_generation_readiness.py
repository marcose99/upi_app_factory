from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_phase11d_pre_agent_generation_readiness.py"


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_phase11d_pre_agent_generation_readiness",
        VALIDATOR_PATH,
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase11d_pre_agent_generation_readiness_passes() -> None:
    validator = load_validator()
    result = validator.validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)


def test_phase11d_go_no_go_is_go() -> None:
    report = ROOT / "docs" / "phase11d" / "pre_generation_go_no_go_report.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["decision"] == "GO"
    assert "tool authorization policy" in " ".join(data["blocked_generation_conditions"])


def test_phase11d_tool_policy_is_deny_by_default() -> None:
    policy = ROOT / "docs" / "phase11d" / "tool_authorization_policy.json"
    data = json.loads(policy.read_text(encoding="utf-8"))
    assert data["default"] == "deny"
    assert "live NPCI calls" in data["forbidden"]
    assert "git push" in data["approval_required_for"]
