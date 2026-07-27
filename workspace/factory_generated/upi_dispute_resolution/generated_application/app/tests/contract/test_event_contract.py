from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from generated_application.app.domain.domain_events import dispute_event, portable_event_envelope


def test_portable_event_envelope_is_versioned_and_checksummed() -> None:
    event = dispute_event(
        "dispute.state_changed",
        "DSP-CONTRACT",
        2,
        {"from": "received", "to": "validated"},
    )
    envelope = portable_event_envelope(event, trace_id="trace-contract")
    rendered = json.loads(envelope.to_json())

    assert rendered["schema_version"] == "upi_app_factory.event_envelope.v1"
    assert rendered["envelope_version"] == 1
    assert rendered["aggregate_version"] == 2
    assert rendered["payload_sha256"]


def test_asyncapi_contract_is_generated() -> None:
    contract = Path(__file__).resolve().parents[3] / "asyncapi.yaml"
    text = contract.read_text(encoding="utf-8")

    assert "asyncapi: 3.0.0" in text
    assert "upi_app_factory.event_envelope.v1" in text
    assert "dispute.state_changed" in text
