from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.documentation import (
    EvidenceGraph,
    FactEdge,
    FactNode,
    FactStatus,
    ProvenanceBinding,
    canonical_json,
    canonical_sha256,
)
from factory.operational_acceptance import (
    BusinessValueDimension,
    CapabilityClaim,
    ChallengeKind,
    ClaimContract,
    ClaimDomain,
    EvidenceRequirement,
    FindingSeverity,
    IndependentReviewError,
    Limitation,
    REVIEWER_VERDICTS,
    RegisteredClaim,
    ReviewerVerdict,
    ValueClosureStatus,
    run_independent_review,
    validate_independent_review_document,
    write_independent_review_evidence,
)


def binding(source_id: str, source_type: str) -> ProvenanceBinding:
    return ProvenanceBinding(
        source_id=source_id,
        revision="revision:1",
        content_sha256=canonical_sha256(
            {"revision": "revision:1", "source_id": source_id}
        ),
        source_type=source_type,
    )


def build_review_input(
    *,
    status: ValueClosureStatus = ValueClosureStatus.PROVEN,
    domain: ClaimDomain = ClaimDomain.FACTORY_CAPABILITY,
    evidence_result: str = "PASS",
    evidence_node_type: str = "MACHINE_EVIDENCE",
    evidence_source_type: str = "MACHINE_EXECUTION_RECORD",
    status_source_type: str = "CANONICAL_MACHINE_EVIDENCE",
    include_evidence: bool | None = None,
    link_evidence: bool = True,
    stale_evidence: bool = False,
) -> tuple[EvidenceGraph, dict[str, tuple[str, str]], RegisteredClaim]:
    positive = status in {ValueClosureStatus.PROVEN, ValueClosureStatus.PARTIAL}
    if include_evidence is None:
        include_evidence = positive
    status_binding = binding("SOURCE-CLAIM-STATUS", status_source_type)
    status_node = FactNode(
        node_id="FACT-CLAIM-STATUS",
        node_type="FACTORY_CAPABILITY",
        status=FactStatus(status.value),
        value={"capability": "reviewed"} if status is ValueClosureStatus.PROVEN else None,
        provenance=(status_binding,) if status is ValueClosureStatus.PROVEN else (),
    )
    nodes = [status_node]
    edges: list[FactEdge] = []
    evidence_ids: tuple[str, ...] = ()
    supporting_ids = [status_node.node_id]
    current_sources: dict[str, tuple[str, str]] = {}
    if status is ValueClosureStatus.PROVEN:
        current_sources[status_binding.source_id] = (
            status_binding.revision,
            status_binding.content_sha256,
        )
    if include_evidence:
        evidence_binding = binding("SOURCE-CLAIM-EVIDENCE", evidence_source_type)
        evidence_node = FactNode(
            node_id="FACT-CLAIM-EVIDENCE",
            node_type=evidence_node_type,
            status=FactStatus.PROVEN,
            value={"result": evidence_result},
            provenance=(evidence_binding,),
        )
        nodes.append(evidence_node)
        evidence_ids = (evidence_node.node_id,)
        supporting_ids.append(evidence_node.node_id)
        if link_evidence:
            edges.append(
                FactEdge(
                    source_id=status_node.node_id,
                    relation="VERIFIED_BY",
                    target_id=evidence_node.node_id,
                    provenance_ids=(evidence_binding.source_id,),
                )
            )
        current_sources[evidence_binding.source_id] = (
            evidence_binding.revision,
            (
                "0" * 64
                if stale_evidence
                else evidence_binding.content_sha256
            ),
        )
    claim = CapabilityClaim(
        capability_id="CAP-INDEPENDENTLY-REVIEWED",
        claim_id="CLAIM-INDEPENDENTLY-REVIEWED",
        claim_text=(
            "The registered local factory capability satisfies its explicit "
            "evidence contract."
        ),
        status=status,
        status_fact_id=status_node.node_id,
        business_value_dimension=BusinessValueDimension.HUMAN_DECISION_CONFIDENCE,
        supporting_fact_ids=tuple(supporting_ids),
        machine_evidence_fact_ids=evidence_ids,
        limitations=(
            Limitation(
                "LIMIT-LOCAL-MOCK-SCOPE",
                "The review covers deterministic local mock evidence and grants "
                "no production authority.",
            ),
        ),
        public_claim_candidate=False,
    )
    return (
        EvidenceGraph(nodes, edges),
        current_sources,
        RegisteredClaim(claim, ClaimContract.for_domain(domain)),
    )


def test_current_authenticated_evidence_can_prove_registered_local_claim() -> None:
    graph, sources, registration = build_review_input()

    report = run_independent_review(graph, sources, (registration,))
    review = report.reviews[0]

    assert review.verdict is ReviewerVerdict.PROVEN
    assert report.overall_verdict is ReviewerVerdict.PROVEN
    assert report.open_blocker_finding_ids == ()
    assert [item.challenge for item in review.findings] == list(ChallengeKind)
    assert all(
        item.verdict in {ReviewerVerdict.PROVEN, ReviewerVerdict.NOT_APPLICABLE}
        for item in review.findings
    )
    assert review.evidence_assessments[0]["evidence_fact_id"] == (
        "FACT-CLAIM-EVIDENCE"
    )
    assert review.evidence_assessments[0]["provenance"][0]["source_id"] == (
        "SOURCE-CLAIM-EVIDENCE"
    )
    fact = report.machine_evidence_fact()
    assert fact.status is FactStatus.PROVEN
    assert fact.value["result"] == "PROVEN"
    assert fact.metadata["authority"] == "MACHINE_OBSERVATION_ONLY"
    assert report.evidence_graph().node(fact.node_id) == fact
    assert validate_independent_review_document(report.to_dict()) is True


def test_same_facts_and_registration_produce_same_canonical_review() -> None:
    graph, sources, registration = build_review_input()

    first = run_independent_review(graph, sources, (registration,))
    second = run_independent_review(graph, dict(reversed(tuple(sources.items()))), (registration,))

    assert first.review_id == second.review_id
    assert first.review_sha256 == second.review_sha256
    assert first.to_json() == second.to_json()
    assert first.to_json() == canonical_json(first.to_dict())


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (ValueClosureStatus.PROVEN, ReviewerVerdict.PROVEN),
        (ValueClosureStatus.PARTIAL, ReviewerVerdict.PARTIAL),
        (ValueClosureStatus.NOT_IMPLEMENTED, ReviewerVerdict.DISPROVEN),
        (ValueClosureStatus.UNKNOWN_EXPLICIT, ReviewerVerdict.UNKNOWN),
        (ValueClosureStatus.NOT_APPLICABLE, ReviewerVerdict.NOT_APPLICABLE),
    ),
)
def test_reviewer_preserves_typed_adverse_and_indeterminate_verdicts(
    status: ValueClosureStatus, expected: ReviewerVerdict
) -> None:
    graph, sources, registration = build_review_input(status=status)

    report = run_independent_review(graph, sources, (registration,))

    assert report.reviews[0].verdict is expected
    assert {item.value for item in REVIEWER_VERDICTS} == {
        "PROVEN",
        "DISPROVEN",
        "PARTIAL",
        "UNKNOWN",
        "NOT_APPLICABLE",
    }
    if expected not in {ReviewerVerdict.PROVEN, ReviewerVerdict.NOT_APPLICABLE}:
        assert report.open_blocker_finding_ids
        assert report.to_dict()["summary"]["open_blocker_count"] > 0


def test_missing_stale_broken_or_unlinked_evidence_cannot_pass() -> None:
    cases = (
        build_review_input(include_evidence=False),
        build_review_input(stale_evidence=True),
        build_review_input(evidence_result="FAIL"),
        build_review_input(link_evidence=False),
    )

    verdicts = [
        run_independent_review(graph, sources, (registration,)).overall_verdict
        for graph, sources, registration in cases
    ]

    assert ReviewerVerdict.PROVEN not in verdicts
    assert verdicts[0] is ReviewerVerdict.UNKNOWN
    assert verdicts[1] is ReviewerVerdict.UNKNOWN
    assert verdicts[2] is ReviewerVerdict.DISPROVEN
    assert verdicts[3] is ReviewerVerdict.DISPROVEN


@pytest.mark.parametrize(
    "domain",
    (
        ClaimDomain.PRODUCTION_READINESS,
        ClaimDomain.REGULATORY_COMPLIANCE,
        ClaimDomain.SECURITY_ASSURANCE,
    ),
)
def test_generic_local_evidence_cannot_prove_production_compliance_or_security(
    domain: ClaimDomain,
) -> None:
    graph, sources, registration = build_review_input(domain=domain)

    report = run_independent_review(graph, sources, (registration,))
    contract_finding = next(
        item
        for item in report.reviews[0].findings
        if item.challenge is ChallengeKind.CLAIM_CONTRACT_SATISFACTION
    )

    assert report.overall_verdict is ReviewerVerdict.DISPROVEN
    assert contract_finding.verdict is ReviewerVerdict.DISPROVEN
    assert contract_finding.blocker is True
    assert contract_finding.finding_id in report.open_blocker_finding_ids
    assert registration.claim.limitations[0].limitation_id in (
        contract_finding.limitation_ids
    )


def test_ai_statement_cannot_be_configured_or_used_as_review_authority() -> None:
    with pytest.raises(IndependentReviewError, match="AI or LLM"):
        EvidenceRequirement(
            "REQ-AI-OPINION",
            ("AI_STATEMENT",),
            ("AI_STATEMENT",),
            ("PROVEN",),
        )

    graph, sources, registration = build_review_input(
        evidence_node_type="MODEL_GENERATED_NARRATIVE",
        evidence_source_type="AI_STATEMENT",
    )
    report = run_independent_review(graph, sources, (registration,))
    authority_finding = next(
        item
        for item in report.reviews[0].findings
        if item.challenge is ChallengeKind.AI_AUTHORITY_BOUNDARY
    )
    assert authority_finding.verdict is ReviewerVerdict.DISPROVEN
    assert report.overall_verdict is ReviewerVerdict.DISPROVEN

    status_graph, status_sources, status_registration = build_review_input(
        status_source_type="AI_STATEMENT"
    )
    status_report = run_independent_review(
        status_graph, status_sources, (status_registration,)
    )
    status_authority_finding = next(
        item
        for item in status_report.reviews[0].findings
        if item.challenge is ChallengeKind.AI_AUTHORITY_BOUNDARY
    )
    assert status_authority_finding.verdict is ReviewerVerdict.DISPROVEN
    assert status_report.overall_verdict is ReviewerVerdict.DISPROVEN


@pytest.mark.parametrize(
    "domain",
    (
        ClaimDomain.PRODUCTION_READINESS,
        ClaimDomain.REGULATORY_COMPLIANCE,
        ClaimDomain.SECURITY_ASSURANCE,
    ),
)
def test_protected_claim_contract_cannot_be_weakened_by_the_caller(
    domain: ClaimDomain,
) -> None:
    generic_requirement = EvidenceRequirement(
        "REQ-GENERIC-LOCAL-RECORD",
        ("MACHINE_EVIDENCE",),
        ("MACHINE_EXECUTION_RECORD",),
        ("PASS",),
    )

    with pytest.raises(IndependentReviewError, match="closed governed"):
        ClaimContract(
            contract_id=f"CLAIM-CONTRACT-{domain.value}-V1",
            domain=domain,
            evidence_requirements=(generic_requirement,),
        )

    governed = ClaimContract.for_domain(domain)
    with pytest.raises(IndependentReviewError, match="closed governed"):
        ClaimContract(
            contract_id=governed.contract_id,
            domain=domain,
            evidence_requirements=governed.evidence_requirements,
            blocks_adoption=False,
            adverse_severity=FindingSeverity.LOW,
        )


def test_serialized_review_detects_tampering_and_preserves_blockers() -> None:
    graph, sources, registration = build_review_input(evidence_result="FAIL")
    report = run_independent_review(graph, sources, (registration,))
    document = report.to_dict()

    assert validate_independent_review_document(document) is True
    assert document["open_blocker_finding_ids"]

    tampered = json.loads(report.to_json())
    tampered["reviews"][0]["verdict"] = "PROVEN"
    with pytest.raises(IndependentReviewError, match="review_sha256"):
        validate_independent_review_document(tampered)

    tampered = json.loads(report.to_json())
    tampered["authority_boundary"]["self_awarded_readiness"] = True
    with pytest.raises(IndependentReviewError, match="authority boundary"):
        validate_independent_review_document(tampered)


def test_written_review_is_canonical_portable_and_non_authoritative(
    tmp_path: Path,
) -> None:
    graph, sources, registration = build_review_input(domain=ClaimDomain.PRODUCTION_READINESS)
    report = run_independent_review(graph, sources, (registration,))
    path = tmp_path / "evidence/independent_review.json"

    summary = write_independent_review_evidence(report, path)
    encoded = path.read_text(encoding="utf-8")

    assert encoded == canonical_json(report.to_dict()) + "\n"
    assert str(tmp_path) not in encoded
    assert summary["status"] == "DISPROVEN"
    assert summary["open_blocker_count"] > 0
    assert report.to_dict()["authority_boundary"] == {
        "adoption_authority": "SUPERVISOR_AND_HUMAN_GATES",
        "ai_authority": "NONE",
        "record_role": "DETERMINISTIC_EVIDENCE_REVIEW",
        "self_awarded_readiness": False,
    }
