from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from upi_factory.phase11b_real_app_mock_ecosystem_boundary import (
    GENERATION_MODE,
    REQUIRED_ARTIFACTS,
    REQUIRED_LABELS,
    generate_phase11b_boundary_artifacts,
    validate_phase11b_boundary_artifacts,
)


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def test_phase11b_boundary_generation_creates_required_artifacts(
    tmp_path: Path,
) -> None:
    generated = generate_phase11b_boundary_artifacts(tmp_path)
    generated_names = {path.name for path in generated}

    assert set(REQUIRED_ARTIFACTS) == generated_names
    for artifact_name in REQUIRED_ARTIFACTS:
        assert (tmp_path / artifact_name).exists()


def test_phase11b_boundary_manifest_has_correct_generation_mode(
    tmp_path: Path,
) -> None:
    generate_phase11b_boundary_artifacts(tmp_path)

    manifest = _load_json(
        tmp_path / "real_app_mock_ecosystem_boundary_manifest.json"
    )

    assert manifest["generation_mode"] == GENERATION_MODE
    assert manifest["primary_application_real"] is True
    assert manifest["external_ecosystem_mock_only"] is True
    assert manifest["synthetic_data_only"] is True
    assert manifest["external_payment_connectivity_allowed"] is False
    assert manifest["real_payment_processing_allowed"] is False
    assert manifest["production_claims_allowed"] is False


def test_phase11b_boundary_artifacts_include_required_labels(
    tmp_path: Path,
) -> None:
    generate_phase11b_boundary_artifacts(tmp_path)

    all_text = "\n".join(
        (tmp_path / artifact_name).read_text(encoding="utf-8")
        for artifact_name in REQUIRED_ARTIFACTS
    )

    for label in REQUIRED_LABELS:
        assert label in all_text


def test_phase11b_boundary_validation_passes_for_generated_artifacts(
    tmp_path: Path,
) -> None:
    generate_phase11b_boundary_artifacts(tmp_path)

    report = validate_phase11b_boundary_artifacts(tmp_path)

    assert report["passed"] is True
    assert report["errors"] == []


def test_phase11b_boundary_rejects_unsafe_claim_in_artifact(
    tmp_path: Path,
) -> None:
    generate_phase11b_boundary_artifacts(tmp_path)

    policy_path = tmp_path / "primary_application_engineering_policy.md"
    policy_path.write_text(
        policy_path.read_text(encoding="utf-8")
        + "\nThis system is production ready.\n",
        encoding="utf-8",
    )

    report = validate_phase11b_boundary_artifacts(tmp_path)

    assert report["passed"] is False
    assert any("production ready" in error for error in report["errors"])
