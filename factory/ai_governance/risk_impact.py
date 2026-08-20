from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .models import GovernedLearningRequest, GovernanceError


@dataclass(frozen=True)
class RiskImpactAssessment:
    risk: str
    impact: str
    approved: bool


class RiskImpactHook:
    def __init__(self, assessor: Callable[[GovernedLearningRequest], RiskImpactAssessment] | None = None) -> None:
        self._assessor = assessor or (lambda _request: RiskImpactAssessment("bounded", "bounded", True))

    def assess(self, request: GovernedLearningRequest) -> RiskImpactAssessment:
        try:
            result = self._assessor(request)
        except Exception as exc:
            raise GovernanceError("risk/impact assessment failed") from exc
        if not isinstance(result, RiskImpactAssessment) or not result.approved:
            raise GovernanceError("risk/impact assessment denied")
        return result
