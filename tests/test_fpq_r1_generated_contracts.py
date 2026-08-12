from __future__ import annotations

import importlib
import json
from pathlib import Path
import shutil
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPLICATION_ROOT = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
GENERATOR = importlib.import_module(
    "run_portal_requirements_driven_application_engineering"
)


def test_checked_in_generated_sbom_exactly_matches_its_lock_and_contract() -> None:
    result = GENERATOR.validate_generated_application_cyclonedx(APPLICATION_ROOT)
    assert result["status"] == "valid"
    assert result["component_count"] == 23


def test_generated_sbom_validation_rejects_component_and_provenance_drift(
    tmp_path: Path,
) -> None:
    copied = tmp_path / "generated_application"
    (copied / "evidence/assurance").mkdir(parents=True)
    for relative in (
        "requirements.lock",
        "dependency_contract.json",
        "evidence/assurance/cyclonedx_1_7_sbom.json",
    ):
        shutil.copy2(APPLICATION_ROOT / relative, copied / relative)
    sbom_path = copied / "evidence/assurance/cyclonedx_1_7_sbom.json"
    payload = json.loads(sbom_path.read_text(encoding="utf-8"))
    payload["components"][0]["version"] = "999.0"
    sbom_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(GENERATOR.AdapterError, match="does not exactly match"):
        GENERATOR.validate_generated_application_cyclonedx(copied)
