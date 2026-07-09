from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_APP_ROOT = (
    PROJECT_ROOT / "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
APP_SOURCE = GENERATED_APP_ROOT / "app"
if str(APP_SOURCE) not in sys.path:
    sys.path.insert(0, str(APP_SOURCE))

from upi_dispute_app.audit import AuditLogger  # noqa: E402
from upi_dispute_app.main import create_app  # noqa: E402
from upi_dispute_app.repository import DisputeRepository  # noqa: E402
from upi_dispute_app.settings import RuntimeConfigurationError, RuntimeSettings  # noqa: E402

POLICY_PATH = PROJECT_ROOT / "policies/phase39_generated_application_runtime_hardening_policy.json"
PROMPT_PATH = PROJECT_ROOT / "prompts/phase39/generated_application_runtime_hardening_prompt.md"
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase39"
)
ENV_EXAMPLE_PATH = GENERATED_APP_ROOT / ".env.example"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def valid_payload() -> dict[str, object]:
    return {
        "client_request_id": "phase39-req-001",
        "dispute_type": "duplicate_debit",
        "transaction_reference": "PHASE39-TXN-001",
        "customer_upi_id": "customername@upi",
        "amount_paise": 50000,
        "description": "Customer reports duplicate debit for a local simulated transaction.",
        "evidence": {"customer_statement": "Duplicate debit visible in app screenshot."},
    }


def make_app(tmp_path: Path) -> Any:
    settings = RuntimeSettings(
        app_env="test",
        data_dir=tmp_path,
        sqlite_path=tmp_path / "disputes.sqlite3",
        audit_log_path=tmp_path / "audit_events.jsonl",
    )
    return create_app(
        repository=DisputeRepository(settings.sqlite_path),
        audit_logger=AuditLogger(settings.audit_log_path),
        settings=settings,
    )


async def _request(
    app: Any,
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
    app: Any,
    method: str,
    path: str,
    *,
    json_payload: dict[str, object] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, json_payload=json_payload))


def test_phase39_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase39_generated_application_runtime_hardening.py"],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_policy_prompt_and_lifecycle_artifacts_keep_boundaries_closed() -> None:
    artifacts = [
        load_json(POLICY_PATH),
        load_json(ARTIFACT_DIR / "runtime_hardening_manifest.json"),
        load_json(ARTIFACT_DIR / "runtime_hardening_gate.json"),
        load_json(ARTIFACT_DIR / "runtime_hardening_audit.json"),
        load_json(ARTIFACT_DIR / "runtime_configuration_contract.json"),
        load_json(ARTIFACT_DIR / "local_runtime_observability_contract.json"),
    ]
    for artifact in artifacts:
        assert artifact["certification_boundary"] == "certification_ready_not_certified"
        assert artifact["official_certification_claimed"] is False
        assert artifact["official_certification_granted"] is False
        assert artifact["production_readiness_claimed"] is False
        assert artifact["live_provider_calls_allowed"] is False
        assert artifact["real_secrets_allowed"] is False
        assert artifact["deployment_allowed"] is False
        assert artifact["merge_allowed"] is False
        assert artifact["tag_allowed"] is False
        assert artifact["push_allowed"] is False
        assert artifact["external_ecosystem_integrations"] == "mocked_or_simulated_only"

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    assert "{{ include: prompts/_contracts/agentic_ai_best_practice_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/generated_application_quality_contract.md }}" in prompt
    assert "{{ include: prompts/_contracts/llm_call_metrics_and_expense_contract.md }}" in prompt


def test_env_example_uses_mock_only_placeholders_without_real_secrets() -> None:
    text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    assert "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE=mock" in text
    assert "UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS=false" in text
    assert "UPI_DISPUTE_ALLOW_REAL_SECRETS=false" in text
    assert "BEGIN PRIVATE KEY" not in text
    assert "client_secret" not in text
    assert "api_key" not in text


def test_runtime_settings_fail_closed_for_live_or_unsafe_configuration() -> None:
    invalid_settings = [
        RuntimeSettings(enable_live_provider_calls=True),
        RuntimeSettings(allow_real_secrets=True),
        RuntimeSettings(external_ecosystem_mode="live"),
        RuntimeSettings(app_env="production"),
        RuntimeSettings(sqlite_path=Path("../outside.sqlite3")),
    ]
    for settings in invalid_settings:
        try:
            settings.validate()
        except RuntimeConfigurationError:
            continue
        raise AssertionError(f"Runtime settings unexpectedly passed: {settings}")


def test_runtime_health_and_metrics_expose_local_observability(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    health = request(app, "GET", "/runtime/health")
    assert health.status_code == 200
    report = health.json()["runtime_hardening"]
    assert report["status"] == "passed"
    assert report["certification_boundary"] == "certification_ready_not_certified"
    assert report["external_ecosystem_mode"] == "mock"
    assert report["live_provider_calls_allowed"] is False

    metrics = request(app, "GET", "/runtime/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["observability_scope"] == "local_structured_runtime_counters_only"
    assert metrics.json()["live_provider_calls_allowed"] is False


def test_structured_validation_error_and_idempotent_replay(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    invalid = request(
        app,
        "POST",
        "/disputes",
        json_payload={**valid_payload(), "client_request_id": "bad request id"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"

    created = request(app, "POST", "/disputes", json_payload=valid_payload())
    replayed = request(app, "POST", "/disputes", json_payload=valid_payload())
    assert created.status_code == 201, created.json()
    assert replayed.status_code == 200, replayed.json()
    assert created.json()["dispute"]["dispute_id"] == replayed.json()["dispute"]["dispute_id"]

    metrics = request(app, "GET", "/runtime/metrics").json()["metrics"]
    assert metrics["validation_failures"] == 1
    assert metrics["disputes_created"] == 1
    assert metrics["idempotency_replays"] == 1


def test_audit_log_stays_local_and_records_boundary_metadata(tmp_path: Path) -> None:
    app = make_app(tmp_path)
    response = request(app, "POST", "/disputes", json_payload=valid_payload())
    assert response.status_code == 201
    audit_path = tmp_path / "audit_events.jsonl"
    entries = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert entries
    assert entries[0]["details"]["certification_boundary"] == "certification_ready_not_certified"
    assert entries[0]["details"]["external_ecosystem_integrations"] == "mocked_or_simulated_only"
