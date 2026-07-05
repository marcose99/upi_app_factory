from __future__ import annotations

import json
from pathlib import Path

from upi_factory.phase10_2_sdlc_best_practice_governance import (
    REQUIRED_ARTIFACTS,
    REQUIRED_LABELS,
    REQUIRED_TECHNOLOGY_IDS,
    generate_sdlc_best_practice_artifacts,
    validate_sdlc_best_practice_artifacts,
)


def test_phase10_2_generation_creates_required_artifacts(tmp_path: Path) -> None:
    written = generate_sdlc_best_practice_artifacts(tmp_path)

    assert {path.name for path in written} == set(REQUIRED_ARTIFACTS)
    for filename in REQUIRED_ARTIFACTS:
        assert (tmp_path / filename).exists(), filename


def test_phase10_2_validation_passes_after_generation(tmp_path: Path) -> None:
    generate_sdlc_best_practice_artifacts(tmp_path)

    report = validate_sdlc_best_practice_artifacts(tmp_path)

    assert report["passed"] is True
    assert report["errors"] == []
    assert sorted(report["checked_required_labels"]) == sorted(REQUIRED_LABELS)


def test_phase10_2_registry_contains_required_technologies(tmp_path: Path) -> None:
    generate_sdlc_best_practice_artifacts(tmp_path)
    registry = json.loads((tmp_path / "sdlc_technology_registry.json").read_text())

    technology_ids = {
        technology["technology_id"]
        for technology in registry["technologies"]
    }

    assert set(REQUIRED_TECHNOLOGY_IDS).issubset(technology_ids)


def test_phase10_2_each_technology_has_controls_and_sources(tmp_path: Path) -> None:
    generate_sdlc_best_practice_artifacts(tmp_path)
    registry = json.loads((tmp_path / "sdlc_technology_registry.json").read_text())

    for technology in registry["technologies"]:
        assert technology["official_doc_url"].startswith("https://")
        assert technology["source_status"] == "OFFICIAL_DOC_REFERENCE_CANDIDATE"
        assert len(technology["best_practice_controls"]) >= 3
        assert technology["lifecycle_phases"]
        assert technology["freshness_rule"]


def test_phase10_2_validation_fails_when_required_technology_removed(
    tmp_path: Path,
) -> None:
    generate_sdlc_best_practice_artifacts(tmp_path)
    registry_path = tmp_path / "sdlc_technology_registry.json"
    registry = json.loads(registry_path.read_text())

    registry["technologies"] = [
        technology
        for technology in registry["technologies"]
        if technology["technology_id"] != "python"
    ]
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True))

    report = validate_sdlc_best_practice_artifacts(tmp_path)

    assert report["passed"] is False
    assert any("Missing required technology id: python" in error for error in report["errors"])
