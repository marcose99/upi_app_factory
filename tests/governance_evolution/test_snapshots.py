from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, Mapping

import pytest

from factory.documentation import ProvenanceBinding, canonical_json, canonical_sha256
from factory.governance_evolution import (
    ExecutionFingerprint,
    GovernanceModelError,
    GovernanceSnapshot,
    GovernanceSourceBinding,
)


def source(
    source_id: str,
    *,
    authority_id: str = "AUTHORITY-policy-owner",
    revision: str = "revision:1",
    content: object | None = None,
    source_type: str = "SIGNED_POLICY_BUNDLE",
) -> GovernanceSourceBinding:
    return GovernanceSourceBinding(
        authority_id=authority_id,
        source_id=source_id,
        revision=revision,
        content_sha256=canonical_sha256(content if content is not None else {"source": source_id}),
        source_type=source_type,
    )


def snapshot(
    *,
    version_id: str = "policy:1",
    payload: Mapping[str, object] | None = None,
    sources: tuple[GovernanceSourceBinding, ...] | None = None,
    previous_snapshot_id: str | None = None,
    supersedes_snapshot_id: str | None = None,
) -> GovernanceSnapshot:
    return GovernanceSnapshot(
        version_id=version_id,
        payload=payload or {"facts": {"FACT-2": False, "FACT-1": True}, "rules": ["RULE-1"]},
        source_bindings=sources or (source("SOURCE-2"), source("SOURCE-1")),
        previous_snapshot_id=previous_snapshot_id,
        supersedes_snapshot_id=supersedes_snapshot_id,
    )


def fingerprint(governance_snapshot: GovernanceSnapshot) -> ExecutionFingerprint:
    return ExecutionFingerprint.for_snapshot(
        factory_source_identity="git:factory-commit-abc",
        requirement_identity="requirements:sha256-abc",
        governance_snapshot=governance_snapshot,
        evidence_snapshot_identity="evidence:sha256-def",
        tool_config_identity="tool-config:sha256-ghi",
    )


def test_snapshot_identity_is_canonical_and_order_independent() -> None:
    first_source = source("SOURCE-1")
    second_source = source("SOURCE-2")
    first = snapshot(
        payload={"rules": ["RULE-1"], "facts": {"FACT-1": True, "FACT-2": False}},
        sources=(second_source, first_source),
    )
    second = snapshot(
        payload={"facts": {"FACT-2": False, "FACT-1": True}, "rules": ["RULE-1"]},
        sources=(first_source, second_source),
    )

    assert first.payload_sha256 == second.payload_sha256
    assert first.snapshot_id == second.snapshot_id
    assert first.to_json() == second.to_json()
    assert [item["source_id"] for item in first.to_dict()["source_bindings"]] == [
        "SOURCE-1",
        "SOURCE-2",
    ]
    assert first.payload_sha256 == canonical_sha256(first.payload)
    assert first.snapshot_sha256 == canonical_sha256(first.identity_payload())
    assert first.to_json() == canonical_json(first.to_dict())


def test_snapshot_payload_is_deeply_immutable_and_detached() -> None:
    caller_payload: dict[str, Any] = {
        "rules": [{"rule_id": "RULE-1", "conditions": ["A"]}]
    }
    governed = snapshot(payload=caller_payload)
    before = governed.to_dict()

    caller_payload["rules"][0]["conditions"].append("CALLER-MUTATION")
    with pytest.raises(TypeError, match="immutable"):
        governed.payload["new"] = True  # type: ignore[index]
    with pytest.raises(TypeError, match="immutable"):
        governed.payload["rules"][0]["rule_id"] = "MUTATED"
    with pytest.raises(AttributeError):
        governed.payload["rules"].append("MUTATED")
    with pytest.raises(FrozenInstanceError):
        governed.version_id = "policy:mutated"  # type: ignore[misc]

    projection = governed.to_dict()
    projection["payload"]["rules"][0]["conditions"].append("PROJECTION-MUTATION")
    assert governed.to_dict() == before


def test_snapshot_identity_is_sensitive_to_payload_and_source_tampering() -> None:
    baseline = snapshot()
    changed_payload = snapshot(
        payload={"facts": {"FACT-2": True, "FACT-1": True}, "rules": ["RULE-1"]}
    )
    changed_source = snapshot(
        sources=(source("SOURCE-1"), source("SOURCE-2", revision="revision:2"))
    )
    changed_authority = snapshot(
        sources=(source("SOURCE-1"), source("SOURCE-2", authority_id="AUTHORITY-corrected"))
    )

    assert baseline.payload_sha256 != changed_payload.payload_sha256
    assert baseline.snapshot_id != changed_payload.snapshot_id
    assert baseline.snapshot_id != changed_source.snapshot_id
    assert baseline.snapshot_id != changed_authority.snapshot_id


def test_source_binding_round_trips_m2_4_provenance_without_inferred_authority() -> None:
    provenance = ProvenanceBinding(
        source_id="SOURCE-1",
        revision="git:abc",
        content_sha256=canonical_sha256({"policy": "bytes"}),
        source_type="REPOSITORY_POLICY",
    )
    governed = GovernanceSourceBinding.from_provenance("AUTHORITY-1", provenance)

    assert governed.to_provenance() == provenance
    assert governed.to_dict() == {
        "authority_id": "AUTHORITY-1",
        **provenance.to_dict(),
    }
    with pytest.raises(TypeError):
        GovernanceSourceBinding.from_provenance(provenance)  # type: ignore[arg-type, call-arg]


def test_snapshot_rejects_invalid_or_ambiguous_source_bindings() -> None:
    with pytest.raises(GovernanceModelError, match="requires source_bindings"):
        GovernanceSnapshot("policy:1", {"rules": []}, ())
    with pytest.raises(GovernanceModelError, match="must be unique"):
        GovernanceSnapshot(
            "policy:1",
            {"rules": []},
            (source("SOURCE-1"), source("SOURCE-1", authority_id="AUTHORITY-2")),
        )
    with pytest.raises(GovernanceModelError, match="lowercase SHA-256"):
        GovernanceSourceBinding(
            "AUTHORITY-1", "SOURCE-1", "revision:1", "not-a-digest", "POLICY"
        )


def test_successor_lineage_is_explicit_and_cannot_replace_predecessor() -> None:
    predecessor = snapshot(version_id="policy:1")
    predecessor_before = predecessor.to_dict()
    successor = snapshot(
        version_id="policy:2",
        previous_snapshot_id=predecessor.snapshot_id,
        supersedes_snapshot_id=predecessor.snapshot_id,
    )

    assert successor.previous_snapshot_id == predecessor.snapshot_id
    assert successor.supersedes_snapshot_id == predecessor.snapshot_id
    assert successor.snapshot_id != predecessor.snapshot_id
    assert predecessor.to_dict() == predecessor_before


def test_execution_fingerprint_binds_every_mandatory_identity_deterministically() -> None:
    governed = snapshot()
    first = fingerprint(governed)
    second = fingerprint(governed)

    assert first.fingerprint_id == second.fingerprint_id
    assert first.fingerprint_sha256 == canonical_sha256(first.identity_payload())
    assert first.to_json() == canonical_json(first.to_dict())
    assert first.governance_snapshot_identity == governed.snapshot_id
    assert set(first.identity_payload()) == {
        "schema_version",
        "factory_source_identity",
        "requirement_identity",
        "governance_snapshot_identity",
        "evidence_snapshot_identity",
        "tool_config_identity",
    }


@pytest.mark.parametrize(
    "field_name",
    (
        "factory_source_identity",
        "requirement_identity",
        "governance_snapshot_identity",
        "evidence_snapshot_identity",
        "tool_config_identity",
    ),
)
def test_execution_fingerprint_rejects_missing_mandatory_identity(field_name: str) -> None:
    values = {
        "factory_source_identity": "git:factory-commit-abc",
        "requirement_identity": "requirements:sha256-abc",
        "governance_snapshot_identity": "GOVERNANCE-SNAPSHOT-abc",
        "evidence_snapshot_identity": "evidence:sha256-def",
        "tool_config_identity": "tool-config:sha256-ghi",
    }
    values[field_name] = ""
    with pytest.raises(GovernanceModelError, match=field_name):
        ExecutionFingerprint(**values)


def test_execution_fingerprint_is_immutable_and_snapshot_sensitive() -> None:
    first_snapshot = snapshot(version_id="policy:1")
    second_snapshot = snapshot(
        version_id="policy:2",
        previous_snapshot_id=first_snapshot.snapshot_id,
        supersedes_snapshot_id=first_snapshot.snapshot_id,
    )
    first = fingerprint(first_snapshot)
    second = fingerprint(second_snapshot)

    assert first.fingerprint_id != second.fingerprint_id
    assert first.governance_snapshot_identity == first_snapshot.snapshot_id
    with pytest.raises(FrozenInstanceError):
        first.governance_snapshot_identity = second_snapshot.snapshot_id  # type: ignore[misc]
