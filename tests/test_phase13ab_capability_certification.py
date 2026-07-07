from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ARTIFACT_DIR = Path("workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase13ab")
VALIDATOR = Path("scripts/validate_capability_certification.py")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_phase13ab_certification_artifacts_exist() -> None:
    for filename in [
        "capability_certification_policy.json",
        "capability_certification_matrix.json",
        "capability_certification_audit.json",
        "requirement_traceability_matrix.json",
        "capability_certification_report.md",
    ]:
        assert (ARTIFACT_DIR / filename).exists(), filename


def test_phase13ab_policy_blocks_live_provider_calls() -> None:
    policy = read_json(ARTIFACT_DIR / "capability_certification_policy.json")

    assert policy["mode"] == "LOCAL_FIRST_ONLY"
    assert policy["live_provider_calls_allowed"] is False
    assert policy["human_approval_required_for_release"] is True
    assert policy["determinism_required"] is True
    assert policy["evidence_required"] is True


def test_phase13ab_matrix_covers_required_dimensions() -> None:
    policy = read_json(ARTIFACT_DIR / "capability_certification_policy.json")
    matrix = read_json(ARTIFACT_DIR / "capability_certification_matrix.json")

    required_dimensions = set(policy["minimum_required_quality_dimensions"])
    capabilities = matrix["capabilities"]

    assert matrix["certification_mode"] == "LOCAL_FIRST_DETERMINISTIC"
    assert matrix["live_provider_calls_allowed"] is False
    assert capabilities

    for capability in capabilities:
        quality_results = capability["quality_results"]
        assert set(quality_results) == required_dimensions
        for dimension, result in quality_results.items():
            assert result["status"] in policy["allowed_statuses"], dimension
            assert result["evidence_refs"], dimension


def test_phase13ab_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--artifact-dir", str(ARTIFACT_DIR)],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Capability certification validation passed" in result.stdout
