from __future__ import annotations

import hashlib
from typing import Any

from .domain import (
    DisputeCase,
    DisputeCategory,
    DisputeStatus,
    PaymentRail,
    utc_now_iso,
)
from .external_mocks import MockBankDirectoryClient, MockNPCIReferenceClient


class DisputeValidationError(ValueError):
    """Raised when a dispute intake request violates local application rules."""


class InMemoryDisputeCaseRepository:
    def __init__(self) -> None:
        self._cases: dict[str, DisputeCase] = {}

    def save(self, case: DisputeCase) -> None:
        self._cases[case.case_id] = case

    def get(self, case_id: str) -> DisputeCase | None:
        return self._cases.get(case_id)


class DisputeCaseIntakeService:
    def __init__(
        self,
        repository: InMemoryDisputeCaseRepository | None = None,
        bank_directory: MockBankDirectoryClient | None = None,
        npci_reference_client: MockNPCIReferenceClient | None = None,
    ) -> None:
        self._repository = repository or InMemoryDisputeCaseRepository()
        self._bank_directory = bank_directory or MockBankDirectoryClient()
        self._npci_reference_client = npci_reference_client or MockNPCIReferenceClient()

    def create_dispute_case(self, payload: dict[str, Any]) -> DisputeCase:
        transaction_id = self._required_text(payload, "transaction_id")
        payer_vpa = self._required_text(payload, "payer_vpa")
        payee_vpa = self._required_text(payload, "payee_vpa")
        amount_paise = self._positive_int(payload, "amount_paise")
        rail = PaymentRail(self._required_text(payload, "rail"))
        category = DisputeCategory(self._required_text(payload, "category"))
        evidence_refs = tuple(payload.get("evidence_refs", ()))

        if rail is not PaymentRail.UPI:
            raise DisputeValidationError("Only UPI rail is supported in this slice.")
        if "@" not in payer_vpa or "@" not in payee_vpa:
            raise DisputeValidationError(
                "Both payer_vpa and payee_vpa must look like VPAs."
            )
        if not evidence_refs:
            raise DisputeValidationError("At least one evidence reference is required.")

        self._bank_directory.lookup_bank_for_vpa(payee_vpa)
        mock_reference = self._npci_reference_client.reserve_dispute_reference(
            transaction_id
        )
        case_id = self._case_id(transaction_id, payer_vpa, payee_vpa)

        case = DisputeCase(
            case_id=case_id,
            transaction_id=transaction_id,
            payer_vpa=payer_vpa,
            payee_vpa=payee_vpa,
            amount_paise=amount_paise,
            rail=rail,
            category=category,
            status=DisputeStatus.INTAKE_ACCEPTED,
            mock_ecosystem_reference=mock_reference,
            evidence_refs=evidence_refs,
            created_at_utc=utc_now_iso(),
            boundary_statement=(
                "Primary UPI dispute application logic is local and runnable; "
                "external banks, rails, NPCI-style, RBI-style, upstream, and "
                "downstream ecosystem interfaces are simulated mocks only."
            ),
        )
        self._repository.save(case)
        return case

    def get_dispute_case(self, case_id: str) -> DisputeCase | None:
        return self._repository.get(case_id)

    @staticmethod
    def _required_text(payload: dict[str, Any], field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise DisputeValidationError(f"{field} is required.")
        return value.strip()

    @staticmethod
    def _positive_int(payload: dict[str, Any], field: str) -> int:
        value = payload.get(field)
        if not isinstance(value, int) or value <= 0:
            raise DisputeValidationError(f"{field} must be a positive integer.")
        return value

    @staticmethod
    def _case_id(transaction_id: str, payer_vpa: str, payee_vpa: str) -> str:
        raw = f"{transaction_id}|{payer_vpa}|{payee_vpa}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"UPI-DISPUTE-{digest[:12].upper()}"
