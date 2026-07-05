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
    generate_phase11a_artifacts,
)
from upi_factory.phase11a1_agentic_harness_hardening import (
    PROTECTED_ACTIONS,
    REQUIRED_ARTIFACTS,
    REQUIRED_AUTONOMY_LEVELS,
    generate_phase11a1_artifacts,
    validate_phase11a1_artifacts,
)


def _generate_ready_phase11a(tmp_path: Path) -> tuple[Path, Path]:
    phase10 = tmp_path / "phase10"
    phase10_1 = tmp_path / "phase10_1"
    phase10_2 = tmp_path / "phase10_2"
    phase10_3 = tmp_path / "phase10_3"
    phase11a = tmp_path / "phase11a"

    generate_lifecycle_artifacts(phase10)
    generate_official_source_artifacts(phase10_1)
    generate_sdlc_best_practice_artifacts(phase10_2)
    generate_pre_generation_readiness_artifacts(
        phase10_3,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )
    generate_phase11a_artifacts(phase11a, phase10_3_dir=phase10_3)

    return phase11a, phase10_3


def test_phase11a1_generation_creates_required_artifacts(tmp_path: Path) -> None:
    phase11a, phase10_3 = _generate_ready_phase11a(tmp_path)
    output = tmp_path / "phase11a_1"

    written = generate_phase11a1_artifacts(
        output,
        phase11a_dir=phase11a,
        phase10_3_dir=phase10_3,
    )

    assert {path.name for path in written} == set(REQUIRED_ARTIFACTS)
    for filename in REQUIRED_ARTIFACTS:
        assert (output / filename).exists(), filename


def test_phase11a1_validation_passes_after_generation(tmp_path: Path) -> None:
    phase11a, phase10_3 = _generate_ready_phase11a(tmp_path)
    output = tmp_path / "phase11a_1"

    generate_phase11a1_artifacts(
        output,
        phase11a_dir=phase11a,
        phase10_3_dir=phase10_3,
    )
    report = validate_phase11a1_artifacts(
        output,
        phase11a_dir=phase11a,
        phase10_3_dir=phase10_3,
    )

    assert report["passed"] is True
    assert report["errors"] == []


def test_phase11a1_checks_autonomy_levels_and_protected_actions(
    tmp_path: Path,
) -> None:
    phase11a, phase10_3 = _generate_ready_phase11a(tmp_path)
    output = tmp_path / "phase11a_1"

    generate_phase11a1_artifacts(
        output,
        phase11a_dir=phase11a,
        phase10_3_dir=phase10_3,
    )
    report = validate_phase11a1_artifacts(
        output,
        phase11a_dir=phase11a,
        phase10_3_dir=phase10_3,
    )

    assert set(report["checked_autonomy_levels"]) == set(REQUIRED_AUTONOMY_LEVELS)
    assert set(report["checked_protected_actions"]) == set(PROTECTED_ACTIONS)


def test_phase11a1_blocks_without_phase11a_readiness(tmp_path: Path) -> None:
    output = tmp_path / "phase11a_1"
    missing_phase11a = tmp_path / "missing_phase11a"
    missing_phase10_3 = tmp_path / "missing_phase10_3"

    with pytest.raises(ValueError, match="Phase 11A.1 generation blocked"):
        generate_phase11a1_artifacts(
            output,
            phase11a_dir=missing_phase11a,
            phase10_3_dir=missing_phase10_3,
        )


def test_phase11a1_validation_blocks_false_claim(tmp_path: Path) -> None:
    phase11a, phase10_3 = _generate_ready_phase11a(tmp_path)
    output = tmp_path / "phase11a_1"

    generate_phase11a1_artifacts(
        output,
        phase11a_dir=phase11a,
        phase10_3_dir=phase10_3,
    )
    policy_path = output / "secret_and_environment_guard_policy.md"
    policy_path.write_text(policy_path.read_text() + "\nRBI certified\n")

    report = validate_phase11a1_artifacts(
        output,
        phase11a_dir=phase11a,
        phase10_3_dir=phase10_3,
    )

    assert report["passed"] is False
    assert any("Forbidden Phase 11A.1 false claim" in error for error in report["errors"])
