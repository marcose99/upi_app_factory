from __future__ import annotations

import json
from pathlib import Path
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
from factory.governance_evolution import (
    ExecutionFingerprint,
    GovernanceSnapshot,
    GovernanceSourceBinding,
    SemanticDiff,
    project_impact,
)
from factory.operational_acceptance import (
    BusinessValueDimension,
    CapabilityClaim,
    ClaimContract,
    ClaimDomain,
    EvidenceRequirement,
    GoldenDemoDossier,
    GoldenDemoError,
    Limitation,
    MANDATORY_NONCLAIMS,
    PORTFOLIO_APPLICATION_COUNT,
    REQUIRED_CAPABILITY_IDS,
    RegisteredClaim,
    ValueClosureInventory,
    ValueClosureStatus,
    build_golden_demo_projection_binding,
    render_golden_demo_html,
    run_independent_review,
    run_representative_operational_acceptance,
    validate_golden_demo_document,
    validate_golden_demo_projection,
    write_golden_demo_evidence,
)


ROOT = Path(__file__).resolve().parents[2]
SELECTED_SCENARIO_ID = "fixture_failed_debit"
SELECTED_CAPABILITIES = (
    "CAP-APPLICATION-ENGINEERING",
    "CAP-UPI-PAYMENT-PORTFOLIO",
)


def _binding(
    source_id: str,
    *,
    content_sha256: str | None = None,
    source_type: str = "CANONICAL_MACHINE_EVIDENCE",
) -> ProvenanceBinding:
    return ProvenanceBinding(
        source_id=source_id,
        revision="evidence:v1",
        content_sha256=content_sha256
        or canonical_sha256({"source_id": source_id, "revision": "evidence:v1"}),
        source_type=source_type,
    )


def _portfolio() -> dict[str, Any]:
    scenario_ids = (
        SELECTED_SCENARIO_ID,
        "fixture_refund_tracking",
        "fixture_duplicate_debit",
        "fixture_merchant_qr",
        "fixture_fraud_triage",
        "fixture_card_exception",
        "fixture_reconciliation",
        "fixture_dispute_evidence",
    )
    return {
        "application_packages": [
            {
                "path": f"applications/{scenario_id}/package.zip",
                "scenario_id": scenario_id,
                "sha256": canonical_sha256(
                    {"package": scenario_id, "format": "fixture"}
                ),
            }
            for scenario_id in scenario_ids
        ],
        "applications": [
            {
                "decision": "NEAR_PRODUCTION_CANDIDATE",
                "external_human_review_status": "PENDING_EXTERNAL_HUMAN_REVIEW",
                "near_production_candidate": True,
                "production_ready": False,
                "scenario_id": scenario_id,
            }
            for scenario_id in scenario_ids
        ],
        "external_human_review_status": "PENDING_EXTERNAL_HUMAN_REVIEW",
        "production_ready": False,
        "scenario_semantic_fingerprints": {
            scenario_id: canonical_sha256(
                {"scenario_id": scenario_id, "semantics": "fixture-distinct"}
            )
            for scenario_id in scenario_ids
        },
        "schema_version": "upi-app-factory.portfolio-acceptance.v1",
    }


def _inventory_and_review(
    operational_evidence: Any,
    portfolio: dict[str, Any],
    portfolio_binding: ProvenanceBinding,
    *,
    adverse_review: bool = False,
) -> tuple[ValueClosureInventory, Any, tuple[str, ...]]:
    nodes: list[FactNode] = []
    edges: list[FactEdge] = []
    claims: list[CapabilityClaim] = []
    current_sources: dict[str, tuple[str, str]] = {}
    operational_fact = operational_evidence.machine_evidence_fact()
    portfolio_fact = FactNode(
        node_id="FACT-AUTHENTICATED-EIGHT-APP-PORTFOLIO",
        node_type="AUTHENTICATED_MACHINE_EVIDENCE",
        status=FactStatus.PROVEN,
        value={
            "application_count": PORTFOLIO_APPLICATION_COUNT,
            "result": "PASS",
            "selected_scenario_id": SELECTED_SCENARIO_ID,
        },
        provenance=(portfolio_binding,),
        metadata={"authority": "MACHINE_OBSERVATION_ONLY"},
    )
    nodes.extend((operational_fact, portfolio_fact))
    selected_claim_ids: list[str] = []

    for index, capability_id in enumerate(sorted(REQUIRED_CAPABILITY_IDS), start=1):
        is_selected = capability_id in SELECTED_CAPABILITIES
        status = (
            ValueClosureStatus.PROVEN
            if is_selected
            else ValueClosureStatus.UNKNOWN_EXPLICIT
        )
        status_binding = (
            _binding(f"SOURCE-STATUS-{index:02d}") if is_selected else None
        )
        status_fact_id = capability_id
        if status_binding is not None:
            current_sources[status_binding.source_id] = (
                status_binding.revision,
                status_binding.content_sha256,
            )
        nodes.append(
            FactNode(
                node_id=status_fact_id,
                node_type="FACTORY_CAPABILITY",
                status=FactStatus(status.value),
                value=(
                    {"capability_id": capability_id, "observed": True}
                    if is_selected
                    else None
                ),
                provenance=(status_binding,) if status_binding is not None else (),
            )
        )
        evidence_fact = None
        if capability_id == "CAP-APPLICATION-ENGINEERING":
            evidence_fact = operational_fact
        elif capability_id == "CAP-UPI-PAYMENT-PORTFOLIO":
            evidence_fact = portfolio_fact
        supporting = [status_fact_id]
        evidence_ids: list[str] = []
        if evidence_fact is not None:
            supporting.append(evidence_fact.node_id)
            evidence_ids.append(evidence_fact.node_id)
            binding = evidence_fact.provenance[0]
            current_sources[binding.source_id] = (
                binding.revision,
                binding.content_sha256,
            )
            edges.append(
                FactEdge(
                    source_id=status_fact_id,
                    relation="VERIFIED_BY",
                    target_id=evidence_fact.node_id,
                    provenance_ids=(binding.source_id,),
                )
            )
        claim_id = f"CLAIM-GOLDEN-DEMO-{index:02d}"
        claims.append(
            CapabilityClaim(
                capability_id=capability_id,
                claim_id=claim_id,
                claim_text=(
                    f"Evidence classifies {capability_id} within deterministic local mock scope."
                ),
                status=status,
                status_fact_id=status_fact_id,
                business_value_dimension=(
                    BusinessValueDimension.DELIVERY_UTILITY
                    if capability_id == "CAP-APPLICATION-ENGINEERING"
                    else BusinessValueDimension.HUMAN_DECISION_CONFIDENCE
                ),
                supporting_fact_ids=tuple(supporting),
                machine_evidence_fact_ids=tuple(evidence_ids),
                limitations=(
                    Limitation(
                        f"LIMIT-GOLDEN-DEMO-{index:02d}",
                        "Evidence is local and mock-only and does not prove production readiness.",
                    ),
                ),
                public_claim_candidate=is_selected,
            )
        )
        if is_selected:
            selected_claim_ids.append(claim_id)

    graph = EvidenceGraph(nodes, edges)
    inventory = ValueClosureInventory(graph, current_sources, tuple(claims))
    claims_by_id = {claim.claim_id: claim for claim in inventory.claims}
    review = run_independent_review(
        graph,
        current_sources,
        tuple(
            RegisteredClaim(
                claims_by_id[claim_id],
                (
                    ClaimContract(
                        contract_id="CLAIM-CONTRACT-FIXTURE-EXECUTABLE-ONLY",
                        domain=ClaimDomain.FACTORY_CAPABILITY,
                        evidence_requirements=(
                            EvidenceRequirement(
                                requirement_id="REQ-FIXTURE-EXECUTABLE-ONLY",
                                node_types=("EXECUTABLE_EVIDENCE",),
                                source_types=("CANONICAL_MACHINE_EVIDENCE",),
                                accepted_results=("PASS",),
                            ),
                        ),
                    )
                    if adverse_review
                    and claims_by_id[claim_id].capability_id
                    == "CAP-UPI-PAYMENT-PORTFOLIO"
                    else ClaimContract.for_domain(ClaimDomain.FACTORY_CAPABILITY)
                ),
            )
            for claim_id in selected_claim_ids
        ),
    )
    return inventory, review, tuple(selected_claim_ids)


def _dossier(
    tmp_path: Path, *, adverse_review: bool = False, **overrides: Any
) -> GoldenDemoDossier:
    operational = run_representative_operational_acceptance(
        ROOT, tmp_path / "operational-workspace"
    )
    assert operational.result.status.value == "PASS"
    portfolio = _portfolio()
    portfolio_binding = _binding(
        "SOURCE-EIGHT-APP-PORTFOLIO-ACCEPTANCE",
        content_sha256=canonical_sha256(portfolio),
    )
    inventory, review, claim_ids = _inventory_and_review(
        operational,
        portfolio,
        portfolio_binding,
        adverse_review=adverse_review,
    )
    before = operational.scenario.governance_snapshot
    assert before is not None
    after_payload = json.loads(canonical_json(dict(before.payload)))
    after_payload["capabilities"] = [
        {
            "capability_id": "CAP-APPLICATION-ENGINEERING",
            "demo_control": "synthetic-controlled-evolution-fixture",
        }
    ]
    after = GovernanceSnapshot(
        version_id="synthetic-golden-demo-governance.v1",
        payload=after_payload,
        source_bindings=(
            GovernanceSourceBinding(
                authority_id="LOCAL-SYNTHETIC-DEMO-AUTHORITY",
                source_id="SOURCE-SYNTHETIC-GOVERNANCE-DEMO",
                revision="synthetic-demo:v1",
                content_sha256=canonical_sha256(after_payload),
                source_type="SYNTHETIC_GOVERNANCE_DEMO_RECORD",
            ),
        ),
        previous_snapshot_id=before.snapshot_id,
        supersedes_snapshot_id=before.snapshot_id,
    )
    semantic_diff = SemanticDiff.between(before, after)
    impact = project_impact(
        semantic_diff, inventory.graph, inventory.current_sources
    )
    old_fingerprint = operational.scenario.execution_fingerprint
    evolved_fingerprint = ExecutionFingerprint(
        factory_source_identity=old_fingerprint.factory_source_identity,
        requirement_identity=old_fingerprint.requirement_identity,
        governance_snapshot_identity=after.snapshot_id,
        evidence_snapshot_identity=old_fingerprint.evidence_snapshot_identity,
        tool_config_identity=old_fingerprint.tool_config_identity,
    )
    arguments = {
        "after_governance": after,
        "before_governance": before,
        "evolved_execution_fingerprint": evolved_fingerprint,
        "impact": impact,
        "independent_review": review,
        "operational_acceptance": operational,
        "portfolio_evidence": portfolio,
        "portfolio_provenance": portfolio_binding,
        "selected_claim_ids": claim_ids,
        "selected_scenario_id": SELECTED_SCENARIO_ID,
        "semantic_diff": semantic_diff,
        "value_closure": inventory,
    }
    arguments.update(overrides)
    return GoldenDemoDossier(**arguments)


def test_dossier_binds_eight_app_selection_claims_and_controlled_evolution(
    tmp_path: Path,
) -> None:
    dossier = _dossier(tmp_path)
    document = dossier.to_dict()

    assert validate_golden_demo_document(document) is True
    assert dossier.to_json() == canonical_json(document)
    assert document["portfolio_selection"]["application_count"] == 8
    assert document["portfolio_selection"]["selected_scenario_id"] == (
        SELECTED_SCENARIO_ID
    )
    assert document["portfolio_selection"]["portfolio_fact_ids"] == [
        "FACT-AUTHENTICATED-EIGHT-APP-PORTFOLIO"
    ]
    assert [stage["stage_id"] for stage in document["journey"]] == [
        "REQUIREMENT",
        "APPLICATION_ENGINEERING",
        "PRODUCT_ARTIFACTS_AND_TESTS",
        "QUALIFICATION_AND_REVIEW",
        "GOVERNANCE_CHANGE_AND_IMPACT",
        "CONTROLLED_EVOLUTION",
    ]
    assert document["governance_evolution"]["classification"] == (
        "SYNTHETIC_GOVERNED_CHANGE_DEMONSTRATION"
    )
    assert document["governance_evolution"]["is_live_regulatory_change"] is False
    assert document["governance_evolution"]["existing_execution_pin_unchanged"] is True
    assert document["governance_evolution"][
        "existing_execution_fingerprint_id"
    ] != document["governance_evolution"]["evolved_execution_fingerprint_id"]
    assert document["nonclaims"] == list(MANDATORY_NONCLAIMS)
    assert all(claim["limitations"] for claim in document["claims"])
    assert all(claim["supporting_fact_ids"] for claim in document["claims"])


def test_html_is_digest_bound_byte_parity_projection(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    encoded = dossier.to_json()
    projection = render_golden_demo_html(encoded)
    binding = build_golden_demo_projection_binding(encoded, projection)

    assert validate_golden_demo_projection(encoded, projection, binding) is True
    assert binding["dossier_id"] == dossier.dossier_id
    assert binding["projection_format"] == "HTML"
    assert 'meta name="canonical-json-sha256"' in projection
    assert f'data-claim-id="{dossier.to_dict()["claims"][0]["claim_id"]}"' in projection
    assert "No production deployment or production readiness is claimed." in projection
    assert "AI authority: NONE" in projection

    tampered = projection.replace("AI authority: NONE", "AI authority: PRESENT", 1)
    with pytest.raises(GoldenDemoError, match="parity projection"):
        validate_golden_demo_projection(encoded, tampered)


def test_adverse_reviewer_verdict_and_open_blocker_remain_visible(
    tmp_path: Path,
) -> None:
    dossier = _dossier(tmp_path, adverse_review=True)
    adverse_claim = next(
        claim
        for claim in dossier.to_dict()["claims"]
        if claim["capability_id"] == "CAP-UPI-PAYMENT-PORTFOLIO"
    )

    assert adverse_claim["reviewer_verdict"] == "DISPROVEN"
    assert adverse_claim["open_blocker_finding_ids"]
    projection = render_golden_demo_html(dossier.to_json())
    assert "DISPROVEN" in projection
    assert adverse_claim["claim_id"] in projection


def test_writer_emits_only_relative_portable_paths_and_valid_binding(
    tmp_path: Path,
) -> None:
    dossier = _dossier(tmp_path / "build")
    result = write_golden_demo_evidence(
        tmp_path / "public", "golden_demo/evidence_dossier", dossier
    )

    assert result["json_path"] == "golden_demo/evidence_dossier.json"
    assert result["html_path"] == "golden_demo/evidence_dossier.html"
    assert result["binding_path"] == "golden_demo/evidence_dossier.projection.json"
    json_text = (tmp_path / "public" / result["json_path"]).read_text(encoding="utf-8")
    html_text = (tmp_path / "public" / result["html_path"]).read_text(encoding="utf-8")
    binding = json.loads(
        (tmp_path / "public" / result["binding_path"]).read_text(encoding="utf-8")
    )
    assert validate_golden_demo_projection(json_text, html_text, binding) is True
    assert "/home/" not in json_text
    assert "/tmp/" not in json_text


def test_selection_must_resolve_in_authenticated_eight_application_portfolio(
    tmp_path: Path,
) -> None:
    with pytest.raises(GoldenDemoError, match="selected from the authenticated portfolio"):
        _dossier(tmp_path, selected_scenario_id="invented_product")


def test_portfolio_count_and_authenticated_fact_fail_closed(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path / "source")
    portfolio = json.loads(canonical_json(dict(dossier.portfolio_evidence)))
    portfolio["applications"].pop()
    binding = _binding(
        "SOURCE-EIGHT-APP-PORTFOLIO-ACCEPTANCE",
        content_sha256=canonical_sha256(portfolio),
    )
    with pytest.raises(GoldenDemoError, match="exactly eight applications"):
        _dossier(
            tmp_path / "count",
            portfolio_evidence=portfolio,
            portfolio_provenance=binding,
        )


def test_tampering_and_public_path_leak_are_rejected(tmp_path: Path) -> None:
    document = _dossier(tmp_path).to_dict()
    document["limitations"].append("Evidence exists at /home/reviewer/private.json.")
    document["limitations"].sort()
    body = {
        key: value
        for key, value in document.items()
        if key not in {"dossier_id", "dossier_sha256"}
    }
    document["dossier_sha256"] = canonical_sha256(body)
    document["dossier_id"] = f"GOLDEN-DEMO-DOSSIER-{document['dossier_sha256']}"

    with pytest.raises(GoldenDemoError, match="personal or local path"):
        validate_golden_demo_document(document)


def test_existing_execution_pin_cannot_silently_move_other_inputs(
    tmp_path: Path,
) -> None:
    source = _dossier(tmp_path / "source")
    evolved = source.evolved_execution_fingerprint
    moved = ExecutionFingerprint(
        factory_source_identity="FACTORY-SOURCE-INVENTED",
        requirement_identity=evolved.requirement_identity,
        governance_snapshot_identity=evolved.governance_snapshot_identity,
        evidence_snapshot_identity=evolved.evidence_snapshot_identity,
        tool_config_identity=evolved.tool_config_identity,
    )
    with pytest.raises(GoldenDemoError, match="non-governance execution inputs"):
        _dossier(
            tmp_path / "moved",
            evolved_execution_fingerprint=moved,
        )
