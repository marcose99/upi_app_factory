from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class MockBankLookupResult:
    vpa: str
    simulated_psp: str
    simulated_bank_code: str


class MockBankDirectoryClient:
    """Simulated bank-directory client for external ecosystem boundaries only."""

    def lookup_bank_for_vpa(self, vpa: str) -> MockBankLookupResult:
        digest = hashlib.sha256(vpa.encode("utf-8")).hexdigest()
        return MockBankLookupResult(
            vpa=vpa,
            simulated_psp=f"MOCK-PSP-{digest[:6].upper()}",
            simulated_bank_code=f"MOCK-BANK-{digest[6:12].upper()}",
        )


class MockNPCIReferenceClient:
    """Simulated NPCI-style reference client; it performs no real rail call."""

    def reserve_dispute_reference(self, transaction_id: str) -> str:
        digest = hashlib.sha256(transaction_id.encode("utf-8")).hexdigest()
        return f"MOCK-NPCI-REF-{digest[:16].upper()}"
