#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import re
import sys
import tempfile
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

from upi_dispute_app.main import create_app  # noqa: E402
from upi_dispute_app.settings import RuntimeConfigurationError, RuntimeSettings  # noqa: E402
from generated_application.app.security.identity import issue_local_test_token  # noqa: E402


APP_ID = "upi_dispute_resolution"
PHASE = "phase39_generated_application_runtime_hardening"
POLICY_PATH = Path("policies/phase39_generated_application_runtime_hardening_policy.json")
PROMPT_PATH = Path("prompts/phase39/generated_application_runtime_hardening_prompt.md")
TEST_PATH = Path("tests/test_phase39_generated_application_runtime_hardening.py")
VALIDATOR_PATH = Path("scripts/validate_phase39_generated_application_runtime_hardening.py")
GENERATED_ROOT = Path("workspace/factory_generated") / APP_ID / "generated_application"
ARTIFACT_DIR = Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase39"

RUNTIME_SOURCE_PATHS = [
    GENERATED_ROOT / ".env.example",
    GENERATED_ROOT / "app/upi_dispute_app/settings.py",
    GENERATED_ROOT / "app/upi_dispute_app/runtime.py",
    GENERATED_ROOT / "app/upi_dispute_app/main.py",
    GENERATED_ROOT / "app/upi_dispute_app/repository.py",
    GENERATED_ROOT / "app/upi_dispute_app/models.py",
    GENERATED_ROOT / "app/upi_dispute_app/audit.py",
    GENERATED_ROOT / "app/interfaces/api/main.py",
    GENERATED_ROOT / "app/interfaces/api/error_handlers.py",
    GENERATED_ROOT / "app/security/identity.py",
]

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    TEST_PATH,
    VALIDATOR_PATH,
    *RUNTIME_SOURCE_PATHS,
    ARTIFACT_DIR / "runtime_hardening_manifest.json",
    ARTIFACT_DIR / "runtime_hardening_gate.json",
    ARTIFACT_DIR / "runtime_hardening_audit.json",
    ARTIFACT_DIR / "runtime_configuration_contract.json",
    ARTIFACT_DIR / "local_runtime_observability_contract.json",
]

REQUIRED_BOUNDARY_FIELDS = [
    "official_certification_claimed",
    "official_certification_granted",
    "production_readiness_claimed",
    "live_provider_calls_allowed",
    "real_secrets_allowed",
    "deployment_allowed",
    "merge_allowed",
    "tag_allowed",
    "push_allowed",
]

FORBIDDEN_SOURCE_TERMS = [
    "requests.",
    "urllib.request",
    "boto3",
    "google.cloud",
    "BEGIN PRIVATE KEY",
    "client_secret",
    "api_key",
    "git push",
    "git tag",
    "git merge",
    "/deploy",
]


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, Any], value)


def validate_boundary_artifact(
    artifact: dict[str, Any],
    errors: list[str],
    context: str,
) -> None:
    if artifact.get("certification_boundary") != "certification_ready_not_certified":
        errors.append(f"{context} changed certification boundary")
    for field in REQUIRED_BOUNDARY_FIELDS:
        if artifact.get(field) is not False:
            errors.append(f"{context} has invalid boundary field: {field}")
    if artifact.get("external_ecosystem_integrations") != "mocked_or_simulated_only":
        errors.append(f"{context} does not keep ecosystem integrations mocked")
    if artifact.get("local_readiness_scope") != "local_generated_application_runtime_only":
        errors.append(f"{context} does not scope readiness to local runtime only")


def validate_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not (PROJECT_ROOT / path).exists():
            errors.append(f"Missing required Phase 39 file: {path}")


def validate_static_artifacts(errors: list[str]) -> None:
    policy = load_json(PROJECT_ROOT / POLICY_PATH)
    manifest = load_json(PROJECT_ROOT / ARTIFACT_DIR / "runtime_hardening_manifest.json")
    gate = load_json(PROJECT_ROOT / ARTIFACT_DIR / "runtime_hardening_gate.json")
    audit = load_json(PROJECT_ROOT / ARTIFACT_DIR / "runtime_hardening_audit.json")
    config_contract = load_json(PROJECT_ROOT / ARTIFACT_DIR / "runtime_configuration_contract.json")
    observability_contract = load_json(
        PROJECT_ROOT / ARTIFACT_DIR / "local_runtime_observability_contract.json"
    )
    prompt = (PROJECT_ROOT / PROMPT_PATH).read_text(encoding="utf-8")
    source_text = "\n".join(
        (PROJECT_ROOT / path).read_text(encoding="utf-8") for path in RUNTIME_SOURCE_PATHS
    )

    if policy.get("mandatory_gate") != "PHASE39-GENERATED-APPLICATION-RUNTIME-HARDENING-GATE":
        errors.append("Phase 39 policy missing mandatory gate")
    if policy.get("configuration_example") != str(GENERATED_ROOT / ".env.example"):
        errors.append("Phase 39 policy does not identify .env.example")
    if policy.get("validation_entrypoint") != str(VALIDATOR_PATH):
        errors.append("Phase 39 policy does not identify validator")

    for artifact, name in [
        (policy, "policy"),
        (manifest, "manifest"),
        (gate, "gate"),
        (audit, "audit"),
        (config_contract, "configuration contract"),
        (observability_contract, "observability contract"),
    ]:
        validate_boundary_artifact(artifact, errors, f"Phase 39 {name}")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        include = "{{ include: " + contract_path + " }}"
        if include not in prompt:
            errors.append(f"Phase 39 prompt does not inherit contract: {contract_path}")

    for phrase in [
        "certification_ready_not_certified",
        "Do not fake success",
        "mocked or simulated",
        "No live provider calls",
        "No real credentials",
        "No deployment, merge, tag, or push",
        "Local-readiness only",
    ]:
        if phrase not in prompt:
            errors.append(f"Phase 39 prompt missing required phrase: {phrase}")

    for marker in [
        "RuntimeSettings",
        "RuntimeConfigurationError",
        "build_runtime_state",
        "payload_fingerprint",
        "get_request_fingerprint",
        "get_by_client_request_id",
        "Legacy import facade that always returns the hardened generated API",
        "generated_application.app.interfaces.api.main",
        "application/problem+json",
        "signed local bearer token",
        "issue_local_test_token",
        "/health",
        "/metrics",
        "UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS=false",
        "UPI_DISPUTE_ALLOW_REAL_SECRETS=false",
        "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE=mock",
    ]:
        if marker not in source_text:
            errors.append(f"Phase 39 runtime source missing marker: {marker}")

    for term in FORBIDDEN_SOURCE_TERMS:
        if term in source_text:
            errors.append(f"Phase 39 runtime source includes forbidden term: {term}")
    external_urls = [
        url
        for url in re.findall(r"https?://[^\"]+", source_text)
        if ".example.invalid" not in url and "upi-app-factory.local" not in url
    ]
    if external_urls:
        errors.append(f"Phase 39 runtime source includes external URL dependencies: {external_urls}")


def valid_payload() -> dict[str, object]:
    return {
        "transaction_ref": "PHASE39-TXN-001",
        "customer_upi": "customername@upi",
        "reason": "Customer reports duplicate debit for a local simulated transaction.",
    }


async def _request(
    app: Any,
    method: str,
    path: str,
    *,
    json_payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://local-generated-upi-dispute-app",
    ) as client:
        return await client.request(method, path, json=json_payload, headers=headers)


def request(
    app: Any,
    method: str,
    path: str,
    *,
    json_payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, json_payload=json_payload, headers=headers))


def bearer_headers(idempotency_key: str = "phase39-idempotency-001") -> dict[str, str]:
    token = issue_local_test_token(
        subject="phase39-client",
        scopes=("dispute:create", "dispute:read", "dispute:read:any"),
    )
    return {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": idempotency_key,
        "X-Correlation-Id": "phase39-correlation",
    }


def make_app(tmpdir: Path) -> Any:
    settings = RuntimeSettings(
        app_env="test",
        data_dir=tmpdir,
        sqlite_path=tmpdir / "disputes.sqlite3",
        audit_log_path=tmpdir / "audit_events.jsonl",
    )
    return create_app(
        database_path=settings.sqlite_path,
        repository=object(),
        audit_logger=object(),
        settings=settings,
    )


def validate_runtime_behavior(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as tmp:
        tmpdir = Path(tmp)
        app = make_app(tmpdir)

        health = request(app, "GET", "/health")
        if health.status_code != 200:
            errors.append(f"Runtime health endpoint failed: {health.status_code}")
        else:
            payload = cast(dict[str, Any], health.json())
            if payload.get("status") != "ok":
                errors.append("Runtime health changed hardened API status contract")
            if health.headers.get("x-content-type-options") != "nosniff":
                errors.append("Runtime health did not include hardened security headers")

        unauthenticated = request(app, "POST", "/disputes", json_payload=valid_payload())
        if unauthenticated.status_code != 401:
            errors.append(
                "Legacy dependency-injection facade allowed unauthenticated dispute creation"
            )

        invalid = request(
            app,
            "POST",
            "/disputes",
            json_payload={**valid_payload(), "unexpected": "rejected"},
            headers=bearer_headers("phase39-validation"),
        )
        if invalid.status_code != 422:
            errors.append(f"Invalid request was not rejected: {invalid.status_code}")
        elif invalid.json().get("code") != "RequestValidationError":
            errors.append("Invalid request did not return RFC 9457 validation problem")

        headers = bearer_headers()
        created = request(app, "POST", "/disputes", json_payload=valid_payload(), headers=headers)
        replayed = request(app, "POST", "/disputes", json_payload=valid_payload(), headers=headers)
        if created.status_code != 201:
            errors.append(f"Create dispute failed: {created.status_code} {created.text}")
        if replayed.status_code != 201:
            errors.append(f"Idempotent replay failed: {replayed.status_code} {replayed.text}")
        elif created.json()["dispute_id"] != replayed.json()["dispute_id"]:
            errors.append("Idempotent replay did not return the original dispute")

        metrics = request(app, "GET", "/metrics")
        if metrics.status_code != 200:
            errors.append(f"Runtime metrics endpoint failed: {metrics.status_code}")
        elif not metrics.headers.get("content-type", "").startswith("application/openmetrics-text"):
            errors.append("Runtime metrics did not use OpenMetrics text output")

        legacy_runtime = request(app, "GET", "/runtime/health")
        if legacy_runtime.status_code != 404:
            errors.append("Legacy runtime health route is still exposed")


def validate_fail_closed_settings(errors: list[str]) -> None:
    cases = [
        RuntimeSettings(enable_live_provider_calls=True),
        RuntimeSettings(allow_real_secrets=True),
        RuntimeSettings(external_ecosystem_mode="live"),
        RuntimeSettings(sqlite_path=Path("../outside.sqlite3")),
    ]
    for settings in cases:
        try:
            settings.validate()
        except RuntimeConfigurationError:
            continue
        errors.append(f"Runtime settings did not fail closed: {settings}")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    if not errors:
        validate_static_artifacts(errors)
        validate_runtime_behavior(errors)
        validate_fail_closed_settings(errors)

    if errors:
        print("Phase 39 generated application runtime hardening validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Phase 39 generated application runtime hardening validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
