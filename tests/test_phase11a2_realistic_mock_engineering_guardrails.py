from __future__ import annotations

import json
from pathlib import Path

from upi_factory.phase11a2_realistic_mock_engineering_guardrails import (
    PROMPT_MARKER,
    REQUIRED_ARTIFACTS,
    TARGET_PROMPTS,
    apply_prompt_enhancements,
    generate_phase11a2_artifacts,
    validate_phase11a2_artifacts,
)


def _write_ready_phase11a1(tmp_path: Path) -> Path:
    phase11a1 = tmp_path / "phase11a_1"
    phase11a1.mkdir()
    report = {"passed": True, "errors": [], "warnings": []}
    (phase11a1 / "phase11a1_validation_report.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )
    return phase11a1


def _write_prompt_files(tmp_path: Path) -> Path:
    for relative in TARGET_PROMPTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Prompt\\n\\nPlaceholder for {relative}\\n", encoding="utf-8")
    return tmp_path


def test_phase11a2_generation_creates_required_artifacts(tmp_path: Path) -> None:
    phase11a1 = _write_ready_phase11a1(tmp_path)
    output = tmp_path / "phase11a_2"

    written = generate_phase11a2_artifacts(output, phase11a1_dir=phase11a1)

    assert {path.name for path in written} == set(REQUIRED_ARTIFACTS)
    for filename in REQUIRED_ARTIFACTS:
        assert (output / filename).exists(), filename


def test_phase11a2_prompt_enhancements_are_idempotent(tmp_path: Path) -> None:
    project_root = _write_prompt_files(tmp_path)

    changed_first = apply_prompt_enhancements(project_root)
    changed_second = apply_prompt_enhancements(project_root)

    assert len(changed_first) == len(TARGET_PROMPTS)
    assert changed_second == []

    for relative in TARGET_PROMPTS:
        assert PROMPT_MARKER in (project_root / relative).read_text(encoding="utf-8")


def test_phase11a2_validation_passes_with_prompt_enhancements(
    tmp_path: Path,
) -> None:
    phase11a1 = _write_ready_phase11a1(tmp_path)
    project_root = _write_prompt_files(tmp_path)
    output = tmp_path / "phase11a_2"

    apply_prompt_enhancements(project_root)
    generate_phase11a2_artifacts(output, phase11a1_dir=phase11a1)

    report = validate_phase11a2_artifacts(output, project_root=project_root)

    assert report["passed"] is True
    assert report["errors"] == []
    assert len(report["checked_prompt_files"]) == len(TARGET_PROMPTS)


def test_phase11a2_validation_blocks_missing_prompt_marker(tmp_path: Path) -> None:
    phase11a1 = _write_ready_phase11a1(tmp_path)
    project_root = _write_prompt_files(tmp_path)
    output = tmp_path / "phase11a_2"

    apply_prompt_enhancements(project_root)
    first_prompt = project_root / TARGET_PROMPTS[0]
    first_prompt.write_text("# Prompt without marker\\n", encoding="utf-8")
    generate_phase11a2_artifacts(output, phase11a1_dir=phase11a1)

    report = validate_phase11a2_artifacts(output, project_root=project_root)

    assert report["passed"] is False
    assert any("Prompt enhancement marker missing" in error for error in report["errors"])


def test_phase11a2_validation_blocks_unsafe_claim(tmp_path: Path) -> None:
    phase11a1 = _write_ready_phase11a1(tmp_path)
    project_root = _write_prompt_files(tmp_path)
    output = tmp_path / "phase11a_2"

    apply_prompt_enhancements(project_root)
    generate_phase11a2_artifacts(output, phase11a1_dir=phase11a1)
    policy = output / "realistic_mock_engineering_policy.md"
    policy.write_text(policy.read_text(encoding="utf-8") + "\\nRBI certified\\n")

    report = validate_phase11a2_artifacts(output, project_root=project_root)

    assert report["passed"] is False
    assert any("Unsafe forbidden claim found" in error for error in report["errors"])
