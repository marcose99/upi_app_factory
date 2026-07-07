from __future__ import annotations

from .models import DisputeRecord, DisputeType, EcosystemDecision


class MockBankAdapter:
    def check_transaction(self, record: DisputeRecord) -> dict[str, str]:
        if record.amount_paise <= 100_000:
            return {"bank_status": "eligible_for_fast_mock_refund"}
        return {"bank_status": "manual_review_required"}


class MockPspAdapter:
    def check_psp_status(self, record: DisputeRecord) -> dict[str, str]:
        if record.dispute_type is DisputeType.DUPLICATE_DEBIT:
            return {"psp_status": "duplicate_detected"}
        return {"psp_status": "mock_status_available"}


class MockOdrAdapter:
    def create_mock_case_reference(self, record: DisputeRecord) -> str:
        return f"MOCK-ODR-{record.dispute_id[-8:].upper()}"


class MockEcosystemGateway:
    def __init__(self) -> None:
        self.bank = MockBankAdapter()
        self.psp = MockPspAdapter()
        self.odr = MockOdrAdapter()

    def decide(self, record: DisputeRecord) -> tuple[EcosystemDecision, str, list[str]]:
        bank_result = self.bank.check_transaction(record)
        psp_result = self.psp.check_psp_status(record)
        sources = ["mock_bank_adapter", "mock_psp_adapter"]

        if record.dispute_type is DisputeType.UNAUTHORIZED_TRANSACTION:
            return (
                EcosystemDecision.ESCALATE_TO_ODR,
                "Unauthorized transaction simulation requires mock escalation path.",
                sources + ["mock_odr_adapter"],
            )

        if record.dispute_type is DisputeType.DUPLICATE_DEBIT:
            return (
                EcosystemDecision.REFUND_ELIGIBLE,
                f"Mock PSP detected duplicate debit: {psp_result['psp_status']}.",
                sources,
            )

        if bank_result["bank_status"] == "eligible_for_fast_mock_refund":
            return (
                EcosystemDecision.REFUND_ELIGIBLE,
                "Mock bank indicates low-value failed transaction refund path.",
                sources,
            )

        return (
            EcosystemDecision.MORE_EVIDENCE_REQUIRED,
            "Mock ecosystem needs more evidence for high-value dispute simulation.",
            sources,
        )
