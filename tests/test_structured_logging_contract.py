from __future__ import annotations

import json
import logging

from factory.observability.structured_logging import (
    JsonLogFormatter,
    logging_context,
    redacted,
    trace_context_from_traceparent,
)


def test_json_log_envelope_redacts_and_sanitizes() -> None:
    formatter = JsonLogFormatter(service_name="factory", service_namespace="upi_app_factory")
    record = logging.LogRecord("factory.test", logging.INFO, __file__, 1, "hello\nworld", (), None)
    record.event_name = "factory.test.event"
    record.attributes = {
        "authorization": "Bearer fictional-token",
        "payment_payload": {"vpa": "fictional@example"},
        "safe": "ok\r\nnext",
    }
    with logging_context(trace_id="1" * 32, span_id="2" * 16, trace_flags="01", request_id="req-1"):
        payload = json.loads(formatter.format(record))
    assert payload["schema_version"] == "upi-app-factory.log.v1"
    assert payload["severity_number"] == 9
    assert payload["trace_id"] == "1" * 32
    assert payload["authorization"] == "[REDACTED]"
    assert payload["payment_payload"] == "[REDACTED]"
    assert "\n" not in payload["body"]
    assert "\r" not in payload["safe"]


def test_traceparent_validation_and_recursive_redaction() -> None:
    context = trace_context_from_traceparent(f"00-{'a'*32}-{'b'*16}-01", request_id="req")
    assert context["trace_id"] == "a" * 32
    assert len(context["span_id"]) == 16
    assert redacted({"nested": {"approval_token": "APPROVE_PORTAL_APPLICATION_ENGINEERING"}})["nested"]["approval_token"] == "[REDACTED]"
