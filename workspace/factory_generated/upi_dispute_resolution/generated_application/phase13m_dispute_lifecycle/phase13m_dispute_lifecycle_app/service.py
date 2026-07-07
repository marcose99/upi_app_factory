from __future__ import annotations

import hashlib
from typing import Any

from .domain import DisputeCase, DisputeStatus, ResolutionOutcome
from .external_mocks import MockBankInvestigationClient


class DisputeLifecycleError(ValueError):
    pass


class InMemoryDisputeLifecycleRepository:
    def __init__(self) -> None:
        self._cases: dict[str, DisputeCase] = {}

    def save(self, case: DisputeCase) -> None:
        self._cases[case.case_id] = case

    def get(self, case_id: str) -> DisputeCase | None:
        return self._cases.get(case_id)


class DisputeLifecycleService:
    # Primary lifecycle logic is local and runnable; external ecosystem
    # interfaces are simulated mocks only.
    def __init__(
        self,
        repository: InMemoryDisputeLifecycleRepository | None = None,
        investigation_client: MockBankInvestigationClient | None = None,
    ) -> None:
        self._repository = repository or InMemoryDisputeLifecycleRepository()
        self._investigation_client = (
            investigation_client or MockBankInvestigationClient()
        )

    def create_case(self, payload: dict[str, Any]) -> DisputeCase:
        transaction_id = self._required_text(payload, "transaction_id")
        payer_vpa = self._required_text(payload, "payer_vpa")
        payee_vpa = self._required_text(payload, "payee_vpa")
        amount_paise = self._positive_int(payload, "amount_paise")
        evidence_refs = self._evidence_refs(payload)
        case = DisputeCase(
            case_id=self._case_id(transaction_id, payer_vpa, payee_vpa),
            transaction_id=transaction_id,
            payer_vpa=payer_vpa,
            payee_vpa=payee_vpa,
            amount_paise=amount_paise,
            status=DisputeStatus.INTAKE_ACCEPTED,
            evidence_refs=evidence_refs,
        )
        case.add_event("case_created", {"transaction_id": transaction_id})
        self._repository.save(case)
        return case

    def validate_evidence(self, case_id: str) -> DisputeCase:
        case = self._require_case(case_id)
        if case.status is not DisputeStatus.INTAKE_ACCEPTED:
            raise DisputeLifecycleError("Evidence can only be validated after intake.")
        if not case.evidence_refs:
            raise DisputeLifecycleError("At least one evidence reference is required.")
        case.status = DisputeStatus.EVIDENCE_VALIDATED
        case.add_event("evidence_validated", {"evidence_count": len(case.evidence_refs)})
        return case

    def request_investigation(self, case_id: str) -> DisputeCase:
        case = self._require_case(case_id)
        if case.status is not DisputeStatus.EVIDENCE_VALIDATED:
            raise DisputeLifecycleError("Investigation requires validated evidence.")
        response = self._investigation_client.request_investigation(
            case.transaction_id,
            case.evidence_refs,
        )
        case.status = DisputeStatus.INVESTIGATION_RESPONDED
        case.mock_investigation_reference = response.reference
        case.add_event(
            "mock_investigation_responded",
            {
                "reference": response.reference,
                "simulated_bank_code": response.simulated_bank_code,
                "simulated_network_status": response.simulated_network_status,
                "evidence_score": response.evidence_score,
            },
        )
        return case

    def propose_resolution(self, case_id: str) -> DisputeCase:
        case = self._require_case(case_id)
        if case.status is not DisputeStatus.INVESTIGATION_RESPONDED:
            raise DisputeLifecycleError(
                "Resolution requires mock investigation response."
            )
        case.status = DisputeStatus.RESOLUTION_PROPOSED
        case.resolution_outcome = ResolutionOutcome.CUSTOMER_CREDIT_RECOMMENDED
        case.add_event("resolution_proposed", {"outcome": case.resolution_outcome.value})
        return case

    def finalize_resolution(self, case_id: str) -> DisputeCase:
        case = self._require_case(case_id)
        if case.status is not DisputeStatus.RESOLUTION_PROPOSED:
            raise DisputeLifecycleError("Only proposed resolutions can be finalized.")
        case.status = DisputeStatus.RESOLVED
        outcome = None if case.resolution_outcome is None else case.resolution_outcome.value
        case.add_event("case_resolved", {"outcome": str(outcome)})
        return case

    def progress_to_resolution(self, case_id: str) -> DisputeCase:
        self.validate_evidence(case_id)
        self.request_investigation(case_id)
        self.propose_resolution(case_id)
        return self.finalize_resolution(case_id)

    def get_case(self, case_id: str) -> DisputeCase | None:
        return self._repository.get(case_id)

    def _require_case(self, case_id: str) -> DisputeCase:
        case = self._repository.get(case_id)
        if case is None:
            raise DisputeLifecycleError(f"Unknown case_id: {case_id}")
        return case

    @staticmethod
    def _required_text(payload: dict[str, Any], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DisputeLifecycleError(f"{field} is required.")
        return value.strip()

    @staticmethod
    def _positive_int(payload: dict[str, Any], field: str) -> int:
        value = payload.get(field)
        if not isinstance(value, int) or value <= 0:
            raise DisputeLifecycleError(f"{field} must be a positive integer.")
        return value

    @staticmethod
    def _evidence_refs(payload: dict[str, Any]) -> list[str]:
        refs = payload.get("evidence_refs")
        if (
            not isinstance(refs, list)
            or not refs
            or not all(isinstance(item, str) and item for item in refs)
        ):
            raise DisputeLifecycleError(
                "evidence_refs must be a non-empty list of strings."
            )
        return list(refs)

    @staticmethod
    def _case_id(transaction_id: str, payer_vpa: str, payee_vpa: str) -> str:
        raw = f"{transaction_id}|{payer_vpa}|{payee_vpa}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"UPI-LIFECYCLE-{digest[:12].upper()}"
