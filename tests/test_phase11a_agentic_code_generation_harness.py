from __future__ import annotations

from pathlib import Path

import pytest

from upi_factory.phase10_lifecycle_planner import generate_lifecycle_artifacts
from upi_factory.phase10_1_official_source_registry import (
    generate_official_source_artifacts,
)
from upi_factory.phase10_2_sdlc_best_practice_governance import (
    generate_sdlc_best_practice_artifacts,
)
from upi_factory.phase10_3_pre_generation_readiness import (
    generate_pre_generation_readiness_artifacts,
)
from upi_factory.phase11a_agentic_code_generation_harness import (
    AGENT_ROLE_IDS,
    REQUIRED_ARTIFACTS,
    TOOL_IDS,
    generate_phase11a_artifacts,
    validate_phase11a_artifacts,
)


def _generate_ready_phase10_3(tmp_path: Path) -> Path:
    phase10 = tmp_path / "phase10"
    phase10_1 = tmp_path / "phase10_1"
    phase10_2 = tmp_path / "phase10_2"
    phase10_3 = tmp_path / "phase10_3"

    generate_lifecycle_artifacts(phase10)
    generate_official_source_artifacts(phase10_1)
    generate_sdlc_best_practice_artifacts(phase10_2)
    generate_pre_generation_readiness_artifacts(
        phase10_3,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    return phase10_3


def test_phase11a_generation_creates_required_artifacts(tmp_path: Path) -> None:
    phase10_3 = _generate_ready_phase10_3(tmp_path)
    output = tmp_path / "phase11a"

    written = generate_phase11a_artifacts(output, phase10_3_dir=phase10_3)

    assert {path.name for path in written} == set(REQUIRED_ARTIFACTS)
    for filename in REQUIRED_ARTIFACTS:
        assert (output / filename).exists(), filename


def test_phase11a_validation_passes_after_generation(tmp_path: Path) -> None:
    phase10_3 = _generate_ready_phase10_3(tmp_path)
    output = tmp_path / "phase11a"

    generate_phase11a_artifacts(output, phase10_3_dir=phase10_3)
    report = validate_phase11a_artifacts(output, phase10_3_dir=phase10_3)

    assert report["passed"] is True
    assert report["errors"] == []


def test_phase11a_contains_all_agent_roles_and_tool_contracts(tmp_path: Path) -> None:
    phase10_3 = _generate_ready_phase10_3(tmp_path)
    output = tmp_path / "phase11a"

    generate_phase11a_artifacts(output, phase10_3_dir=phase10_3)
    report = validate_phase11a_artifacts(output, phase10_3_dir=phase10_3)

    assert set(report["checked_agent_roles"]) == set(AGENT_ROLE_IDS)
    assert set(report["checked_tool_contracts"]) == set(TOOL_IDS)


def test_phase11a_blocks_without_phase10_3_readiness(tmp_path: Path) -> None:
    output = tmp_path / "phase11a"
    missing_phase10_3 = tmp_path / "missing_phase10_3"

    with pytest.raises(ValueError, match="Phase 11A generation blocked"):
        generate_phase11a_artifacts(output, phase10_3_dir=missing_phase10_3)


def test_phase11a_validation_blocks_false_claim(tmp_path: Path) -> None:
    phase10_3 = _generate_ready_phase10_3(tmp_path)
    output = tmp_path / "phase11a"

    generate_phase11a_artifacts(output, phase10_3_dir=phase10_3)
    policy_path = output / "agent_execution_policy.md"
    policy_path.write_text(policy_path.read_text() + "\nRBI certified\n")

    report = validate_phase11a_artifacts(output, phase10_3_dir=phase10_3)

    assert report["passed"] is False
    assert any("Forbidden Phase 11A false claim" in error for error in report["errors"])
