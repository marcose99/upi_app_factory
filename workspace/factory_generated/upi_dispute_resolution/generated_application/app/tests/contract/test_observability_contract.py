from __future__ import annotations

import json
import logging
from pathlib import Path

from _pytest.logging import LogCaptureFixture

from generated_application.app.domain.domain_events import dispute_event
from generated_application.app.domain.domain_events import portable_event_envelope
from generated_application.app.observability.logging import log_event
from generated_application.app.observability.metrics import Metrics
from generated_application.app.observability.tracing import (
    current_traceparent,
    trace_context_from_headers,
    use_trace_context,
)


def test_openmetrics_names_units_and_bounded_labels() -> None:
    metrics = Metrics()
    metrics.record_http(
        method="GET",
        route="/ready",
        outcome="success",
        duration_seconds=0.012,
    )
    metrics.record_http(
        method="PATCH",
        route="/unbounded/customer/123",
        outcome="unexpected",
        duration_seconds=0.2,
    )
    metrics.record_business_event(event_type="dispute.created", outcome="success")

    output = metrics.openmetrics()

    assert "upi_app_factory_http_requests_total" in output
    assert "upi_app_factory_http_request_duration_seconds_bucket" in output
    assert 'route="other"' in output
    assert 'method="OTHER"' in output
    assert 'outcome="error"' in output
    assert output.endswith("# EOF\n")


def test_w3c_trace_context_propagates_to_event_envelope() -> None:
    traceparent = "00-11111111111111111111111111111111-2222222222222222-01"
    context = trace_context_from_headers(
        traceparent=traceparent,
        tracestate="vendor=value",
        correlation_id="corr-123",
    )
    event = dispute_event("dispute.created", "DSP-1", 1, {"state": "received"})

    with use_trace_context(context):
        envelope = portable_event_envelope(
            event,
            trace_context={
                "traceparent": current_traceparent(),
                **context,
            },
        )

    assert envelope.traceparent == traceparent
    assert envelope.trace_id == "11111111111111111111111111111111"
    assert envelope.correlation_id == "corr-123"
    assert envelope.tracestate == "vendor=value"


def test_structured_logs_include_correlation_and_redact_sensitive_fields(
    caplog: LogCaptureFixture,
) -> None:
    logger = logging.getLogger("generated_application.test")
    context = trace_context_from_headers(
        traceparent="00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
        correlation_id="corr-log",
    )

    with caplog.at_level(logging.INFO), use_trace_context(context):
        log_event(
            logger,
            "dispute.received",
            {"customer_upi": "customer@example", "token": "secret-token"},
        )

    payload = json.loads(caplog.records[-1].message)
    assert payload["trace_id"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert payload["correlation_id"] == "corr-log"
    assert payload["customer_upi"] == "cu***@example"
    assert payload["token"] == "[redacted]"


def test_health_check_accepts_runtime_probe_status_contract(tmp_path: Path) -> None:
    from generated_application.app.runtime import RuntimeLifecycle

    database = tmp_path / "runtime_contract.sqlite3"
    runtime = RuntimeLifecycle(database)
    runtime.startup()

    health_check_text = (
        Path(__file__).resolve().parents[3] / "scripts" / "health_check.py"
    ).read_text(encoding="utf-8")
    statuses = {
        runtime.startup_status()[1]["status"],
        runtime.liveness()[1]["status"],
        runtime.readiness()[1]["status"],
    }

    for status in statuses:
        assert repr(status) in health_check_text or f'"{status}"' in health_check_text
