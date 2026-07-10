from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.transformation_controller.phase46i import (
    CANONICAL_TECHNICAL_ID,
    LEGACY_TECHNICAL_ID,
    canonical_write_identity,
    resolve_technical_identity,
    verify_contract,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_canonical_identity_resolves_without_compatibility() -> None:
    result = resolve_technical_identity(CANONICAL_TECHNICAL_ID)
    assert result["canonical"] == CANONICAL_TECHNICAL_ID
    assert result["compatibility_applied"] is False


def test_legacy_identity_resolves_through_compatibility() -> None:
    result = resolve_technical_identity(LEGACY_TECHNICAL_ID)
    assert result["canonical"] == CANONICAL_TECHNICAL_ID
    assert result["compatibility_applied"] is True


def test_unknown_identity_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unknown technical identity"):
        resolve_technical_identity("unknown_factory")


def test_canonical_write_identity_is_new_namespace() -> None:
    assert canonical_write_identity() == CANONICAL_TECHNICAL_ID


def test_verify_contract_preserves_physical_rename_boundaries(
    tmp_path: Path,
) -> None:
    root = tmp_path / "factory"
    write_json(
        root / "config/technical_identity_contract.json",
        {
            "canonical_technical_identifier": CANONICAL_TECHNICAL_ID,
            "canonical_write_posture": "CANONICAL_ONLY",
            "physical_package_rename": "NOT_PERFORMED",
        },
    )
    write_json(
        root / "config/technical_namespace_aliases.json",
        {
            "legacy_aliases": [LEGACY_TECHNICAL_ID],
            "legacy_alias_retirement": "HUMAN_APPROVAL_REQUIRED",
        },
    )
    write_json(
        root / "config/identity_compatibility_runtime.json",
        {
            "technical_identity_contract": (
                "config/technical_identity_contract.json"
            ),
            "technical_namespace_posture": (
                "CANONICAL_WRITES_COMPATIBILITY_READS"
            ),
        },
    )
    write_json(
        root / "policies/technical_namespace_migration_policy.json",
        {"physical_package_rename_allowed": False},
    )
    report = verify_contract(root)
    assert report["status"] == "PASSED"
    assert report["physical_package_rename"] == "NOT_PERFORMED"
