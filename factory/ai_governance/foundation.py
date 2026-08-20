from __future__ import annotations

from typing import Any, Mapping

from .incident_drift import IncidentDriftRecorder, IncidentStore
from .learning_envelope import LearningEnvelope
from .models import GovernedLearningRequest, GovernanceDecision, GovernanceError
from .promotion_governor import PromotionGovernor
from .registry import AISystemRegistry
from .risk_impact import RiskImpactHook


class GovernedSelfLearningFoundation:
    def __init__(self, registry: AISystemRegistry, envelope: LearningEnvelope, store: IncidentStore | None = None) -> None:
        self.registry = registry
        self.envelope = envelope
        self.promotion = PromotionGovernor()
        self.risk_impact = RiskImpactHook()
        self.incidents = IncidentDriftRecorder(store) if store is not None else None
        self._kill_switch = False

    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    def set_kill_switch(self, enabled: bool) -> None:
        self._kill_switch = bool(enabled)

    def authorize(self, raw: object, campaign_id: str | None = None) -> GovernanceDecision:
        try:
            if self._kill_switch:
                raise GovernanceError("learning kill switch is active")
            request = GovernedLearningRequest.parse(raw)
            self.registry.require(request.system_id, request.system_version)
            self.envelope.validate(request)
            self.risk_impact.assess(request)
            return self.promotion.decide(request)
        except GovernanceError as exc:
            if self.incidents is not None and campaign_id is not None:
                self.incidents.record(campaign_id, "GOVERNED_LEARNING_DENIAL", str(exc))
            return GovernanceDecision("deny", (str(exc),))

    preflight = authorize


def metadata_marker(metadata: Mapping[str, Any]) -> object | None:
    return metadata.get("governed_learning")
