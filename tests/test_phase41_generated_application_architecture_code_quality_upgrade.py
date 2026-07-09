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

POLICY_PATH = (
    PROJECT_ROOT
    / "policies/phase41_generated_application_architecture_code_quality_upgrade_policy.json"
)
PROMPT_PATH = (
    PROJECT_ROOT
    / "prompts/phase41/generated_application_architecture_code_quality_upgrade_prompt.md"
)
ARTIFACT_DIR = (
    PROJECT_ROOT
    / "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase41"
)
APP_PACKAGE = GENERATED_APP_ROOT / "app/upi_dispute_app"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_phase41_validator_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_phase41_generated_application_architecture_code_quality_upgrade.py",
        ],
        cwd=PROJECT_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_policy_prompt_and_artifacts_preserve_governance_boundaries() -> None:
    artifacts = [
        load_json(POLICY_PATH),
        load_json(ARTIFACT_DIR / "generated_application_architecture_evidence.json"),
        load_json(ARTIFACT_DIR / "generated_application_code_quality_checklist.json"),
        load_json(ARTIFACT_DIR / "generated_application_architecture_gate.json"),
        load_json(ARTIFACT_DIR / "generated_application_architecture_audit.json"),
        load_json(ARTIFACT_DIR / "generated_application_lifecycle_manifest.json"),
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


def test_architecture_evidence_covers_required_controls() -> None:
    evidence = load_json(ARTIFACT_DIR / "generated_application_architecture_evidence.json")
    controls = {entry["control"] for entry in evidence["architecture_controls"]}
    assert controls == {
        "ddd_layered_boundaries",
        "ports_and_adapters",
        "command_query_separation",
        "domain_events",
        "repository_and_unit_of_work",
        "error_taxonomy",
        "local_mock_ecosystem_boundary",
    }
    for entry in evidence["architecture_controls"]:
        for relative_path in entry["evidence_files"]:
            assert (GENERATED_APP_ROOT / relative_path).is_file()


def test_generated_app_contains_architecture_modules_and_markers() -> None:
    required_markers = {
        "cqrs.py": ["SubmitDisputeCommand", "GetDisputeQuery", "RunMockEcosystemCheckCommand"],
        "domain_events.py": ["DomainEvent", "DomainEventCollector", "dispute_created_event"],
        "errors.py": ["AppErrorCode", "ApplicationError", "as_error_payload"],
        "ports.py": ["DisputeRepositoryPort", "AuditLogPort", "MockEcosystemPort"],
        "unit_of_work.py": ["LocalSqliteUnitOfWork", "commit", "rollback"],
        "main.py": ["SubmitDisputeCommand.from_payload", "domain_events.record"],
        "repository.py": ["DuplicateClientRequestError(ApplicationError)"],
    }
    for filename, markers in required_markers.items():
        text = (APP_PACKAGE / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text


async def run_generated_app_event_flow(tmp_path: Path) -> None:
    from upi_dispute_app.audit import AuditLogger
    from upi_dispute_app.main import create_app
    from upi_dispute_app.repository import DisputeRepository

    audit_path = tmp_path / "audit.jsonl"
    app = create_app(
        repository=DisputeRepository(),
        audit_logger=AuditLogger(audit_path),
    )
    transport = httpx.ASGITransport(app=app)

    payload = {
        "client_request_id": "phase41-client-002",
        "dispute_type": "duplicate_debit",
        "transaction_reference": "PHASE41TXN002",
        "customer_upi_id": "localcustomer@upi",
        "amount_paise": 12000,
        "description": "Local simulated duplicate debit dispute for event validation.",
        "evidence": {"source": "phase41_test"},
    }
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://local-generated-upi-dispute-app",
    ) as client:
        created = await client.post("/disputes", json=payload)
        assert created.status_code == 201, created.text
        dispute_id = created.json()["dispute"]["dispute_id"]
        checked = await client.post(f"/disputes/{dispute_id}/actions/mock-ecosystem-check")
        assert checked.status_code == 200, checked.text
        assert all(source.startswith("mock_") for source in checked.json()["mock_sources_checked"])

    audit_events = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    domain_event_types = [
        domain_event["event_type"]
        for audit_event in audit_events
        for domain_event in audit_event["details"]["domain_events"]
    ]
    assert "dispute.created" in domain_event_types
    assert "dispute.mock_ecosystem_checked" in domain_event_types


def test_generated_app_emits_domain_events_to_local_audit(tmp_path: Path) -> None:
    asyncio.run(run_generated_app_event_flow(tmp_path))


def test_no_phase41_release_or_live_provider_enablement() -> None:
    policy = load_json(POLICY_PATH)
    assert policy["local_readiness_scope"] == (
        "local_generated_application_architecture_and_code_quality_validation_only"
    )
    assert "official certification claim" in policy["prohibited_actions"]
    assert "broad production readiness claim" in policy["prohibited_actions"]
    assert "generated export bundle ZIP files" in policy["prohibited_actions"]

    scanned_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            POLICY_PATH,
            PROMPT_PATH,
            *sorted(APP_PACKAGE.glob("*.py")),
        ]
    )
    assert "BEGIN PRIVATE KEY" not in scanned_text
    assert "boto3" not in scanned_text
    assert "google.cloud" not in scanned_text
    assert '"deployment_allowed": true' not in scanned_text
    assert '"push_allowed": true' not in scanned_text
