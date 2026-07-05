from __future__ import annotations

import json
from pathlib import Path

from upi_factory.phase10_lifecycle_planner import (
    HONESTY_LABELS,
    REQUIRED_ARTIFACTS,
    generate_lifecycle_artifacts,
    validate_lifecycle_artifacts,
)


def test_phase10_generation_creates_all_required_artifacts(tmp_path: Path) -> None:
    written = generate_lifecycle_artifacts(tmp_path)

    written_names = {path.name for path in written}
    assert written_names == set(REQUIRED_ARTIFACTS)

    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).exists(), filename


def test_phase10_validation_passes_after_generation(tmp_path: Path) -> None:
    generate_lifecycle_artifacts(tmp_path)

    report = validate_lifecycle_artifacts(tmp_path)

    assert report["passed"] is True
    assert report["errors"] == []
    assert sorted(report["checked_honesty_labels"]) == sorted(HONESTY_LABELS)


def test_phase10_traceability_covers_all_requirements(tmp_path: Path) -> None:
    generate_lifecycle_artifacts(tmp_path)

    requirements = json.loads((tmp_path / "requirements_analysis.json").read_text())
    traceability = json.loads((tmp_path / "traceability_matrix.json").read_text())

    requirement_ids = {item["id"] for item in requirements["requirements"]}
    traceability_ids = {item["requirement_id"] for item in traceability["rows"]}

    assert requirement_ids == traceability_ids

    for row in traceability["rows"]:
        assert row["design_artifacts"]
        assert row["wbs_task_ids"]
        assert row["validation_refs"]
        assert row["honesty_labels"]


def test_phase10_validation_fails_when_required_label_removed(tmp_path: Path) -> None:
    generate_lifecycle_artifacts(tmp_path)
    architecture_path = tmp_path / "architecture_options.md"
    original = architecture_path.read_text()
    for label in HONESTY_LABELS:
        original = original.replace(label, "")
    architecture_path.write_text(original)

    report = validate_lifecycle_artifacts(tmp_path)

    assert report["passed"] is False
    assert any("Missing required honesty label" in error for error in report["errors"])
