from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from factory.documentation import Freshness, ProvenanceBinding, canonical_json, canonical_sha256
from factory.governance_evolution import (
    AuthorityRegistry,
    GovernanceLifecycleState,
    GovernanceSourceBinding,
    SourceAuthorityContract,
    SourceMetadata,
    SourceObservation,
    SourceVerification,
    SourceVerificationError,
    UnsupportedSourceTransition,
    sha256_bytes,
)


def metadata(
    content: bytes,
    *,
    authority_id: str = "AUTHORITY-policy-owner",
    source_id: str = "SOURCE-policy",
    revision: str = "revision:1",
    source_type: str = "SIGNED_POLICY_BUNDLE",
) -> SourceMetadata:
    return SourceMetadata(
        authority_id=authority_id,
        source_id=source_id,
        revision=revision,
        content_sha256=sha256_bytes(content),
        source_type=source_type,
    )


def contract(content: bytes, **overrides: str) -> SourceAuthorityContract:
    values = metadata(content, **overrides)
    return SourceAuthorityContract(
        authority_id=values.authority_id,
        source_id=values.source_id,
        revision=values.revision,
        content_sha256=values.content_sha256,
        source_type=values.source_type,
    )


def test_external_observation_starts_unverified_and_cannot_assert_authority() -> None:
    content = b'{"policy":"observed"}'
    observation = SourceObservation.from_bytes(content, metadata(content))

    assert observation.state is GovernanceLifecycleState.OBSERVED_UNVERIFIED
    assert observation.observed_content_sha256 == sha256_bytes(content)
    assert observation.to_json() == canonical_json(observation.to_dict())
    with pytest.raises(FrozenInstanceError):
        observation.metadata = metadata(content, authority_id="MODEL-ASSERTION")  # type: ignore[misc]
    with pytest.raises(UnsupportedSourceTransition, match="requires a governed registry"):
        observation.transition_to(GovernanceLifecycleState.AUTHORITY_VERIFIED)
    with pytest.raises(SourceVerificationError, match="must be created by AuthorityRegistry"):
        SourceVerification(
            _token=object(),
            observation_id=observation.observation_id,
            authority_contract_id="MODEL-CONTRACT",
            authority_registry_id="MODEL-REGISTRY",
            lifecycle_state=GovernanceLifecycleState.AUTHORITY_VERIFIED,
            freshness=Freshness.CURRENT,
            changed_components=(),
            source_binding=GovernanceSourceBinding(
                "MODEL", "SOURCE-policy", "revision:1", sha256_bytes(content), "MODEL"
            ),
        )


def test_registry_verifies_exact_caller_bytes_and_bridges_m2_4_provenance() -> None:
    content = b"authenticated policy bytes\n"
    authority_registry = AuthorityRegistry((contract(content),))
    observation = SourceObservation(content, metadata(content))

    result = authority_registry.verify(observation)
    binding = result.require_authoritative_binding()

    assert result.state is GovernanceLifecycleState.AUTHORITY_VERIFIED
    assert result.freshness is Freshness.CURRENT
    assert result.changed_components == ()
    assert binding == GovernanceSourceBinding(
        "AUTHORITY-policy-owner",
        "SOURCE-policy",
        "revision:1",
        sha256_bytes(content),
        "SIGNED_POLICY_BUNDLE",
    )
    assert result.to_provenance() == binding.to_provenance()
    assert isinstance(result.to_provenance(), ProvenanceBinding)
    assert authority_registry.freshness_of(binding) is Freshness.CURRENT
    assert result.verification_sha256 == canonical_sha256(result.identity_payload())


def test_revision_or_content_mismatch_is_explicitly_stale_not_authoritative() -> None:
    current = b"current governed bytes"
    changed = b"changed observed bytes"
    authority_registry = AuthorityRegistry((contract(current),))

    changed_content = authority_registry.verify(SourceObservation(changed, metadata(changed)))
    changed_revision = authority_registry.verify(
        SourceObservation(
            current,
            metadata(current, revision="revision:2"),
        )
    )

    assert changed_content.state is GovernanceLifecycleState.OBSERVED_UNVERIFIED
    assert changed_content.freshness is Freshness.STALE
    assert changed_content.changed_components == ("CONTENT_SHA256",)
    assert changed_content.source_binding is None
    assert changed_revision.freshness is Freshness.STALE
    assert changed_revision.changed_components == ("REVISION",)
    with pytest.raises(SourceVerificationError, match="no current authoritative"):
        changed_content.require_authoritative_binding()

    stale_m2_4_binding = ProvenanceBinding(
        "SOURCE-policy",
        "revision:1",
        sha256_bytes(changed),
        "SIGNED_POLICY_BUNDLE",
    )
    assert authority_registry.freshness_of(stale_m2_4_binding) is Freshness.STALE


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"authority_id": "AUTHORITY-unaccepted"}, "invalid authority"),
        ({"source_type": "MODEL_SUMMARY"}, "invalid source type"),
        ({"source_id": "SOURCE-unregistered"}, "unregistered source authority"),
    ),
)
def test_invalid_authority_source_type_or_source_fails_closed(
    overrides: dict[str, str], message: str
) -> None:
    content = b"policy"
    authority_registry = AuthorityRegistry((contract(content),))
    observation = SourceObservation(content, metadata(content, **overrides))

    with pytest.raises(SourceVerificationError, match=message):
        authority_registry.verify(observation)


def test_invalid_digest_revision_and_byte_metadata_mismatch_fail_closed() -> None:
    with pytest.raises(SourceVerificationError, match="lowercase SHA-256"):
        SourceMetadata("AUTHORITY-1", "SOURCE-1", "revision:1", "not-a-digest", "POLICY")
    with pytest.raises(SourceVerificationError, match="revision"):
        SourceMetadata("AUTHORITY-1", "SOURCE-1", "", "0" * 64, "POLICY")

    declared = metadata(b"declared bytes")
    with pytest.raises(SourceVerificationError, match="does not match caller-supplied bytes"):
        SourceObservation(b"different bytes", declared)
    with pytest.raises(SourceVerificationError, match="exact bytes"):
        SourceObservation(bytearray(b"mutable"), declared)  # type: ignore[arg-type]


def test_registry_identity_is_order_independent_and_rejects_duplicate_or_conflict() -> None:
    first = contract(b"one", source_id="SOURCE-1")
    second = contract(b"two", source_id="SOURCE-2")
    forward = AuthorityRegistry((first, second))
    reverse = AuthorityRegistry((second, first))

    assert forward.registry_id == reverse.registry_id
    assert forward.to_json() == reverse.to_json()
    assert list(forward.current_sources()) == ["SOURCE-1", "SOURCE-2"]
    with pytest.raises(SourceVerificationError, match="duplicate"):
        AuthorityRegistry((first, first))
    with pytest.raises(SourceVerificationError, match="conflicting"):
        AuthorityRegistry(
            (
                first,
                contract(b"changed", source_id="SOURCE-1", revision="revision:2"),
            )
        )


def test_batch_verification_rejects_duplicate_or_conflicting_observation_identity() -> None:
    one = b"one"
    two = b"two"
    authority_registry = AuthorityRegistry(
        (
            contract(one, source_id="SOURCE-1"),
            contract(two, source_id="SOURCE-2"),
        )
    )
    observations = (
        SourceObservation(two, metadata(two, source_id="SOURCE-2")),
        SourceObservation(one, metadata(one, source_id="SOURCE-1")),
    )

    results = authority_registry.verify_many(observations)
    assert [item.observation_id for item in results] == sorted(
        item.observation_id for item in observations
    )
    assert all(item.is_authority_verified for item in results)
    with pytest.raises(SourceVerificationError, match="duplicate observation"):
        authority_registry.verify_many((observations[0], observations[0]))

    changed_two = b"two changed"
    conflict = SourceObservation(
        changed_two,
        metadata(changed_two, source_id="SOURCE-2"),
    )
    with pytest.raises(SourceVerificationError, match="conflicting observation"):
        authority_registry.verify_many((observations[0], conflict))
