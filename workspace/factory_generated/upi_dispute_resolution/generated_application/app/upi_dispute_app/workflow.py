from __future__ import annotations

from .models import DisputeRecord, DisputeStatus, DisputeType, EcosystemDecision


BOUNDARY_NOTICE = (
    "Local simulation only. External NPCI/RBI/bank/PSP/ODR/payment-rail "
    "ecosystem interactions are mock/simulated. No compliance, certification, "
    "production-readiness, or live-payment claim is made."
)


def initial_status(dispute_type: DisputeType) -> DisputeStatus:
    if dispute_type is DisputeType.UNAUTHORIZED_TRANSACTION:
        return DisputeStatus.EVIDENCE_PENDING
    return DisputeStatus.VALIDATION_PENDING


def next_actions_for(record: DisputeRecord) -> list[str]:
    if record.status is DisputeStatus.VALIDATION_PENDING:
        return ["run_mock_ecosystem_check", "attach_more_evidence"]
    if record.status is DisputeStatus.EVIDENCE_PENDING:
        return ["attach_more_evidence", "run_mock_ecosystem_check"]
    if record.status is DisputeStatus.REFUND_INITIATED:
        return ["close_after_refund_confirmation"]
    if record.status is DisputeStatus.ESCALATED_TO_ODR:
        return ["track_mock_odr_case"]
    if record.status is DisputeStatus.CUSTOMER_ACTION_REQUIRED:
        return ["collect_customer_confirmation"]
    return []


def status_from_ecosystem_decision(decision: EcosystemDecision) -> DisputeStatus:
    mapping = {
        EcosystemDecision.REFUND_ELIGIBLE: DisputeStatus.REFUND_INITIATED,
        EcosystemDecision.MORE_EVIDENCE_REQUIRED: DisputeStatus.CUSTOMER_ACTION_REQUIRED,
        EcosystemDecision.ESCALATE_TO_ODR: DisputeStatus.ESCALATED_TO_ODR,
        EcosystemDecision.REJECT: DisputeStatus.REJECTED,
    }
    return mapping[decision]
