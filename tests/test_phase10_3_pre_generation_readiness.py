from __future__ import annotations

import json
from pathlib import Path

from upi_factory.phase10_lifecycle_planner import generate_lifecycle_artifacts
from upi_factory.phase10_1_official_source_registry import (
    generate_official_source_artifacts,
)
from upi_factory.phase10_2_sdlc_best_practice_governance import (
    generate_sdlc_best_practice_artifacts,
)
from upi_factory.phase10_3_pre_generation_readiness import (
    PHASE11_AGENT_ROLES,
    REQUIRED_ARTIFACTS,
    generate_pre_generation_readiness_artifacts,
    validate_pre_generation_readiness_artifacts,
)


def _generate_upstream(tmp_path: Path) -> tuple[Path, Path, Path]:
    phase10 = tmp_path / "phase10"
    phase10_1 = tmp_path / "phase10_1"
    phase10_2 = tmp_path / "phase10_2"

    generate_lifecycle_artifacts(phase10)
    generate_official_source_artifacts(phase10_1)
    generate_sdlc_best_practice_artifacts(phase10_2)

    return phase10, phase10_1, phase10_2


def test_phase10_3_generation_creates_required_artifacts(tmp_path: Path) -> None:
    phase10, phase10_1, phase10_2 = _generate_upstream(tmp_path)
    output = tmp_path / "phase10_3"

    written = generate_pre_generation_readiness_artifacts(
        output,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    assert {path.name for path in written} == set(REQUIRED_ARTIFACTS)
    for filename in REQUIRED_ARTIFACTS:
        assert (output / filename).exists(), filename


def test_phase10_3_validation_passes_after_generation(tmp_path: Path) -> None:
    phase10, phase10_1, phase10_2 = _generate_upstream(tmp_path)
    output = tmp_path / "phase10_3"

    generate_pre_generation_readiness_artifacts(
        output,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    report = validate_pre_generation_readiness_artifacts(
        output,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    assert report["passed"] is True
    assert report["errors"] == []


def test_phase10_3_readiness_gate_allows_phase11(tmp_path: Path) -> None:
    phase10, phase10_1, phase10_2 = _generate_upstream(tmp_path)
    output = tmp_path / "phase10_3"

    generate_pre_generation_readiness_artifacts(
        output,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    gate = json.loads((output / "code_generation_readiness_gate.json").read_text())

    assert gate["phase11_allowed"] is True
    assert set(PHASE11_AGENT_ROLES).issubset(set(gate["phase11_agent_roles"]))


def test_phase10_3_validation_fails_when_upstream_missing(tmp_path: Path) -> None:
    phase10, phase10_1, phase10_2 = _generate_upstream(tmp_path)
    output = tmp_path / "phase10_3"

    generate_pre_generation_readiness_artifacts(
        output,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    (phase10 / "requirements_analysis.json").unlink()

    report = validate_pre_generation_readiness_artifacts(
        output,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    assert report["passed"] is False
    assert any("Missing upstream artifact" in error for error in report["errors"])


def test_phase10_3_validation_blocks_false_claim(tmp_path: Path) -> None:
    phase10, phase10_1, phase10_2 = _generate_upstream(tmp_path)
    output = tmp_path / "phase10_3"

    generate_pre_generation_readiness_artifacts(
        output,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    guardrail_path = output / "implementation_guardrails.md"
    guardrail_path.write_text(guardrail_path.read_text() + "\nRBI certified\n")

    report = validate_pre_generation_readiness_artifacts(
        output,
        phase10_dir=phase10,
        phase10_1_dir=phase10_1,
        phase10_2_dir=phase10_2,
    )

    assert report["passed"] is False
    assert any("Forbidden pre-generation false claim" in error for error in report["errors"])
