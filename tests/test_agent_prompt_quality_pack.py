from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "factory_governance" / "agent_prompts" / "agent_prompt_manifest.json"


def test_agent_prompt_validator_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_agent_prompts.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    assert result == {"errors": [], "passed": True}


def test_prompt_manifest_contains_core_factory_agents() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    agent_ids = {agent["agent_id"] for agent in manifest["agents"]}

    assert "requirement_agent" in agent_ids
    assert "architect_agent" in agent_ids
    assert "developer_agent" in agent_ids
    assert "test_agent" in agent_ids
    assert "governance_agent" in agent_ids
    assert "release_agent" in agent_ids
    assert "validation_agent" in agent_ids
