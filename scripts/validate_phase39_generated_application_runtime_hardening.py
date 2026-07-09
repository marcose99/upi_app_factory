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

from upi_dispute_app.audit import AuditLogger  # noqa: E402
from upi_dispute_app.main import create_app  # noqa: E402
from upi_dispute_app.repository import DisputeRepository  # noqa: E402
from upi_dispute_app.settings import RuntimeConfigurationError, RuntimeSettings  # noqa: E402


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
        "/runtime/health",
        "/runtime/metrics",
        "validation_error",
        "structured_errors",
        "UPI_DISPUTE_ENABLE_LIVE_PROVIDER_CALLS=false",
        "UPI_DISPUTE_ALLOW_REAL_SECRETS=false",
        "UPI_DISPUTE_EXTERNAL_ECOSYSTEM_MODE=mock",
    ]:
        if marker not in source_text:
            errors.append(f"Phase 39 runtime source missing marker: {marker}")

    for term in FORBIDDEN_SOURCE_TERMS:
        if term in source_text:
            errors.append(f"Phase 39 runtime source includes forbidden term: {term}")
    external_urls = re.findall(r"https?://[^\"]+", source_text)
    if external_urls:
        errors.append(f"Phase 39 runtime source includes external URL dependencies: {external_urls}")


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


def make_app(tmpdir: Path) -> Any:
    settings = RuntimeSettings(
        app_env="test",
        data_dir=tmpdir,
        sqlite_path=tmpdir / "disputes.sqlite3",
        audit_log_path=tmpdir / "audit_events.jsonl",
    )
    return create_app(
        repository=DisputeRepository(settings.sqlite_path),
        audit_logger=AuditLogger(settings.audit_log_path),
        settings=settings,
    )


def validate_runtime_behavior(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as tmp:
        tmpdir = Path(tmp)
        app = make_app(tmpdir)

        health = request(app, "GET", "/runtime/health")
        if health.status_code != 200:
            errors.append(f"Runtime health endpoint failed: {health.status_code}")
        else:
            payload = cast(dict[str, Any], health.json())
            report = cast(dict[str, Any], payload.get("runtime_hardening", {}))
            if report.get("certification_boundary") != "certification_ready_not_certified":
                errors.append("Runtime health changed certification boundary")
            if report.get("live_provider_calls_allowed") is not False:
                errors.append("Runtime health allows live provider calls")

        invalid = request(
            app,
            "POST",
            "/disputes",
            json_payload={**valid_payload(), "client_request_id": "bad request id"},
        )
        if invalid.status_code != 422:
            errors.append(f"Invalid request was not rejected: {invalid.status_code}")
        elif invalid.json().get("error", {}).get("code") != "validation_error":
            errors.append("Invalid request did not return structured validation error")

        created = request(app, "POST", "/disputes", json_payload=valid_payload())
        replayed = request(app, "POST", "/disputes", json_payload=valid_payload())
        if created.status_code != 201:
            errors.append(f"Create dispute failed: {created.status_code} {created.text}")
        if replayed.status_code != 200:
            errors.append(f"Idempotent replay failed: {replayed.status_code} {replayed.text}")
        elif created.json()["dispute"]["dispute_id"] != replayed.json()["dispute"]["dispute_id"]:
            errors.append("Idempotent replay did not return the original dispute")

        metrics = request(app, "GET", "/runtime/metrics")
        if metrics.status_code != 200:
            errors.append(f"Runtime metrics endpoint failed: {metrics.status_code}")
        else:
            counters = cast(dict[str, Any], metrics.json().get("metrics", {}))
            if counters.get("disputes_created") != 1:
                errors.append("Runtime metrics did not count dispute creation")
            if counters.get("idempotency_replays") != 1:
                errors.append("Runtime metrics did not count idempotency replay")
            if counters.get("validation_failures") != 1:
                errors.append("Runtime metrics did not count validation failure")

        if not (tmpdir / "audit_events.jsonl").exists():
            errors.append("Audit log was not created in local runtime data dir")


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
