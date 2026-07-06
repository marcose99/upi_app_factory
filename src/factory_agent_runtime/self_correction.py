from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .ledger import JsonlLedger


class FindingSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class CorrectionAction(str, Enum):
    AUTO_REMEDIATE = "auto_remediate"
    PLAN_ONLY = "plan_only"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    BLOCKED = "blocked"
    NO_CHANGE_NEEDED = "no_change_needed"


@dataclass(frozen=True)
class ValidationFinding:
    finding_id: str
    severity: FindingSeverity
    category: str
    source: str
    summary: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CorrectionDecision:
    finding_id: str
    severity: FindingSeverity
    category: str
    action: CorrectionAction
    reason: str
    requires_human_approval: bool
    max_attempts: int
    status: str = "decided"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity.value,
            "category": self.category,
            "action": self.action.value,
            "reason": self.reason,
            "requires_human_approval": self.requires_human_approval,
            "max_attempts": self.max_attempts,
            "status": self.status,
        }


@dataclass(frozen=True)
class SelfCorrectionPolicy:
    auto_remediable_categories: tuple[str, ...] = (
        "formatting",
        "lint",
        "import_path",
        "test_fixture",
        "portal_population",
        "documentation_gap",
        "validator_message",
        "low_risk_generated_app_fix",
    )
    human_approval_categories: tuple[str, ...] = (
        "git_release",
        "dependency_install",
        "security_policy_weakening",
        "tool_authorization_expansion",
        "destructive_reset",
        "regulatory_claim",
        "live_integration",
        "customer_data_handling",
        "quality_objective_waiver",
    )
    blocked_categories: tuple[str, ...] = (
        "real_payment_execution",
        "real_customer_data_use",
        "false_compliance_claim",
        "credential_exposure",
    )
    max_attempts_per_finding: int = 3


class SelfCorrectionController:
    def __init__(self, *, policy: SelfCorrectionPolicy, ledger_root: Path) -> None:
        self.policy = policy
        self.ledger_root = ledger_root
        self.decision_ledger = JsonlLedger(ledger_root / "self_correction_decision_ledger.jsonl")
        self.attempt_ledger = JsonlLedger(ledger_root / "self_correction_attempt_ledger.jsonl")

    def decide(self, finding: ValidationFinding) -> CorrectionDecision:
        if finding.category in self.policy.blocked_categories:
            action = CorrectionAction.BLOCKED
            requires_approval = True
            reason = "Finding category is blocked by governance policy."
        elif finding.category in self.policy.human_approval_categories:
            action = CorrectionAction.HUMAN_APPROVAL_REQUIRED
            requires_approval = True
            reason = "Finding category requires human approval before correction."
        elif finding.category in self.policy.auto_remediable_categories:
            action = CorrectionAction.AUTO_REMEDIATE
            requires_approval = False
            reason = "Finding category is low-risk and eligible for bounded auto-remediation."
        else:
            action = CorrectionAction.PLAN_ONLY
            requires_approval = False
            reason = "Finding category is not auto-remediable; create a remediation plan."

        decision = CorrectionDecision(
            finding_id=finding.finding_id,
            severity=finding.severity,
            category=finding.category,
            action=action,
            reason=reason,
            requires_human_approval=requires_approval,
            max_attempts=self.policy.max_attempts_per_finding,
        )
        self.decision_ledger.append(
            "self_correction_decision",
            {
                "finding": {
                    "finding_id": finding.finding_id,
                    "severity": finding.severity.value,
                    "category": finding.category,
                    "source": finding.source,
                    "summary": finding.summary,
                },
                "decision": decision.to_jsonable(),
            },
        )
        return decision

    def process_findings(self, findings: list[ValidationFinding]) -> list[CorrectionDecision]:
        decisions = [self.decide(finding) for finding in findings]
        self.attempt_ledger.append(
            "self_correction_batch_triaged",
            {
                "findings_seen": len(findings),
                "decisions_made": len(decisions),
                "auto_remediate": sum(
                    1 for item in decisions if item.action is CorrectionAction.AUTO_REMEDIATE
                ),
                "human_approval_required": sum(
                    1 for item in decisions if item.action is CorrectionAction.HUMAN_APPROVAL_REQUIRED
                ),
                "blocked": sum(1 for item in decisions if item.action is CorrectionAction.BLOCKED),
                "plan_only": sum(1 for item in decisions if item.action is CorrectionAction.PLAN_ONLY),
            },
        )
        return decisions

    @staticmethod
    def summarize(decisions: list[CorrectionDecision]) -> dict[str, int]:
        return {
            "total_decisions": len(decisions),
            "auto_remediate": sum(
                1 for item in decisions if item.action is CorrectionAction.AUTO_REMEDIATE
            ),
            "human_approval_required": sum(
                1 for item in decisions if item.action is CorrectionAction.HUMAN_APPROVAL_REQUIRED
            ),
            "blocked": sum(1 for item in decisions if item.action is CorrectionAction.BLOCKED),
            "plan_only": sum(1 for item in decisions if item.action is CorrectionAction.PLAN_ONLY),
            "untriaged": 0,
        }
