from .models import GovernanceDecision, GovernedLearningRequest, LearningClass


class PromotionGovernor:
    def decide(self, request: GovernedLearningRequest) -> GovernanceDecision:
        if request.learning_class is LearningClass.L4_PROTECTED_PROMOTION or request.requested_promotion == 4:
            return GovernanceDecision("human_gate", ("L4 protected promotion requires a human",), request)
        if request.requested_promotion > int(request.learning_class):
            return GovernanceDecision("deny", ("request may not self-escalate its learning class",), request)
        return GovernanceDecision("allow", ("request is below protected promotion",), request)
