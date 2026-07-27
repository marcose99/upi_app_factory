from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = PROJECT_ROOT / "factory/templates/mock_dispute_app/generated_application"
EXPECTED_GENERATED_FILE_COUNT = 78


def test_wave_d_template_contains_runtime_observability_operator_contracts() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            TEMPLATE_ROOT / "app/runtime.py",
            TEMPLATE_ROOT / "app/interfaces/api/main.py",
            TEMPLATE_ROOT / "app/observability/metrics.py",
            TEMPLATE_ROOT / "app/observability/tracing.py",
            TEMPLATE_ROOT / "app/domain/domain_events.py",
            TEMPLATE_ROOT / "docs/reliability_slo_error_budget.md",
            TEMPLATE_ROOT / "docs/runtime_runbook.md",
        ]
    )

    for required in [
        "/startup",
        "/live",
        "/ready",
        "/drain",
        "runtime:drain",
        "runtime:diagnostics",
        "UPI_DISPUTE_SQLITE_PATH",
        "upi_app_factory_http_requests_total",
        "upi_app_factory_http_request_duration_seconds",
        "traceparent",
        "tracestate",
        "correlation_id",
        "Error budget benchmark",
        "Rollback",
        "production_capacity_claimed",
    ]:
        assert required in combined


def test_wave_d_validation_proves_fresh_generated_output() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase71_82_wave_d_runtime_observability.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
    assert payload["generated_file_count"] == EXPECTED_GENERATED_FILE_COUNT
    assert payload["production_capacity_claimed"] is False
    assert payload["live_provider_calls_allowed"] is False
    assert payload["real_payment_calls_allowed"] is False
    assert "generated_application/app/runtime.py" in payload["wave_d_generated_files"]
