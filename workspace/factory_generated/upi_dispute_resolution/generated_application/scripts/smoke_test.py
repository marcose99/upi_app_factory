#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import asyncio
from pathlib import Path

import httpx


APP_ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = APP_ROOT / "app"
if str(APP_SOURCE) not in sys.path:
    sys.path.insert(0, str(APP_SOURCE))

from upi_dispute_app.audit import AuditLogger  # noqa: E402
from upi_dispute_app.main import create_app  # noqa: E402
from upi_dispute_app.repository import DisputeRepository  # noqa: E402


def smoke_payload() -> dict[str, object]:
    return {
        "client_request_id": "phase42-local-smoke-001",
        "dispute_type": "duplicate_debit",
        "transaction_reference": "PHASE42LOCAL001",
        "customer_upi_id": "localreviewer@upi",
        "amount_paise": 4200,
        "description": "Reviewer local smoke test for a simulated duplicate debit dispute.",
        "evidence": {"source": "phase42_local_smoke"},
    }


async def run_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="phase42-local-smoke-") as raw_tmp:
        tmp_path = Path(raw_tmp)
        app = create_app(
            repository=DisputeRepository(),
            audit_logger=AuditLogger(tmp_path / "audit_events.jsonl"),
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://local-generated-upi-dispute-app",
        ) as client:
            health = await client.get("/health")
            assert health.status_code == 200, health.text
            assert health.json()["boundary"] == "local_app_with_mock_external_ecosystem"

            created = await client.post("/disputes", json=smoke_payload())
            assert created.status_code == 201, created.text
            body = created.json()
            dispute_id = body["dispute"]["dispute_id"]
            assert "mock/simulated" in body["boundary_notice"]

            fetched = await client.get(f"/disputes/{dispute_id}")
            assert fetched.status_code == 200, fetched.text

            checked = await client.post(f"/disputes/{dispute_id}/actions/mock-ecosystem-check")
            assert checked.status_code == 200, checked.text
            checked_body = checked.json()
            assert all(source.startswith("mock_") for source in checked_body["mock_sources_checked"])

            metrics = await client.get("/runtime/metrics")
            assert metrics.status_code == 200, metrics.text
            assert metrics.json()["live_provider_calls_allowed"] is False


def main() -> int:
    asyncio.run(run_smoke())
    print("Generated app local smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
