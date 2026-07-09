#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import tempfile
import asyncio
from pathlib import Path
from typing import Any, cast

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
PHASE = "phase41_generated_application_architecture_code_quality_upgrade"
POLICY_PATH = Path("policies/phase41_generated_application_architecture_code_quality_upgrade_policy.json")
PROMPT_PATH = Path("prompts/phase41/generated_application_architecture_code_quality_upgrade_prompt.md")
VALIDATOR_PATH = Path(
    "scripts/validate_phase41_generated_application_architecture_code_quality_upgrade.py"
)
TEST_PATH = Path("tests/test_phase41_generated_application_architecture_code_quality_upgrade.py")
GENERATED_APP_ROOT = Path("workspace/factory_generated/upi_dispute_resolution/generated_application")
APP_PACKAGE = GENERATED_APP_ROOT / "app/upi_dispute_app"
ARTIFACT_DIR = (
    Path("workspace/factory_generated") / APP_ID / "lifecycle_artifacts" / "phase41"
)

ARCHITECTURE_EVIDENCE_PATH = ARTIFACT_DIR / "generated_application_architecture_evidence.json"
CODE_QUALITY_CHECKLIST_PATH = ARTIFACT_DIR / "generated_application_code_quality_checklist.json"
GATE_PATH = ARTIFACT_DIR / "generated_application_architecture_gate.json"
AUDIT_PATH = ARTIFACT_DIR / "generated_application_architecture_audit.json"
MANIFEST_PATH = ARTIFACT_DIR / "generated_application_lifecycle_manifest.json"

REQUIRED_FILES = [
    POLICY_PATH,
    PROMPT_PATH,
    VALIDATOR_PATH,
    TEST_PATH,
    APP_PACKAGE / "cqrs.py",
    APP_PACKAGE / "domain_events.py",
    APP_PACKAGE / "errors.py",
    APP_PACKAGE / "ports.py",
    APP_PACKAGE / "repository.py",
    APP_PACKAGE / "unit_of_work.py",
    ARCHITECTURE_EVIDENCE_PATH,
    CODE_QUALITY_CHECKLIST_PATH,
    GATE_PATH,
    AUDIT_PATH,
    MANIFEST_PATH,
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

REQUIRED_CONTROLS = {
    "ddd_layered_boundaries",
    "ports_and_adapters",
    "command_query_separation",
    "domain_events",
    "repository_and_unit_of_work",
    "error_taxonomy",
    "local_mock_ecosystem_boundary",
}

REQUIRED_CODE_MARKERS = {
    "cqrs.py": [
        "class SubmitDisputeCommand",
        "class GetDisputeQuery",
        "class ListDisputesQuery",
        "class RunMockEcosystemCheckCommand",
    ],
    "domain_events.py": [
        "class DomainEvent",
        "class DomainEventCollector",
        "dispute_created_event",
        "mock_ecosystem_checked_event",
    ],
    "errors.py": [
        "class AppErrorCode",
        "class ApplicationError",
        "as_error_payload",
    ],
    "ports.py": [
        "class DisputeRepositoryPort",
        "class AuditLogPort",
        "class MockEcosystemPort",
        "class UnitOfWorkPort",
    ],
    "unit_of_work.py": [
        "class LocalSqliteUnitOfWork",
        "def commit",
        "def rollback",
    ],
    "main.py": [
        "SubmitDisputeCommand.from_payload",
        "GetDisputeQuery",
        "RunMockEcosystemCheckCommand",
        "domain_events.record",
        "ApplicationError",
        "LocalSqliteUnitOfWork",
    ],
    "repository.py": [
        "DuplicateClientRequestError(ApplicationError)",
        "DisputeNotFoundError(ApplicationError)",
    ],
}

LIVE_CALL_PATTERNS = [
    r"\brequests\.",
    r"\burllib\.request\b",
    r"\bhttpx\.(get|post|put|delete|patch|stream)\(",
    r"\bboto3\b",
    r"\bgoogle\.cloud\b",
    r"\bazure\.",
    r"\bstripe\b",
    r"\brazorpay\b",
]

SECRET_PATTERNS = [
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "client_secret =",
    "client_secret:",
    "api_key =",
    "api_key:",
    "password =",
]

RELEASE_ENABLEMENT_PATTERNS = [
    r"\bdeployment_allowed\"\s*:\s*true",
    r"\bmerge_allowed\"\s*:\s*true",
    r"\btag_allowed\"\s*:\s*true",
    r"\bpush_allowed\"\s*:\s*true",
    r"\bgit\s+push\b",
    r"\bgit\s+tag\b",
    r"\bgit\s+merge\b",
    r"\bnpm\s+publish\b",
    r"\bdeploy\b.*\benabled\b",
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
    readiness_scope = artifact.get("local_readiness_scope")
    if readiness_scope != "local_generated_application_architecture_and_code_quality_validation_only":
        errors.append(f"{context} does not scope readiness to local architecture validation only")


def validate_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not (PROJECT_ROOT / path).exists():
            errors.append(f"Missing required Phase 41 file: {path}")


def validate_policy_prompt_and_lifecycle_artifacts(errors: list[str]) -> None:
    policy = load_json(PROJECT_ROOT / POLICY_PATH)
    evidence = load_json(PROJECT_ROOT / ARCHITECTURE_EVIDENCE_PATH)
    checklist = load_json(PROJECT_ROOT / CODE_QUALITY_CHECKLIST_PATH)
    gate = load_json(PROJECT_ROOT / GATE_PATH)
    audit = load_json(PROJECT_ROOT / AUDIT_PATH)
    manifest = load_json(PROJECT_ROOT / MANIFEST_PATH)
    prompt = (PROJECT_ROOT / PROMPT_PATH).read_text(encoding="utf-8")

    if policy.get("mandatory_gate") != "PHASE41-GENERATED-APPLICATION-ARCHITECTURE-CODE-QUALITY-UPGRADE-GATE":
        errors.append("Phase 41 policy missing mandatory gate")
    if policy.get("validation_entrypoint") != str(VALIDATOR_PATH):
        errors.append("Phase 41 policy does not identify validator")
    if policy.get("test_entrypoint") != str(TEST_PATH):
        errors.append("Phase 41 policy does not identify tests")
    if gate.get("gate_status") != "passed":
        errors.append("Phase 41 architecture gate is not passed")

    for artifact, name in [
        (policy, "policy"),
        (evidence, "architecture evidence"),
        (checklist, "code quality checklist"),
        (gate, "gate"),
        (audit, "audit"),
        (manifest, "manifest"),
    ]:
        validate_boundary_artifact(artifact, errors, f"Phase 41 {name}")
        if artifact.get("phase") != PHASE:
            errors.append(f"Phase 41 {name} has wrong phase")

    controls = {
        str(entry.get("control"))
        for entry in evidence.get("architecture_controls", [])
        if isinstance(entry, dict)
    }
    if controls != REQUIRED_CONTROLS:
        errors.append(f"Phase 41 architecture controls mismatch: {sorted(controls)}")

    rules = checklist.get("rules")
    if not isinstance(rules, list) or len(rules) < 7:
        errors.append("Phase 41 code quality checklist is incomplete")
    else:
        for rule in rules:
            if not isinstance(rule, dict):
                errors.append("Phase 41 code quality checklist has non-object rule")
                continue
            if rule.get("required") is not True or rule.get("status") != "implemented":
                errors.append(f"Phase 41 code quality rule not implemented: {rule.get('id')}")

    for contract_path in [
        "prompts/_contracts/agentic_ai_best_practice_contract.md",
        "prompts/_contracts/generated_application_quality_contract.md",
        "prompts/_contracts/llm_call_metrics_and_expense_contract.md",
    ]:
        include = "{{ include: " + contract_path + " }}"
        if include not in prompt:
            errors.append(f"Phase 41 prompt does not inherit contract: {contract_path}")

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
            errors.append(f"Phase 41 prompt missing required phrase: {phrase}")


def validate_architecture_code_markers(errors: list[str]) -> None:
    for filename, markers in REQUIRED_CODE_MARKERS.items():
        path = PROJECT_ROOT / APP_PACKAGE / filename
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"Missing architecture marker in {path}: {marker}")

    main_text = (PROJECT_ROOT / APP_PACKAGE / "main.py").read_text(encoding="utf-8")
    if "MockEcosystemGateway" not in main_text:
        errors.append("Generated app does not depend on mock ecosystem adapter")
    if "current_gateway.decide" not in main_text:
        errors.append("Generated app does not route ecosystem checks through adapter")


async def validate_local_app_behavior_async(errors: list[str]) -> None:
    app_source = PROJECT_ROOT / GENERATED_APP_ROOT / "app"
    if str(app_source) not in sys.path:
        sys.path.insert(0, str(app_source))

    from upi_dispute_app.audit import AuditLogger
    from upi_dispute_app.main import create_app
    from upi_dispute_app.repository import DisputeRepository

    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "workspace") as tmp:
        app = create_app(
            repository=DisputeRepository(),
            audit_logger=AuditLogger(Path(tmp) / "audit.jsonl"),
        )
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://local-generated-upi-dispute-app",
        ) as client:
            health = await client.get("/health")
            if health.status_code != 200:
                errors.append("Generated app health endpoint is not locally runnable")
                return
            runtime = health.json().get("runtime_hardening", {})
            if runtime.get("live_provider_calls_allowed") is not False:
                errors.append("Generated app runtime permits live provider calls")
            if runtime.get("certification_boundary") != "certification_ready_not_certified":
                errors.append("Generated app runtime changed certification boundary")

            payload = {
                "client_request_id": "phase41-client-001",
                "dispute_type": "duplicate_debit",
                "transaction_reference": "PHASE41TXN001",
                "customer_upi_id": "localcustomer@upi",
                "amount_paise": 12000,
                "description": "Local simulated duplicate debit dispute for architecture validation.",
                "evidence": {"source": "phase41_local_validation"},
            }
            created = await client.post("/disputes", json=payload)
            if created.status_code != 201:
                errors.append(f"Generated app cannot create local dispute: {created.text}")
                return
            dispute_id = created.json()["dispute"]["dispute_id"]
            checked = await client.post(f"/disputes/{dispute_id}/actions/mock-ecosystem-check")
            if checked.status_code != 200:
                errors.append(f"Generated app mock ecosystem check failed: {checked.text}")
                return
            body = checked.json()
            if not all(source.startswith("mock_") for source in body["mock_sources_checked"]):
                errors.append("Generated app ecosystem sources are not mock-only")


def validate_local_app_behavior(errors: list[str]) -> None:
    asyncio.run(validate_local_app_behavior_async(errors))


def validate_static_governance_boundaries(errors: list[str]) -> None:
    source_paths = [
        PROJECT_ROOT / POLICY_PATH,
        PROJECT_ROOT / PROMPT_PATH,
        PROJECT_ROOT / ARCHITECTURE_EVIDENCE_PATH,
        PROJECT_ROOT / CODE_QUALITY_CHECKLIST_PATH,
        PROJECT_ROOT / GATE_PATH,
        PROJECT_ROOT / AUDIT_PATH,
        PROJECT_ROOT / MANIFEST_PATH,
        *sorted((PROJECT_ROOT / APP_PACKAGE).glob("*.py")),
    ]
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)

    for pattern in LIVE_CALL_PATTERNS:
        if re.search(pattern, source_text):
            errors.append(f"Phase 41 source enables or imports live call pattern: {pattern}")
    for pattern in SECRET_PATTERNS:
        if pattern in source_text:
            errors.append(f"Phase 41 source appears to contain a real secret pattern: {pattern}")
    for pattern in RELEASE_ENABLEMENT_PATTERNS:
        if re.search(pattern, source_text, flags=re.IGNORECASE):
            errors.append(f"Phase 41 source appears to enable release action: {pattern}")

    external_urls = [
        url
        for url in re.findall(r"https?://[^\"'\s]+", source_text)
        if not url.startswith("http://local-generated-upi-dispute-app")
    ]
    if external_urls:
        errors.append(f"Phase 41 source includes external URL dependencies: {external_urls}")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    if not errors:
        validate_policy_prompt_and_lifecycle_artifacts(errors)
        validate_architecture_code_markers(errors)
        validate_static_governance_boundaries(errors)
        validate_local_app_behavior(errors)

    if errors:
        print("Phase 41 generated application architecture/code quality validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Phase 41 generated application architecture/code quality upgrade validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
