from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from factory.ai_governance import GovernanceDecision
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.manifest import CampaignManifest


class Policy:
    def evaluate(self, action: str, risk: str) -> object:
        return SimpleNamespace(outcome="allow")


def engine(decision: str) -> ControlPlaneEngine:
    value = cast(Any, object.__new__(ControlPlaneEngine))
    value.policy = Policy()
    value.executor = SimpleNamespace(guard=SimpleNamespace(
        resolve=lambda activity: None,
        validate_runtime_noise=lambda path, scope: None,
    ))
    value.learning_foundation = SimpleNamespace(
        authorize=lambda marker: GovernanceDecision(decision, ("test decision",))
    )
    return cast(ControlPlaneEngine, value)


def manifest(metadata: dict[str, object]) -> CampaignManifest:
    activity = SimpleNamespace(action="execute_engineering", risk="LOW")
    controls = SimpleNamespace(deterministic_runtime_noise=())
    return cast(
        CampaignManifest,
        SimpleNamespace(
            metadata=metadata,
            campaign_id="campaign",
            activities=(activity,),
            scope={},
            validation_controls=controls,
        ),
    )


def test_learning_preflight_denies_before_activity_guard() -> None:
    value = engine("deny")
    guard = cast(Any, value.executor.guard)
    guard.resolve = lambda activity: (_ for _ in ()).throw(
        AssertionError("mutation guard reached")
    )
    result = value._authorize_before_mutation(manifest({"governed_learning": {}}))
    assert result is not None and result["status"] == "failed"


def test_l4_decision_maps_to_existing_human_gate_shape() -> None:
    result = engine("human_gate")._authorize_before_mutation(manifest({"governed_learning": {}}))
    assert result is not None and result["status"] == "human_gate"


def test_ordinary_execute_engineering_is_not_inferred_as_learning() -> None:
    assert engine("deny")._authorize_before_mutation(manifest({})) is None
