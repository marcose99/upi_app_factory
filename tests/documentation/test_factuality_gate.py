import pytest

from factory.documentation import (
    Claim,
    EvidenceGraph,
    FactNode,
    FactStatus,
    FactualityError,
    ProvenanceBinding,
    canonical_sha256,
    validate_factuality,
)


def proven_graph() -> tuple[EvidenceGraph, ProvenanceBinding]:
    source = ProvenanceBinding(
        "SRC-TEST", "git:abc", canonical_sha256({"passed": True}), "TEST_RESULT"
    )
    node = FactNode("FACT-PASS", "TEST_RESULT", FactStatus.PROVEN, {"passed": True}, (source,))
    return EvidenceGraph((node,)), source


def test_factuality_gate_accepts_only_current_proven_support() -> None:
    graph, source = proven_graph()
    result = validate_factuality(
        (Claim("CLAIM-1", "The targeted test passed.", ("FACT-PASS",)),),
        graph,
        {source.source_id: (source.revision, source.content_sha256)},
    )
    assert result == {
        "claim_count": 1,
        "gate": "DOCUMENT_AND_EVIDENCE_FACTUALITY_GATE",
        "status": "PROVEN",
        "validated_claim_ids": ["CLAIM-1"],
    }


@pytest.mark.parametrize("current", [{}, {"SRC-TEST": ("git:old", "0" * 64)}])
def test_factuality_gate_rejects_missing_or_stale_source_identity(
    current: dict[str, tuple[str, str]],
) -> None:
    graph, _ = proven_graph()
    with pytest.raises(FactualityError, match="lacks current PROVEN support"):
        validate_factuality((Claim("CLAIM-1", "Passed.", ("FACT-PASS",)),), graph, current)


def test_factuality_gate_rejects_unsupported_and_unknown_claims() -> None:
    graph = EvidenceGraph((FactNode("FACT-UNKNOWN", "SLO", FactStatus.NOT_YET_MEASURED),))
    with pytest.raises(FactualityError, match="unknown facts"):
        validate_factuality((Claim("CLAIM-1", "Production ready.", ("MISSING",)),), graph, {})
    with pytest.raises(FactualityError, match="lacks current PROVEN support"):
        validate_factuality((Claim("CLAIM-2", "Latency is 10ms.", ("FACT-UNKNOWN",)),), graph, {})


def test_claim_rejects_unstable_or_blank_identity() -> None:
    with pytest.raises(FactualityError, match="claim_id"):
        Claim(" CLAIM-1 ", "A claim.", ("FACT-1",))
