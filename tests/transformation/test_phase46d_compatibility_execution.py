from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.transformation_controller import phase46d


def registry() -> dict[str, object]:
    return {
        "schema_version": 1,
        "aliases": [
            {
                "alias_id": "display",
                "alias_type": "display_identity",
                "legacy": "Factory\x46romNothing",
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
        ],
    }


def runtime() -> dict[str, object]:
    return {
        "schema_version": 1,
        "unknown_identity_posture": "PRESERVE",
        "human_gate_alias_types": [
            "physical_path",
            "remote_repository",
        ],
    }


def policy() -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": "state_only_additive",
        "llm": {"enabled": False, "allowed_calls": 0},
        "wave_alias_types": {
            "W1": ["display_identity"],
            "W3": ["technical_identifier"],
        },
        "max_aliases_per_wave": 10,
        "prohibited_actions": ["repository_mutation"],
    }


def test_load_object_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(phase46d.CompatibilityExecutionError):
        phase46d.load_object(path, "Test payload")


def test_load_policy_rejects_enabled_llm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "policy.json"
    payload = policy()
    payload["llm"] = {"enabled": True, "allowed_calls": 1}
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        phase46d,
        "DEFAULT_POLICY",
        Path("policy.json"),
    )
    with pytest.raises(phase46d.CompatibilityExecutionError):
        phase46d.load_policy(tmp_path)


def test_registry_rejects_duplicate_alias_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = registry()
    aliases = payload["aliases"]
    assert isinstance(aliases, list)
    aliases.append(dict(aliases[0]))
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        phase46d,
        "DEFAULT_REGISTRY",
        Path("registry.json"),
    )
    with pytest.raises(phase46d.CompatibilityExecutionError):
        phase46d.load_registry(tmp_path)


def test_legacy_display_identity_resolves_to_canonical() -> None:
    result = phase46d.resolve_identity(
        registry(),
        runtime(),
        "Factory\x46romNothing",
        "display_identity",
    )
    assert result.result == "ALIAS_RESOLVED"
    assert result.canonical_value == "UPI App Factory"
    assert result.compatibility_applied is True


def test_canonical_identity_is_idempotent() -> None:
    result = phase46d.resolve_identity(
        registry(),
        runtime(),
        "UPI App Factory",
        "display_identity",
    )
    assert result.result == "CANONICAL_IDENTITY"
    assert result.compatibility_applied is False


def test_unknown_identity_is_preserved() -> None:
    result = phase46d.resolve_identity(
        registry(),
        runtime(),
        "Independent Product",
    )
    assert result.result == "UNRECOGNIZED_PRESERVED"
    assert result.canonical_value == "Independent Product"


def test_physical_path_alias_remains_human_gate() -> None:
    result = phase46d.resolve_identity(
        registry(),
        runtime(),
        "upi_dispute_resolution\x5ffactory",
        "physical_path",
    )
    assert result.result == "HUMAN_GATE"
    assert result.requires_human_approval is True
    assert result.compatibility_applied is False


def test_w1_selects_only_display_aliases() -> None:
    selected = phase46d.select_wave_aliases(
        registry(),
        policy(),
        "W1",
    )
    assert [item["alias_id"] for item in selected] == ["display"]


def test_w3_selects_only_technical_aliases() -> None:
    selected = phase46d.select_wave_aliases(
        registry(),
        policy(),
        "W3",
    )
    assert [item["alias_id"] for item in selected] == ["technical"]


def test_unsupported_wave_fails_closed() -> None:
    with pytest.raises(phase46d.CompatibilityExecutionError):
        phase46d.wave_alias_types(policy(), "W4")


def test_checkpoint_chain_verifies(tmp_path: Path) -> None:
    checkpoints: list[dict[str, object]] = []
    phase46d.append_checkpoint(
        tmp_path,
        checkpoints,
        "FIRST",
        {"value": 1},
    )
    phase46d.append_checkpoint(
        tmp_path,
        checkpoints,
        "SECOND",
        {"value": 2},
    )
    result = phase46d.verify_checkpoints(tmp_path)
    assert result["status"] == "PASSED"
    assert result["checkpoints_verified"] == 2


def test_evidence_manifest_excludes_itself(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "phase46d_evidence_manifest.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    manifest = phase46d.evidence_manifest(tmp_path)
    assert {item["path"] for item in manifest["files"]} == {"run.json"}


def test_checkpoint_verifier_ignores_summary_file(
    tmp_path: Path,
) -> None:
    checkpoints: list[dict[str, object]] = []
    phase46d.append_checkpoint(
        tmp_path,
        checkpoints,
        "FIRST",
        {"value": 1},
    )
    (tmp_path / "checkpoint_verification.json").write_text(
        "{}\n",
        encoding="utf-8",
    )
    result = phase46d.verify_checkpoints(tmp_path)
    assert result["status"] == "PASSED"
    assert result["checkpoints_verified"] == 1
