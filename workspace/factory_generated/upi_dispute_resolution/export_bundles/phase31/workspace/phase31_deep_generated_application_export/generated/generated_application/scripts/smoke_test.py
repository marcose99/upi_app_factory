#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from fastapi import HTTPException


APP_ROOT = Path(__file__).resolve().parents[1]
APP_PARENT = APP_ROOT.parent
if str(APP_PARENT) not in sys.path:
    sys.path.insert(0, str(APP_PARENT))


def smoke_payload() -> dict[str, object]:
    return {
        "transaction_ref": "PHASE42LOCAL001",
        "customer_upi": "localreviewer@upi",
        "reason": "Reviewer local smoke test for a simulated duplicate debit dispute.",
    }


def run_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="phase42-local-smoke-") as raw_tmp:
        from generated_application.app.interfaces.api.main import app
        from generated_application.app.application.commands import CreateDisputeCommand
        from generated_application.app.application.services import DisputeService
        from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import SqliteUnitOfWork
        from generated_application.app.observability.metrics import METRICS
        from generated_application.app.security.identity import (
            issue_local_test_token,
            local_principal,
            verify_local_test_token,
        )

        schema = app.openapi()
        assert schema["paths"]["/disputes"]["post"]["security"], "POST /disputes must be secured"
        try:
            local_principal(authorization=None, subject=None)
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("missing principal was not rejected")
        token = issue_local_test_token(
            subject="local-reviewer",
            scopes=("dispute:create", "dispute:read", "dispute:read:any"),
        )
        principal = verify_local_test_token(token)
        assert "dispute:create" in principal.scopes

        database = Path(raw_tmp) / "disputes.sqlite3"
        payload = smoke_payload()
        service = DisputeService(SqliteUnitOfWork(database))
        dispute_id = service.create_dispute(
            CreateDisputeCommand(
                transaction_ref=str(payload["transaction_ref"]),
                customer_upi=str(payload["customer_upi"]),
                reason=str(payload["reason"]),
                idempotency_key="phase42-local-smoke-001",
                correlation_id="phase42-local-smoke",
                owner_subject=principal.subject,
            )
        )
        dispute = service.get_dispute(dispute_id)
        assert dispute is not None
        assert dispute.customer_upi == "[masked:lo***@upi]"

        metrics_text = METRICS.openmetrics()
        assert "upi_app_factory_http_requests_total" in metrics_text


def main() -> int:
    run_smoke()
    print("Generated app local smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
