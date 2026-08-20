from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = PROJECT_ROOT / "factory/templates/mock_dispute_app/generated_application"
TEMPLATE_MANIFEST_PATH = (
    PROJECT_ROOT / "factory/templates/mock_dispute_app/template_manifest.v1.json"
)
EXPECTED_GENERATED_FILE_COUNT = len(
    json.loads(TEMPLATE_MANIFEST_PATH.read_text(encoding="utf-8"))["template_files"]
)


REQUIRED_WAVE_C_GENERATED_FILES = {
    "generated_application/app/security/identity.py",
    "generated_application/app/infrastructure/external_adapters.py",
    "generated_application/app/tests/contract/test_api_identity_adapter_contract.py",
    "generated_application/app/tests/security/test_authorization_contract.py",
}


def test_wave_c_template_sources_are_parseable_and_contractual() -> None:
    for path in [
        TEMPLATE_ROOT / "app/interfaces/api/main.py",
        TEMPLATE_ROOT / "app/interfaces/api/error_handlers.py",
        TEMPLATE_ROOT / "app/security/identity.py",
        TEMPLATE_ROOT / "app/infrastructure/external_adapters.py",
    ]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            TEMPLATE_ROOT / "app/interfaces/api/main.py",
            TEMPLATE_ROOT / "app/interfaces/api/error_handlers.py",
            TEMPLATE_ROOT / "app/security/identity.py",
            TEMPLATE_ROOT / "app/infrastructure/external_adapters.py",
        ]
    )
    for required in [
        "application/problem+json",
        "RFC 9457 compatible",
        "correlation_id",
        "LocalTestPrincipal",
        "OAuth2AuthorizationCodePkce",
        "listDisputes",
        "getDispute",
        "beginDrain",
        "runtimeDiagnostics",
        "x-deterministic-examples",
        "runtime:drain",
        "runtime:diagnostics",
        "RFC 9700 aligned",
        "issue_local_test_token",
        "verify_local_test_token",
        "LOCAL_ISSUER",
        "UPI_APP_FACTORY_ALLOW_HEADER_PRINCIPAL",
        "masked_customer_upi",
        "require_object_access",
        "x-content-type-options",
        "content-security-policy",
        "service.list_disputes",
        "timeout_ms",
        "retry_budget",
        "jitter_ms",
        "circuit_breaker_failure_threshold",
        "AdapterCircuitOpenError",
        "AdapterBackpressureError",
        "AdapterPayloadTooLargeError",
        "AdapterRateLimitError",
        "DeterministicResilientAdapter",
        "rate_limit_per_minute",
        "_guard_payload",
        "_guard_rate_limit",
        "degraded_mode",
        "live_provider_calls_allowed",
    ]:
        assert required in combined


def test_wave_c_generator_emits_fresh_api_identity_adapter_files() -> None:
    with tempfile.TemporaryDirectory(prefix="phase71_82_wave_c_") as workspace:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "factory.generators.mock_dispute_app_generator",
                "--run-id",
                "phase71_82_wave_c_api_identity_adapters_test",
                "--workspace-root",
                workspace,
                "--clean",
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["generated_file_count"] == EXPECTED_GENERATED_FILE_COUNT
        generated_files = {
            item["relative_path"] for item in payload["generated_files"]
        }
        assert REQUIRED_WAVE_C_GENERATED_FILES.issubset(generated_files)

        manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
        assert manifest["live_provider_calls_allowed"] is False
        assert manifest["real_payment_calls_allowed"] is False
        assert manifest["official_certification_claimed"] is False
