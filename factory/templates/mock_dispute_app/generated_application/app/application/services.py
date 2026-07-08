from __future__ import annotations

from uuid import uuid4

from generated_application.app.domain.entities import Dispute
from generated_application.app.domain.policies import initial_policy_state
from generated_application.app.domain.value_objects import DisputeId, UpiTransactionRef

from .commands import CreateDisputeCommand
from .unit_of_work import UnitOfWork


class DisputeService:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self.unit_of_work = unit_of_work

    def create_dispute(self, command: CreateDisputeCommand) -> str:
        with self.unit_of_work as uow:
            replayed = uow.idempotency.get(command.idempotency_key)
            if replayed is not None:
                return replayed

            dispute_id = f"DSP-{uuid4().hex[:12].upper()}"
            dispute = Dispute(
                dispute_id=DisputeId(dispute_id),
                transaction_ref=UpiTransactionRef(command.transaction_ref),
                customer_upi=command.customer_upi,
                reason=command.reason,
            )
            dispute.transition_to(initial_policy_state(dispute), actor="application_service")
            uow.disputes.add(dispute)
            for event in dispute.audit_events:
                uow.outbox.enqueue(event.event_type, event.aggregate_id, event.payload)
            uow.idempotency.put(command.idempotency_key, dispute_id)
            uow.commit()
            return dispute_id
