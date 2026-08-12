from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from generated_application.app.domain.entities import Dispute
from generated_application.app.domain.domain_events import DomainEvent, dispute_event
from generated_application.app.domain.exceptions import (
    DuplicateBusinessSubmissionError,
    IdempotencyConflictError,
    OptimisticConcurrencyError,
    ValidationFailed,
)
from generated_application.app.domain.policies import initial_policy_state
from generated_application.app.domain.value_objects import DisputeId, UpiTransactionRef
from generated_application.app.security.pii_redaction import stored_masked_upi, upi_storage_digest

from .commands import (
    AttachFailedDebitEvidenceCommand,
    ClassifyFailedDebitCaseCommand,
    CloseFailedDebitCaseCommand,
    CreateDisputeCommand,
    CreateFailedDebitCaseCommand,
    QuarantineFailedDebitCaseCommand,
    RecordFailedDebitDispositionCommand,
    RecordFailedDebitReviewDecisionCommand,
    RecordInvestigationOutcomeCommand,
    RequestFailedDebitHumanReviewCommand,
)
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
                "system",
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

class FailedDebitRuntimeService:
    REQUIRED_EVIDENCE_TYPES = frozenset({"switch_failure", "core_ledger", "customer_statement"})
    HIGH_VALUE_THRESHOLD_MINOR = 100_000
    CONFIDENCE_REVIEW_THRESHOLD = 75
    SUPPORTED_DISPOSITIONS = frozenset(
        {
            "WAIT_FOR_NETWORK_UPDATE",
            "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
            "CONFIRM_REVERSAL_OBSERVED",
            "CONFIRM_BENEFICIARY_CREDIT_OBSERVED",
            "REQUIRE_ADDITIONAL_EVIDENCE",
            "ESCALATE_FOR_SPECIALIST_REVIEW",
            "UNRESOLVED",
        }
    )

    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self.unit_of_work = unit_of_work

    def create_case(self, command: CreateFailedDebitCaseCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        business_fingerprint = self._create_business_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail
            if uow.failed_debit.has_open_transaction_ref(command.transaction_ref):
                raise DuplicateBusinessSubmissionError(
                    "duplicate failed-debit case already open for transaction reference"
                )

            dispute_id = f"FDB-{uuid4().hex[:12].upper()}"
            now = self._utc_now()
            amount_minor = self._parse_amount_minor(command.amount)
            created_audit_hash = uow.audit.append(
                command.owner_subject,
                command.owner_role,
                "failed_debit.case.create",
                dispute_id,
                {
                    "transaction_ref": command.transaction_ref,
                    "reason_code": command.reason_code,
                    "amount_minor": amount_minor,
                    "currency": "INR",
                },
            )
            uow.failed_debit.add_case(
                {
                    "dispute_id": dispute_id,
                    "transaction_ref": command.transaction_ref,
                    "customer_upi_digest": upi_storage_digest(command.customer_upi),
                    "customer_upi_masked": stored_masked_upi(command.customer_upi),
                    "amount_minor": amount_minor,
                    "currency": "INR",
                    "reason_code": command.reason_code,
                    "case_type": "failed_debit_beneficiary_not_credited",
                    "owner_subject": command.owner_subject,
                    "assigned_analyst": "",
                    "state": "received",
                    "version": 0,
                    "resolution_kind": None,
                    "resolution_reason_code": None,
                    "resolution_amount_minor": None,
                    "resolution_rationale": None,
                    "resolution_status": "pending",
                    "latest_investigation_payload_json": None,
                    "created_at_utc": now,
                    "updated_at_utc": now,
                    "last_correlation_id": command.correlation_id,
                    "audit_link_hash": created_audit_hash,
                    "business_fingerprint": business_fingerprint,
                    "latest_classification_payload_json": None,
                    "human_review_required": False,
                    "human_review_status": "NOT_REQUIRED",
                    "proposed_disposition": None,
                    "approved_disposition": None,
                    "latest_disposition_payload_json": None,
                    "pending_review_id": None,
                    "review_requested_by": None,
                    "review_requested_at_utc": None,
                    "last_audit_check_status": "not_run",
                    "last_audit_check_payload_json": None,
                    "closed_at_utc": None,
                    "closed_by": None,
                    "quarantined_at_utc": None,
                    "quarantined_by": None,
                    "quarantine_reason_code": None,
                    "quarantine_reason": None,
                }
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=dispute_id,
                event_type="FailedDebitCaseCreated",
                state="received",
                aggregate_version=0,
                actor_subject=command.owner_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=created_audit_hash,
                payload={
                    "transaction_ref": command.transaction_ref,
                    "reason_code": command.reason_code,
                    "required_evidence_types": sorted(self.REQUIRED_EVIDENCE_TYPES),
                },
            )
            validated_version, validated_hash = self._transition_case(
                uow=uow,
                case={"version": 0, "state": "received"},
                dispute_id=dispute_id,
                next_state="validated",
                actor_subject=command.owner_subject,
                actor_role=command.owner_role,
                correlation_id=command.correlation_id,
                action="failed_debit.case.validate",
                audit_payload={
                    "required_evidence_types": sorted(self.REQUIRED_EVIDENCE_TYPES),
                },
                updates={"updated_at_utc": now, "last_correlation_id": command.correlation_id},
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=dispute_id,
                event_type="FailedDebitEligibilityValidated",
                state="validated",
                aggregate_version=validated_version,
                actor_subject=command.owner_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=validated_hash,
                payload={
                    "eligible": True,
                    "required_evidence_types": sorted(self.REQUIRED_EVIDENCE_TYPES),
                },
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, dispute_id)
            detail = self._require_case_detail(uow, dispute_id)
            uow.commit()
            return detail

    def get_case(self, dispute_id: str) -> dict[str, Any] | None:
        with self.unit_of_work as uow:
            detail = uow.failed_debit.get_case_detail(dispute_id)
            uow.commit()
            return detail

    def get_history(self, dispute_id: str) -> dict[str, Any] | None:
        return self.get_case(dispute_id)

    def list_cases(
        self,
        *,
        limit: int,
        cursor: int,
        transaction_reference: str | None = None,
        state: str | None = None,
        age_bucket: str | None = None,
        analyst: str | None = None,
        resolution_status: str | None = None,
        classification: str | None = None,
        human_review_status: str | None = None,
    ) -> dict[str, Any]:
        with self.unit_of_work as uow:
            payload = uow.failed_debit.list_cases(
                limit=limit,
                cursor=cursor,
                transaction_reference=transaction_reference,
                state=state,
                age_bucket=age_bucket,
                analyst=analyst,
                resolution_status=resolution_status,
                classification=classification,
                human_review_status=human_review_status,
            )
            uow.commit()
            return payload

    def attach_evidence(self, command: AttachFailedDebitEvidenceCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail

            case = self._require_case(uow, command.dispute_id)
            current_version = self._expected_current_version(case, command.expected_version)
            current_state = str(case["state"])
            if current_state not in {"validated", "investigating", "awaiting_evidence"} and not (
                current_state == "decision_recorded"
                and str(case["human_review_status"]) == "MORE_EVIDENCE_REQUIRED"
            ):
                raise ValidationFailed("failed-debit case is not open for new evidence")

            evidence_id = command.evidence_id or self._derived_evidence_id(command)
            if evidence_id in {
                str(item["evidence_id"]) for item in uow.failed_debit.list_evidence(command.dispute_id)
            }:
                raise DuplicateBusinessSubmissionError("duplicate failed-debit evidence identifier")

            observed_at_utc = self._normalize_utc(command.observed_at_utc)
            attached_at_utc = self._utc_now()
            content_sha256 = hashlib.sha256(
                json.dumps(
                    {
                        "evidence_type": command.evidence_type,
                        "source": command.source,
                        "summary": command.summary,
                        "observed_at_utc": observed_at_utc,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            audit_link_hash = uow.audit.append(
                command.actor_subject,
                command.actor_role,
                "failed_debit.evidence.attach",
                command.dispute_id,
                {
                    "evidence_id": evidence_id,
                    "evidence_type": command.evidence_type,
                    "source": command.source,
                    "content_sha256": content_sha256,
                },
            )
            uow.failed_debit.add_evidence(
                {
                    "dispute_id": command.dispute_id,
                    "evidence_id": evidence_id,
                    "evidence_type": command.evidence_type,
                    "source": command.source,
                    "summary": command.summary,
                    "observed_at_utc": observed_at_utc,
                    "attached_by": command.actor_subject,
                    "attached_at_utc": attached_at_utc,
                    "content_sha256": content_sha256,
                    "audit_link_hash": audit_link_hash,
                }
            )

            missing_after_attach = uow.failed_debit.missing_evidence_types(command.dispute_id)
            next_state = "awaiting_evidence" if missing_after_attach else (
                "investigating" if case.get("latest_investigation_payload_json") else "validated"
            )
            updates: dict[str, Any] = {
                "updated_at_utc": attached_at_utc,
                "last_correlation_id": command.correlation_id,
                "audit_link_hash": audit_link_hash,
                "last_audit_check_status": "not_run",
                "last_audit_check_payload_json": None,
            }
            if current_state == "decision_recorded" and str(case["human_review_status"]) == "MORE_EVIDENCE_REQUIRED":
                updates["human_review_status"] = "NOT_REQUIRED"
                updates["pending_review_id"] = None
            next_version = self._update_case(
                uow=uow,
                dispute_id=command.dispute_id,
                current_state=current_state,
                next_state=next_state,
                expected_version=current_version,
                updates=updates,
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=command.dispute_id,
                event_type="FailedDebitEvidenceAttached",
                state=next_state,
                aggregate_version=next_version,
                actor_subject=command.actor_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=audit_link_hash,
                payload={
                    "evidence_id": evidence_id,
                    "evidence_type": command.evidence_type,
                    "source": command.source,
                    "missing_evidence_types": sorted(missing_after_attach),
                },
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, command.dispute_id)
            detail = self._require_case_detail(uow, command.dispute_id)
            uow.commit()
            return detail

    def record_investigation(self, command: RecordInvestigationOutcomeCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail

            case = self._require_case(uow, command.dispute_id)
            current_version = self._expected_current_version(case, command.expected_version)
            current_state = str(case["state"])
            if current_state not in {"validated", "awaiting_evidence", "investigating"}:
                raise ValidationFailed("investigation is not allowed from the current case state")

            missing_evidence = sorted(uow.failed_debit.missing_evidence_types(command.dispute_id))
            recorded_at_utc = self._utc_now()
            observation = self._observation_from_status(command.simulated_bank_status)
            investigation_payload = {
                "analyst_notes": command.analyst_notes,
                "simulated_bank_status": command.simulated_bank_status,
                "recorded_at_utc": recorded_at_utc,
                "observation": observation,
                "provider_snapshot": {
                    "adapter_mode": "local_simulated_only",
                    "provider_call_performed": False,
                    "certification_boundary": "certification_ready_not_certified",
                },
                "timeline_events_observed": len(uow.failed_debit.list_events(command.dispute_id)),
                "missing_evidence_types": missing_evidence,
            }
            next_state = "awaiting_evidence" if missing_evidence else "investigating"
            audit_link_hash = uow.audit.append(
                command.actor_subject,
                command.actor_role,
                "failed_debit.investigation.record",
                command.dispute_id,
                {
                    "simulated_bank_status": command.simulated_bank_status,
                    "assigned_analyst": command.actor_subject,
                    "missing_evidence_types": missing_evidence,
                },
            )
            next_version = self._update_case(
                uow=uow,
                dispute_id=command.dispute_id,
                current_state=current_state,
                next_state=next_state,
                expected_version=current_version,
                updates={
                    "assigned_analyst": command.actor_subject,
                    "latest_investigation_payload_json": json.dumps(
                        investigation_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "updated_at_utc": recorded_at_utc,
                    "last_correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                    "last_audit_check_status": "not_run",
                    "last_audit_check_payload_json": None,
                },
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=command.dispute_id,
                event_type="FailedDebitInvestigationRecorded",
                state=next_state,
                aggregate_version=next_version,
                actor_subject=command.actor_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=audit_link_hash,
                payload={
                    "simulated_bank_status": command.simulated_bank_status,
                    "assigned_analyst": command.actor_subject,
                    "missing_evidence_types": missing_evidence,
                },
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, command.dispute_id)
            detail = self._require_case_detail(uow, command.dispute_id)
            uow.commit()
            return detail

    def classify_case(self, command: ClassifyFailedDebitCaseCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail

            case = self._require_case(uow, command.dispute_id)
            current_version = self._expected_current_version(case, command.expected_version)
            current_state = str(case["state"])
            if current_state not in {"investigating", "awaiting_evidence"}:
                raise ValidationFailed("classification requires an investigated case")
            if case.get("latest_investigation_payload_json") in (None, ""):
                raise ValidationFailed("investigation must be recorded before classification")

            investigation = json.loads(str(case["latest_investigation_payload_json"]))
            classification_payload = self._classification_payload(
                case=case,
                investigation=investigation,
                missing_evidence=sorted(uow.failed_debit.missing_evidence_types(command.dispute_id)),
                actor_subject=command.actor_subject,
            )
            next_state = (
                "awaiting_evidence"
                if classification_payload["missing_evidence_types"]
                else "decision_recorded"
                if not classification_payload["human_review_required"]
                else "investigating"
            )
            now = self._utc_now()
            audit_link_hash = uow.audit.append(
                command.actor_subject,
                command.actor_role,
                "failed_debit.case.classify",
                command.dispute_id,
                {
                    "classification": classification_payload["classification"],
                    "reason_code": classification_payload["reason_code"],
                    "confidence": classification_payload["confidence"],
                    "proposed_disposition": classification_payload["proposed_disposition"],
                    "human_review_required": classification_payload["human_review_required"],
                },
            )
            next_version = self._update_case(
                uow=uow,
                dispute_id=command.dispute_id,
                current_state=current_state,
                next_state=next_state,
                expected_version=current_version,
                updates={
                    "latest_classification_payload_json": json.dumps(
                        classification_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "human_review_required": int(classification_payload["human_review_required"]),
                    "human_review_status": (
                        "PENDING" if classification_payload["human_review_required"] else "NOT_REQUIRED"
                    ),
                    "proposed_disposition": classification_payload["proposed_disposition"],
                    "approved_disposition": None,
                    "updated_at_utc": now,
                    "last_correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                    "resolution_status": (
                        "review_pending"
                        if classification_payload["human_review_required"]
                        else "decision_recorded"
                    ),
                    "last_audit_check_status": "not_run",
                    "last_audit_check_payload_json": None,
                },
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=command.dispute_id,
                event_type="FailedDebitCaseClassified",
                state=next_state,
                aggregate_version=next_version,
                actor_subject=command.actor_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=audit_link_hash,
                payload={
                    "classification": classification_payload["classification"],
                    "reason_code": classification_payload["reason_code"],
                    "confidence": classification_payload["confidence"],
                    "impact": classification_payload["impact"],
                    "human_review_required": classification_payload["human_review_required"],
                    "proposed_disposition": classification_payload["proposed_disposition"],
                },
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, command.dispute_id)
            detail = self._require_case_detail(uow, command.dispute_id)
            uow.commit()
            return detail

    def request_human_review(self, command: RequestFailedDebitHumanReviewCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail

            case = self._require_case(uow, command.dispute_id)
            current_version = self._expected_current_version(case, command.expected_version)
            current_state = str(case["state"])
            if current_state not in {"investigating", "awaiting_evidence"}:
                raise ValidationFailed("human review can only be requested after classification")
            if case.get("latest_classification_payload_json") in (None, ""):
                raise ValidationFailed("classification must be recorded before human review")

            review_id = "REV-" + hashlib.sha256(
                f"{command.dispute_id}|{command.correlation_id}".encode("utf-8")
            ).hexdigest()[:12].upper()
            now = self._utc_now()
            audit_link_hash = uow.audit.append(
                command.actor_subject,
                command.actor_role,
                "failed_debit.human_review.request",
                command.dispute_id,
                {
                    "review_id": review_id,
                    "reason_code": command.reason_code,
                },
            )
            uow.failed_debit.add_review_decision(
                {
                    "review_event_id": review_id + "-REQUEST",
                    "dispute_id": command.dispute_id,
                    "review_id": review_id,
                    "decision_status": "REQUESTED",
                    "actor_subject": command.actor_subject,
                    "actor_role": command.actor_role,
                    "reason_code": command.reason_code,
                    "rationale": command.rationale,
                    "approved_disposition": None,
                    "occurred_at_utc": now,
                    "correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                }
            )
            next_version = self._update_case(
                uow=uow,
                dispute_id=command.dispute_id,
                current_state=current_state,
                next_state="awaiting_human_review",
                expected_version=current_version,
                updates={
                    "pending_review_id": review_id,
                    "review_requested_by": command.actor_subject,
                    "review_requested_at_utc": now,
                    "human_review_status": "PENDING",
                    "updated_at_utc": now,
                    "last_correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                    "resolution_status": "review_pending",
                },
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=command.dispute_id,
                event_type="FailedDebitHumanReviewRequested",
                state="awaiting_human_review",
                aggregate_version=next_version,
                actor_subject=command.actor_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=audit_link_hash,
                payload={"review_id": review_id, "reason_code": command.reason_code},
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, command.dispute_id)
            detail = self._require_case_detail(uow, command.dispute_id)
            uow.commit()
            return detail

    def record_review_decision(self, command: RecordFailedDebitReviewDecisionCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail

            case = self._require_case(uow, command.dispute_id)
            current_version = self._expected_current_version(case, command.expected_version)
            if str(case["state"]) != "awaiting_human_review":
                raise ValidationFailed("review decisions require an awaiting_human_review case")
            pending_review_id = str(case.get("pending_review_id") or "")
            review_id = command.review_id or pending_review_id
            if not review_id or review_id != pending_review_id:
                raise ValidationFailed("review identifier does not match the pending review")

            classification = self._load_json(case.get("latest_classification_payload_json"))
            prohibited_subjects = {
                str(case.get("assigned_analyst") or ""),
                str(case.get("review_requested_by") or ""),
                str(classification.get("actor_subject", "")),
            }
            if command.actor_subject in prohibited_subjects:
                raise ValidationFailed("segregation of duties rejected the review decision")

            approved_disposition = command.approved_disposition
            if command.decision == "APPROVED":
                approved_disposition = approved_disposition or str(case.get("proposed_disposition") or "")
                if approved_disposition not in self.SUPPORTED_DISPOSITIONS:
                    raise ValidationFailed("approved disposition is unsupported")
            now = self._utc_now()
            audit_link_hash = uow.audit.append(
                command.actor_subject,
                command.actor_role,
                "failed_debit.human_review.decision",
                command.dispute_id,
                {
                    "review_id": review_id,
                    "decision": command.decision,
                    "approved_disposition": approved_disposition,
                },
            )
            uow.failed_debit.add_review_decision(
                {
                    "review_event_id": review_id + "-" + command.decision,
                    "dispute_id": command.dispute_id,
                    "review_id": review_id,
                    "decision_status": command.decision,
                    "actor_subject": command.actor_subject,
                    "actor_role": command.actor_role,
                    "reason_code": command.reason_code,
                    "rationale": command.rationale,
                    "approved_disposition": approved_disposition,
                    "occurred_at_utc": now,
                    "correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                }
            )
            next_version = self._update_case(
                uow=uow,
                dispute_id=command.dispute_id,
                current_state="awaiting_human_review",
                next_state="decision_recorded",
                expected_version=current_version,
                updates={
                    "approved_disposition": approved_disposition,
                    "human_review_status": command.decision,
                    "updated_at_utc": now,
                    "last_correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                    "resolution_status": "decision_recorded",
                },
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=command.dispute_id,
                event_type="FailedDebitReviewDecisionRecorded",
                state="decision_recorded",
                aggregate_version=next_version,
                actor_subject=command.actor_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=audit_link_hash,
                payload={
                    "review_id": review_id,
                    "decision": command.decision,
                    "approved_disposition": approved_disposition,
                },
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, command.dispute_id)
            detail = self._require_case_detail(uow, command.dispute_id)
            uow.commit()
            return detail

    def record_disposition(self, command: RecordFailedDebitDispositionCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail

            case = self._require_case(uow, command.dispute_id)
            current_version = self._expected_current_version(case, command.expected_version)
            if str(case["state"]) != "decision_recorded":
                raise ValidationFailed("disposition requires a decision_recorded case")
            if command.disposition not in self.SUPPORTED_DISPOSITIONS:
                raise ValidationFailed("unsupported disposition")
            human_review_required = bool(case["human_review_required"])
            if human_review_required and str(case["human_review_status"]) != "APPROVED":
                raise ValidationFailed("approved human review is required before disposition")
            approved_disposition = str(case.get("approved_disposition") or "")
            proposed_disposition = str(case.get("proposed_disposition") or "")
            allowed_disposition = approved_disposition if human_review_required else proposed_disposition
            if allowed_disposition and command.disposition != allowed_disposition:
                raise ValidationFailed("disposition must match the governed decision")

            now = self._utc_now()
            disposition_payload = {
                "disposition": command.disposition,
                "reason_code": command.reason_code,
                "rationale": command.rationale,
                "recorded_by": command.actor_subject,
                "recorded_at_utc": now,
            }
            audit_link_hash = uow.audit.append(
                command.actor_subject,
                command.actor_role,
                "failed_debit.disposition.record",
                command.dispute_id,
                {
                    "disposition": command.disposition,
                    "reason_code": command.reason_code,
                },
            )
            next_version = self._update_case(
                uow=uow,
                dispute_id=command.dispute_id,
                current_state="decision_recorded",
                next_state="resolved",
                expected_version=current_version,
                updates={
                    "latest_disposition_payload_json": json.dumps(
                        disposition_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "approved_disposition": command.disposition,
                    "resolution_status": "resolved",
                    "updated_at_utc": now,
                    "last_correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                    "last_audit_check_status": "not_run",
                    "last_audit_check_payload_json": None,
                },
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=command.dispute_id,
                event_type="FailedDebitDispositionRecorded",
                state="resolved",
                aggregate_version=next_version,
                actor_subject=command.actor_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=audit_link_hash,
                payload={"disposition": command.disposition, "reason_code": command.reason_code},
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, command.dispute_id)
            detail = self._require_case_detail(uow, command.dispute_id)
            uow.commit()
            return detail

    def close_case(self, command: CloseFailedDebitCaseCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail

            case = self._require_case(uow, command.dispute_id)
            current_version = self._expected_current_version(case, command.expected_version)
            if str(case["state"]) != "resolved":
                raise ValidationFailed("only resolved cases can be closed")
            if case.get("latest_disposition_payload_json") in (None, ""):
                raise ValidationFailed("a recorded disposition is required before closure")
            if str(case.get("last_audit_check_status")) != "passed":
                raise ValidationFailed("audit integrity verification must pass before closure")
            if bool(case["human_review_required"]) and str(case["human_review_status"]) != "APPROVED":
                raise ValidationFailed("approved human review is required before closure")

            now = self._utc_now()
            audit_link_hash = uow.audit.append(
                command.actor_subject,
                command.actor_role,
                "failed_debit.case.close",
                command.dispute_id,
                {"reason_code": command.reason_code},
            )
            next_version = self._update_case(
                uow=uow,
                dispute_id=command.dispute_id,
                current_state="resolved",
                next_state="closed",
                expected_version=current_version,
                updates={
                    "closed_at_utc": now,
                    "closed_by": command.actor_subject,
                    "resolution_status": "closed",
                    "updated_at_utc": now,
                    "last_correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                },
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=command.dispute_id,
                event_type="FailedDebitCaseClosed",
                state="closed",
                aggregate_version=next_version,
                actor_subject=command.actor_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=audit_link_hash,
                payload={"reason_code": command.reason_code, "rationale": command.rationale},
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, command.dispute_id)
            detail = self._require_case_detail(uow, command.dispute_id)
            uow.commit()
            return detail

    def quarantine_case(self, command: QuarantineFailedDebitCaseCommand) -> dict[str, Any]:
        request_fingerprint = self._request_fingerprint(command)
        with self.unit_of_work as uow:
            replayed = uow.idempotency.reserve(command.idempotency_key, request_fingerprint)
            if replayed is not None:
                detail = self._replayed_detail(replayed, request_fingerprint, uow)
                uow.commit()
                return detail

            case = self._require_case(uow, command.dispute_id)
            current_version = self._expected_current_version(case, command.expected_version)
            current_state = str(case["state"])
            if current_state == "closed":
                raise ValidationFailed("closed cases require explicit governed recovery before quarantine")

            now = self._utc_now()
            audit_link_hash = uow.audit.append(
                command.actor_subject,
                command.actor_role,
                "failed_debit.case.quarantine",
                command.dispute_id,
                {"reason_code": command.reason_code, "reason": command.rationale},
            )
            next_version = self._update_case(
                uow=uow,
                dispute_id=command.dispute_id,
                current_state=current_state,
                next_state="quarantined",
                expected_version=current_version,
                updates={
                    "quarantined_at_utc": now,
                    "quarantined_by": command.actor_subject,
                    "quarantine_reason_code": command.reason_code,
                    "quarantine_reason": command.rationale,
                    "resolution_status": "quarantined",
                    "updated_at_utc": now,
                    "last_correlation_id": command.correlation_id,
                    "audit_link_hash": audit_link_hash,
                },
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=command.dispute_id,
                event_type="FailedDebitCaseQuarantined",
                state="quarantined",
                aggregate_version=next_version,
                actor_subject=command.actor_subject,
                correlation_id=command.correlation_id,
                audit_link_hash=audit_link_hash,
                payload={"reason_code": command.reason_code, "reason": command.rationale},
            )
            uow.idempotency.finalize(command.idempotency_key, request_fingerprint, command.dispute_id)
            detail = self._require_case_detail(uow, command.dispute_id)
            uow.commit()
            return detail

    def verify_audit_integrity(
        self,
        *,
        dispute_id: str,
        actor_subject: str,
        actor_role: str,
        correlation_id: str,
    ) -> dict[str, Any]:
        with self.unit_of_work as uow:
            case = self._require_case(uow, dispute_id)
            verification_passed = bool(getattr(uow.audit, "verify")())
            details = {
                "verified_at_utc": self._utc_now(),
                "verification_scope": "global_hash_chain",
                "passed": verification_passed,
            }
            verification_id = "AUD-" + hashlib.sha256(
                f"{dispute_id}|{correlation_id}|{details['verified_at_utc']}".encode("utf-8")
            ).hexdigest()[:12].upper()
            audit_link_hash = uow.audit.append(
                actor_subject,
                actor_role,
                "failed_debit.audit_integrity.verify",
                dispute_id,
                details,
            )
            quarantine_applied = False
            current_state = str(case["state"])
            current_version = int(case["version"])
            if verification_passed:
                next_state = current_state
                next_version = self._update_case(
                    uow=uow,
                    dispute_id=dispute_id,
                    current_state=current_state,
                    next_state=next_state,
                    expected_version=current_version,
                    updates={
                        "last_audit_check_status": "passed",
                        "last_audit_check_payload_json": json.dumps(
                            details,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "updated_at_utc": details["verified_at_utc"],
                        "last_correlation_id": correlation_id,
                        "audit_link_hash": audit_link_hash,
                    },
                )
            else:
                quarantine_applied = current_state not in {"quarantined", "closed"}
                details["quarantine_required"] = True
                next_state = "quarantined" if quarantine_applied else current_state
                updates = {
                    "last_audit_check_status": "failed",
                    "last_audit_check_payload_json": json.dumps(
                        details,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    "updated_at_utc": details["verified_at_utc"],
                    "last_correlation_id": correlation_id,
                    "audit_link_hash": audit_link_hash,
                }
                if quarantine_applied:
                    updates.update(
                        {
                            "quarantined_at_utc": details["verified_at_utc"],
                            "quarantined_by": actor_subject,
                            "quarantine_reason_code": "AUDIT_INTEGRITY_FAILURE",
                            "quarantine_reason": "Audit integrity verification failed.",
                            "resolution_status": "quarantined",
                        }
                    )
                next_version = self._update_case(
                    uow=uow,
                    dispute_id=dispute_id,
                    current_state=current_state,
                    next_state=next_state,
                    expected_version=current_version,
                    updates=updates,
                )
            uow.failed_debit.add_audit_check(
                {
                    "verification_id": verification_id,
                    "dispute_id": dispute_id,
                    "actor_subject": actor_subject,
                    "actor_role": actor_role,
                    "verification_status": "passed" if verification_passed else "failed",
                    "quarantine_applied": quarantine_applied,
                    "verified_at_utc": details["verified_at_utc"],
                    "correlation_id": correlation_id,
                    "details_json": json.dumps(details, sort_keys=True, separators=(",", ":")),
                    "audit_link_hash": audit_link_hash,
                }
            )
            self._append_timeline_event(
                uow=uow,
                dispute_id=dispute_id,
                event_type="FailedDebitAuditIntegrityVerified",
                state=next_state,
                aggregate_version=next_version,
                actor_subject=actor_subject,
                correlation_id=correlation_id,
                audit_link_hash=audit_link_hash,
                payload={"passed": verification_passed, "verification_id": verification_id},
            )
            if quarantine_applied:
                self._append_timeline_event(
                    uow=uow,
                    dispute_id=dispute_id,
                    event_type="FailedDebitCaseQuarantined",
                    state="quarantined",
                    aggregate_version=next_version,
                    actor_subject=actor_subject,
                    correlation_id=correlation_id,
                    audit_link_hash=audit_link_hash,
                    payload={"reason_code": "AUDIT_INTEGRITY_FAILURE"},
                )
            detail = self._require_case_detail(uow, dispute_id)
            uow.commit()
            return {
                "dispute_id": dispute_id,
                "version": detail["version"],
                "state": detail["state"],
                "passed": verification_passed,
                "verification_status": "passed" if verification_passed else "failed",
                "quarantine_applied": quarantine_applied,
                "details": details,
                "certification_boundary": "certification_ready_not_certified",
            }

    def propose_resolution(self, command: RecordFailedDebitDispositionCommand) -> dict[str, Any]:
        return self.record_disposition(command)

    def get_timeline(self, dispute_id: str) -> dict[str, Any] | None:
        return self.get_history(dispute_id)

    def _replayed_detail(
        self,
        replayed: tuple[str, str],
        request_fingerprint: str,
        uow: UnitOfWork,
    ) -> dict[str, Any]:
        stored_fingerprint, stored_result = replayed
        if not hmac.compare_digest(stored_fingerprint, request_fingerprint):
            raise IdempotencyConflictError(
                "idempotency key reused with a different failed-debit payload"
            )
        if not stored_result:
            raise IdempotencyConflictError("idempotency key reservation has no stored result")
        return self._require_case_detail(uow, stored_result)

    def _require_case(self, uow: UnitOfWork, dispute_id: str) -> dict[str, Any]:
        case = uow.failed_debit.get_case(dispute_id)
        if case is None:
            raise ValidationFailed("failed-debit dispute not found")
        return case

    def _require_case_detail(self, uow: UnitOfWork, dispute_id: str) -> dict[str, Any]:
        detail = uow.failed_debit.get_case_detail(dispute_id)
        if detail is None:
            raise ValidationFailed("failed-debit dispute not found")
        return detail

    @staticmethod
    def _expected_current_version(case: dict[str, Any], expected_version: int | None) -> int:
        current_version = int(case["version"])
        if expected_version is None:
            raise ValidationFailed("expected_version is required for state-changing requests")
        if expected_version < 1:
            raise ValidationFailed("expected_version must be at least 1")
        if expected_version != current_version:
            raise OptimisticConcurrencyError("failed-debit case stale write rejected")
        return current_version

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _normalize_utc(value: str) -> str:
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValidationFailed("timestamp must be RFC 3339 / ISO 8601 UTC") from exc
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _parse_amount_minor(value: str) -> int:
        if not isinstance(value, str) or re.fullmatch(
            r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?",
            value,
        ) is None:
            raise ValidationFailed(
                "amount must be a bounded fixed-point decimal with at most two decimal places"
            )
        try:
            amount = Decimal(value)
            if not amount.is_finite():
                raise ValidationFailed("amount must be finite")
            if amount <= Decimal("0"):
                raise ValidationFailed("amount must be greater than zero")
            quantized = amount.quantize(Decimal("0.01"))
            if quantized != amount:
                raise ValidationFailed("amount must have at most two decimal places")
            return int(quantized * 100)
        except (InvalidOperation, OverflowError, ValueError) as exc:
            raise ValidationFailed("amount must be a fixed-point decimal string") from exc

    @staticmethod
    def _append_timeline_event(
        *,
        uow: UnitOfWork,
        dispute_id: str,
        event_type: str,
        state: str,
        aggregate_version: int,
        actor_subject: str,
        correlation_id: str,
        audit_link_hash: str,
        payload: dict[str, Any],
    ) -> None:
        event_payload = {**payload, "audit_link_hash": audit_link_hash}
        event = dispute_event(event_type, dispute_id, aggregate_version, event_payload)
        uow.failed_debit.add_event(
            {
                "event_id": FailedDebitRuntimeService._event_id(event),
                "dispute_id": dispute_id,
                "event_type": event_type,
                "state": state,
                "aggregate_version": aggregate_version,
                "actor_subject": actor_subject,
                "occurred_at_utc": event.occurred_at_utc,
                "correlation_id": correlation_id,
                "payload_json": json.dumps(event_payload, sort_keys=True, separators=(",", ":")),
                "audit_link_hash": audit_link_hash,
            }
        )
        uow.outbox.enqueue(event, trace_id=correlation_id)

    @staticmethod
    def _event_id(event: DomainEvent) -> str:
        material = "|".join(
            [
                event.event_type,
                event.aggregate_id,
                str(event.aggregate_version),
                event.occurred_at_utc,
                json.dumps(event.payload, sort_keys=True, separators=(",", ":")),
            ]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _request_fingerprint(command: object) -> str:
        if not hasattr(command, "__dict__"):
            raise TypeError("command must be dataclass-like")
        material = {key: value for key, value in sorted(vars(command).items())}
        return hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _create_business_fingerprint(command: CreateFailedDebitCaseCommand) -> str:
        material = {
            "transaction_ref": command.transaction_ref,
            "customer_upi": command.customer_upi,
            "amount": command.amount,
            "reason_code": command.reason_code,
            "owner_subject": command.owner_subject,
        }
        return hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _derived_evidence_id(command: AttachFailedDebitEvidenceCommand) -> str:
        material = {
            "dispute_id": command.dispute_id,
            "evidence_type": command.evidence_type,
            "source": command.source,
            "summary": command.summary,
            "observed_at_utc": command.observed_at_utc,
        }
        return "EVD-" + hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:12].upper()

    def _update_case(
        self,
        *,
        uow: UnitOfWork,
        dispute_id: str,
        current_state: str,
        next_state: str,
        expected_version: int,
        updates: dict[str, Any],
    ) -> int:
        from generated_application.app.domain.entities import ensure_failed_debit_transition

        ensure_failed_debit_transition(current_state, next_state)
        merged_updates = dict(updates)
        merged_updates["state"] = next_state
        return uow.failed_debit.update_case(
            dispute_id,
            expected_version=expected_version,
            updates=merged_updates,
        )

    def _transition_case(
        self,
        *,
        uow: UnitOfWork,
        case: dict[str, Any],
        dispute_id: str,
        next_state: str,
        actor_subject: str,
        actor_role: str,
        correlation_id: str,
        action: str,
        audit_payload: dict[str, Any],
        updates: dict[str, Any],
    ) -> tuple[int, str]:
        audit_link_hash = uow.audit.append(actor_subject, actor_role, action, dispute_id, audit_payload)
        next_version = self._update_case(
            uow=uow,
            dispute_id=dispute_id,
            current_state=str(case["state"]),
            next_state=next_state,
            expected_version=int(case["version"]),
            updates={**updates, "audit_link_hash": audit_link_hash},
        )
        return next_version, audit_link_hash

    def _classification_payload(
        self,
        *,
        case: dict[str, Any],
        investigation: dict[str, Any],
        missing_evidence: list[str],
        actor_subject: str,
    ) -> dict[str, Any]:
        observation = investigation["observation"]
        impact = self._impact_for_amount(int(case["amount_minor"]))
        contradictory = bool(observation["contradictory"])
        complete = not missing_evidence
        if contradictory or observation["status"] in {"unknown", "temporary_failure", "timeout"}:
            classification = "UNCERTAIN"
            reason_code = "INSUFFICIENT_OR_CONTRADICTORY_EVIDENCE"
            proposed_disposition = "ESCALATE_FOR_SPECIALIST_REVIEW"
        elif observation["status"] == "credit_pending":
            classification = "PENDING"
            reason_code = "CREDIT_PENDING"
            proposed_disposition = "WAIT_FOR_NETWORK_UPDATE"
        elif observation["status"] == "beneficiary_credit_failed":
            classification = "FAILED"
            reason_code = "BENEFICIARY_CREDIT_FAILED"
            proposed_disposition = "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP"
        elif observation["status"] == "reversal_confirmed":
            classification = "REVERSED"
            reason_code = "REVERSAL_CONFIRMED"
            proposed_disposition = "CONFIRM_REVERSAL_OBSERVED"
        else:
            classification = "CREDIT_CONFIRMED"
            reason_code = "BENEFICIARY_CREDIT_CONFIRMED"
            proposed_disposition = "CONFIRM_BENEFICIARY_CREDIT_OBSERVED"

        confidence = 90
        if not complete:
            confidence -= 25
        if contradictory:
            confidence = 20
        elif observation["status"] in {"unknown", "temporary_failure", "timeout"}:
            confidence = 35
        elif observation["status"] == "credit_pending":
            confidence = 70
        confidence = max(0, min(confidence, 100))
        human_review_required = (
            classification == "UNCERTAIN"
            or confidence < self.CONFIDENCE_REVIEW_THRESHOLD
            or impact in {"HIGH", "CRITICAL"}
            or contradictory
            or not complete
        )
        if not complete and proposed_disposition not in {"ESCALATE_FOR_SPECIALIST_REVIEW"}:
            proposed_disposition = "REQUIRE_ADDITIONAL_EVIDENCE"
        return {
            "classification": classification,
            "reason_code": reason_code,
            "confidence": confidence,
            "impact": impact,
            "human_review_required": human_review_required,
            "proposed_disposition": proposed_disposition,
            "missing_evidence_types": missing_evidence,
            "actor_subject": actor_subject,
            "classified_at_utc": self._utc_now(),
            "provider_snapshot": investigation["provider_snapshot"],
        }

    @staticmethod
    def _observation_from_status(status: str) -> dict[str, Any]:
        normalized = status.strip().lower()
        mapping = {
            "beneficiary_credit_pending": {
                "status": "credit_pending",
                "debit_status": "succeeded",
                "beneficiary_credit_status": "pending",
                "reversal_status": "not_observed",
                "contradictory": False,
            },
            "beneficiary_not_credited": {
                "status": "beneficiary_credit_failed",
                "debit_status": "succeeded",
                "beneficiary_credit_status": "failed",
                "reversal_status": "not_observed",
                "contradictory": False,
            },
            "reversal_confirmed": {
                "status": "reversal_confirmed",
                "debit_status": "succeeded",
                "beneficiary_credit_status": "not_observed",
                "reversal_status": "confirmed",
                "contradictory": False,
            },
            "beneficiary_credited": {
                "status": "credit_confirmed",
                "debit_status": "succeeded",
                "beneficiary_credit_status": "confirmed",
                "reversal_status": "not_observed",
                "contradictory": False,
            },
            "contradictory": {
                "status": "unknown",
                "debit_status": "contradictory",
                "beneficiary_credit_status": "contradictory",
                "reversal_status": "contradictory",
                "contradictory": True,
            },
            "unknown": {
                "status": "unknown",
                "debit_status": "unknown",
                "beneficiary_credit_status": "unknown",
                "reversal_status": "unknown",
                "contradictory": False,
            },
            "simulated_timeout": {
                "status": "timeout",
                "debit_status": "unknown",
                "beneficiary_credit_status": "unknown",
                "reversal_status": "unknown",
                "contradictory": False,
            },
            "temporary_failure": {
                "status": "temporary_failure",
                "debit_status": "unknown",
                "beneficiary_credit_status": "unknown",
                "reversal_status": "unknown",
                "contradictory": False,
            },
        }
        if normalized not in mapping:
            raise ValidationFailed("unsupported simulated bank status")
        return {
            **mapping[normalized],
            "observation_timestamp_utc": FailedDebitRuntimeService._utc_now(),
            "provider_reason_code": normalized.upper(),
            "mock_adapter_version": "local-simulated-v1",
            "observation_digest": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        }

    @staticmethod
    def _impact_for_amount(amount_minor: int) -> str:
        if amount_minor >= 500_000:
            return "CRITICAL"
        if amount_minor >= FailedDebitRuntimeService.HIGH_VALUE_THRESHOLD_MINOR:
            return "HIGH"
        if amount_minor >= 10_000:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _load_json(value: Any) -> dict[str, Any]:
        if not isinstance(value, str) or not value:
            return {}
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
