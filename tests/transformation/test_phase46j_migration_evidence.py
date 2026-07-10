from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.transformation_controller.phase46j import (
    EVIDENCE_INPUTS,
    build_evidence_index,
    verify_readiness,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prepare_root(tmp_path: Path) -> Path:
    root = tmp_path / "factory"
    for relative in EVIDENCE_INPUTS:
        write_json(root / relative, {"path": relative, "value": "test"})
    write_json(
        root / "config/identity_migration_readiness.json",
        {
            "controls": {
                "display_identity_contract": "COMPLETE",
                "path_neutral_runtime": "COMPLETE",
                "technical_namespace_compatibility": "COMPLETE",
                "physical_checkout_rename": "DEFERRED_HUMAN_GATE",
                "remote_repository_rename": "DEFERRED_HUMAN_GATE",
                "legacy_alias_retirement": "DEFERRED_HUMAN_GATE",
                "formal_certification": "NOT_PERFORMED",
            },
            "certification_posture": "CERTIFICATION_READY_NOT_CERTIFIED",
        },
    )
    write_json(
        root / "policies/identity_migration_evidence_policy.json",
        {"official_certification_claim_allowed": False},
    )
    write_json(
        root / "evidence/phase46j/identity_migration_evidence_index.json",
        build_evidence_index(root),
    )
    return root


def test_build_evidence_index_is_deterministic(tmp_path: Path) -> None:
    root = prepare_root(tmp_path)
    first = build_evidence_index(root)
    second = build_evidence_index(root)
    assert first == second
    assert first["evidence_record_count"] == len(EVIDENCE_INPUTS)


def test_verify_readiness_replays_all_hashes(tmp_path: Path) -> None:
    root = prepare_root(tmp_path)
    report = verify_readiness(root)
    assert report["status"] == "PASSED"
    assert report["certification_posture"] == (
        "CERTIFICATION_READY_NOT_CERTIFIED"
    )


def test_verify_readiness_detects_evidence_drift(tmp_path: Path) -> None:
    root = prepare_root(tmp_path)
    write_json(root / EVIDENCE_INPUTS[0], {"changed": True})
    with pytest.raises(ValueError, match="hashes do not replay"):
        verify_readiness(root)
