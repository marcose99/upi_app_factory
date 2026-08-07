from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from adapters.mock_core_banking import get_ledger_observation
from adapters.mock_customer_notification import record_notification_request
from adapters.mock_dispute_evidence_store import store_evidence_pack
from adapters.mock_upi_switch import get_failed_transaction, list_failed_transactions
from app.disputes.models import (
    CaseAction,
    CaseActionRequest,
    CaseStatus,
    CreateCaseRequest,
    DisputeCase,
    FailedTransactionEvent,
    MockEvidenceObservation,
    REQUIRED_EVIDENCE_LABELS,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


class DisputeCaseService:
    def __init__(self) -> None:
        self._cases: dict[str, DisputeCase] = {}

    def list_failed_transactions(self) -> list[FailedTransactionEvent]:
        return [
            FailedTransactionEvent.model_validate(event)
            for event in list_failed_transactions()
        ]

    def list_cases(self) -> list[DisputeCase]:
        return list(self._cases.values())

    def get_case(self, case_id: str) -> DisputeCase:
        case = self._cases.get(case_id)
        if case is None:
            raise KeyError(case_id)
        return case

    def create_case(self, request: CreateCaseRequest) -> DisputeCase:
        event = get_failed_transaction(request.transaction_id)
        if event is None:
            raise KeyError(request.transaction_id)

        case_id = stable_id("CASE", request.transaction_id)
        existing = self._cases.get(case_id)
        if existing is not None:
            return existing

        now = utc_now()
        ledger = get_ledger_observation(request.transaction_id)
        evidence = [
            MockEvidenceObservation(
                source_system="mock_upi_switch",
                observation=str(event["failure_reason"]),
                observed_at_utc=str(event["observed_at_utc"]),
            ),
            MockEvidenceObservation(
                source_system=str(ledger["source_system"]),
                observation=str(ledger["observation"]),
                observed_at_utc=str(ledger["observed_at_utc"]),
            ),
        ]

        case = DisputeCase(
            case_id=case_id,
            transaction_id=str(event["transaction_id"]),
            status=CaseStatus.EVIDENCE_PENDING,
            created_at_utc=now,
            updated_at_utc=now,
            created_by=request.created_by,
            amount_paise=int(event["amount_paise"]),
            currency=str(event["currency"]),
            customer_reference=str(event["customer_reference"]),
            failure_reason=str(event["failure_reason"]),
            evidence=evidence,
            reviewer_notes=[
                "Synthetic dispute case created from mock failed transaction."
            ],
            audit_event_ids=[stable_id("AUD", f"create:{case_id}:{now}")],
            evidence_labels=REQUIRED_EVIDENCE_LABELS.copy(),
        )
        self._cases[case_id] = case
        store_evidence_pack(
            case_id,
            [observation.model_dump() for observation in evidence],
        )
        record_notification_request(
            case_id=case_id,
            customer_reference=case.customer_reference,
            message="Mock notification recorded; nothing sent to real customer.",
        )
        return case

    def apply_action(
        self,
        case_id: str,
        request: CaseActionRequest,
    ) -> DisputeCase:
        case = self.get_case(case_id)
        now = utc_now()

        next_status = case.status
        if request.action == CaseAction.ASSIGN_REVIEWER:
            next_status = CaseStatus.IN_REVIEW
        elif request.action == CaseAction.REQUEST_EVIDENCE:
            next_status = CaseStatus.EVIDENCE_PENDING
        elif request.action == CaseAction.MARK_RESOLVED:
            next_status = CaseStatus.RESOLVED
        elif request.action == CaseAction.CLOSE_CASE:
            next_status = CaseStatus.CLOSED

        note = (
            f"{request.reviewer}: {request.action.value}"
            if request.notes is None
            else f"{request.reviewer}: {request.action.value} - {request.notes}"
        )

        updated = case.model_copy(
            update={
                "status": next_status,
                "updated_at_utc": now,
                "reviewer_notes": [*case.reviewer_notes, note],
                "audit_event_ids": [
                    *case.audit_event_ids,
                    stable_id("AUD", f"{case_id}:{request.action.value}:{now}"),
                ],
            }
        )
        self._cases[case_id] = updated
        return updated


dispute_case_service = DisputeCaseService()
