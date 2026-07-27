#!/usr/bin/env python3
from __future__ import annotations

import atexit
import hashlib
import json
import sys
import tempfile
from time import perf_counter
from pathlib import Path
from typing import Any

_STARTUP_PYCACHE = tempfile.TemporaryDirectory(
    prefix="phase71_82_wave_d_startup_pycache_"
)
sys.pycache_prefix = _STARTUP_PYCACHE.name
atexit.register(_STARTUP_PYCACHE.cleanup)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.generators.mock_dispute_app_generator import generate  # noqa: E402


RUN_ID = "phase71_82_wave_d_runtime_observability"
TEMPLATE_GENERATED_ROOT = (
    PROJECT_ROOT / "factory/templates/mock_dispute_app/generated_application"
)
REQUIRED_WAVE_D_FILES = {
    "generated_application/app/runtime.py",
    "generated_application/app/observability/metrics.py",
    "generated_application/app/observability/tracing.py",
    "generated_application/app/observability/logging.py",
    "generated_application/docs/reliability_slo_error_budget.md",
    "generated_application/docs/runtime_runbook.md",
    "generated_application/docs/failure_mode_evidence.md",
    "generated_application/app/tests/resilience/test_runtime_lifecycle.py",
    "generated_application/app/tests/contract/test_observability_contract.py",
    "generated_application/app/tests/performance/test_local_performance_smoke.py",
}
GENERATED_TEST_TARGETS = [
    "generated_application/app/tests/resilience/test_runtime_lifecycle.py",
    "generated_application/app/tests/contract/test_observability_contract.py",
    "generated_application/app/tests/performance/test_local_performance_smoke.py",
]


def bytecode_artifacts(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    artifacts: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}:
            relative_path = path.relative_to(root).as_posix()
            if path.is_file():
                artifacts[relative_path] = (
                    f"file:{path.stat().st_size}:"
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}"
                )
            else:
                artifacts[relative_path] = "dir"
    return artifacts


def run_generated_wave_d_checks(generated_root: Path) -> list[str]:
    previous_path = list(sys.path)
    previous_prefix = sys.pycache_prefix
    checks: list[str] = []

    with tempfile.TemporaryDirectory(prefix="phase71_82_wave_d_pycache_") as cache_dir:
        sys.pycache_prefix = cache_dir
        sys.path.insert(0, str(generated_root))
        try:
            from generated_application.app.domain.domain_events import dispute_event
            from generated_application.app.domain.domain_events import portable_event_envelope
            from generated_application.app.application.commands import CreateDisputeCommand
            from generated_application.app.application.services import DisputeService
            from generated_application.app.infrastructure.persistence.sqlite_unit_of_work import (
                SqliteUnitOfWork,
            )
            from generated_application.app.observability.logging import safe_fields
            from generated_application.app.observability.metrics import Metrics, percentile
            from generated_application.app.observability.tracing import (
                current_traceparent,
                trace_context_from_headers,
                use_trace_context,
            )
            from generated_application.app.runtime import RuntimeLifecycle

            with tempfile.TemporaryDirectory(prefix="phase71_82_wave_d_db_") as db_dir:
                database = Path(db_dir) / "runtime.sqlite3"
                runtime = RuntimeLifecycle(database)
                assert runtime.startup_status()[0] == 503
                runtime.startup()
                assert runtime.startup_status()[0] == 200
                assert runtime.liveness()[0] == 200
                assert runtime.readiness()[0] == 200
                runtime.begin_drain()
                assert runtime.liveness()[0] == 200
                assert runtime.readiness()[0] == 503
                runtime.shutdown()
                assert runtime.liveness()[0] == 503
                restarted = RuntimeLifecycle(database)
                restarted.startup()
                assert restarted.readiness()[0] == 200
            checks.append("startup_liveness_readiness_drain_shutdown_restart")

            metrics = Metrics()
            metrics.record_http(
                method="PATCH",
                route="/customer/123",
                outcome="unexpected",
                duration_seconds=0.2,
            )
            output = metrics.openmetrics()
            assert "upi_app_factory_http_requests_total" in output
            assert "upi_app_factory_http_request_duration_seconds_bucket" in output
            assert 'method="OTHER"' in output
            assert 'route="other"' in output
            assert 'outcome="error"' in output
            checks.append("openmetrics_units_suffixes_bounded_labels")

            context = trace_context_from_headers(
                traceparent="00-11111111111111111111111111111111-2222222222222222-01",
                tracestate="vendor=value",
                correlation_id="corr-123",
            )
            with use_trace_context(context):
                envelope = portable_event_envelope(
                    dispute_event("dispute.created", "DSP-1", 1, {"state": "received"}),
                    trace_context={"traceparent": current_traceparent(), **context},
                )
            assert envelope.traceparent == (
                "00-11111111111111111111111111111111-2222222222222222-01"
            )
            assert envelope.correlation_id == "corr-123"
            checks.append("w3c_trace_context_event_envelope")

            redacted = safe_fields(
                {"customer_upi": "customer@example", "token": "secret-token"}
            )
            assert redacted["customer_upi"] == "cu***@example"
            assert redacted["token"] == "[redacted]"
            checks.append("safe_structured_log_redaction")

            timing_db = Path(db_dir) / "timing.sqlite3"
            service = DisputeService(SqliteUnitOfWork(timing_db))
            samples: list[float] = []
            for index in range(10):
                started = perf_counter()
                service.create_dispute(
                    CreateDisputeCommand(
                        transaction_ref=f"UPID{index:08d}",
                        customer_upi=f"timing{index:02d}@example",
                        reason="bounded local timing smoke",
                        idempotency_key=f"idem-wave-d-{index}",
                        correlation_id=f"corr-wave-d-{index}",
                        owner_subject="local-owner",
                    )
                )
                service.list_disputes(limit=5, cursor=0)
                samples.append(perf_counter() - started)
            assert percentile(samples, 95) < 1.0
            checks.append("actual_local_service_timing_smoke_without_capacity_claim")
        finally:
            sys.path = previous_path
            sys.pycache_prefix = previous_prefix

    return checks


def validate_docs(generated_root: Path) -> list[str]:
    checks: list[str] = []
    slo = (
        generated_root / "generated_application/docs/reliability_slo_error_budget.md"
    ).read_text(encoding="utf-8")
    runbook = (
        generated_root / "generated_application/docs/runtime_runbook.md"
    ).read_text(encoding="utf-8")
    failure = (
        generated_root / "generated_application/docs/failure_mode_evidence.md"
    ).read_text(encoding="utf-8")

    for required in [
        "do not claim production capacity",
        "Error budget benchmark",
        "p95",
    ]:
        if required not in slo:
            raise RuntimeError(f"SLO documentation missing: {required}")
    checks.append("sli_slo_error_budget_documentation")

    for required in [
        "Startup",
        "Drain And Shutdown",
        "Rollback",
        "MOCK_BOUNDARY",
        "UPI_DISPUTE_SQLITE_PATH",
        "runtime:drain",
        "runtime:diagnostics",
    ]:
        if required not in runbook:
            raise RuntimeError(f"Runtime runbook missing: {required}")
    checks.append("runtime_runbook")

    for required in ["W3C trace context", "OpenMetrics-compatible", "Shutdown"]:
        if required not in failure:
            raise RuntimeError(f"Failure-mode evidence missing: {required}")
    checks.append("failure_mode_evidence")

    return checks


def validate_source_contracts(generated_root: Path) -> list[str]:
    combined = "\n".join(
        (generated_root / path).read_text(encoding="utf-8")
        for path in [
            "generated_application/app/runtime.py",
            "generated_application/app/interfaces/api/main.py",
            "generated_application/app/observability/metrics.py",
            "generated_application/app/observability/tracing.py",
            "generated_application/app/domain/domain_events.py",
        ]
    )
    required_markers = [
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
        "live_payment_calls_allowed",
        "production_capacity_claimed",
    ]
    missing = [marker for marker in required_markers if marker not in combined]
    if missing:
        raise RuntimeError(f"Generated source missing Wave D markers: {missing}")
    return ["lifecycle_metrics_trace_source_contracts"]


def validate() -> dict[str, Any]:
    before_template_bytecode = bytecode_artifacts(TEMPLATE_GENERATED_ROOT)

    with tempfile.TemporaryDirectory(prefix="phase71_82_wave_d_generation_") as workspace:
        result = generate(run_id=RUN_ID, workspace_root=Path(workspace), clean=True)
        generated_root = result.output_dir / "generated"
        emitted_files = {item.relative_path for item in result.generated_files}
        missing = sorted(REQUIRED_WAVE_D_FILES - emitted_files)
        if missing:
            raise RuntimeError(f"Fresh generated output missing Wave D files: {missing}")

        generated_before_bytecode = bytecode_artifacts(generated_root)
        docs_checks = validate_docs(generated_root)
        source_checks = validate_source_contracts(generated_root)
        runtime_checks = run_generated_wave_d_checks(generated_root)
        test_targets = GENERATED_TEST_TARGETS
        generated_after_bytecode = bytecode_artifacts(generated_root)
        if generated_after_bytecode != generated_before_bytecode:
            raise RuntimeError("Validation wrote bytecode inside fresh generated output")

        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        proof: dict[str, Any] = {
            "passed": True,
            "run_id": result.run_id,
            "generation_mode": manifest["generation_mode"],
            "generated_file_count": len(result.generated_files),
            "wave_d_generated_files": sorted(REQUIRED_WAVE_D_FILES),
            "functional_smoke_checks": docs_checks + source_checks + runtime_checks,
            "generated_test_targets": test_targets,
            "bytecode_cache_policy": "PYTHONPYCACHEPREFIX redirected to temporary directory",
            "production_capacity_claimed": False,
            "live_provider_calls_allowed": manifest["live_provider_calls_allowed"],
            "real_payment_calls_allowed": manifest["real_payment_calls_allowed"],
        }

    after_template_bytecode = bytecode_artifacts(TEMPLATE_GENERATED_ROOT)
    if after_template_bytecode != before_template_bytecode:
        raise RuntimeError("Validation mutated template bytecode artifacts")

    return proof


def main() -> int:
    try:
        print(json.dumps(validate(), indent=2) + "\n")
    except Exception as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
