from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.application.reconciliation_resolution import (
    NON_EXECUTION_NOTICE,
    Observation,
    ReconciliationResolutionService,
    ResolutionProposal,
)
from generated_application.app.domain.exceptions import OptimisticConcurrencyError


def observations() -> list[Observation]:
    return [
        Observation("Switch", "SUCCESS", 1250, "inr", "payer", "accepted", "switch-01"),
        Observation("Core", "PENDING", 1200, "INR", "payee", "held", "core-01"),
    ]


def proposal(
    service: ReconciliationResolutionService, version: int = 1
) -> ResolutionProposal:
    return service.create_proposal(
        case_id="CASE-01",
        expected_version=version,
        recommended_actions=["contact customer", "manual evidence review"],
        prohibited_actions=["refund", "payment", "reversal", "adjustment"],
        rationale="Conflicting mock observations require human review.",
        customer_message="We are reviewing the reported observations.",
        risk="Do not infer settlement from inconsistent sources.",
        dependencies=["control owner review", "source evidence"],
    )


def test_observation_reconciliation_is_deterministic_and_non_financial(tmp_path: Path) -> None:
    service = ReconciliationResolutionService(tmp_path / "reconciliation.sqlite3")
    first = service.reconcile("CASE-01", observations())
    second = service.reconcile("CASE-01", reversed(observations()))

    assert first.result_id == second.result_id
    assert first.version == second.version == 1
    assert second.equivalent is True
    assert set(first.conflicts) == {"status", "value", "product_leg", "control_state"}
    assert {item.evidence_reference for item in first.observations} == {"switch-01", "core-01"}
    assert first.ledger_kind == "observation_only"
    assert first.financial_ledger is first.executes_remediation is False
    assert first.live_provider_calls_allowed is False
    assert "not a financial/accounting ledger" in NON_EXECUTION_NOTICE


def test_complete_version_bound_proposal_event_review_and_stale_retry(tmp_path: Path) -> None:
    service = ReconciliationResolutionService(tmp_path / "proposal.sqlite3")
    service.reconcile("CASE-01", observations())
    created = proposal(service)

    assert created.recommended_actions == ("contact customer", "manual evidence review")
    assert created.prohibited_actions == ("adjustment", "payment", "refund", "reversal")
    assert created.rationale and created.customer_message and created.risk and created.dependencies
    assert created.bound_version == 1 and created.review_state == "pending_review"
    assert created.event_type == "reconciliation.resolution_proposed" and created.event_id
    assert created.executes_remediation is created.live_provider_calls_allowed is False

    reviewed = service.review_proposal(
        proposal_id=created.proposal_id, expected_version=1,
        state="reviewed", reviewer="local-reviewer", note="evidence checked",
    )
    assert reviewed.review_state == "reviewed"
    assert reviewed.proposal_id == created.proposal_id

    changed = observations()
    changed[0] = Observation("Switch", "FAILED", 1250, "INR", "payer", "rejected", "switch-02")
    assert service.reconcile("CASE-01", changed).version == 2
    with pytest.raises(OptimisticConcurrencyError, match="stale expected version"):
        proposal(service, version=1)
    with pytest.raises(OptimisticConcurrencyError, match="latest/current"):
        service.review_proposal(
            proposal_id=created.proposal_id, expected_version=2,
            state="approved", reviewer="local-reviewer", note="retry",
        )


def test_authenticated_api_contract_is_non_executing_and_local_only(
    tmp_path: Path,
) -> None:
    import_root = Path(__file__).resolve().parents[4]
    database = tmp_path / "api.sqlite3"
    probe = r"""
import sys
from pathlib import Path

import asyncio
import httpx as local_http_client

import_root = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(import_root))

from generated_application.app.interfaces.api import main
from generated_application.app.runtime import RuntimeLifecycle
from generated_application.app.security.identity import issue_local_test_token

main.DATABASE_PATH = database
main.RUNTIME = RuntimeLifecycle(database)
main.app.openapi_schema = None

token = issue_local_test_token(subject="reviewer", scopes=["dispute:read:any"])
headers = {"Authorization": f"Bearer {token}"}
payload = {
    "observations": [
        {
            "source": "Switch",
            "status": "SUCCESS",
            "value_minor": 1250,
            "currency": "inr",
            "product_leg": "payer",
            "control_state": "accepted",
            "evidence_reference": "switch-01",
        },
        {
            "source": "Core",
            "status": "PENDING",
            "value_minor": 1200,
            "currency": "INR",
            "product_leg": "payee",
            "control_state": "held",
            "evidence_reference": "core-01",
        },
    ]
}

async def exercise_api():
  main.RUNTIME.startup()
  try:
    transport = local_http_client.ASGITransport(app=main.app)
    async with local_http_client.AsyncClient(transport=transport, base_url="http://local") as client:
      assert (await client.post("/reconciliation/CASE-API", json=payload)).status_code == 401
      denied_token = issue_local_test_token(subject="reader", scopes=["dispute:read"])
      assert (await client.post(
          "/reconciliation/CASE-API",
          json=payload,
          headers={"Authorization": f"Bearer {denied_token}"},
      )).status_code == 403
      reconciled = await client.post(
          "/reconciliation/CASE-API", json=payload, headers=headers
      )
      assert reconciled.status_code == 200
      body = reconciled.json()
      assert body["financial_ledger"] is body["executes_remediation"] is False
      assert body["live_provider_calls_allowed"] is False

      created = await client.post(
          "/reconciliation/CASE-API/proposals",
          headers=headers,
          json={
              "expected_version": 1,
              "recommended_actions": ["manual review"],
              "prohibited_actions": ["payment", "refund"],
              "rationale": "local evidence conflict",
              "customer_message": "We are reviewing this case.",
              "risk": "No automated remediation.",
              "dependencies": ["reviewer"],
          },
      )
      assert created.status_code == 201
      assert created.json()["executes_remediation"] is False
      capabilities = (await client.get("/capabilities")).json()
      assert "reconciliation_reviewed_resolution" in capabilities["capabilities"]
  finally:
    main.RUNTIME.shutdown()

asyncio.run(exercise_api())

schema = main.app.openapi()
operation = schema["paths"]["/reconciliation/{case_id}/proposals"]["post"]
assert operation["x-local-boundary"]["live_provider_calls_allowed"] is False
assert "non-executing" in operation["summary"]
print("API_ISOLATION_PROOF=PASS")
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(import_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", probe, str(import_root), str(database)],
        cwd=import_root,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "API_ISOLATION_PROOF=PASS" in result.stdout
