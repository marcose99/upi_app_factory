from __future__ import annotations

from pathlib import Path

from factory.agents.contracts import AGENT_SEQUENCE
from factory.agents.prompt_loader import prompt_path_for_agent
from factory.agents.role_runner import run_multi_agent_simulation
from scripts.validate_multi_agent_run import validate_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_all_phase8_agents_have_governed_prompts() -> None:
    for agent_id in AGENT_SEQUENCE:
        prompt_path = prompt_path_for_agent(PROJECT_ROOT, agent_id)
        assert prompt_path.exists(), f"Missing prompt for {agent_id}"


def test_phase8_multi_agent_simulation_is_traceable(tmp_path: Path) -> None:
    run_dir = run_multi_agent_simulation(
        project_root=PROJECT_ROOT,
        run_id="pytest_phase8_agent_run",
        output_root=tmp_path,
        force=True,
    )

    errors = validate_run(run_dir)
    assert errors == []

    output_text = (run_dir / "agent_outputs.jsonl").read_text(encoding="utf-8")
    assert "requirement_agent" in output_text
    assert "validation_agent" in output_text
    assert "MISSING_OFFICIAL_SOURCE" in output_text
    assert "MOCK_BOUNDARY" in output_text
    assert "debug-friendly" in output_text
