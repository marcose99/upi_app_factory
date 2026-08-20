from __future__ import annotations

from dataclasses import dataclass

from .models import GovernedLearningRequest, GovernanceError


@dataclass(frozen=True)
class LearningEnvelope:
    permitted_data_classes: frozenset[str]
    permitted_objectives: frozenset[str]
    permitted_change_classes: frozenset[str]
    maximum_change_budget: int
    minimum_evaluation_score: float
    minimum_held_out_score: float
    promotion_ceiling: int

    def validate(self, request: GovernedLearningRequest) -> None:
        if not set(request.data_classes) <= self.permitted_data_classes:
            raise GovernanceError("data class is outside the learning envelope")
        if request.objective not in self.permitted_objectives:
            raise GovernanceError("objective is outside the learning envelope")
        if request.change_class not in self.permitted_change_classes:
            raise GovernanceError("change class is outside the learning envelope")
        if request.change_budget > self.maximum_change_budget:
            raise GovernanceError("change budget exceeds the learning envelope")
        if request.evaluation_score < self.minimum_evaluation_score:
            raise GovernanceError("evaluation threshold was not met")
        if request.held_out_score < self.minimum_held_out_score:
            raise GovernanceError("held-out threshold was not met")
        if request.requested_promotion > self.promotion_ceiling:
            raise GovernanceError("promotion exceeds the learning envelope")
        if request.acceptance_bar_delta < 0:
            raise GovernanceError("learning may never lower the acceptance bar")
