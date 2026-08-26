from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, Mapping

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
    GovernanceSnapshot,
    GovernanceSourceBinding,
    ImpactModelError,
    SemanticChangeKind,
    diff_governance_snapshots,
    project_impact,
)


def binding(
    *, revision: str = "revision:1", content: object = "policy-v1"
) -> GovernanceSourceBinding:
    return GovernanceSourceBinding(
        authority_id="AUTHORITY-policy-owner",
        source_id="SOURCE-policy",
        revision=revision,
        content_sha256=canonical_sha256(content),
        source_type="SIGNED_POLICY_BUNDLE",
    )


def snapshot(
    version_id: str,
    payload: Mapping[str, Any],
    *,
    source_binding: GovernanceSourceBinding | None = None,
) -> GovernanceSnapshot:
    return GovernanceSnapshot(
        version_id=version_id,
        payload=payload,
        source_bindings=(source_binding or binding(),),
    )


def graph_node(
    node_id: str,
    node_type: str,
    provenance: ProvenanceBinding,
) -> FactNode:
    return FactNode(
        node_id=node_id,
        node_type=node_type,
        status=FactStatus.PROVEN,
        value={"identity": node_id},
        provenance=(provenance,),
    )


def reverse_dependency_graph(
    *, unsupported_dependent: bool = False
) -> tuple[EvidenceGraph, ProvenanceBinding, ProvenanceBinding]:
    stale = binding().to_provenance()
    current = binding(revision="revision:2", content="policy-v2").to_provenance()
    nodes: tuple[FactNode, ...] = (
        graph_node("FACT-policy", "FACT", stale),
        graph_node("RULE-dependent", "RULE", current),
        graph_node("CAPABILITY-dependent", "CAPABILITY", current),
        graph_node("TEMPLATE-dependent", "TEMPLATE", current),
        graph_node(
            "APP-PROVENANCE-dependent",
            "GENERATED_APPLICATION_PROVENANCE",
            current,
        ),
    )
    edges: tuple[FactEdge, ...] = (
        FactEdge("RULE-dependent", "DEPENDS_ON", "FACT-policy", ("SOURCE-policy",)),
        FactEdge(
            "CAPABILITY-dependent",
            "DEPENDS_ON",
            "RULE-dependent",
            ("SOURCE-policy",),
        ),
        FactEdge(
            "TEMPLATE-dependent",
            "DEPENDS_ON",
            "CAPABILITY-dependent",
            ("SOURCE-policy",),
        ),
        FactEdge(
            "APP-PROVENANCE-dependent",
            "DEPENDS_ON",
            "TEMPLATE-dependent",
            ("SOURCE-policy",),
        ),
    )
    if unsupported_dependent:
        report = graph_node("REPORT-dependent", "NARRATIVE_REPORT", current)
        nodes = (*nodes, report)
        edges = (
            *edges,
            FactEdge(
                "REPORT-dependent",
                "DEPENDS_ON",
                "FACT-policy",
                ("SOURCE-policy",),
            ),
        )
    return EvidenceGraph(nodes, edges), stale, current


def test_noop_diff_has_stable_empty_classifications_and_digest() -> None:
    governed = snapshot(
        "policy:1",
        {"facts": {"FACT-2": False, "FACT-1": True}, "rules": ["RULE-1"]},
    )

    first = diff_governance_snapshots(governed, governed)
    second = diff_governance_snapshots(governed, governed)

    assert first.is_noop
    assert first.added == first.removed == first.changed == ()
    assert first.diff_sha256 == second.diff_sha256
    assert first.to_json() == canonical_json(first.to_dict())


def test_reorder_only_entity_collections_are_semantically_equivalent() -> None:
    before = snapshot(
        "policy:1",
        {
            "facts": {"FACT-2": {"enabled": False}, "FACT-1": {"enabled": True}},
            "rules": [
                {"rule_id": "RULE-2", "effect": "DENY"},
                {"rule_id": "RULE-1", "effect": "ALLOW"},
            ],
        },
    )
    after = snapshot(
        "policy:2",
        {
            "rules": [
                {"effect": "ALLOW", "rule_id": "RULE-1"},
                {"effect": "DENY", "rule_id": "RULE-2"},
            ],
            "facts": {"FACT-1": {"enabled": True}, "FACT-2": {"enabled": False}},
        },
    )

    assert diff_governance_snapshots(before, after).is_noop


def test_real_semantic_change_is_added_removed_changed_and_stably_ordered() -> None:
    before = snapshot(
        "policy:1",
        {
            "facts": {"FACT-Z": False, "FACT-A": {"limit": 10}},
            "rules": {"RULE-B": {"effect": "DENY"}},
        },
    )
    after = snapshot(
        "policy:2",
        {
            "rules": {
                "RULE-C": {"effect": "ALLOW"},
                "RULE-B": {"effect": "DENY"},
            },
            "facts": {"FACT-A": {"limit": 20}, "FACT-B": True},
        },
    )

    result = diff_governance_snapshots(before, after)

    assert [(item.entity_type.value, item.entity_id) for item in result.added] == [
        ("FACT", "FACT-B"),
        ("RULE", "RULE-C"),
    ]
    assert result.removed_ids == ("FACT-Z",)
    assert result.changed_ids == ("FACT-A",)
    assert result.changed[0].kind is SemanticChangeKind.CHANGED
    assert result.changed[0].change_sha256 == canonical_sha256(result.changed[0].identity_payload())
    with pytest.raises(TypeError, match="immutable"):
        result.changed[0].after["limit"] = 30
    with pytest.raises(FrozenInstanceError):
        result.changed[0].entity_id = "FACT-mutated"  # type: ignore[misc]


def test_narrative_text_is_not_a_governed_semantic_diff_input() -> None:
    before = snapshot(
        "policy:1",
        {"facts": {"FACT-1": True}, "human_summary": "old narrative"},
    )
    after = snapshot(
        "policy:2",
        {"human_summary": "new narrative", "facts": {"FACT-1": True}},
    )

    assert diff_governance_snapshots(before, after).is_noop


def test_reverse_impact_is_transitive_typed_deduplicated_and_ordered() -> None:
    before = snapshot("policy:1", {"facts": {"FACT-policy": {"limit": 10}}})
    after = snapshot("policy:2", {"facts": {"FACT-policy": {"limit": 20}}})
    evidence_graph, _stale, _current = reverse_dependency_graph()

    impact = project_impact(
        diff_governance_snapshots(before, after),
        evidence_graph,
    )

    assert impact.affected_fact_ids == ("FACT-policy",)
    assert impact.affected_rule_ids == ("RULE-dependent",)
    assert impact.affected_capability_ids == ("CAPABILITY-dependent",)
    assert impact.affected_template_ids == ("TEMPLATE-dependent",)
    assert impact.affected_generated_application_provenance_ids == ("APP-PROVENANCE-dependent",)
    assert impact.reverse_transitive_ids == (
        "APP-PROVENANCE-dependent",
        "CAPABILITY-dependent",
        "RULE-dependent",
        "TEMPLATE-dependent",
    )
    assert impact.impact_sha256 == canonical_sha256(impact.identity_payload())


def test_stale_m2_4_provenance_propagates_through_reverse_relationships() -> None:
    first = snapshot("policy:1", {"facts": {"FACT-policy": True}})
    second = snapshot("policy:2", {"facts": {"FACT-policy": True}})
    evidence_graph, stale, current = reverse_dependency_graph()

    impact = project_impact(
        diff_governance_snapshots(first, second),
        evidence_graph,
        {current.source_id: (current.revision, current.content_sha256)},
    )

    assert impact.stale_evidence_ids == ("FACT-policy",)
    assert (
        stale.freshness_against(
            {current.source_id: (current.revision, current.content_sha256)}
        ).value
        == "STALE"
    )
    assert impact.affected_rule_ids == ("RULE-dependent",)
    assert impact.affected_generated_application_provenance_ids == ("APP-PROVENANCE-dependent",)


def test_unresolved_and_unsupported_impact_remain_explicit_without_invention() -> None:
    before = snapshot(
        "policy:1",
        {"facts": {"FACT-policy": 1}, "rules": {"RULE-unresolved": 1}},
    )
    after = snapshot(
        "policy:2",
        {"facts": {"FACT-policy": 2}, "rules": {"RULE-unresolved": 2}},
    )
    evidence_graph, _stale, _current = reverse_dependency_graph(unsupported_dependent=True)

    impact = project_impact(
        diff_governance_snapshots(before, after),
        evidence_graph,
    )

    assert impact.unresolved_reference_ids == ("RULE-unresolved",)
    assert impact.unknown_impact_ids == ("REPORT-dependent", "RULE-unresolved")
    assert impact.has_unknown_impact
    all_projected = set(impact.reverse_transitive_ids) | set(impact.unknown_impact_ids)
    assert "APPLICATION-invented" not in all_projected


def test_absent_relationship_evidence_keeps_downstream_impact_unknown() -> None:
    before = snapshot("policy:1", {"facts": {"FACT-policy": 1}})
    after = snapshot("policy:2", {"facts": {"FACT-policy": 2}})

    impact = project_impact(diff_governance_snapshots(before, after))

    assert impact.affected_fact_ids == ("FACT-policy",)
    assert impact.unresolved_reference_ids == ("FACT-policy",)
    assert impact.unknown_impact_ids == ("FACT-policy",)
    assert impact.has_unknown_impact


def test_ambiguous_or_unusable_governed_structures_fail_closed() -> None:
    source_binding = binding()
    conflicting = snapshot(
        "policy:bad",
        {"rules": {"RULE-1": {"rule_id": "RULE-2", "effect": "DENY"}}},
        source_binding=source_binding,
    )
    valid = snapshot(
        "policy:valid",
        {"rules": {"RULE-1": {"effect": "DENY"}}},
        source_binding=source_binding,
    )
    missing_id = snapshot(
        "policy:missing-id",
        {"capabilities": [{"name": "narrative only"}]},
        source_binding=source_binding,
    )

    with pytest.raises(ImpactModelError, match="conflicting entity ID"):
        diff_governance_snapshots(conflicting, valid)
    with pytest.raises(ImpactModelError, match="require capability_id"):
        diff_governance_snapshots(missing_id, valid)
    with pytest.raises(ImpactModelError, match="freshness propagation requires"):
        project_impact(diff_governance_snapshots(valid, valid), None, {})
