from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from scripts.build_guided_requirement_intake_preview import (
    READY,
    build_requirement_intake_preview,
    validate_requirement_intake_preview,
    write_requirement_intake_preview,
)
from scripts.start_factory_operator_portal import create_app


def sample_payload() -> dict[str, object]:
    return {
        "business_domain": "UPI dispute resolution",
        "application_name": "upi_dispute_resolution",
        "capabilities": "case intake, dispute triage, evidence tracking, SLA escalation",
        "regulatory_constraints": "NPCI traceability, RBI audit evidence, PII handling",
        "mock_ecosystem": "mock bank rails, mock NPCI switch, mock notifications",
        "data_sensitivity": "regulated payment PII",
        "llm_mode": "offline/replay",
        "approval_mode": "human approval required",
    }


def test_requirement_intake_preview_is_ready_and_safe() -> None:
    preview = build_requirement_intake_preview(sample_payload())
    assert preview.ready is True
    assert preview.preview_status == READY
    assert preview.preview_only is True
    assert preview.requirement_package_written_from_ui is False
    assert preview.application_generation_triggered_from_ui is False
    assert validate_requirement_intake_preview(preview) == []


def test_requirement_intake_missing_fields_blocks_preview() -> None:
    preview = build_requirement_intake_preview({"business_domain": "Payments"})
    assert preview.ready is False
    assert "Missing required fields" in preview.reasons[0]


def test_requirement_intake_classifies_regulated_payment_data_as_medium_or_high() -> None:
    preview = build_requirement_intake_preview(sample_payload())
    assert preview.risk_classification["risk_tier"] in {"medium", "high"}
    assert preview.risk_classification["human_approval_required"] is True


def test_requirement_intake_mock_boundary_keeps_ecosystem_mocked() -> None:
    preview = build_requirement_intake_preview(sample_payload())
    assert preview.mock_boundary["primary_generated_application_should_be_real_local_runnable"] is True
    assert preview.mock_boundary["external_ecosystem_integrations_should_remain_mocked"] is True


def test_requirement_intake_audit_report_is_written(tmp_path: Path) -> None:
    preview = build_requirement_intake_preview(sample_payload())
    output = tmp_path / "requirement_preview.json"
    write_requirement_intake_preview(preview, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "guided-requirement-intake-preview.v1"
    assert payload["preview_only"] is True


def test_portal_requirement_page_renders() -> None:
    client = TestClient(create_app(Path.cwd()))
    response = client.get("/requirements")
    assert response.status_code == 200
    assert "Guided Requirement Intake" in response.text
    assert "preview-only" in response.text


def test_portal_requirement_preview_api_returns_ready_preview() -> None:
    client = TestClient(create_app(Path.cwd()))
    response = client.post("/api/requirements/preview", json=sample_payload())
    assert response.status_code == 200
    payload = response.json()
    assert payload["preview_status"] == READY
    assert payload["application_generation_triggered_from_ui"] is False
    assert payload["requirement_package_written_from_ui"] is False


def test_requirement_preview_cli_exits_success() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_guided_requirement_intake_preview.py",
            "--payload-json",
            json.dumps(sample_payload()),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["preview_status"] == READY


def test_phase13ax_artifact_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase13ax_requirement_intake_ui.py"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 13AX guided requirement intake UI artifacts validated." in result.stdout
