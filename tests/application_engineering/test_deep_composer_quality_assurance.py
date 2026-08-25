from __future__ import annotations

from pathlib import Path

import pytest

from factory.application_engineering.deep_composer import DeepApplicationComposer, DeepComposerError
from factory.quality_assurance.kernel import DIMENSION_WEIGHTS, HARD_GATES


def _raw_measures() -> dict[str, object]:
    return {
        "dimensions": {name: {"met": 1, "total": 1} for name in DIMENSION_WEIGHTS},
        "hard_gates": {
            name: {"met": 1, "total": 1, "evidence_ids": ["qualification-run"]}
            for name in HARD_GATES
        },
    }


def test_composer_rejects_requirements_supplied_quality_measurements(tmp_path: Path) -> None:
    output_root = tmp_path / "generated"
    requirements = {
        "quality_assurance": {
            "claims": [],
            "evidence": [
                {
                    "evidence_id": "qualification-run",
                    "source": "test",
                    "version": "1",
                    "sha256": "0" * 64,
                    "location": "tests/application_engineering",
                    "method": "executable test",
                    "result": "PASS",
                }
            ],
            "raw_measures": _raw_measures(),
        }
    }

    with pytest.raises(DeepComposerError, match="cannot supply raw_measures"):
        DeepApplicationComposer(tmp_path).compose(
            requirements_ir=requirements,
            output_root=output_root,
            app_id="quality_probe",
        )

    assurance_root = output_root / "quality_probe" / "evidence" / "quality_assurance"
    assert not assurance_root.exists()


def test_composer_supports_isolated_campaign_root_outside_worktree(tmp_path: Path) -> None:
    project_root = tmp_path / "source"
    output_root = tmp_path / "campaign" / "generation"

    DeepApplicationComposer(project_root).compose(
        requirements_ir={},
        output_root=output_root,
        app_id="campaign_probe",
    )

    assert (output_root / "campaign_probe").is_dir()


def test_composer_rejects_project_ancestor_as_output_root(tmp_path: Path) -> None:
    project_root = tmp_path / "source"
    with pytest.raises(DeepComposerError, match="project root or its ancestor"):
        DeepApplicationComposer(project_root).compose(
            requirements_ir={},
            output_root=tmp_path,
            app_id="unsafe_probe",
        )
