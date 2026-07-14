from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.transformation_controller import phase46f


def source_registry() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": "46C",
        "aliases": [
            {
                "alias_id": "display-upi-dispute-resolution\x2dfactory",
                "alias_type": "display_identity",
                "legacy": "UPI Dispute Resolution\x20Factory",
                "canonical": "UPI App Factory",
                "status": "PLAN_CONTRACT_FIRST",
                "removal": "HUMAN_APPROVAL_REQUIRED",
            },
            {
                "alias_id": "technical",
                "alias_type": "technical_identifier",
                "legacy": "upi_dispute_resolution\x5ffactory",
                "canonical": "upi_app_factory",
                "status": "COMPATIBILITY_REQUIRED_BEFORE_MIGRATION",
                "removal": "HUMAN_APPROVAL_REQUIRED",
            },
            {
                "alias_id": "physical",
                "alias_type": "physical_path",
                "legacy": "upi_dispute_resolution\x5ffactory",
                "canonical": "upi_app_factory",
                "status": "HUMAN_GATE",
                "removal": "NOT_APPLICABLE",
            },
            {
                "alias_id": "remote",
                "alias_type": "remote_repository",
                "legacy": "upi_dispute_resolution\x5ffactory",
                "canonical": "upi_app_factory",
                "status": "HUMAN_GATE",
                "removal": "NOT_APPLICABLE",
            },
        ],
    }


def source_runtime() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": "46D",
        "canonical_product": {
            "display_name": "UPI App Factory",
            "identifier": "upi_app_factory",
            "cli": "upi-app-factory",
        },
        "unknown_identity_posture": "PRESERVE",
        "compatibility_layer": "RETAINED",
    }


def policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "phase": "46F",
        "mode": "CONTRACT_FIRST_BOUNDED",
        "legacy_alias_removal": "HUMAN_APPROVAL_REQUIRED",
        "physical_checkout_rename": "PROHIBITED",
        "remote_repository_rename": "PROHIBITED",
        "technical_identifier_migration": "DEFERRED",
        "historical_evidence_rewrite": "PROHIBITED",
        "llm_calls_allowed": 0,
    }


def write_fixture(root: Path) -> None:
    phase46f.write_json(root / phase46f.REGISTRY_PATH, phase46f.updated_registry(source_registry()))
    phase46f.write_json(root / phase46f.RUNTIME_PATH, phase46f.updated_runtime(source_runtime()))
    registry = phase46f.load_object(root / phase46f.REGISTRY_PATH, "Alias registry")
    phase46f.write_json(root / phase46f.CONTRACT_PATH, phase46f.build_contract(registry))
    phase46f.write_json(root / phase46f.POLICY_PATH, policy())


def test_build_contract_uses_canonical_display_name() -> None:
    contract = phase46f.build_contract(source_registry())
    identity = contract["canonical_display_identity"]
    assert isinstance(identity, dict)
    assert identity["name"] == "UPI App Factory"
    assert contract["write_posture"] == "CANONICAL_ONLY"


def test_build_contract_retains_governed_legacy_alias() -> None:
    contract = phase46f.build_contract(source_registry())
    aliases = contract["accepted_legacy_display_identities"]
    assert isinstance(aliases, list)
    assert {item["name"] for item in aliases if isinstance(item, dict)} == {
        "UPI Dispute Resolution\x20Factory"
    }


def test_missing_display_alias_fails_closed() -> None:
    registry = source_registry()
    aliases = registry["aliases"]
    assert isinstance(aliases, list)
    aliases.pop(0)
    with pytest.raises(phase46f.DisplayIdentityMigrationError):
        phase46f.build_contract(registry)


def test_conflicting_canonical_display_name_fails_closed() -> None:
    registry = source_registry()
    aliases = registry["aliases"]
    assert isinstance(aliases, list)
    first = aliases[0]
    assert isinstance(first, dict)
    first["canonical"] = "Unexpected Factory"
    with pytest.raises(phase46f.DisplayIdentityMigrationError):
        phase46f.build_contract(registry)


def test_alias_removal_must_remain_human_approved() -> None:
    registry = source_registry()
    aliases = registry["aliases"]
    assert isinstance(aliases, list)
    first = aliases[0]
    assert isinstance(first, dict)
    first["removal"] = "AUTOMATIC"
    with pytest.raises(phase46f.DisplayIdentityMigrationError):
        phase46f.build_contract(registry)


def test_updated_registry_activates_display_contract_only() -> None:
    updated = phase46f.updated_registry(source_registry())
    aliases = updated["aliases"]
    assert isinstance(aliases, list)
    display = [
        item
        for item in aliases
        if isinstance(item, dict) and item.get("alias_type") == "display_identity"
    ]
    assert len(display) == len(phase46f.EXPECTED_LEGACY_DISPLAY_NAMES)
    assert {item["status"] for item in display} == {"CONTRACT_ACTIVE_COMPATIBILITY_RETAINED"}
    technical = [
        item
        for item in aliases
        if isinstance(item, dict) and item.get("alias_type") == "technical_identifier"
    ]
    assert technical[0]["status"] == "COMPATIBILITY_REQUIRED_BEFORE_MIGRATION"


def test_updated_runtime_enforces_canonical_write() -> None:
    updated = phase46f.updated_runtime(source_runtime())
    assert updated["display_write_posture"] == "CANONICAL_ONLY"
    assert updated["compatibility_layer"] == "RETAINED"
    assert updated["phase"] == "46F"


def test_verify_contract_passes_for_governed_fixture(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    result = phase46f.verify_contract(tmp_path)
    assert result["status"] == "PASSED"
    assert result["display_alias_count"] == len(phase46f.EXPECTED_LEGACY_DISPLAY_NAMES)
    assert result["llm_calls"] == 0


def test_verify_contract_rejects_legacy_write_posture(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    runtime = phase46f.load_object(tmp_path / phase46f.RUNTIME_PATH, "Runtime")
    runtime["display_write_posture"] = "LEGACY_ALLOWED"
    phase46f.write_json(tmp_path / phase46f.RUNTIME_PATH, runtime)
    with pytest.raises(phase46f.DisplayIdentityMigrationError):
        phase46f.verify_contract(tmp_path)


def test_verify_contract_rejects_compatibility_removal(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    runtime = phase46f.load_object(tmp_path / phase46f.RUNTIME_PATH, "Runtime")
    runtime["compatibility_layer"] = "REMOVED"
    phase46f.write_json(tmp_path / phase46f.RUNTIME_PATH, runtime)
    with pytest.raises(phase46f.DisplayIdentityMigrationError):
        phase46f.verify_contract(tmp_path)


def test_verify_contract_rejects_physical_rename_permission(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    current = phase46f.load_object(tmp_path / phase46f.POLICY_PATH, "Policy")
    current["physical_checkout_rename"] = "ALLOWED"
    phase46f.write_json(tmp_path / phase46f.POLICY_PATH, current)
    with pytest.raises(phase46f.DisplayIdentityMigrationError):
        phase46f.verify_contract(tmp_path)


def test_verify_contract_rejects_remote_rename_permission(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    current = phase46f.load_object(tmp_path / phase46f.POLICY_PATH, "Policy")
    current["remote_repository_rename"] = "ALLOWED"
    phase46f.write_json(tmp_path / phase46f.POLICY_PATH, current)
    with pytest.raises(phase46f.DisplayIdentityMigrationError):
        phase46f.verify_contract(tmp_path)


def test_implement_is_idempotent(tmp_path: Path) -> None:
    phase46f.write_json(tmp_path / phase46f.REGISTRY_PATH, source_registry())
    phase46f.write_json(tmp_path / phase46f.RUNTIME_PATH, source_runtime())
    phase46f.write_json(tmp_path / phase46f.POLICY_PATH, policy())
    first = phase46f.implement(tmp_path)
    second = phase46f.implement(tmp_path)
    assert first == second
    assert second["status"] == "PASSED"


def test_contract_prohibits_historical_evidence_rewrite() -> None:
    contract = phase46f.build_contract(source_registry())
    assert contract["historical_evidence_rewrite"] == "PROHIBITED"
    assert contract["technical_identifier_migration"] == "NOT_PERFORMED"
    assert contract["physical_checkout_rename"] == "NOT_PERFORMED"
    assert contract["remote_repository_rename"] == "NOT_PERFORMED"
