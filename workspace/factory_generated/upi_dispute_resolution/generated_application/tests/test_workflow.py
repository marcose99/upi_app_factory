from upi_dispute_app.models import DisputeStatus, DisputeType, EcosystemDecision
from upi_dispute_app.workflow import initial_status, status_from_ecosystem_decision


def test_unauthorized_transaction_starts_with_evidence_pending() -> None:
    assert initial_status(DisputeType.UNAUTHORIZED_TRANSACTION) is DisputeStatus.EVIDENCE_PENDING


def test_failed_transaction_starts_with_validation_pending() -> None:
    assert initial_status(DisputeType.FAILED_TRANSACTION) is DisputeStatus.VALIDATION_PENDING


def test_ecosystem_decision_maps_to_refund_status() -> None:
    assert status_from_ecosystem_decision(EcosystemDecision.REFUND_ELIGIBLE) is (
        DisputeStatus.REFUND_INITIATED
    )
