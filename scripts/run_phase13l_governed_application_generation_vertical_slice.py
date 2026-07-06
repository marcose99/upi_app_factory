#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

APP_ID = "upi_dispute_resolution"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
GEN_APP_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "generated_application"
    / "phase13l_dispute_case_intake"
)
PACKAGE_NAME = "phase13l_dispute_case_intake_app"
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / APP_ID
    / "lifecycle_artifacts"
    / "phase13l"
)
AUDIT_PATH = ARTIFACT_DIR / "governed_application_generation_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "governed_application_generation_manifest.json"
REPORT_PATH = ARTIFACT_DIR / "governed_application_generation_report.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_file(relative_path: str, content: str) -> pathlib.Path:
    path = GEN_APP_DIR / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def relative(path: pathlib.Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def run_generated_tests() -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{GEN_APP_DIR}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "checks/dispute_case_intake_checks.py"],
        cwd=GEN_APP_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": [sys.executable, "-m", "pytest", "-q", "checks/dispute_case_intake_checks.py"],
        "cwd": relative(GEN_APP_DIR),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": result.returncode == 0,
    }


def app_files() -> dict[str, str]:
    return {
        "README.md": """# Phase 13L Dispute Case Intake Slice

This generated component is a local runnable UPI dispute-resolution application slice. It owns primary application logic for dispute case intake, validation,
case creation, and local retrieval.

External ecosystem boundaries are deliberately mock/simulated only. Bank,
NPCI-style, RBI-style, payment rail, and upstream/downstream interfaces are not
real integrations in this slice.

The generated Python package uses a phase-specific package name,
`phase13l_dispute_case_intake_app`, to avoid collision with the factory repo's
existing top-level `app` package.

## Run locally

```bash
cd workspace/factory_generated/upi_dispute_resolution/generated_application/phase13l_dispute_case_intake
python3 scripts/run_smoke.py
PYTHONPATH=. python3 -m pytest -q checks/dispute_case_intake_checks.py
```
""",
        f"{PACKAGE_NAME}/__init__.py": """from .api import create_dispute_case, get_dispute_case

__all__ = ["create_dispute_case", "get_dispute_case"]
""",
        f"{PACKAGE_NAME}/domain.py": """from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PaymentRail(str, Enum):
    UPI = "UPI"


class DisputeCategory(str, Enum):
    FAILED_TRANSACTION = "FAILED_TRANSACTION"
    UNAUTHORIZED_TRANSACTION = "UNAUTHORIZED_TRANSACTION"
    DUPLICATE_DEBIT = "DUPLICATE_DEBIT"
    GOODS_OR_SERVICE_NOT_RECEIVED = "GOODS_OR_SERVICE_NOT_RECEIVED"


class DisputeStatus(str, Enum):
    INTAKE_ACCEPTED = "INTAKE_ACCEPTED"
    VALIDATION_REJECTED = "VALIDATION_REJECTED"


@dataclass(frozen=True)
class DisputeCase:
    case_id: str
    transaction_id: str
    payer_vpa: str
    payee_vpa: str
    amount_paise: int
    rail: PaymentRail
    category: DisputeCategory
    status: DisputeStatus
    mock_ecosystem_reference: str
    evidence_refs: tuple[str, ...]
    created_at_utc: str
    boundary_statement: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "transaction_id": self.transaction_id,
            "payer_vpa": self.payer_vpa,
            "payee_vpa": self.payee_vpa,
            "amount_paise": self.amount_paise,
            "rail": self.rail.value,
            "category": self.category.value,
            "status": self.status.value,
            "mock_ecosystem_reference": self.mock_ecosystem_reference,
            "evidence_refs": list(self.evidence_refs),
            "created_at_utc": self.created_at_utc,
            "boundary_statement": self.boundary_statement,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
""",
        f"{PACKAGE_NAME}/external_mocks.py": """from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class MockBankLookupResult:
    vpa: str
    simulated_psp: str
    simulated_bank_code: str


class MockBankDirectoryClient:
    \"\"\"Simulated bank-directory client for external ecosystem boundaries only.\"\"\"

    def lookup_bank_for_vpa(self, vpa: str) -> MockBankLookupResult:
        digest = hashlib.sha256(vpa.encode("utf-8")).hexdigest()
        return MockBankLookupResult(
            vpa=vpa,
            simulated_psp=f"MOCK-PSP-{digest[:6].upper()}",
            simulated_bank_code=f"MOCK-BANK-{digest[6:12].upper()}",
        )


class MockNPCIReferenceClient:
    \"\"\"Simulated NPCI-style reference client; it performs no real rail call.\"\"\"

    def reserve_dispute_reference(self, transaction_id: str) -> str:
        digest = hashlib.sha256(transaction_id.encode("utf-8")).hexdigest()
        return f"MOCK-NPCI-REF-{digest[:16].upper()}"
""",
        f"{PACKAGE_NAME}/service.py": """from __future__ import annotations

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
    \"\"\"Raised when a dispute intake request violates local application rules.\"\"\"


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
""",
        f"{PACKAGE_NAME}/api.py": """from __future__ import annotations

from typing import Any

from .service import DisputeCaseIntakeService

_SERVICE = DisputeCaseIntakeService()


def create_dispute_case(payload: dict[str, Any]) -> dict[str, Any]:
    \"\"\"Application API facade for dispute intake.\"\"\"
    return _SERVICE.create_dispute_case(payload).to_dict()


def get_dispute_case(case_id: str) -> dict[str, Any] | None:
    case = _SERVICE.get_dispute_case(case_id)
    return None if case is None else case.to_dict()
""",
        "checks/dispute_case_intake_checks.py": f"""from __future__ import annotations

import pathlib
import sys

import pytest

GENERATED_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(GENERATED_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATED_ROOT))

from {PACKAGE_NAME}.api import create_dispute_case, get_dispute_case
from {PACKAGE_NAME}.service import DisputeCaseIntakeService, DisputeValidationError


def valid_payload() -> dict[str, object]:
    return {{
        "transaction_id": "TXN-20260706-0001",
        "payer_vpa": "payer@upi",
        "payee_vpa": "merchant@upi",
        "amount_paise": 125000,
        "rail": "UPI",
        "category": "FAILED_TRANSACTION",
        "evidence_refs": ["txn-log:TXN-20260706-0001", "customer-note:case-1"],
    }}


def test_create_dispute_case_accepts_valid_upi_intake() -> None:
    created = create_dispute_case(valid_payload())

    assert created["case_id"].startswith("UPI-DISPUTE-")
    assert created["status"] == "INTAKE_ACCEPTED"
    assert created["rail"] == "UPI"
    assert created["mock_ecosystem_reference"].startswith("MOCK-NPCI-REF-")
    assert "simulated mocks only" in created["boundary_statement"]

    loaded = get_dispute_case(str(created["case_id"]))
    assert loaded == created


def test_service_rejects_missing_evidence() -> None:
    payload = valid_payload()
    payload["evidence_refs"] = []

    with pytest.raises(DisputeValidationError, match="evidence"):
        DisputeCaseIntakeService().create_dispute_case(payload)


def test_service_rejects_invalid_vpa() -> None:
    payload = valid_payload()
    payload["payer_vpa"] = "not-a-vpa"

    with pytest.raises(DisputeValidationError, match="VPAs"):
        DisputeCaseIntakeService().create_dispute_case(payload)
""",
        "scripts/run_smoke.py": f"""from __future__ import annotations

import json

from {PACKAGE_NAME}.api import create_dispute_case

payload = {{
    "transaction_id": "TXN-20260706-SMOKE",
    "payer_vpa": "payer@upi",
    "payee_vpa": "merchant@upi",
    "amount_paise": 9900,
    "rail": "UPI",
    "category": "FAILED_TRANSACTION",
    "evidence_refs": ["smoke-test:evidence"],
}}

print(json.dumps(create_dispute_case(payload), indent=2, sort_keys=True))
""",
    }


def build_audit(
    files: dict[str, str],
    generated_paths: list[pathlib.Path],
    test_result: dict[str, Any],
) -> dict[str, Any]:
    agents = [
        {
            "agent_name": "requirement_intake_agent",
            "status": "completed",
            "output": "dispute case intake requirement package",
        },
        {
            "agent_name": "domain_model_agent",
            "status": "completed",
            "output": "UPI dispute domain model and validation errors",
        },
        {
            "agent_name": "application_slice_agent",
            "status": "completed",
            "output": "local runnable application service and API facade",
        },
        {
            "agent_name": "ecosystem_mock_agent",
            "status": "completed",
            "output": "mock bank and NPCI-style external boundary clients",
        },
        {
            "agent_name": "test_agent",
            "status": "completed",
            "output": "generated verification checks and smoke run for the generated slice",
        },
        {
            "agent_name": "governance_evidence_agent",
            "status": "completed",
            "output": "audit, manifest, hashes, and boundary evidence",
        },
    ]
    return {
        "app_id": APP_ID,
        "phase": "Phase 13L",
        "run_id": "phase13l_governed_application_generation_vertical_slice_001",
        "generated_at_utc": utc_now(),
        "adapter_mode": "local_deterministic",
        "truth_boundary": (
            "The primary generated UPI dispute application slice is local and "
            "runnable. External bank, rail, NPCI-style, RBI-style, upstream, "
            "and downstream integrations are simulated mocks only."
        ),
        "completed_agents": len(agents),
        "agents": agents,
        "generated_application_dir": relative(GEN_APP_DIR),
        "generated_package": PACKAGE_NAME,
        "generated_files": [relative(path) for path in generated_paths],
        "file_hashes": {
            relative(GEN_APP_DIR / path): sha256_text(text)
            for path, text in files.items()
        },
        "validation": {
            "generated_tests_passed": test_result["passed"],
            "generated_test_command": test_result["command"],
            "generated_test_cwd": test_result["cwd"],
        },
    }


def write_artifacts(audit: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    MANIFEST_PATH.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = f"""# Phase 13L Governed Application Generation Vertical Slice

Status: `generated`

Run ID: `{audit['run_id']}`

Generated application directory:

`{audit['generated_application_dir']}`

Generated package:

`{audit['generated_package']}`

Completed deterministic governed agents: `{audit['completed_agents']}`

Truth boundary:

{audit['truth_boundary']}

Generated tests passed: `{audit['validation']['generated_tests_passed']}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def generate() -> dict[str, Any]:
    if GEN_APP_DIR.exists():
        shutil.rmtree(GEN_APP_DIR)
    files = app_files()
    generated_paths = [write_file(path, text) for path, text in files.items()]
    test_result = run_generated_tests()
    audit = build_audit(files, generated_paths, test_result)
    write_artifacts(audit)
    if not test_result["passed"]:
        print(json.dumps(test_result, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    audit = generate()
    if not args.quiet:
        print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
