from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class MockInvestigationResponse:
    reference: str
    simulated_bank_code: str
    simulated_network_status: str
    evidence_score: int


class MockBankInvestigationClient:
    # Simulated bank/NPCI-style investigation client; performs no real rail call.

    def request_investigation(
        self,
        transaction_id: str,
        evidence_refs: list[str],
    ) -> MockInvestigationResponse:
        raw = transaction_id + "|" + "|".join(evidence_refs)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return MockInvestigationResponse(
            reference=f"MOCK-INV-{digest[:14].upper()}",
            simulated_bank_code=f"MOCK-BANK-{digest[14:20].upper()}",
            simulated_network_status="SIMULATED_RESPONSE_RECEIVED",
            evidence_score=92 if evidence_refs else 0,
        )
