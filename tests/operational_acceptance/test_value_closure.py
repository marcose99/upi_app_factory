from __future__ import annotations

import json
from typing import Any

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
    Limitation,
    PublicClaimEligibility,
    REQUIRED_CAPABILITY_IDS,
    ValueClosureError,
    ValueClosureInventory,
    ValueClosureStatus,
    validate_value_closure_document,
)


STATUS_BY_CAPABILITY = {
    "CAP-APPLICATION-ENGINEERING": ValueClosureStatus.PROVEN,
    "CAP-UPI-PAYMENT-PORTFOLIO": ValueClosureStatus.PARTIAL,
    "CAP-SECURITY-GOVERNANCE": ValueClosureStatus.PROVEN,
    "CAP-MAINTAINABILITY": ValueClosureStatus.PARTIAL,
    "CAP-REPRODUCIBILITY": ValueClosureStatus.PROVEN,
    "CAP-OPERATIONAL-ACCEPTANCE": ValueClosureStatus.NOT_YET_MEASURED,
    "CAP-CLEAN-ROOM-RECONSTRUCTION": ValueClosureStatus.UNKNOWN_EXPLICIT,
    "CAP-EXTERNAL-DOMAIN-CONTINUITY": ValueClosureStatus.NOT_IMPLEMENTED,
    "CAP-SUPPLY-CHAIN-DEPENDENCY-CONTINUITY": ValueClosureStatus.PARTIAL,
    "CAP-HUMAN-REVIEW": ValueClosureStatus.UNKNOWN_EXPLICIT,
    "CAP-GOLDEN-DEMO-READINESS": ValueClosureStatus.PARTIAL,
}


def binding(
    source_id: str,
    revision: str = "revision:1",
    source_type: str = "MACHINE_EXECUTION_RECORD",
) -> ProvenanceBinding:
    return ProvenanceBinding(
        source_id=source_id,
        revision=revision,
        content_sha256=canonical_sha256({"source_id": source_id, "revision": revision}),
        source_type=source_type,
    )


def build_inventory(
    *,
    reverse: bool = False,
    omit_capability: str | None = None,
    evidence_node_type: str = "MACHINE_EVIDENCE",
    evidence_source_type: str = "MACHINE_EXECUTION_RECORD",
    evidence_result: str = "PASS",
    link_evidence: bool = True,
) -> tuple[ValueClosureInventory, dict[str, tuple[str, str]]]:
    nodes: list[FactNode] = []
    edges: list[FactEdge] = []
    claims: list[CapabilityClaim] = []
    current_sources: dict[str, tuple[str, str]] = {}
    for index, capability_id in enumerate(sorted(REQUIRED_CAPABILITY_IDS), start=1):
        if capability_id == omit_capability:
            continue
        status = STATUS_BY_CAPABILITY[capability_id]
        fact_id = f"FACT-CLOSURE-{index:02d}"
        claim_id = f"CLAIM-CLOSURE-{index:02d}"
        supporting = [fact_id]
        evidence_ids: list[str] = []
        status_provenance: tuple[ProvenanceBinding, ...] = ()
        status_value: Any = None
        if status is ValueClosureStatus.PROVEN:
            status_source = binding(f"SOURCE-STATUS-{index:02d}")
            status_provenance = (status_source,)
            status_value = {"capability_id": capability_id, "observed": True}
            current_sources[status_source.source_id] = (
                status_source.revision,
                status_source.content_sha256,
            )
        nodes.append(
            FactNode(
                node_id=fact_id,
                node_type="FACTORY_CAPABILITY",
                status=FactStatus(status.value),
                value=status_value,
                provenance=status_provenance,
            )
        )
        if status in {ValueClosureStatus.PROVEN, ValueClosureStatus.PARTIAL}:
            evidence_id = f"EVIDENCE-MACHINE-{index:02d}"
            evidence_source = binding(
                f"SOURCE-MACHINE-{index:02d}", source_type=evidence_source_type
            )
            nodes.append(
                FactNode(
                    node_id=evidence_id,
                    node_type=evidence_node_type,
                    status=FactStatus.PROVEN,
                    value={
                        "command": "supported-local-entrypoint",
                        "result": evidence_result,
                    },
                    provenance=(evidence_source,),
                )
            )
            if link_evidence:
                edges.append(
                    FactEdge(
                        source_id=fact_id,
                        relation="VERIFIED_BY",
                        target_id=evidence_id,
                        provenance_ids=(evidence_source.source_id,),
                    )
                )
            current_sources[evidence_source.source_id] = (
                evidence_source.revision,
                evidence_source.content_sha256,
            )
            evidence_ids.append(evidence_id)
            supporting.append(evidence_id)
        claims.append(
            CapabilityClaim(
                capability_id=capability_id,
                claim_id=claim_id,
                claim_text=f"Evidence classifies {capability_id} within the local mock scope.",
                status=status,
                status_fact_id=fact_id,
                business_value_dimension=(
                    BusinessValueDimension.DEMONSTRATION_TRUST
                    if capability_id == "CAP-GOLDEN-DEMO-READINESS"
                    else BusinessValueDimension.HUMAN_DECISION_CONFIDENCE
                ),
                supporting_fact_ids=tuple(reversed(supporting) if reverse else supporting),
                machine_evidence_fact_ids=tuple(evidence_ids),
                limitations=(
                    Limitation(
                        f"LIMIT-{index:02d}",
                        "The evidence is local, deterministic, and does not prove production readiness.",
                    ),
                ),
                public_claim_candidate=capability_id
                in {"CAP-APPLICATION-ENGINEERING", "CAP-UPI-PAYMENT-PORTFOLIO"},
            )
        )
    if reverse:
        nodes.reverse()
        claims.reverse()
        current_sources = dict(reversed(tuple(current_sources.items())))
    return (
        ValueClosureInventory(EvidenceGraph(nodes, edges), current_sources, tuple(claims)),
        current_sources,
    )


def test_inventory_covers_enterprise_value_truth_with_stable_statuses() -> None:
    inventory, _sources = build_inventory()
    document = inventory.to_dict()

    assert {item["capability_id"] for item in document["capabilities"]} == set(
        REQUIRED_CAPABILITY_IDS
    )
    assert document["status_summary"] == {
        "NOT_APPLICABLE": 0,
        "NOT_IMPLEMENTED": 1,
        "NOT_YET_MEASURED": 1,
        "PARTIAL": 4,
        "PROVEN": 3,
        "UNKNOWN_EXPLICIT": 2,
    }
    assert validate_value_closure_document(document) is True
    assert inventory.to_json() == canonical_json(document)
    assert inventory.inventory_id == f"VALUE-CLOSURE-{inventory.inventory_digest}"


def test_order_does_not_change_json_digest_or_provenance_projection() -> None:
    first, _first_sources = build_inventory()
    second, _second_sources = build_inventory(reverse=True)

    assert first.inventory_digest == second.inventory_digest
    assert first.to_json() == second.to_json()
    entries = first.to_dict()["capabilities"]
    assert [(row["capability_id"], row["claim_id"]) for row in entries] == sorted(
        (row["capability_id"], row["claim_id"]) for row in entries
    )
    proven = next(row for row in entries if row["status"] == "PROVEN")
    assert proven["evidence_provenance"][0]["content_sha256"]
    assert proven["evidence_provenance"][0]["source_id"].startswith("SOURCE-MACHINE-")
    assert proven["evidence_provenance"][0]["relationship"] == "VERIFIED_BY"
    assert proven["evidence_provenance"][0]["relationship_id"].startswith("EDGE-")


def test_proven_status_requires_current_machine_evidence() -> None:
    inventory, sources = build_inventory()
    original = next(
        item for item in inventory.claims if item.status is ValueClosureStatus.PROVEN
    )
    without_evidence = CapabilityClaim(
        capability_id=original.capability_id,
        claim_id=original.claim_id,
        claim_text=original.claim_text,
        status=original.status,
        status_fact_id=original.status_fact_id,
        business_value_dimension=original.business_value_dimension,
        supporting_fact_ids=(original.status_fact_id,),
        limitations=original.limitations,
        public_claim_candidate=True,
    )
    claims = tuple(without_evidence if item is original else item for item in inventory.claims)

    with pytest.raises(ValueClosureError, match="requires machine evidence"):
        ValueClosureInventory(inventory.graph, sources, claims)

    stale_sources = dict(sources)
    evidence_node = inventory.graph.node(original.machine_evidence_fact_ids[0])
    source_id = evidence_node.provenance[0].source_id
    stale_sources[source_id] = ("revision:stale", "0" * 64)
    with pytest.raises(ValueClosureError, match="lacks current PROVEN support|stale"):
        ValueClosureInventory(inventory.graph, stale_sources, inventory.claims)


def test_narrative_or_ai_label_cannot_substitute_for_machine_evidence() -> None:
    with pytest.raises(ValueClosureError, match="is not machine evidence"):
        build_inventory(evidence_node_type="MODEL_GENERATED_NARRATIVE")
    with pytest.raises(ValueClosureError, match="authenticated machine source type"):
        build_inventory(evidence_source_type="AI_STATEMENT")


def test_non_passing_or_unlinked_machine_record_cannot_grant_closure() -> None:
    with pytest.raises(ValueClosureError, match="lacks a passing result"):
        build_inventory(evidence_result="FAIL")
    with pytest.raises(ValueClosureError, match="not linked by VERIFIED_BY"):
        build_inventory(link_evidence=False)


def test_status_must_match_the_canonical_status_fact() -> None:
    inventory, sources = build_inventory()
    original = next(
        item for item in inventory.claims if item.status is ValueClosureStatus.UNKNOWN_EXPLICIT
    )
    overstated = CapabilityClaim(
        capability_id=original.capability_id,
        claim_id=original.claim_id,
        claim_text=original.claim_text,
        status=ValueClosureStatus.PROVEN,
        status_fact_id=original.status_fact_id,
        business_value_dimension=original.business_value_dimension,
        supporting_fact_ids=original.supporting_fact_ids,
        machine_evidence_fact_ids=(),
        limitations=original.limitations,
        public_claim_candidate=True,
    )
    claims = tuple(overstated if item is original else item for item in inventory.claims)

    with pytest.raises(ValueClosureError, match="status does not match"):
        ValueClosureInventory(inventory.graph, sources, claims)


def test_inventory_fails_closed_when_a_required_dimension_is_omitted() -> None:
    with pytest.raises(ValueClosureError, match="CAP-HUMAN-REVIEW"):
        build_inventory(omit_capability="CAP-HUMAN-REVIEW")


def test_public_projection_selects_only_proven_candidates_and_keeps_limitations() -> None:
    inventory, _sources = build_inventory()
    projection = inventory.public_claims()

    assert [item["capability_id"] for item in projection["claims"]] == [
        "CAP-APPLICATION-ENGINEERING"
    ]
    assert projection["claims"][0]["status"] == "PROVEN"
    assert projection["claims"][0]["limitations"]
    assert projection["source_inventory_digest"] == inventory.inventory_digest
    assert projection["projection_digest"] == canonical_sha256(
        {key: value for key, value in projection.items() if key != "projection_digest"}
    )
    partial = next(
        item
        for item in inventory.to_dict()["capabilities"]
        if item["capability_id"] == "CAP-UPI-PAYMENT-PORTFOLIO"
    )
    assert partial["public_claim_eligibility"] == (
        PublicClaimEligibility.NOT_ELIGIBLE_NOT_PROVEN.value
    )


@pytest.mark.parametrize(
    "unsafe_text",
    (
        "Evidence exists at /home/reviewer/private/result.json.",
        "Evidence exists at file:///tmp/private-result.json.",
        "Evidence was emitted for campaign_id=temporary-123.",
        "Evidence was emitted with token=do-not-publish.",
    ),
)
def test_public_text_rejects_personal_paths_and_transient_campaign_ids(
    unsafe_text: str,
) -> None:
    with pytest.raises(ValueClosureError):
        Limitation("LIMIT-SAFE", unsafe_text)


def test_serialized_document_validation_detects_tampering() -> None:
    inventory, _sources = build_inventory()
    tampered = json.loads(inventory.to_json())
    non_proven = next(
        item for item in tampered["capabilities"] if item["status"] != "PROVEN"
    )
    non_proven["status"] = "PROVEN"

    with pytest.raises(ValueClosureError, match="digest is invalid"):
        validate_value_closure_document(tampered)


def test_canonical_fact_status_vocabulary_includes_value_closure_absence_states() -> None:
    assert FactStatus.PARTIAL.value == "PARTIAL"
    assert FactStatus.NOT_IMPLEMENTED.value == "NOT_IMPLEMENTED"
