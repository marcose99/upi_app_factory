from __future__ import annotations

import pytest

from factory.ai_governance import (
    AISystem, AISystemRegistry, GovernedLearningRequest,
    GovernedSelfLearningFoundation, GovernanceError, LearningEnvelope,
    RegulatoryMetadata, RuleVersionChain,
)
from factory.ai_governance.incident_drift import IncidentDriftRecorder
from factory.ai_governance.risk_impact import RiskImpactAssessment, RiskImpactHook


def request(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "system_id": "builder", "system_version": "1", "learning_class": "L2",
        "data_classes": ["source"], "objective": "implementation",
        "change_class": "engineering_candidate", "change_budget": 2,
        "evaluation_score": .9, "held_out_score": .9,
        "requested_promotion": 2, "acceptance_bar_delta": 0,
    }
    value.update(changes)
    return value


def foundation() -> GovernedSelfLearningFoundation:
    registry = AISystemRegistry()
    registry.register(AISystem("builder", "1"))
    envelope = LearningEnvelope(frozenset({"source"}), frozenset({"implementation"}),
                                frozenset({"engineering_candidate"}), 2, .8, .8, 4)
    return GovernedSelfLearningFoundation(registry, envelope)


def test_registry_rejects_unknown_duplicate_and_unversioned() -> None:
    registry = AISystemRegistry()
    registry.register(AISystem("x", "1"))
    with pytest.raises(GovernanceError):
        registry.register(AISystem("x", "1"))
    with pytest.raises(GovernanceError):
        registry.require("unknown", "1")
    with pytest.raises(GovernanceError):
        registry.require("x", "")


@pytest.mark.parametrize("change", [
    {"data_classes": ["customer"]}, {"objective": "weaken_tests"},
    {"change_budget": 3}, {"evaluation_score": .7}, {"held_out_score": .7},
    {"acceptance_bar_delta": -1},
])
def test_envelope_denies_every_out_of_bounds_dimension(change: dict[str, object]) -> None:
    assert foundation().authorize(request(**change)).outcome == "deny"


def test_kill_switch_and_l4_are_pre_mutation_gates() -> None:
    control = foundation()
    control.set_kill_switch(True)
    assert control.authorize(request()).outcome == "deny"
    control.set_kill_switch(False)
    assert control.authorize(request(learning_class="L4", requested_promotion=4)).outcome == "human_gate"


def test_rule_chain_is_hash_chained_and_rollback_only_selects() -> None:
    chain = RuleVersionChain()
    first = chain.append("1", {"threshold": 1})
    second = chain.append("2", {"threshold": 2})
    chain.rollback("1")
    assert chain.active == first
    assert chain.versions == (first, second)
    assert chain.verify()


def test_regulatory_metadata_is_claim_safe() -> None:
    assert RegulatoryMetadata.parse({"alignment": "alignment mapping", "readiness_evidence": ["test report"]})
    with pytest.raises(GovernanceError):
        RegulatoryMetadata.parse({"alignment": "RBI-approved", "readiness_evidence": []})


def test_invalid_and_unknown_requests_fail_closed() -> None:
    assert foundation().authorize({}).outcome == "deny"
    assert foundation().authorize(request(system_id="other")).outcome == "deny"


def test_risk_impact_drift_incidents_are_deterministic() -> None:
    class Store:
        def __init__(self) -> None: self.calls: list[tuple[object, ...]] = []
        def record_incident(self, campaign_id: str, activity_id: str | None,
                            failure_class: str, payload: dict[str, object]) -> str:
            call = (campaign_id, activity_id, failure_class, payload)
            self.calls.append(call)
            return repr(call)

    store = Store()
    recorder = IncidentDriftRecorder(store)
    assert recorder.drift("campaign", "held-out drift") == recorder.drift("campaign", "held-out drift")
    assert store.calls[0] == store.calls[1]
    hook = RiskImpactHook(lambda unused: RiskImpactAssessment("high", "high", False))
    with pytest.raises(GovernanceError):
        hook.assess(GovernedLearningRequest.parse(request()))
