from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.current_operational_contract import (
    GENERIC_CONTRACT_RELATIVE_PATH,
    documentation_discussion_is_safe,
    find_executable_boundary_violations,
    find_secret_like_text,
    load_application_profile,
    load_contract_registry,
    load_generic_upi_factory_contract,
    recipient_test_command,
    registered_application_ids,
    repository_file,
)
from scripts.validate_current_operational_contract import (
    EXPECTED_PROTECTED_BOUNDARIES,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
PHASE42_PATH = ROOT / "scripts/validate_phase42_generated_application_local_run_pack.py"
PHASE13C_PATH = ROOT / "scripts/validate_phase13c_handover_documentation.py"
MATRIX_PATH = ROOT / "docs/documentation/DOCUMENTATION_EVIDENCE_MATRIX.json"


def test_current_operational_contract_validator_passes() -> None:
    result = validate()
    assert result["passed"], json.dumps(result, indent=2, sort_keys=True)
    assert result["validated_application_ids"] == result["application_ids"]


def test_generic_upi_contract_is_not_dispute_application_specific() -> None:
    generic = load_generic_upi_factory_contract()
    encoded = json.dumps(generic, sort_keys=True).lower()
    assert generic["scope"]["application_family"] == "UPI"
    assert generic["scope"]["applies_to"] == "all UPI applications engineered by the factory"
    assert "upi_dispute_resolution" not in encoded
    assert "beneficiary-not-credited" not in encoded
    assert "upi_dispute_" not in encoded


def test_registry_separates_generic_contract_from_all_application_profiles() -> None:
    registry = load_contract_registry()
    assert registry["generic_upi_factory_contract"] == GENERIC_CONTRACT_RELATIVE_PATH

    profiles = registry["application_profiles"]
    assert profiles
    ids = [item["application_id"] for item in profiles]
    assert len(ids) == len(set(ids))
    assert tuple(ids) == registered_application_ids(registry)

    for item in profiles:
        application_id = item["application_id"]
        assert item["status"] == "CURRENT_AND_VERIFIED"
        assert item["path"] == (
            "factory_governance/current_contracts/application_profiles/"
            f"{application_id}.json"
        )


def test_every_registered_application_profile_is_loadable_and_safe() -> None:
    generic = load_generic_upi_factory_contract()
    false_fields = generic["generated_application_profile_requirements"][
        "runtime_safety_required_false_fields"
    ]

    for application_id in registered_application_ids():
        profile = load_application_profile(application_id)
        assert profile["application_id"] == application_id
        assert profile["inherits_generic_contract"] == GENERIC_CONTRACT_RELATIVE_PATH
        for field in false_fields:
            assert profile["runtime_safety"][field] is False


def test_dispute_application_details_live_only_in_application_profile() -> None:
    profile = load_application_profile("upi_dispute_resolution")
    assert profile["application_id"] == "upi_dispute_resolution"
    assert profile["upi_application_type"].startswith("UPI dispute resolution")
    assert recipient_test_command(
        "upi_dispute_resolution", profile
    ) == "PYTHONPATH=.. python -m pytest -q app/tests"


def test_generic_protected_boundaries_are_durable_not_campaign_specific() -> None:
    generic = load_generic_upi_factory_contract()
    boundaries = generic["governance"]["protected_boundaries"]
    assert boundaries == list(EXPECTED_PROTECTED_BOUNDARIES)
    encoded = json.dumps(boundaries).lower()
    for forbidden in (
        "documentation_reconstruction",
        "current_contract_and_validator_modernization",
        "rc_requalification",
        "rc1_tag_publication",
    ):
        assert forbidden not in encoded


def test_repository_contract_paths_fail_closed_on_escape() -> None:
    with pytest.raises(ValueError):
        repository_file("../outside.json")
    with pytest.raises(ValueError):
        repository_file("/tmp/outside.json")
    with pytest.raises(ValueError):
        repository_file("docs\\..\\outside.json")


def test_documentation_evidence_matrix_is_valid_and_byte_current() -> None:
    payload = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    documents = payload["documents"]
    assert payload["document_count"] == len(documents)
    assert payload["total_information_item_count"] == len(documents) + 1

    seen: set[str] = set()
    for entry in documents:
        relative = entry["path"]
        assert relative not in seen
        seen.add(relative)
        expected = entry["sha256_after"]
        path = repository_file(relative)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, relative


def test_documentation_may_explain_prohibited_git_commands_without_becoming_executable() -> None:
    text = "Never run git push or git tag from this local acceptance workflow."
    assert documentation_discussion_is_safe(text)
    assert find_secret_like_text(text) == []


def test_executable_release_enablement_remains_detectable() -> None:
    violations = find_executable_boundary_violations(
        "#!/usr/bin/env bash\ngit push origin main\n"
    )
    assert any("git" in item and "push" in item for item in violations)


def test_documentation_secret_material_remains_rejected() -> None:
    text = "BEGIN PRIVATE KEY\nsecret-shaped-material"
    assert not documentation_discussion_is_safe(text)
    assert "BEGIN PRIVATE KEY" in find_secret_like_text(text)


def test_phase42_delegates_application_specific_facts_to_profile() -> None:
    source = PHASE42_PATH.read_text(encoding="utf-8")
    assert "load_application_profile(APP_ID)" in source
    assert "recipient_test_command(APP_ID, profile)" in source
    assert "REQUIRED_ENV_VALUES" not in source


def test_phase13c_is_legacy_provenance_wrapper() -> None:
    source = PHASE13C_PATH.read_text(encoding="utf-8")
    assert "validate_current()" in source
    assert "REQUIRED_TERMS" not in source
    for legacy_literal in (
        "Factory Handover Guide",
        "./factory doctor",
        "./factory generate",
        "Current script equivalents",
    ):
        assert legacy_literal not in source
