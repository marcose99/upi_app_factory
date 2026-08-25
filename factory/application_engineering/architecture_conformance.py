"""Deterministic, independently re-verifiable source architecture conformance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from factory.architecture_decisioning.canonical import canonical_sha256


def _pattern(contract: Mapping[str, Any], pattern_id: object) -> Mapping[str, Any] | None:
    for row in contract.get("patterns", []):
        if isinstance(row, Mapping) and row.get("pattern_id") == pattern_id:
            return row
    return None


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def validate_architecture_conformance(
    application_root: Path, reviewed_freeze: Mapping[str, Any],
    realization_contract: Mapping[str, Any],
) -> dict[str, Any]:
    app_directory = application_root / "app"
    app_ids = sorted(
        path.name for path in app_directory.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    ) if app_directory.is_dir() else []
    app_id = app_ids[0] if len(app_ids) == 1 else application_root.name
    selected = reviewed_freeze.get("selected_candidate_id")
    pattern = _pattern(realization_contract, selected)
    rules = list(realization_contract.get("common_conformance_rules", []))
    if pattern is not None:
        rules.extend(pattern.get("conformance_rules", []))
    domain_paths = sorted(application_root.glob(f"app/{app_id}/domain/**/*.py"))
    domain = "\n".join(path.read_text(encoding="utf-8") for path in domain_paths)
    api = _read(application_root, f"app/{app_id}/interfaces/api/main.py")
    service = _read(application_root, f"app/{app_id}/application/services/dispute_service.py")
    workflow = _read(application_root, f"app/{app_id}/application/workflows/dispute_workflow.py")
    events = _read(application_root, f"app/{app_id}/application/events.py")
    outbox_path = f"app/{app_id}/infrastructure/messaging/outbox.py"
    outbox = _read(application_root, outbox_path)
    migration = _read(application_root, f"app/{app_id}/infrastructure/persistence/migrations/0001_initial.sql")
    manifest_text = _read(application_root, "evidence/generation_manifest.json")
    try:
        manifest = json.loads(manifest_text) if manifest_text else None
    except json.JSONDecodeError:
        manifest = {}
    freeze_text = _read(application_root, "evidence/architecture/architecture_freeze.json")
    try:
        frozen_evidence = json.loads(freeze_text) if freeze_text else {}
    except json.JSONDecodeError:
        frozen_evidence = {}
    manifest_valid = manifest is None or (
        isinstance(manifest, dict)
        and manifest.get("requirements_ir_sha256") == reviewed_freeze.get("requirements_sha256")
        and manifest.get("architecture_pattern_id") == selected
        and manifest.get("architecture_adapter_id") == reviewed_freeze.get("adapter_id")
        and manifest.get("architecture_freeze_digest") == reviewed_freeze.get("freeze_digest")
    )
    checks: dict[str, bool] = {
        "requirements_hash_matches_reviewed_freeze": frozen_evidence.get("requirements_sha256") == reviewed_freeze.get("requirements_sha256"),
        "reviewed_freeze_digest_valid": reviewed_freeze.get("freeze_digest") == canonical_sha256({k: v for k, v in reviewed_freeze.items() if k != "freeze_digest"}),
        "realization_contract_digest_valid": realization_contract.get("contract_digest") == canonical_sha256({k: v for k, v in realization_contract.items() if k != "contract_digest"}),
        "generation_manifest_binds_reviewed_architecture": manifest_valid,
        "architecture_evidence_identity_chain_complete": all(reviewed_freeze.get(key) for key in ("driver_ir_digest", "architecture_packet_digest", "review_set_digest", "adjudication_digest", "reviewed_decision_digest", "evolution_contract_digest")),
        "generated_application_runtime_llm_calls_zero": "FACTORY_LLM_ENABLED=0" in _read(application_root, "configuration/example.env"),
        "real_payment_calls_disabled": "REAL_PAYMENT_CALLS=disabled" in _read(application_root, "configuration/example.env"),
        "no_provider_sdk_in_generated_domain": not any(token in domain for token in ("openai", "anthropic", "google.generativeai")),
        "no_external_infrastructure_enablement": not any(token in "\n".join((domain, service, migration)).lower() for token in ("kubernetes", "kafka", "postgresql://", "http://", "https://")),
        "domain_does_not_import_infrastructure": ".infrastructure" not in domain and " import infrastructure" not in domain,
        "domain_does_not_import_interfaces": ".interfaces" not in domain and " import interfaces" not in domain,
        "api_depends_on_application_service": ".application.services.dispute_service" in api,
        "outbound_dependencies_are_adapter_bounded": ".infrastructure" not in domain,
        "explicit_workflow_state": "def next_state" in workflow,
        "deadline_policy_declared": "DEADLINE_POLICY" in workflow,
        "reentry_policy_declared": "REENTRY_POLICY" in workflow,
        "human_review_states_declared": "HUMAN_REVIEW_STATES" in workflow,
        "runtime_imports_workflow_module": "application.workflows.dispute_workflow import" in service,
        "runtime_calls_workflow_transition": "next_state(" in service,
        "runtime_consumes_deadline_policy": "DEADLINE_POLICY.get" in service,
        "runtime_consumes_reentry_policy": "REENTRY_POLICY.items" in service,
        "runtime_consumes_human_review_policy": "state in HUMAN_REVIEW_STATES" in service,
        "event_schema_version_declared": "EVENT_SCHEMA_VERSION" in events,
        "transactional_outbox_present": bool(outbox) and "outbox_events" in migration,
        "service_records_domain_events": "DomainEvent" in service and "save_case_and_event" in service,
        "idempotent_outbox_contract_present": "idempotency_key" in outbox and "UNIQUE" in outbox,
        "outbox_migration_present": "CREATE TABLE outbox_events" in migration and "idempotency_key" in migration,
        "runtime_outbox_is_persistent": "sqlite3.connect" in outbox and "data/generated_application.sqlite3" in outbox,
        "case_and_outbox_share_atomic_transaction_boundary": all(
            token in outbox
            for token in ("BEGIN IMMEDIATE", "INSERT INTO dispute_cases", "INSERT INTO outbox_events", "connection.commit")
        ),
    }
    required_paths = [] if pattern is None else [
        str(item).format(app_id=app_id) for item in pattern.get("required_generated_paths", [])
    ]
    identities = []
    for relative in sorted(set(required_paths)):
        path = application_root / relative
        identities.append({
            "path": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        })
    outcomes = {rule: bool(checks.get(rule, False)) for rule in rules}
    if selected == "WORKFLOW_CENTRIC_MODULAR_MONOLITH":
        for rule in (
            "runtime_imports_workflow_module", "runtime_calls_workflow_transition",
            "runtime_consumes_deadline_policy", "runtime_consumes_reentry_policy",
            "runtime_consumes_human_review_policy",
        ):
            outcomes[rule] = checks[rule]
    if selected == "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX":
        for rule in ("runtime_outbox_is_persistent", "case_and_outbox_share_atomic_transaction_boundary"):
            outcomes[rule] = checks[rule]
    if any(not (application_root / relative).is_file() for relative in required_paths):
        outcomes["required_generated_paths_present"] = False
    else:
        outcomes["required_generated_paths_present"] = pattern is not None
    failed = sorted(rule for rule, passed in outcomes.items() if not passed)
    report: dict[str, Any] = {
        "schema_version": "upi-app-factory.architecture-conformance.v1",
        "status": "PASS" if not failed else "FAIL",
        "selected_candidate_id": selected,
        "adapter_id": reviewed_freeze.get("adapter_id"),
        "architecture_freeze_digest": reviewed_freeze.get("freeze_digest"),
        "realization_contract_digest": realization_contract.get("contract_digest"),
        "rule_outcomes": outcomes,
        "failed_rules": failed,
        "source_identities": identities,
    }
    report["conformance_digest"] = canonical_sha256(report)
    return report


def verify_architecture_conformance_report(
    report: Mapping[str, Any], application_root: Path,
    reviewed_freeze: Mapping[str, Any], realization_contract: Mapping[str, Any],
) -> bool:
    return dict(report) == validate_architecture_conformance(
        application_root, reviewed_freeze, realization_contract
    )
