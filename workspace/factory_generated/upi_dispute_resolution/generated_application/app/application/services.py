from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

from generated_application.app.domain.entities import Dispute
from generated_application.app.domain.exceptions import DuplicateBusinessSubmissionError, IdempotencyConflictError
from generated_application.app.domain.policies import initial_policy_state
from generated_application.app.domain.value_objects import DisputeId, UpiTransactionRef

from .commands import CreateDisputeCommand
from .unit_of_work import UnitOfWork


class DisputeService:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self.unit_of_work = unit_of_work

    def create_dispute(self, command: CreateDisputeCommand) -> str:
        request_fingerprint = self._request_fingerprint(command)
        business_fingerprint = self._business_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                stored_fingerprint, stored_result = replayed
                if hmac.compare_digest(stored_fingerprint, request_fingerprint):
                    if not stored_result:
                        raise IdempotencyConflictError("idempotency key reservation has no stored result")
                    return stored_result
                raise IdempotencyConflictError(
                    "idempotency key reused with a different dispute payload"
                )
            if uow.disputes.exists_for_business_fingerprint(business_fingerprint):
                raise DuplicateBusinessSubmissionError(
                    "duplicate dispute submission for transaction/customer/reason"
                )

            dispute_id = f"DSP-{uuid4().hex[:12].upper()}"
            dispute = Dispute(
                dispute_id=DisputeId(dispute_id),
                transaction_ref=UpiTransactionRef(command.transaction_ref),
                customer_upi=command.customer_upi,
                reason=command.reason,
                owner_subject=command.owner_subject,
            )
            dispute.transition_to(initial_policy_state(dispute), actor="application_service")
            audit_hash = uow.audit.append(
                "application_service",
                "dispute.create",
                dispute.dispute_id.value,
                {
                    "transaction_ref": command.transaction_ref,
                    "state": dispute.state.value,
                    "version": dispute.version,
                },
            )
            dispute.audit_link_hash = audit_hash
            uow.disputes.add(
                dispute,
                audit_link_hash=audit_hash,
                business_fingerprint=business_fingerprint,
            )
            for event in dispute.audit_events:
                event.payload["audit_link_hash"] = audit_hash
                uow.outbox.enqueue(event, trace_id=command.correlation_id)
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, dispute_id)
            uow.commit()
            return dispute_id

    @staticmethod
    def _request_fingerprint(command: CreateDisputeCommand) -> str:
        material = {
            "transaction_ref": command.transaction_ref,
            "customer_upi": command.customer_upi,
            "reason": command.reason,
            "owner_subject": command.owner_subject,
        }
        return hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _business_fingerprint(command: CreateDisputeCommand) -> str:
        material = {
            "transaction_ref": command.transaction_ref,
            "customer_upi": command.customer_upi,
            "reason": command.reason,
        }
        return hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def get_dispute(self, dispute_id: str) -> Dispute | None:
        with self.unit_of_work as uow:
            dispute = uow.disputes.get(dispute_id)
            uow.commit()
            return dispute

    def list_disputes(self, *, limit: int, cursor: int) -> list[Dispute]:
        with self.unit_of_work as uow:
            disputes = uow.disputes.list_page(limit=limit, cursor=cursor)
            uow.commit()
            return disputes
