from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATED_APP_ROOT = (
    PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
APP_SOURCE = GENERATED_APP_ROOT / "app"
if str(APP_SOURCE) not in sys.path:
    sys.path.insert(0, str(APP_SOURCE))

from upi_dispute_app.audit import AuditLogger  # noqa: E402
from upi_dispute_app.main import create_app  # noqa: E402
from upi_dispute_app.repository import DisputeRepository  # noqa: E402
from upi_dispute_app.settings import RuntimeSettings  # noqa: E402


async def _request(
    app: object,
    method: str,
    path: str,
    *,
    json_payload: dict[str, object] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://local-generated-upi-dispute-app",
    ) as client:
        return await client.request(method, path, json=json_payload)


def request(
    app: object,
    method: str,
    path: str,
    *,
    json_payload: dict[str, object] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, json_payload=json_payload))


def test_create_app_preserves_legacy_harness_backcompat_for_concrete_di_runtime(tmp_path: Path) -> None:
    settings = RuntimeSettings(
        app_env="test",
        data_dir=tmp_path,
        sqlite_path=tmp_path / "disputes.sqlite3",
        audit_log_path=tmp_path / "audit_events.jsonl",
    )
    app = create_app(
        repository=DisputeRepository(settings.sqlite_path),
        audit_logger=AuditLogger(settings.audit_log_path),
        settings=settings,
    )

    assert getattr(app.state, "compatibility_mode") == "explicit_legacy_dependency_injection_harness"
    assert getattr(app.state, "database_path") == settings.sqlite_path

    payload = {
        "client_request_id": "phase41-client-compat",
        "dispute_type": "duplicate_debit",
        "transaction_reference": "PHASE41TXNCOMPAT",
        "customer_upi_id": "localcustomer@upi",
        "amount_paise": 12000,
        "description": "Local simulated duplicate debit dispute for compatibility validation.",
        "evidence": {"source": "compatibility_test"},
    }
    created = request(app, "POST", "/disputes", json_payload=payload)
    runtime_health = request(app, "GET", "/runtime/health")

    assert created.status_code == 201, created.text
    assert runtime_health.status_code == 200
    assert runtime_health.json()["runtime_hardening"]["certification_boundary"] == (
        "certification_ready_not_certified"
    )
