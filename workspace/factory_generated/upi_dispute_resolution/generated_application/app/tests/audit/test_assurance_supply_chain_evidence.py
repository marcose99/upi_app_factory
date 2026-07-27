from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EVIDENCE_ROOT = Path(__file__).resolve().parents[3] / "evidence" / "assurance"


def read_json(name: str) -> dict[str, Any]:
    value = json.loads((EVIDENCE_ROOT / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def require_object(value: Any) -> dict[str, Any]:
    assert isinstance(value, dict)
    return value


def require_list(value: Any) -> list[Any]:
    assert isinstance(value, list)
    return value


def test_wave_e_assurance_evidence_is_non_certifying_and_owned() -> None:
    for name in [
        "asvs_5_0_l2_mapping.json",
        "samm_maturity_evidence.json",
        "threat_model_abuse_cases.json",
        "openssf_scorecard_assessment.json",
        "verification_summary.json",
    ]:
        payload = read_json(name)
        assert payload.get("certification_claim") == "none"

    asvs = read_json("asvs_5_0_l2_mapping.json")
    assert asvs["version"] == "5.0"
    assert asvs["level_orientation"] == "Level 2 oriented"
    assert require_object(require_list(asvs["unresolved_risks"])[0])["owner"]

    threat_model = read_json("threat_model_abuse_cases.json")
    assert len(require_list(threat_model["abuse_cases"])) >= 5
    assert require_object(require_list(threat_model["unresolved_risks"])[0])["owner"]


def test_wave_e_sbom_and_provenance_shapes_are_local_only() -> None:
    cyclonedx = read_json("cyclonedx_1_7_sbom.json")
    assert cyclonedx["bomFormat"] == "CycloneDX"
    assert cyclonedx["specVersion"] == "1.7"
    assert {
        require_object(component)["name"]
        for component in require_list(cyclonedx["components"])
    } >= {
        "fastapi",
        "uvicorn",
        "pydantic",
        "python-dotenv",
        "PyYAML",
        "httpx",
        "sqlite3",
    }

    spdx = read_json("spdx_3_0_sbom.json")
    assert spdx["spdxVersion"] == "SPDX-3.0"
    assert spdx["dataLicense"] == "CC0-1.0"
    assert len(require_list(spdx["relationships"])) >= 7
    spdx_versions = {
        require_object(component)["name"]: require_object(component)["version"]
        for component in require_list(spdx["elements"])
        if require_object(component).get("type") == "Package"
        and require_object(component)["name"] != "upi_dispute_resolution_generated_application"
    }
    assert spdx_versions["fastapi"] == "0.139.0"
    assert spdx_versions["httpx"] == "0.28.1"

    provenance = read_json("slsa_1_2_provenance_verification.json")
    assert "no SLSA level claimed" in provenance["claim"]
    build_definition = require_object(provenance["buildDefinition"])
    external_parameters = require_object(build_definition["externalParameters"])
    assert external_parameters["network"] == "disabled"


def test_wave_e_dependency_license_inventory_uses_existing_dependency_set() -> None:
    inventory = read_json("dependency_license_inventory.json")
    assert inventory["new_dependencies_added"] == []
    lock_evidence = require_object(inventory["offline_lock_evidence"])
    assert lock_evidence["lockfile"] == "requirements/ci-lock.txt"
    assert lock_evidence["exact_runtime_versions_present"] is True
    assert lock_evidence["wheel_hashes_present"] is False
    assert lock_evidence["installed_distribution_metadata_inspected"] is True
    license_evidence = require_object(inventory["license_evidence"])
    assert license_evidence["project_license"] == "Apache-2.0"
    assert {
        require_object(component)["name"]
        for component in require_list(inventory["components"])
    } == {
        "fastapi",
        "uvicorn",
        "pydantic",
        "python-dotenv",
        "PyYAML",
        "httpx",
        "sqlite3",
    }
    assert len(require_list(inventory["transitive_dependency_license_evidence"])) >= 8
    installed_integrity = require_list(inventory["installed_file_integrity_evidence"])
    assert len(installed_integrity) >= 6
    assert all("sha256=" in require_object(item)["sample_record_entry"] for item in installed_integrity)
