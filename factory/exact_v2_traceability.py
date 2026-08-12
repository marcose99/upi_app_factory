from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence, cast

from factory.native_capability_prerun.engine import extract_text, inventory_obligations


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRACKED_APPLICATION_ROOT = (
    PROJECT_ROOT
    / "workspace"
    / "factory_generated"
    / "upi_dispute_resolution"
    / "generated_application"
)
AUTHORITATIVE_INPUT_ROOT = PROJECT_ROOT / "factory_governance" / "exact_v2_authoritative_inputs"
AUTHORITATIVE_REQUIREMENTS_PDF_PATH = (
    AUTHORITATIVE_INPUT_ROOT
    / "historical"
    / "r10"
    / "UPI_FAILED_DEBIT_BENEFICIARY_NOT_CREDITED_REQUIREMENTS.pdf"
)
AUTHORITATIVE_REQUIREMENTS_TEXT_PATH = (
    AUTHORITATIVE_INPUT_ROOT
    / "historical"
    / "r10"
    / "UPI_FAILED_DEBIT_BENEFICIARY_NOT_CREDITED_REQUIREMENTS.txt"
)
AUTHORITATIVE_R9_REQUIREMENTS_TEXT_PATH = (
    AUTHORITATIVE_INPUT_ROOT
    / "historical"
    / "r9"
    / "UPI_FAILED_DEBIT_BENEFICIARY_NOT_CREDITED_REQUIREMENTS.txt"
)
AUTHORITATIVE_VALIDATION_SUMMARY_PATH = AUTHORITATIVE_INPUT_ROOT / "validation_summary.json"
AUTHORITATIVE_INPUT_MANIFEST_PATH = AUTHORITATIVE_INPUT_ROOT / "manifest.json"
REQUIREMENTS_SCHEMA = "upi_failed_debit_no_credit.requirements.v2"
REQUIREMENTS_PDF_SHA256 = "37c94a02891e84b59e4071d68f1aafb968730a0c458cdf3092562a5a1ea9ea1c"
REQUIREMENTS_TEXT_SHA256 = "8a67787690640d4af932a266fc44e2a70348ac0785eb4f91b8842aa3c70b0d82"
VALIDATION_SUMMARY_SOURCE_SHA256 = "32fe0943a9c776ecdc09ebe5b515fc732cafdd50973ea343e8786ce7e1ad22ab"
VALIDATION_SUMMARY_SHA256 = "d877a2174908f9fa887ad9651027319231a4449d2065c3a043d5115b7c49c30d"
REJECTED_PROJECTION_SHA256 = "1c169ae23d3a95a1c37bd6b421da952c813f045b5b42215a94b2f329b6eea2ab"
REQUIREMENTS_PAGE_COUNT = 29
SCHEMA_VERSION = "upi-failed-debit-generated-application-evidence.v3"
ATOMIC_INVENTORY_SCHEMA = "upi-failed-debit-atomic-obligation-inventory-v1"
CANONICAL_APPLICATION_ID = "upi_failed_debit_no_credit"
COMPATIBILITY_APPLICATION_ID = "upi_dispute_resolution"
HUMAN_READABLE_NAME = "UPI Failed Debit — Beneficiary Not Credited"
SUPPORTED_STATUSES = {
    "SUPPORTED",
    "PARTIAL",
    "UNSUPPORTED",
    "NOT_APPLICABLE_WITH_JUSTIFICATION",
}
EVIDENCE_AUTHORITY = "obligation_specific_fail_closed"
PUBLICATION_AUTHORITY = True
DIAGNOSTIC_PROJECTION_USED = False
NO_GO_EVIDENCE_DECISION = "NO_GO_WITH_IMPROVEMENT_REQUIREMENTS"
PROVEN_EVIDENCE_DECISION = "ALL_MANDATORY_OBLIGATIONS_PROVEN"
HEADING_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\.\s+(?P<title>.+)$")
ENDPOINT_RE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)")
TRANSITION_RE = re.compile(r"\b([A-Z_]+)\s*->\s*([A-Z_]+)\b")
TOKEN_RE = re.compile(
    r"[A-Z][A-Z0-9_]{2,}"
    r"|[A-Z][a-zA-Z0-9]+(?:[A-Z][a-zA-Z0-9]+)+"
    r"|[a-z][a-z0-9]*(?:_[a-z0-9]+)+"
    r"|/[A-Za-z0-9{}._/-]+"
)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
}
GENERIC_BINDING_TERMS = frozenset(
    STOPWORDS
    | {
        "action",
        "actor",
        "actors",
        "agent",
        "allowed",
        "all",
        "amount",
        "any",
        "api",
        "append",
        "application",
        "approved",
        "audit",
        "bank",
        "beneficiary",
        "bounded",
        "call",
        "calls",
        "can",
        "cannot",
        "case",
        "cases",
        "certification",
        "claim",
        "claims",
        "classification",
        "classify",
        "close",
        "closed",
        "closure",
        "code",
        "command",
        "commands",
        "complete",
        "confirmed",
        "conflict",
        "contract",
        "control",
        "correlation",
        "create",
        "created",
        "credit",
        "current",
        "customer",
        "data",
        "database",
        "debit",
        "delete",
        "decision",
        "default",
        "deterministic",
        "digest",
        "disposition",
        "dispute",
        "disputes",
        "domain",
        "duration",
        "endpoint",
        "error",
        "evidence",
        "event",
        "every",
        "expected",
        "explicit",
        "factory",
        "failed",
        "final",
        "failure",
        "generic",
        "generated",
        "get",
        "governed",
        "health",
        "history",
        "human",
        "id",
        "identifier",
        "idempotency",
        "impact",
        "implementation",
        "infrastructure",
        "input",
        "integrity",
        "investigate",
        "investigation",
        "items",
        "key",
        "level",
        "local",
        "logging",
        "mandatory",
        "mapping",
        "may",
        "metrics",
        "missing",
        "mock",
        "must",
        "negative",
        "no",
        "not",
        "obligation",
        "object",
        "observability",
        "only",
        "operation",
        "operations",
        "output",
        "partial",
        "patch",
        "payload",
        "payer",
        "payment",
        "payments",
        "pending",
        "persistence",
        "positive",
        "post",
        "prevent",
        "process",
        "production",
        "profile",
        "prohibited",
        "proposed",
        "provider",
        "put",
        "quarantine",
        "rationale",
        "readiness",
        "ready",
        "real",
        "reason",
        "record",
        "records",
        "reference",
        "request",
        "requested",
        "required",
        "requirement",
        "resolution",
        "response",
        "result",
        "return",
        "review",
        "reviewer",
        "role",
        "runtime",
        "schema",
        "sequence",
        "service",
        "shall",
        "should",
        "simulated",
        "source",
        "startup",
        "state",
        "statement",
        "status",
        "summary",
        "support",
        "supported",
        "system",
        "test",
        "tests",
        "threshold",
        "transaction",
        "transactions",
        "transition",
        "type",
        "unit",
        "upi",
        "unsupported",
        "user",
        "value",
        "verification",
        "verified",
        "version",
        "where",
        "workflow",
        "work",
    }
)
BINDING_TYPES = frozenset({"endpoint", "identifier", "phrase", "state_transition"})

QUARANTINED_APPLICATION_SUBTREE = "current_definition_of_done"
_TRACKED_APPLICATION_RELATIVE_ROOT = Path(
    "workspace/factory_generated/upi_dispute_resolution/generated_application"
)
_QUARANTINED_SUBTREE_ARTIFACTS: tuple[str, ...] = (
    "docs/adr/ADR-0001-authoritative-failed-debit-runtime.md",
    "docs/persistence_reset_policy.md",
    "evidence/CAPABILITY_PRE_RUN_REPORT.json",
    "evidence/PRE_RUN_MANIFEST.json",
    "evidence/REQUIREMENT_CAPABILITY_MATRIX.json",
    "evidence/atomic_obligation_inventory.json",
    "evidence/classification_decision_table.json",
    "evidence/coverage_report.json",
    "evidence/evidence_manifest_description.json",
    "evidence/generation_summary.json",
    "evidence/openapi_inventory.json",
    "evidence/requirements_traceability_matrix.json",
    "evidence/residual_risk_register.json",
    "evidence/unsupported_obligation_report.json",
    "generation_metadata.json",
)
QUARANTINED_ARTIFACT_RELATIVE_PATHS: tuple[str, ...] = tuple(
    (
        _TRACKED_APPLICATION_RELATIVE_ROOT
        / QUARANTINED_APPLICATION_SUBTREE
        / relative_path
    ).as_posix()
    for relative_path in _QUARANTINED_SUBTREE_ARTIFACTS
)

REQUIRED_ARTIFACT_RELATIVE_PATHS: tuple[str, ...] = (
    "generation_metadata.json",
    "evidence/atomic_obligation_inventory.json",
    "evidence/requirements_traceability_matrix.json",
    "evidence/openapi_inventory.json",
    "evidence/CAPABILITY_PRE_RUN_REPORT.json",
    "evidence/REQUIREMENT_CAPABILITY_MATRIX.json",
    "evidence/PRE_RUN_MANIFEST.json",
    "evidence/classification_decision_table.json",
    "evidence/residual_risk_register.json",
    "evidence/unsupported_obligation_report.json",
    "evidence/evidence_manifest_description.json",
    "evidence/coverage_report.json",
    "evidence/generation_summary.json",
    "docs/persistence_reset_policy.md",
    "docs/adr/ADR-0001-authoritative-failed-debit-runtime.md",
    "requirements-bootstrap.lock",
    "requirements.lock",
    "dependency_contract.json",
    "scripts/bootstrap_cleanroom.sh",
    "scripts/validate_dependency_contract.py",
)

SECTION_REFERENCE_RULES: tuple[dict[str, Any], ...] = (
    {
        "sections": ("document_control", "1", "24", "28", "29", "30", "31", "32"),
        "implementation_paths": (
            "factory/generated_application_artifacts.py",
            "factory/exact_v2_traceability.py",
            "scripts/run_portal_requirements_driven_application_engineering.py",
        ),
        "test_references": (
            "tests/post_r9_5/test_exact_v2_traceability.py::ExactV2TraceabilityTest::test_materializer_reproduces_tracked_exact_v2_artifacts",
        ),
        "evidence_references": (
            "generation_metadata.json",
            "evidence/atomic_obligation_inventory.json",
            "evidence/requirements_traceability_matrix.json",
            "evidence/coverage_report.json",
            "evidence/unsupported_obligation_report.json",
            "evidence/CAPABILITY_PRE_RUN_REPORT.json",
            "evidence/REQUIREMENT_CAPABILITY_MATRIX.json",
            "evidence/PRE_RUN_MANIFEST.json",
            "evidence/openapi_inventory.json",
        ),
    },
    {
        "sections": ("2", "3", "4", "4.1", "4.2", "5", "6", "6.1", "6.2", "6.3", "6.4", "7", "7.1", "7.2"),
        "implementation_paths": (
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/application/services.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/domain/entities.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py",
        ),
        "test_references": (
            "tests/phase50/test_generated_runtime_failed_debit_workflow.py",
            "tests/post_r9_5/test_primary_portal_failed_debit_e2e.py::test_primary_portal_registers_and_proves_the_authoritative_failed_debit_runtime",
            "tests/post_r9_5/test_rejection_audit_actor_role.py::test_rejection_audit_chain_records_actor_role_and_redacted_failures",
        ),
        "evidence_references": (
            "docs/lld.md",
            "docs/workflow_state_machine.md",
            "docs/security_design.md",
        ),
    },
    {
        "sections": ("8", "8.1", "8.2", "8.3", "9", "9.1", "9.2", "9.3", "9.4", "10", "11", "12", "13", "14", "15", "16", "17", "18"),
        "implementation_paths": (
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/application/services.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/infrastructure/persistence/migrations.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/infrastructure/persistence/audit_log.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/error_handlers.py",
        ),
        "test_references": (
            "tests/phase50/test_generated_runtime_failed_debit_workflow.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/integration/test_transactional_integrity.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/unit/test_optimistic_concurrency.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/resilience/test_migrations_restart.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/resilience/test_runtime_lifecycle.py",
        ),
        "evidence_references": (
            "docs/lld.md",
            "docs/persistence_reset_policy.md",
            "docs/security_design.md",
            "docs/workflow_state_machine.md",
            "evidence/classification_decision_table.json",
        ),
    },
    {
        "sections": ("19", "19.1", "19.2", "19.3", "19.4"),
        "implementation_paths": (
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/error_handlers.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/schemas.py",
        ),
        "test_references": (
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/contract/test_api_identity_adapter_contract.py",
            "tests/post_r9_5/test_primary_portal_failed_debit_e2e.py::test_primary_portal_registers_and_proves_the_authoritative_failed_debit_runtime",
        ),
        "evidence_references": (
            "docs/api_contract.md",
            "evidence/openapi_inventory.json",
        ),
    },
    {
        "sections": ("20", "21", "22", "23", "25", "26", "26.1", "26.2", "26.3", "26.4", "26.5", "26.6", "26.7", "26.8", "26.9", "26.10", "27"),
        "implementation_paths": (
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/observability/metrics.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/security/identity.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/infrastructure/persistence/sqlite_unit_of_work.py",
        ),
        "test_references": (
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/contract/test_observability_contract.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/security/test_authorization_contract.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/security/test_control_plane_policy.py",
            "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/negative/test_negative_security_and_persistence.py",
            "tests/phase50/test_generated_runtime_failed_debit_workflow.py",
        ),
        "evidence_references": (
            "README.md",
            "docs/observability_design.md",
            "docs/security_design.md",
            "docs/runtime_runbook.md",
            "evidence/openapi_inventory.json",
        ),
    },
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _authority_fields() -> dict[str, Any]:
    return {
        "evidence_authority": EVIDENCE_AUTHORITY,
        "publication_authority": PUBLICATION_AUTHORITY,
        "diagnostic_projection_used": DIAGNOSTIC_PROJECTION_USED,
    }


def _is_authority_json_surface(relative_path: str) -> bool:
    return relative_path == "generation_metadata.json" or (
        relative_path.startswith("evidence/") and relative_path.endswith(".json")
    )


def _artifact_ref(relative_path: str) -> str:
    return (
        "workspace/factory_generated/upi_dispute_resolution/generated_application/"
        + relative_path
    )


def _tracked_application_root() -> str:
    return _TRACKED_APPLICATION_RELATIVE_ROOT.as_posix()


def is_quarantined_application_path(
    path: Path,
    *,
    project_root: Path | None = None,
) -> bool:
    candidate = path.resolve()
    quarantine_suffix = (
        _TRACKED_APPLICATION_RELATIVE_ROOT / QUARANTINED_APPLICATION_SUBTREE
    ).parts
    candidate_parts = candidate.parts
    if any(
        candidate_parts[index : index + len(quarantine_suffix)] == quarantine_suffix
        for index in range(len(candidate_parts) - len(quarantine_suffix) + 1)
    ):
        return True
    quarantine_root = (
        (project_root or PROJECT_ROOT).resolve()
        / _TRACKED_APPLICATION_RELATIVE_ROOT
        / QUARANTINED_APPLICATION_SUBTREE
    ).resolve()
    return candidate == quarantine_root or quarantine_root in candidate.parents


def _reject_quarantined_application_root(
    application_root: Path | None,
    *,
    project_root: Path,
) -> None:
    if application_root is not None and is_quarantined_application_path(
        application_root,
        project_root=project_root,
    ):
        raise ValueError(
            "current_definition_of_done is quarantined and cannot be an authoritative target"
        )


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\f", " ")).strip(" \t;")


def _slugify(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return lowered or "section"


def _section_key(section: str) -> str:
    match = HEADING_RE.match(section)
    if not match:
        return section
    return match.group("number")


def _logical_line_locations(text: str) -> dict[int, dict[str, Any]]:
    locations: dict[int, dict[str, Any]] = {}
    page_number = 1
    page_line = 0
    current_section = "document_control"
    for global_line, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        if "\f" in raw_line:
            locations[global_line] = {
                "page": page_number,
                "page_line": page_line + 1,
                "section": current_section,
            }
            page_number += raw_line.count("\f")
            page_line = 0
            continue
        page_line += 1
        stripped = raw_line.strip()
        match = HEADING_RE.match(stripped)
        if match:
            current_section = f"{match.group('number')}. {match.group('title')}"
        locations[global_line] = {
            "page": page_number,
            "page_line": page_line,
            "section": current_section,
        }
    return locations


def _validated_external_file(path: Path, *, expected_sha256: str, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} is missing: {resolved}")
    actual_sha256 = _sha256_file(resolved)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"{label} SHA-256 mismatch: {actual_sha256} != {expected_sha256}"
        )
    return resolved


def _load_authoritative_input_manifest() -> dict[str, Mapping[str, Any]]:
    payload = json.loads(AUTHORITATIVE_INPUT_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("authoritative input manifest must be a JSON object")
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        raise ValueError("authoritative input manifest files must be a list")
    indexed: dict[str, Mapping[str, Any]] = {}
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict):
            raise ValueError("authoritative input manifest entry must be an object")
        path = raw_entry.get("path")
        sha256 = raw_entry.get("sha256")
        provenance = raw_entry.get("provenance")
        if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError("authoritative input manifest path must be safe and relative")
        if not isinstance(sha256, str) or len(sha256) != 64:
            raise ValueError(f"authoritative input manifest has invalid sha256 for {path}")
        if not isinstance(provenance, str) or not provenance:
            raise ValueError(f"authoritative input manifest has invalid provenance for {path}")
        source_sha256 = raw_entry.get("source_sha256")
        if source_sha256 is not None and (
            not isinstance(source_sha256, str) or len(source_sha256) != 64
        ):
            raise ValueError(f"authoritative input manifest has invalid source_sha256 for {path}")
        indexed[path] = raw_entry
    return indexed


def _validated_authoritative_input(
    relative_path: str,
    *,
    expected_sha256: str,
    label: str,
) -> Path:
    manifest = _load_authoritative_input_manifest()
    entry = manifest.get(relative_path)
    if entry is None:
        raise FileNotFoundError(f"{label} is not declared in authoritative input manifest")
    if entry["sha256"] != expected_sha256:
        raise ValueError(
            f"{label} manifest SHA-256 mismatch: {entry['sha256']} != {expected_sha256}"
        )
    path = AUTHORITATIVE_INPUT_ROOT / relative_path
    return _validated_external_file(path, expected_sha256=expected_sha256, label=label)


def _authoritative_requirements_text() -> Path:
    _validated_authoritative_input(
        "historical/r10/UPI_FAILED_DEBIT_BENEFICIARY_NOT_CREDITED_REQUIREMENTS.pdf",
        expected_sha256=REQUIREMENTS_PDF_SHA256,
        label="authoritative requirements PDF",
    )
    return _validated_authoritative_input(
        "historical/r10/UPI_FAILED_DEBIT_BENEFICIARY_NOT_CREDITED_REQUIREMENTS.txt",
        expected_sha256=REQUIREMENTS_TEXT_SHA256,
        label="authoritative requirements text",
    )


def _current_validation_summary() -> dict[str, Any]:
    path = _validated_authoritative_input(
        "validation_summary.json",
        expected_sha256=VALIDATION_SUMMARY_SHA256,
        label="current validation summary",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("current validation summary must be a JSON object")
    return payload


def _read_text_document(requirements_document: Path) -> str:
    extracted = extract_text(requirements_document)
    normalized_text = str(extracted["text"])
    actual_sha = _sha256_bytes(normalized_text.encode("utf-8"))
    if actual_sha != REQUIREMENTS_TEXT_SHA256:
        raise ValueError(
            "authoritative requirements text SHA-256 mismatch: "
            f"{actual_sha} != {REQUIREMENTS_TEXT_SHA256}"
        )
    return normalized_text


def _extract_openapi_inventory(project_root: Path) -> dict[str, Any]:
    application_parent = (
        project_root
        / "workspace"
        / "factory_generated"
        / "upi_dispute_resolution"
    )
    main_path = (
        application_parent
        / "generated_application"
        / "app"
        / "interfaces"
        / "api"
        / "main.py"
    )
    # Keep exact-v2 evidence deterministic even when runtime dependencies are not
    # importable in the current environment.
    source_text = main_path.read_text(encoding="utf-8")
    endpoint_inventory = [
        {"method": method.upper(), "path": path}
        for method, path in re.findall(
            r'@app\.(get|post|put|patch|delete)\("([^"]+)"',
            source_text,
        )
    ]
    endpoint_inventory.extend(
        [
            {"method": "GET", "path": "/openapi.json"},
            {"method": "GET", "path": "/docs"},
        ]
    )
    deduplicated_routes = list(
        dict.fromkeys((item["method"], item["path"]) for item in endpoint_inventory)
    )
    endpoint_inventory = [
        {"method": method, "path": path} for method, path in deduplicated_routes
    ]
    endpoint_inventory.sort(key=lambda item: (item["path"], item["method"]))
    paths: dict[str, dict[str, dict[str, str]]] = {}
    for item in endpoint_inventory:
        paths.setdefault(item["path"], {})[item["method"].lower()] = {
            "operationId": f"{item['method']}_{item['path']}"
        }
    document = {
        "openapi": "3.1.0",
        "info": {
            "title": "Local UPI Dispute Resolution",
            "version": "source-parse-fallback",
        },
        "paths": paths,
    }
    openapi_text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    return {
        "schema_version": "upi-failed-debit-openapi-inventory.v1",
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "requirements_text_sha256": REQUIREMENTS_TEXT_SHA256,
        "canonical_application_id": CANONICAL_APPLICATION_ID,
        "compatibility_application_id": COMPATIBILITY_APPLICATION_ID,
        "catalogue_only_fallback_used": True,
        "openapi_sha256": _sha256_bytes(openapi_text.encode("utf-8")),
        "endpoint_inventory": endpoint_inventory,
    }


def _load_file_index(project_root: Path) -> dict[str, str]:
    indexed_paths = {
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/application/services.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/domain/entities.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/main.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/error_handlers.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/interfaces/api/schemas.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/infrastructure/persistence/audit_log.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/infrastructure/persistence/migrations.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/infrastructure/persistence/sqlite_unit_of_work.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/observability/metrics.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/security/identity.py",
        "tests/phase50/test_generated_runtime_failed_debit_workflow.py",
        "tests/post_r9_5/test_primary_portal_failed_debit_e2e.py",
        "tests/post_r9_5/test_rejection_audit_actor_role.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/contract/test_api_identity_adapter_contract.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/contract/test_observability_contract.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/integration/test_transactional_integrity.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/negative/test_negative_security_and_persistence.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/resilience/test_migrations_restart.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/resilience/test_runtime_lifecycle.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/security/test_authorization_contract.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/security/test_control_plane_policy.py",
        "workspace/factory_generated/upi_dispute_resolution/generated_application/app/tests/unit/test_optimistic_concurrency.py",
    }
    contents: dict[str, str] = {}
    for relative in sorted(indexed_paths):
        path = project_root / relative
        if path.is_file():
            contents[relative] = path.read_text(encoding="utf-8")
    return contents


def _test_reference_exists(project_root: Path, nodeid: str) -> bool:
    relative_path, _, target = nodeid.partition("::")
    path = project_root / relative_path
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    if not target:
        return bool(re.search(r"^\s*(?:async\s+)?def\s+test_", text, re.MULTILINE))
    for fragment in target.split("::"):
        if fragment not in text:
            return False
    return True


def _evidence_reference_exists(
    project_root: Path,
    relative_path: str,
    generated_relative_paths: set[str],
) -> bool:
    if relative_path in generated_relative_paths:
        return True
    return (project_root / _tracked_application_root() / relative_path).is_file()


def _section_rule(section: str) -> Mapping[str, Any]:
    key = _section_key(section)
    for rule in SECTION_REFERENCE_RULES:
        if key in rule["sections"] or section in rule["sections"]:
            return rule
    return SECTION_REFERENCE_RULES[0]


def _canonical_binding_text(value: str) -> str:
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    acronym_split = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", camel_split)
    return " ".join(re.findall(r"[a-z0-9]+", acronym_split.casefold()))


def _binding_tokens(value: str) -> tuple[str, ...]:
    return tuple(_canonical_binding_text(value).split())


def _binding_occurs(binding_key: str, source_text: str) -> bool:
    needle = _canonical_binding_text(binding_key)
    haystack = _canonical_binding_text(source_text)
    return bool(needle) and f" {needle} " in f" {haystack} "


def _binding_token_is_generic(token: str) -> bool:
    variants = {token}
    if token.endswith("s") and len(token) > 3:
        variants.add(token[:-1])
    if token.endswith("ies") and len(token) > 4:
        variants.add(token[:-3] + "y")
    return bool(variants & GENERIC_BINDING_TERMS)


def _binding_is_distinctive(binding_key: str) -> bool:
    tokens = _binding_tokens(binding_key)
    return bool(tokens) and any(not _binding_token_is_generic(token) for token in tokens)


def _binding_candidates(text: str) -> list[tuple[str, str]]:
    endpoint_match = ENDPOINT_RE.match(text)
    if endpoint_match:
        method, path = endpoint_match.groups()
        return [(f"{method.upper()} {path}", "endpoint")]

    transition_candidates = list(
        dict.fromkeys(
            f"{source_state} -> {target_state}"
            for source_state, target_state in TRANSITION_RE.findall(text)
        )
    )
    if transition_candidates:
        if len(transition_candidates) == 1:
            return [(transition_candidates[0], "state_transition")]
        return []

    identifier_candidates = list(
        dict.fromkeys(match.group(0) for match in TOKEN_RE.finditer(text))
    )
    canonical_identifiers = {
        _canonical_binding_text(identifier)
        for identifier in identifier_candidates
        if _canonical_binding_text(identifier)
    }
    compound_identifier_constraint = (
        len(canonical_identifiers) > 1
        and re.search(r"\b(?:and|or)\b", text, re.IGNORECASE) is not None
    )

    candidates: list[tuple[str, str]] = []
    if not compound_identifier_constraint:
        candidates.extend(
            (identifier, "identifier") for identifier in identifier_candidates
        )

    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", text)
    for width in range(min(5, len(words)), 1, -1):
        candidates.extend(
            (" ".join(words[index : index + width]), "phrase")
            for index in range(len(words) - width + 1)
        )

    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for binding_key, binding_type in candidates:
        canonical = _canonical_binding_text(binding_key)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        unique.append((binding_key, binding_type))
    return unique

def _paths_with_binding(
    canonical_file_index: Mapping[str, str],
    binding_key: str,
    section_candidates: Sequence[str],
) -> list[str]:
    needle = _canonical_binding_text(binding_key)
    if not needle:
        return []
    return [
        relative
        for relative in dict.fromkeys(section_candidates)
        if f" {needle} " in f" {canonical_file_index.get(relative, '')} "
    ]


def _verify_and_materialize_refs(
    project_root: Path,
    values: Iterable[str],
    *,
    mode: str,
    generated_relative_paths: set[str],
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for value in dict.fromkeys(values):
        if mode == "implementation":
            exists = (project_root / value).is_file()
        elif mode == "test":
            exists = _test_reference_exists(project_root, value)
        else:
            exists = _evidence_reference_exists(project_root, value, generated_relative_paths)
        if exists:
            record: dict[str, Any] = {"path": value}
            if mode == "implementation":
                record["sha256"] = _sha256_file(project_root / value)
            verified.append(record)
    return verified


def _build_support_reason(
    *,
    implementation_refs: Sequence[Mapping[str, Any]],
    test_refs: Sequence[Mapping[str, Any]],
    evidence_refs: Sequence[Mapping[str, Any]],
    openapi_verified: bool | None,
    support_binding: Mapping[str, Any] | None,
) -> str:
    if support_binding is not None and evidence_refs and openapi_verified is not False:
        return (
            "Current implementation and executable tests share obligation-specific binding "
            f"{support_binding['binding_key']!r}; evidence references were verified."
        )
    missing: list[str] = []
    if support_binding is None:
        missing.append("shared obligation-specific implementation/test binding")
    else:
        if not implementation_refs:
            missing.append("implementation")
        if not test_refs:
            missing.append("tests")
    if not evidence_refs:
        missing.append("evidence")
    if openapi_verified is False:
        missing.append("OpenAPI operation")
    return "Missing verified " + ", ".join(missing) + "."


def _classify_support(
    *,
    obligation: Mapping[str, Any],
    project_root: Path,
    openapi_inventory: Mapping[str, Any],
    file_index: Mapping[str, str],
    generated_relative_paths: set[str],
) -> dict[str, Any]:
    source = obligation["source"]
    rule = _section_rule(str(source["section"]))
    normalized_text = _normalize_whitespace(
        str(obligation.get("normalized_text", obligation.get("text", "")))
    )
    section_implementation_paths = list(rule["implementation_paths"])
    section_test_references = list(rule["test_references"])
    section_evidence_references = list(rule["evidence_references"])
    section_test_paths = [ref.partition("::")[0] for ref in section_test_references]
    canonical_file_index = {
        relative_path: _canonical_binding_text(file_index.get(relative_path, ""))
        for relative_path in dict.fromkeys(
            [*section_implementation_paths, *section_test_paths]
        )
    }

    support_binding: dict[str, Any] | None = None
    matched_paths: list[str] = []
    matched_test_paths: list[str] = []
    for binding_key, binding_type in _binding_candidates(normalized_text):
        if not _binding_is_distinctive(binding_key):
            continue
        candidate_paths = _paths_with_binding(
            canonical_file_index,
            binding_key,
            section_implementation_paths,
        )
        candidate_test_paths = _paths_with_binding(
            canonical_file_index,
            binding_key,
            section_test_paths,
        )
        matched_paths.extend(candidate_paths)
        matched_test_paths.extend(candidate_test_paths)
        if support_binding is None and candidate_paths and candidate_test_paths:
            binding_test_references = [
                reference
                for reference in section_test_references
                if reference.partition("::")[0] in candidate_test_paths
            ]
            support_binding = {
                "binding_key": binding_key,
                "binding_type": binding_type,
                "implementation_paths": list(dict.fromkeys(candidate_paths)),
                "test_references": list(dict.fromkeys(binding_test_references)),
            }

    if support_binding is not None:
        matched_paths = list(support_binding["implementation_paths"])
        matched_test_paths = [
            reference.partition("::")[0]
            for reference in support_binding["test_references"]
        ]
    else:
        matched_paths = list(dict.fromkeys(matched_paths))
        matched_test_paths = list(dict.fromkeys(matched_test_paths))
    implementation_refs = _verify_and_materialize_refs(
        project_root,
        matched_paths,
        mode="implementation",
        generated_relative_paths=generated_relative_paths,
    )
    verified_test_candidates = [
        reference
        for reference in section_test_references
        if reference.partition("::")[0] in matched_test_paths
    ]
    test_refs = _verify_and_materialize_refs(
        project_root,
        verified_test_candidates,
        mode="test",
        generated_relative_paths=generated_relative_paths,
    )
    evidence_refs = _verify_and_materialize_refs(
        project_root,
        section_evidence_references,
        mode="evidence",
        generated_relative_paths=generated_relative_paths,
    )
    if support_binding is not None:
        binding_key = str(support_binding["binding_key"])
        bound_implementation_paths = [
            str(reference["path"])
            for reference in implementation_refs
            if _binding_occurs(
                binding_key,
                (project_root / str(reference["path"])).read_text(encoding="utf-8"),
            )
        ]
        bound_test_references = [
            str(reference["path"])
            for reference in test_refs
            if _binding_occurs(
                binding_key,
                (
                    project_root
                    / str(reference["path"]).partition("::")[0]
                ).read_text(encoding="utf-8"),
            )
        ]
        if bound_implementation_paths and bound_test_references:
            support_binding["implementation_paths"] = bound_implementation_paths
            support_binding["test_references"] = bound_test_references
            implementation_refs = [
                reference
                for reference in implementation_refs
                if reference["path"] in bound_implementation_paths
            ]
            test_refs = [
                reference
                for reference in test_refs
                if reference["path"] in bound_test_references
            ]
        else:
            support_binding = None

    openapi_verified: bool | None = None
    endpoint_match = ENDPOINT_RE.match(normalized_text)
    if endpoint_match:
        method, path = endpoint_match.groups()
        endpoint_inventory = {
            (str(item.get("method", "")).upper(), str(item.get("path", "")))
            for item in cast(list[dict[str, Any]], openapi_inventory.get("endpoint_inventory", []))
        }
        openapi_verified = (method.upper(), path) in endpoint_inventory
    elif "/v1/disputes" in normalized_text or normalized_text.startswith(("GET /", "POST /")):
        openapi_verified = False

    if "where supported" in normalized_text.casefold() and not implementation_refs:
        support_status = "NOT_APPLICABLE_WITH_JUSTIFICATION"
        reason = "The requirement is explicitly conditional and no supported implementation surface was found."
    elif support_binding is not None and evidence_refs and openapi_verified is not False:
        support_status = "SUPPORTED"
        reason = _build_support_reason(
            implementation_refs=implementation_refs,
            test_refs=test_refs,
            evidence_refs=evidence_refs,
            openapi_verified=openapi_verified,
            support_binding=support_binding,
        )
    elif implementation_refs or test_refs or evidence_refs:
        support_status = "PARTIAL"
        reason = _build_support_reason(
            implementation_refs=implementation_refs,
            test_refs=test_refs,
            evidence_refs=evidence_refs,
            openapi_verified=openapi_verified,
            support_binding=None,
        )
    else:
        support_status = "UNSUPPORTED"
        reason = "No current verified implementation, test, or evidence references matched this obligation."

    return {
        "support_status": support_status,
        "support_reason": reason,
        "implementation_refs": implementation_refs,
        "test_refs": test_refs,
        "evidence_refs": evidence_refs,
        "openapi_verified": openapi_verified,
        "support_binding": support_binding if support_status == "SUPPORTED" else None,
    }



def _demote_shared_support_bindings(items: Sequence[dict[str, Any]]) -> None:
    supported_by_binding: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("support_status") != "SUPPORTED":
            continue
        binding = item.get("support_binding")
        if not isinstance(binding, dict):
            continue
        binding_key = binding.get("binding_key")
        if not isinstance(binding_key, str):
            continue
        canonical = _canonical_binding_text(binding_key)
        if canonical:
            supported_by_binding.setdefault(canonical, []).append(item)

    for rows in supported_by_binding.values():
        obligation_texts = {
            _canonical_binding_text(str(row.get("normalized_text", "")))
            for row in rows
        }
        if len(rows) < 2 or len(obligation_texts) < 2:
            continue
        obligation_ids = sorted(str(row.get("obligation_id", "")) for row in rows)
        for row in rows:
            binding = row.get("support_binding")
            binding_key = (
                str(binding.get("binding_key"))
                if isinstance(binding, dict)
                else "<invalid>"
            )
            row["support_status"] = "PARTIAL"
            row["support_reason"] = (
                f"Binding {binding_key!r} is shared across distinct atomic obligations "
                f"{obligation_ids}; fail-closed obligation-specific proof is absent."
            )
            row["support_binding"] = None


def _validate_inventory_support_bindings(
    items: Sequence[Mapping[str, Any]],
    *,
    project_root: Path,
    openapi_inventory: Mapping[str, Any],
) -> None:
    required_fields = {
        "binding_key",
        "binding_type",
        "implementation_paths",
        "test_references",
    }
    endpoint_inventory = {
        (str(item.get("method", "")).upper(), str(item.get("path", "")))
        for item in cast(
            list[dict[str, Any]],
            openapi_inventory.get("endpoint_inventory", []),
        )
    }
    supported_binding_owner: dict[str, str] = {}
    for item in items:
        if item.get("support_status") != "SUPPORTED":
            continue
        support_binding = item.get("support_binding")
        if not isinstance(support_binding, dict):
            continue
        binding_key = support_binding.get("binding_key")
        if not isinstance(binding_key, str):
            continue
        canonical = _canonical_binding_text(binding_key)
        obligation_id = str(item.get("obligation_id", ""))
        prior_owner = supported_binding_owner.get(canonical)
        if prior_owner is not None and prior_owner != obligation_id:
            raise ValueError(
                "supported binding is reused across distinct atomic obligations"
            )
        supported_binding_owner[canonical] = obligation_id

    for item in items:
        support_status = item.get("support_status")
        support_binding = item.get("support_binding")
        if support_status != "SUPPORTED":
            if support_binding is not None:
                raise ValueError("non-supported obligation cannot have a support binding")
            continue
        if not isinstance(support_binding, dict) or set(support_binding) != required_fields:
            raise ValueError("supported obligation has an invalid support binding object")
        binding_key = support_binding.get("binding_key")
        binding_type = support_binding.get("binding_type")
        implementation_paths = support_binding.get("implementation_paths")
        test_references = support_binding.get("test_references")
        if not isinstance(binding_key, str) or not _binding_is_distinctive(binding_key):
            raise ValueError("supported obligation binding key is generic or invalid")
        if binding_type not in BINDING_TYPES:
            raise ValueError("supported obligation binding type is invalid")
        if not _binding_occurs(binding_key, str(item.get("normalized_text", ""))):
            raise ValueError("support binding is not tied to the obligation text")
        if (
            not isinstance(implementation_paths, list)
            or not implementation_paths
            or not all(isinstance(path, str) for path in implementation_paths)
        ):
            raise ValueError("support binding implementation paths are invalid")
        if (
            not isinstance(test_references, list)
            or not test_references
            or not all(isinstance(reference, str) for reference in test_references)
        ):
            raise ValueError("support binding test references are invalid")
        if list(item.get("implementation_paths", [])) != implementation_paths:
            raise ValueError("support binding implementation paths disagree with inventory")
        if list(item.get("test_references", [])) != test_references:
            raise ValueError("support binding test references disagree with inventory")
        for relative_path in implementation_paths:
            path = project_root / relative_path
            if not path.is_file() or not _binding_occurs(
                binding_key,
                path.read_text(encoding="utf-8"),
            ):
                raise ValueError("support binding is absent from implementation")
        for nodeid in test_references:
            relative_path = nodeid.partition("::")[0]
            path = project_root / relative_path
            if not _test_reference_exists(project_root, nodeid) or not _binding_occurs(
                binding_key,
                path.read_text(encoding="utf-8"),
            ):
                raise ValueError("support binding is absent from executable test source")
        if binding_type == "endpoint":
            endpoint_match = ENDPOINT_RE.fullmatch(binding_key)
            if endpoint_match is None or endpoint_match.groups() not in endpoint_inventory:
                raise ValueError("endpoint support binding lacks exact OpenAPI verification")


def build_atomic_obligation_inventory(
    requirements_document: Path,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or PROJECT_ROOT).resolve()
    text = _read_text_document(requirements_document)
    raw_obligations = inventory_obligations(text, application_id=CANONICAL_APPLICATION_ID)
    locations = _logical_line_locations(text)
    ordinals_by_section: dict[str, int] = {}
    openapi_inventory = _extract_openapi_inventory(root)
    file_index = _load_file_index(root)
    generated_relative_paths = set(REQUIRED_ARTIFACT_RELATIVE_PATHS)
    items: list[dict[str, Any]] = []
    for raw in raw_obligations:
        line_number = int(raw["source_location"]["line"])
        source = locations[line_number]
        section = str(source["section"])
        ordinal = ordinals_by_section.get(section, 0) + 1
        ordinals_by_section[section] = ordinal
        obligation_id = (
            f"OBL-P{int(source['page']):02d}-"
            f"{_slugify(_section_key(section))}-"
            f"{ordinal:03d}"
        )
        support = _classify_support(
            obligation=raw
            | {
                "source": {
                    "page": source["page"],
                    "section": section,
                    "ordinal": ordinal,
                    "page_line": source["page_line"],
                }
            },
            project_root=root,
            openapi_inventory=openapi_inventory,
            file_index=file_index,
            generated_relative_paths=generated_relative_paths,
        )
        if support["support_status"] not in SUPPORTED_STATUSES:
            raise ValueError("unexpected support status")
        items.append(
            {
                "obligation_id": obligation_id,
                "source": {
                    "page": int(source["page"]),
                    "section": section,
                    "ordinal": ordinal,
                    "page_line": int(source["page_line"]),
                },
                "normalized_text": _normalize_whitespace(str(raw["text"])),
                "normative_terms": list(raw.get("keywords", [])),
                "mandatory": bool(raw.get("mandatory", True)),
                "support_status": support["support_status"],
                "support_reason": support["support_reason"],
                "support_binding": support["support_binding"],
                "implementation_paths": [
                    ref["path"] for ref in support["implementation_refs"]
                ],
                "test_references": [ref["path"] for ref in support["test_refs"]],
                "evidence_references": [
                    ref["path"] if ref["path"] in generated_relative_paths else _artifact_ref(ref["path"])
                    if not ref["path"].startswith("workspace/")
                    else ref["path"]
                    for ref in support["evidence_refs"]
                ],
            }
        )
    _demote_shared_support_bindings(items)
    _validate_inventory_support_bindings(
        items,
        project_root=root,
        openapi_inventory=openapi_inventory,
    )
    decision = "NO_GO" if any(
        item["mandatory"] and item["support_status"] in {"PARTIAL", "UNSUPPORTED"}
        for item in items
    ) else "GO"
    return {
        **_authority_fields(),
        "schema_version": ATOMIC_INVENTORY_SCHEMA,
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "requirements_pdf_sha256": REQUIREMENTS_PDF_SHA256,
        "requirements_text_sha256": REQUIREMENTS_TEXT_SHA256,
        "canonical_application_id": CANONICAL_APPLICATION_ID,
        "compatibility_application_id": COMPATIBILITY_APPLICATION_ID,
        "compatibility_mapping": {
            "canonical_application_id": CANONICAL_APPLICATION_ID,
            "runtime_compatibility_id": COMPATIBILITY_APPLICATION_ID,
            "mapping_reason": "The repository tracks the generated application under the governed compatibility identifier.",
        },
        "human_readable_application_name": HUMAN_READABLE_NAME,
        "mandatory_obligation_count": len(items),
        "decision": decision,
        "items": items,
    }


def load_tracked_atomic_obligation_inventory(project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or PROJECT_ROOT).resolve()
    path = root / _tracked_application_root() / "evidence" / "atomic_obligation_inventory.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing tracked atomic inventory: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("tracked atomic inventory is malformed")
    return payload


def _summarize_inventory(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    summary = {
        "SUPPORTED": 0,
        "PARTIAL": 0,
        "UNSUPPORTED": 0,
        "NOT_APPLICABLE_WITH_JUSTIFICATION": 0,
    }
    for item in items:
        summary[str(item["support_status"])] += 1
    return summary


def _unsupported_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "obligation_id": item["obligation_id"],
            "source": item["source"],
            "normalized_text": item["normalized_text"],
            "support_status": item["support_status"],
            "support_reason": item["support_reason"],
        }
        for item in items
        if item["mandatory"] and item["support_status"] in {"PARTIAL", "UNSUPPORTED"}
    ]


def _mandatory_gate_passed(items: Sequence[Mapping[str, Any]]) -> bool:
    return all(
        not item["mandatory"]
        or item["support_status"]
        in {"SUPPORTED", "NOT_APPLICABLE_WITH_JUSTIFICATION"}
        for item in items
    )


def _traceability_items(
    project_root: Path,
    inventory_items: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory_items:
        implementation_refs = [
            {"path": path, "sha256": _sha256_file(project_root / path)}
            for path in item["implementation_paths"]
            if (project_root / path).is_file()
        ]
        rows.append(
            {
                "obligation_id": item["obligation_id"],
                "source": dict(item["source"]),
                "normalized_text": item["normalized_text"],
                "normative_terms": list(item["normative_terms"]),
                "mandatory": item["mandatory"],
                "support_status": item["support_status"],
                "support_reason": item["support_reason"],
                "support_binding": item["support_binding"],
                "implementation_refs": implementation_refs,
                "test_refs": list(item["test_references"]),
                "evidence_refs": list(item["evidence_references"]),
            }
        )
    return rows


def _classification_decision_table(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "upi-failed-debit-classification-decision-table.v3",
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "items": [
            {
                "obligation_id": item["obligation_id"],
                "support_status": item["support_status"],
                "mandatory": item["mandatory"],
                "decision_basis": item["support_reason"],
                "support_binding": item["support_binding"],
            }
            for item in items
        ],
    }


def _residual_risk_register(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    unsupported = _unsupported_items(items)
    top_items = unsupported[:10]
    return {
        "schema_version": "upi-failed-debit-residual-risk-register.v3",
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "decision": "NO_GO" if unsupported else "GO",
        "items": [
            {
                "risk_id": "RR-001",
                "title": "Unsupported or partially verified mandatory obligations remain",
                "status": "OPEN" if unsupported else "CLOSED",
                "residual_risk": (
                    f"{len(unsupported)} mandatory obligations remain partial or unsupported."
                    if unsupported
                    else "No partial or unsupported mandatory obligations remain."
                ),
                "mitigation_refs": [
                    _artifact_ref("evidence/unsupported_obligation_report.json"),
                    _artifact_ref("evidence/requirements_traceability_matrix.json"),
                ],
                "sample_obligations": [item["obligation_id"] for item in top_items],
            },
            {
                "risk_id": "RR-002",
                "title": "Mock-only external ecosystem boundary",
                "status": "ACCEPTED_WITH_BOUNDARY",
                "residual_risk": "The runtime remains local-only and mock-only and does not prove live payment ecosystem behaviour.",
                "mitigation_refs": [
                    _artifact_ref("docs/security_design.md"),
                    _artifact_ref("docs/persistence_reset_policy.md"),
                ],
            },
        ],
    }


def _coverage_report(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary = _summarize_inventory(items)
    mandatory_no_go_count = len(_unsupported_items(items))
    coverage_status = (
        "NO_GO_UNSUPPORTED_MANDATORY_OBLIGATIONS"
        if mandatory_no_go_count
        else "TRACEABLE_GO_CANDIDATE"
    )
    return {
        "schema_version": "upi-failed-debit-coverage-report.v3",
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "requirements_text_sha256": REQUIREMENTS_TEXT_SHA256,
        "coverage_status": coverage_status,
        "summary": {
            "obligation_count": len(items),
            "supported_count": summary["SUPPORTED"],
            "partial_count": summary["PARTIAL"],
            "unsupported_count": summary["UNSUPPORTED"],
            "not_applicable_count": summary["NOT_APPLICABLE_WITH_JUSTIFICATION"],
            "mandatory_no_go_count": mandatory_no_go_count,
        },
    }


def _generation_summary(
    project_root: Path,
    items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validation_summary = _current_validation_summary()
    summary = _summarize_inventory(items)
    source_hash_paths = (
        "factory/exact_v2_traceability.py",
        "factory/generated_application_artifacts.py",
        "factory/native_capability_prerun/improvement_workflow.py",
        "factory/operator_portal/local_web_api.py",
        "factory/token_economics/service.py",
        "scripts/run_portal_requirements_driven_application_engineering.py",
    )
    mandatory_no_go_count = len(_unsupported_items(items))
    mandatory_gate_passed = _mandatory_gate_passed(items)
    return {
        **_authority_fields(),
        "schema_version": "upi-failed-debit-generation-summary.v4",
        "status": (
            "definition_of_done_ready"
            if mandatory_no_go_count == 0
            else "definition_of_done_blocked"
        ),
        "phase": "governed_self_improvement",
        "run_id": "r10_1_exact_input_obligation_specific_evidence",
        "decision": (
            PROVEN_EVIDENCE_DECISION
            if mandatory_gate_passed
            else NO_GO_EVIDENCE_DECISION
        ),
        "mandatory_gate_passed": mandatory_gate_passed,
        "canonical_application_id": CANONICAL_APPLICATION_ID,
        "compatibility_application_id": COMPATIBILITY_APPLICATION_ID,
        "authoritative_requirements": {
            "schema": REQUIREMENTS_SCHEMA,
            "pdf_path": f"external_authoritative_input/{AUTHORITATIVE_REQUIREMENTS_PDF_PATH.name}",
            "pdf_sha256": REQUIREMENTS_PDF_SHA256,
            "text_path": f"external_authoritative_input/{AUTHORITATIVE_REQUIREMENTS_TEXT_PATH.name}",
            "text_sha256": REQUIREMENTS_TEXT_SHA256,
            "pages": REQUIREMENTS_PAGE_COUNT,
        },
        "current_validation_summary": {
            "path": f"external_validation/{AUTHORITATIVE_VALIDATION_SUMMARY_PATH.name}",
            "sha256": VALIDATION_SUMMARY_SHA256,
            "source_sha256": VALIDATION_SUMMARY_SOURCE_SHA256,
            "phase": validation_summary.get("phase"),
            "status": validation_summary.get("status"),
            "all_gates_executed": validation_summary.get("all_gates_executed"),
            "passed_tests": validation_summary.get("passed_tests"),
            "collected_tests": validation_summary.get("collected_tests"),
            "recorded_at_utc": validation_summary.get("recorded_at_utc"),
            "candidate_projection_unchanged": validation_summary.get(
                "candidate_projection_unchanged"
            ),
        },
        "exact_input_traceability": {
            "decision": "GO" if mandatory_no_go_count == 0 else "NO_GO",
            "supported_count": summary["SUPPORTED"],
            "partial_count": summary["PARTIAL"],
            "unsupported_count": summary["UNSUPPORTED"],
            "not_applicable_count": summary["NOT_APPLICABLE_WITH_JUSTIFICATION"],
        },
        "source_hashes": {
            path: _sha256_file(project_root / path)
            for path in source_hash_paths
            if (project_root / path).is_file()
        },
        "mock_boundary": "enforced",
        "no_live_integrations": True,
        "no_real_customer_data": True,
        "real_payment_calls": "disabled",
        "certification_posture": "certification-ready-not-certified",
    }


def _unsupported_report(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    unsupported = _unsupported_items(items)
    return {
        "schema_version": "upi-failed-debit-unsupported-obligation-report.v3",
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "requirements_text_sha256": REQUIREMENTS_TEXT_SHA256,
        "unsupported_obligation_count": len(unsupported),
        "status": "UNSUPPORTED_OR_PARTIAL_MANDATORY_OBLIGATIONS_PRESENT" if unsupported else "NONE",
        "items": unsupported,
    }


def _prerun_report(
    items: Sequence[Mapping[str, Any]],
    *,
    project_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    matrix_items = [
        {
            "id": item["obligation_id"],
            "requirement_id": item["obligation_id"],
            "source_location": item["source"],
            "text": item["normalized_text"],
            "classification": item["support_status"],
            "fulfillable": item["support_status"] == "SUPPORTED",
            "mandatory": item["mandatory"],
            "reason": item["support_reason"],
            "reasons": [item["support_reason"]],
            "support_binding": item["support_binding"],
            "proof_mode": "exact_text",
            "matched_by": [{"kind": "exact_text", "value": item["normalized_text"]}],
            "matched_capabilities": [],
            "evidence": [
                {"path": path}
                for path in list(item["implementation_paths"]) + list(item["test_references"])
            ],
            "proof_trace": {
                "explicit_requirement_binding": True,
                "implementation_evidence": list(item["implementation_paths"]),
                "automated_test_evidence": list(item["test_references"]),
                "additional_evidence": list(item["evidence_references"]),
                "support_binding": item["support_binding"],
                "requirement_to_code_and_test_complete": (
                    item["support_status"] == "SUPPORTED"
                ),
            },
        }
        for item in items
    ]
    mandatory_gate_passed = _mandatory_gate_passed(items)
    decision = (
        PROVEN_EVIDENCE_DECISION
        if mandatory_gate_passed
        else NO_GO_EVIDENCE_DECISION
    )
    report = {
        **_authority_fields(),
        "schema_version": "native-capability-prerun.v1",
        "artifact": "CAPABILITY_PRE_RUN_REPORT",
        "application_id": CANONICAL_APPLICATION_ID,
        "compatibility_application_id": COMPATIBILITY_APPLICATION_ID,
        "requirements_sha256": REQUIREMENTS_TEXT_SHA256,
        "status": decision,
        "decision": decision,
        "mandatory_gate_passed": mandatory_gate_passed,
        "obligation_count": len(matrix_items),
        "summary": {
            "supported_count": sum(1 for item in items if item["support_status"] == "SUPPORTED"),
            "partial_count": sum(1 for item in items if item["support_status"] == "PARTIAL"),
            "unsupported_count": sum(1 for item in items if item["support_status"] == "UNSUPPORTED"),
        },
        "obligations": matrix_items,
        "factory_identity": {
            "head": os.environ.get("UPI_APP_FACTORY_SOURCE_COMMIT", "unavailable"),
            "tracked_application_root": _tracked_application_root(),
        },
        "requirements_path": "authoritative_exact_text",
        "requirements_size_bytes": len(json.dumps(items, sort_keys=True)),
    }
    matrix = {
        **_authority_fields(),
        "schema_version": "native-capability-prerun.v1",
        "artifact": "REQUIREMENT_CAPABILITY_MATRIX",
        "application_id": CANONICAL_APPLICATION_ID,
        "compatibility_application_id": COMPATIBILITY_APPLICATION_ID,
        "requirements_sha256": REQUIREMENTS_TEXT_SHA256,
        "obligation_count": len(matrix_items),
        "atomic_obligation_count": len(matrix_items),
        "items": matrix_items,
        "requirements": matrix_items,
        "decision": decision,
        "mandatory_gate_passed": mandatory_gate_passed,
    }
    manifest = {
        **_authority_fields(),
        "schema_version": "native-capability-prerun.v1",
        "artifact": "PRE_RUN_MANIFEST",
        "application_id": CANONICAL_APPLICATION_ID,
        "compatibility_application_id": COMPATIBILITY_APPLICATION_ID,
        "requirements_sha256": REQUIREMENTS_TEXT_SHA256,
        "decision": decision,
        "mandatory_gate_passed": mandatory_gate_passed,
        "artifacts": [
            "CAPABILITY_PRE_RUN_REPORT.json",
            "REQUIREMENT_CAPABILITY_MATRIX.json",
            "PRE_RUN_MANIFEST.json",
        ],
        "tracked_application_root": _tracked_application_root(),
    }
    return report, matrix, manifest


def _generation_metadata(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    summary = _summarize_inventory(items)
    return {
        **_authority_fields(),
        "schema_version": SCHEMA_VERSION,
        "canonical_application_id": CANONICAL_APPLICATION_ID,
        "compatibility_application_id": COMPATIBILITY_APPLICATION_ID,
        "human_readable_application_name": HUMAN_READABLE_NAME,
        "requirements_lineage": {
            "schema": REQUIREMENTS_SCHEMA,
            "supplied_pdf_sha256": REQUIREMENTS_PDF_SHA256,
            "supplied_text_sha256": REQUIREMENTS_TEXT_SHA256,
            "rejected_projection_sha256": REJECTED_PROJECTION_SHA256,
        },
        "compatibility_mapping": {
            "canonical_application_id": CANONICAL_APPLICATION_ID,
            "runtime_compatibility_id": COMPATIBILITY_APPLICATION_ID,
            "mapping_reason": "The tracked runtime root retains the governed compatibility identifier while the exact requirement package binds the canonical ID.",
        },
        "materialization_strategy": "deterministic_exact_input_atomic_obligation_inventory",
        "llm_calls": 0,
        "real_payment_calls": "disabled",
        "certification_posture": "certification-ready-not-certified",
        "production_posture": "not production-ready",
        "requirements_summary": summary,
        "tracked_application_root": _tracked_application_root(),
    }


def _manifest_description() -> dict[str, Any]:
    descriptions = {
        "generation_metadata.json": "Canonical identity, compatibility mapping, and truthful exact-input lineage metadata.",
        "evidence/atomic_obligation_inventory.json": "Atomic obligation inventory derived from the exact authoritative requirements text.",
        "evidence/requirements_traceability_matrix.json": "Per-obligation implementation, test, and evidence traceability.",
        "evidence/openapi_inventory.json": "Runtime-derived OpenAPI endpoint inventory and checksum.",
        "evidence/CAPABILITY_PRE_RUN_REPORT.json": "Current capability pre-run conclusion derived from actual obligation classifications.",
        "evidence/REQUIREMENT_CAPABILITY_MATRIX.json": "Current capability matrix derived from actual obligation classifications.",
        "evidence/PRE_RUN_MANIFEST.json": "Current capability pre-run manifest.",
        "evidence/classification_decision_table.json": "Per-obligation support-status classification decisions.",
        "evidence/residual_risk_register.json": "Truthful residual risks preserved after exact-input classification.",
        "evidence/unsupported_obligation_report.json": "Mandatory obligations still partial or unsupported.",
        "evidence/evidence_manifest_description.json": "Descriptions and checksums for the exact-v2 evidence pack.",
        "evidence/coverage_report.json": "Truthful exact-v2 support-status coverage summary.",
        "evidence/generation_summary.json": "Definition-of-done status bound to authoritative requirements, validation evidence, and obligation-specific support.",
        "docs/persistence_reset_policy.md": "Persistence and deterministic reset boundaries.",
        "docs/adr/ADR-0001-authoritative-failed-debit-runtime.md": "Architecture decision grounding the authoritative failed-debit runtime.",
        "requirements-bootstrap.lock": "Exact packaging-tool bootstrap contract for independent clean-room replay.",
        "requirements.lock": "Exact third-party dependency closure for the authoritative generated runtime and tests.",
        "dependency_contract.json": "Machine-checkable dependency and clean-room handover contract.",
        "scripts/bootstrap_cleanroom.sh": "Independent local virtual-environment bootstrap using generated-app-owned locks.",
        "scripts/validate_dependency_contract.py": "Fail-closed generated-app dependency validator.",
    }
    return {
        **_authority_fields(),
        "schema_version": "upi-failed-debit-evidence-manifest-description.v3",
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "requirements_text_sha256": REQUIREMENTS_TEXT_SHA256,
        "tracked_application_root": _tracked_application_root(),
        "artifacts": [
            {"path": path, "description": description}
            for path, description in descriptions.items()
        ],
    }


ADR_TEXT = """# ADR-0001: Authoritative Failed-Debit Runtime

## Status

Accepted

## Context

The exact v2 requirement package binds the canonical application identity
`upi_failed_debit_no_credit`, while the repository still tracks the generated
runtime under the governed compatibility identifier `upi_dispute_resolution`.
Traceability therefore has to preserve both identifiers without overclaiming
full exact-v2 support.

## Decision

Use a deterministic exact-input atomic obligation inventory as the source for
truthful traceability. Keep the authoritative failed-debit runtime as the
published implementation surface, keep compatibility mapping explicit in the
generated evidence, and derive GO or NO_GO from actual supported, partial, and
unsupported mandatory obligations.

## Consequences

- The canonical and compatibility identifiers are both recorded.
- Exact-input obligation coverage is computed rather than hard-coded.
- Any partial or unsupported mandatory obligation yields a governed NO_GO.
- Evidence references are verified before they are emitted.
"""

PERSISTENCE_RESET_POLICY = """# Persistence And Reset Policy

The generated application remains local-first, deterministic-first, and
mock-only.

## Durable State

- SQLite runtime state remains inside the generated application state root.
- Audit-chain records remain append-only under the local deterministic runtime.
- Exact-v2 evidence artifacts are repository-owned validation evidence and are
  rematerialized deterministically.

## Reset Rules

- Reset operations apply only to disposable local demonstration state.
- Deterministic evidence regeneration must not require external network access.
- Runtime execution must not mutate tracked source files.

## Non-Claims

- No live payment-rail, bank, PSP, NPCI, or identity-provider state is stored.
- This policy does not claim production retention, regulatory approval, or
  certification.
"""


GENERATED_APP_REQUIREMENTS_BOOTSTRAP = '# Governed recipient bootstrap lock.\n# Exact packaging-tool pins prevent a fresh recipient virtual environment from\n# inheriting an obsolete vulnerable setuptools from the host Python installation.\npip==26.1.2\nsetuptools==83.0.0\nwheel==0.47.0\n'
GENERATED_APP_REQUIREMENTS_LOCK = '# Exact third-party dependency closure for the authoritative generated application.\n# Derived from executable imports/tests and the V3-qualified recipient environment.\nannotated-doc==0.0.4\nannotated-types==0.7.0\nanyio==4.14.1\ncertifi==2026.6.17\nclick==8.4.2\nexceptiongroup==1.3.1\nfastapi==0.139.0\nh11==0.16.0\nhttpcore==1.0.9\nhttpx==0.28.1\nidna==3.18\niniconfig==2.3.0\npackaging==26.2\npluggy==1.6.0\npydantic==2.13.4\npydantic_core==2.46.4\nPygments==2.20.0\npytest==9.1.1\nstarlette==1.3.1\ntomli==2.4.1\ntyping_extensions==4.16.0\ntyping-inspection==0.4.2\nuvicorn==0.50.0\n'
GENERATED_APP_DEPENDENCY_CONTRACT = '{\n  "application_id": "upi_dispute_resolution",\n  "bootstrap_lock_sha256": "17ab1e8492376e363e619e3ae9473e8624f654c335fc4a696ccd1480ed797ef4",\n  "certification_claimed": false,\n  "derivation": {\n    "resolver": "importlib.metadata.packages_distributions",\n    "runtime_distributions": [\n      "fastapi",\n      "pydantic",\n      "starlette",\n      "uvicorn"\n    ],\n    "runtime_import_to_distribution": {\n      "fastapi": "fastapi",\n      "pydantic": "pydantic",\n      "starlette": "starlette",\n      "uvicorn": "uvicorn"\n    },\n    "runtime_imports": [\n      "fastapi",\n      "pydantic",\n      "starlette",\n      "uvicorn"\n    ],\n    "runtime_scan_excludes_app_tests": true,\n    "test_distributions": [\n      "fastapi",\n      "httpx",\n      "pydantic",\n      "pytest"\n    ],\n    "test_import_to_distribution": {\n      "_pytest": "pytest",\n      "fastapi": "fastapi",\n      "httpx": "httpx",\n      "pydantic": "pydantic",\n      "pytest": "pytest"\n    },\n    "test_imports": [\n      "_pytest",\n      "fastapi",\n      "httpx",\n      "pydantic",\n      "pytest"\n    ]\n  },\n  "direct_distributions": [\n    "fastapi",\n    "httpx",\n    "pydantic",\n    "pytest",\n    "starlette",\n    "uvicorn"\n  ],\n  "locked_distribution_count": 23,\n  "mock_only": true,\n  "production_deployment_claimed": false,\n  "python_requires": ">=3.10",\n  "real_payment_calls": "disabled",\n  "requirements_lock_sha256": "b6524c3d782ebb446f0b3f7c19b6188b2bc00757a0307ace75c425f606954255",\n  "runtime_entrypoint": "generated_application.app.interfaces.api.main:app",\n  "schema_version": "upi-generated-app-dependency-contract.v1",\n  "standalone_source_bundle": true,\n  "wheel_packaging_claimed": false\n}\n'
GENERATED_APP_BOOTSTRAP_SCRIPT = '#!/usr/bin/env bash\nset -euo pipefail\nSCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\nAPP_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"\nPYTHON_BOOTSTRAP="${PYTHON_BOOTSTRAP:-$(command -v python3.10 || command -v python3 || true)}"\nVENV="${APP_ROOT}/.venv"\n[[ -n "${PYTHON_BOOTSTRAP}" ]] || { printf \'ERROR: Python 3.10+ not found\\n\' >&2; exit 2; }\n"${PYTHON_BOOTSTRAP}" - <<\'PY\'\nimport sys\nraise SystemExit(0 if sys.version_info >= (3,10) else "Python 3.10+ required")\nPY\n[[ -x "${VENV}/bin/python" ]] || "${PYTHON_BOOTSTRAP}" -m venv "${VENV}"\n"${VENV}/bin/python" -m pip install --disable-pip-version-check -r "${APP_ROOT}/requirements-bootstrap.lock"\n"${VENV}/bin/python" -m pip install --disable-pip-version-check -r "${APP_ROOT}/requirements.lock"\n"${VENV}/bin/python" -m pip check\n"${VENV}/bin/python" - "${APP_ROOT}/requirements-bootstrap.lock" "${APP_ROOT}/requirements.lock" <<\'PY\'\nfrom importlib import metadata\nfrom pathlib import Path\nimport re\nimport sys\n\ndef canon(name: str) -> str:\n    return re.sub(r"[-_.]+", "-", name).lower()\n\nexpected = {}\nfor raw_path in sys.argv[1:]:\n    for raw in Path(raw_path).read_text(encoding="utf-8").splitlines():\n        line = raw.strip()\n        if not line or line.startswith("#"):\n            continue\n        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\\s;]+)", line)\n        if match is None:\n            raise SystemExit(f"non-exact lock entry: {line}")\n        expected[canon(match.group(1))] = match.group(2)\ninstalled = {}\nfor dist in metadata.distributions():\n    name = dist.metadata.get("Name")\n    if name:\n        installed[canon(name)] = dist.version\nmissing = sorted(set(expected) - set(installed))\nmismatch = sorted((n, expected[n], installed.get(n)) for n in expected if installed.get(n) != expected[n])\nextras = sorted(set(installed) - set(expected))\nif missing or mismatch or extras:\n    raise SystemExit(f"dependency closure mismatch: missing={missing} mismatch={mismatch} extras={extras}")\nprint(f"GENERATED_APP_EXACT_INSTALLED_CLOSURE=PASS count={len(expected)}")\nPY\n"${VENV}/bin/python" "${APP_ROOT}/scripts/validate_dependency_contract.py"\nprintf \'GENERATED_APP_BOOTSTRAP_STATUS=PASS\\n\'\nprintf \'GENERATED_APP_PYTHON=%s\\n\' "${VENV}/bin/python"\n'
GENERATED_APP_DEPENDENCY_VALIDATOR = '#!/usr/bin/env python3\nfrom __future__ import annotations\n\nimport hashlib\nimport json\nfrom pathlib import Path\nimport re\nfrom typing import Any\n\n\nROOT = Path(__file__).resolve().parents[1]\n\n\ndef sha256_file(path: Path) -> str:\n    return hashlib.sha256(path.read_bytes()).hexdigest()\n\n\ndef canonical_name(name: str) -> str:\n    return re.sub(r"[-_.]+", "-", name).lower()\n\n\ndef parse_exact_lock(path: Path) -> dict[str, str]:\n    result: dict[str, str] = {}\n    for raw in path.read_text(encoding="utf-8").splitlines():\n        line = raw.strip()\n        if not line or line.startswith("#"):\n            continue\n        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\\s;]+)", line)\n        if match is None:\n            raise AssertionError(f"{path.name}: non-exact requirement: {line}")\n        name, version = match.groups()\n        key = canonical_name(name)\n        if key in result:\n            raise AssertionError(f"{path.name}: duplicate distribution: {key}")\n        result[key] = version\n    if not result:\n        raise AssertionError(f"{path.name}: empty lock")\n    return result\n\n\ndef load_contract() -> dict[str, Any]:\n    payload = json.loads((ROOT / "dependency_contract.json").read_text(encoding="utf-8"))\n    if not isinstance(payload, dict):\n        raise AssertionError("dependency_contract.json must contain an object")\n    return payload\n\n\ndef main() -> int:\n    contract = load_contract()\n    bootstrap = parse_exact_lock(ROOT / "requirements-bootstrap.lock")\n    locked = parse_exact_lock(ROOT / "requirements.lock")\n\n    assert sha256_file(ROOT / "requirements-bootstrap.lock") == contract[\n        "bootstrap_lock_sha256"\n    ]\n    assert sha256_file(ROOT / "requirements.lock") == contract[\n        "requirements_lock_sha256"\n    ]\n\n    direct = {\n        canonical_name(str(name))\n        for name in contract["direct_distributions"]\n    }\n    assert direct.issubset(locked), sorted(direct - set(locked))\n    assert int(bootstrap["setuptools"].split(".", 1)[0]) >= 83\n\n    start_script = (ROOT / "scripts/start_local.sh").read_text(encoding="utf-8")\n    assert \'${APP_ROOT}/.venv/bin/python\' in start_script\n\n    bootstrap_script = (ROOT / "scripts/bootstrap_cleanroom.sh").read_text(\n        encoding="utf-8"\n    )\n    for marker in (\n        "requirements-bootstrap.lock",\n        "requirements.lock",\n        "pip check",\n        "validate_dependency_contract.py",\n    ):\n        assert marker in bootstrap_script\n\n    print(\n        json.dumps(\n            {\n                "status": "PASS",\n                "direct_distribution_count": len(direct),\n                "locked_distribution_count": len(locked),\n                "bootstrap_distribution_count": len(bootstrap),\n            },\n            sort_keys=True,\n        )\n    )\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'

def build_generated_application_artifact_payloads(
    project_root: Path | None = None,
    *,
    application_root: Path | None = None,
    requirements_document: Path | None = None,
) -> dict[str, str]:
    root = (project_root or PROJECT_ROOT).resolve()
    _reject_quarantined_application_root(application_root, project_root=root)
    authoritative_requirements = requirements_document or _authoritative_requirements_text()
    inventory_payload = build_atomic_obligation_inventory(
        authoritative_requirements,
        project_root=root,
    )
    items = list(inventory_payload["items"])
    traceability_items = _traceability_items(root, items)
    traceability_matrix = {
        "schema_version": "upi-failed-debit-traceability-matrix.v3",
        "application_id": COMPATIBILITY_APPLICATION_ID,
        "canonical_application_id": CANONICAL_APPLICATION_ID,
        "compatibility_application_id": COMPATIBILITY_APPLICATION_ID,
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "supplied_pdf_sha256": REQUIREMENTS_PDF_SHA256,
        "supplied_text_sha256": REQUIREMENTS_TEXT_SHA256,
        "rejected_projection_sha256": REJECTED_PROJECTION_SHA256,
        "supported_obligation_count": sum(1 for item in items if item["support_status"] == "SUPPORTED"),
        "partial_obligation_count": sum(1 for item in items if item["support_status"] == "PARTIAL"),
        "unsupported_obligation_count": sum(1 for item in items if item["support_status"] == "UNSUPPORTED"),
        "decision": inventory_payload["decision"],
        "items": traceability_items,
    }
    openapi_inventory = _extract_openapi_inventory(root)
    coverage_report = _coverage_report(items)
    unsupported_report = _unsupported_report(items)
    classification_table = _classification_decision_table(items)
    residual_risk_register = _residual_risk_register(items)
    capability_report, capability_matrix, capability_manifest = _prerun_report(
        items,
        project_root=root,
    )
    generation_metadata = _generation_metadata(items)
    manifest_description = _manifest_description()
    payloads = {
        "generation_metadata.json": _json_text(generation_metadata),
        "evidence/atomic_obligation_inventory.json": _json_text(inventory_payload),
        "evidence/requirements_traceability_matrix.json": _json_text(traceability_matrix),
        "evidence/openapi_inventory.json": _json_text(openapi_inventory),
        "evidence/CAPABILITY_PRE_RUN_REPORT.json": _json_text(capability_report),
        "evidence/REQUIREMENT_CAPABILITY_MATRIX.json": _json_text(capability_matrix),
        "evidence/PRE_RUN_MANIFEST.json": _json_text(capability_manifest),
        "evidence/classification_decision_table.json": _json_text(classification_table),
        "evidence/residual_risk_register.json": _json_text(residual_risk_register),
        "evidence/unsupported_obligation_report.json": _json_text(unsupported_report),
        "evidence/evidence_manifest_description.json": _json_text(manifest_description),
        "evidence/coverage_report.json": _json_text(coverage_report),
        "evidence/generation_summary.json": _json_text(
            _generation_summary(root, items)
        ),
        "docs/persistence_reset_policy.md": PERSISTENCE_RESET_POLICY,
        "docs/adr/ADR-0001-authoritative-failed-debit-runtime.md": ADR_TEXT,
        "requirements-bootstrap.lock": GENERATED_APP_REQUIREMENTS_BOOTSTRAP,
        "requirements.lock": GENERATED_APP_REQUIREMENTS_LOCK,
        "dependency_contract.json": GENERATED_APP_DEPENDENCY_CONTRACT,
        "scripts/bootstrap_cleanroom.sh": GENERATED_APP_BOOTSTRAP_SCRIPT,
        "scripts/validate_dependency_contract.py": GENERATED_APP_DEPENDENCY_VALIDATOR,
    }
    for relative_path, content in tuple(payloads.items()):
        if not _is_authority_json_surface(relative_path):
            continue
        json_surface = json.loads(content)
        if not isinstance(json_surface, dict):
            raise ValueError(f"authoritative JSON surface must be an object: {relative_path}")
        json_surface.update(_authority_fields())
        payloads[relative_path] = _json_text(json_surface)
    manifest_payload = json.loads(payloads["evidence/evidence_manifest_description.json"])
    for artifact in manifest_payload["artifacts"]:
        path = artifact["path"]
        artifact["sha256"] = _sha256_bytes(payloads[path].encode("utf-8"))
    payloads["evidence/evidence_manifest_description.json"] = _json_text(manifest_payload)
    return payloads

def materialize_generated_application_artifacts(
    project_root: Path | None = None,
    *,
    application_root: Path | None = None,
    requirements_document: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or PROJECT_ROOT).resolve()
    generated_root = (application_root or TRACKED_APPLICATION_ROOT).resolve()
    _reject_quarantined_application_root(generated_root, project_root=root)
    payloads = build_generated_application_artifact_payloads(
        root,
        application_root=generated_root,
        requirements_document=requirements_document,
    )
    if set(payloads) != set(REQUIRED_ARTIFACT_RELATIVE_PATHS):
        raise ValueError("authoritative exact-v2 artifact set is incomplete")
    for relative_path, content in payloads.items():
        if not _is_authority_json_surface(relative_path):
            continue
        surface = json.loads(content)
        if not isinstance(surface, dict) or any(
            surface.get(field) != expected
            for field, expected in _authority_fields().items()
        ):
            raise ValueError(
                f"authoritative exact-v2 JSON surface is invalid: {relative_path}"
            )
    capability_report = json.loads(
        payloads["evidence/CAPABILITY_PRE_RUN_REPORT.json"]
    )
    generation_summary = json.loads(payloads["evidence/generation_summary.json"])
    mandatory_gate_passed = capability_report["mandatory_gate_passed"]
    decision = capability_report["decision"]
    if not isinstance(mandatory_gate_passed, bool):
        raise ValueError("exact-v2 mandatory-gate status is not boolean")
    if generation_summary["mandatory_gate_passed"] is not mandatory_gate_passed:
        raise ValueError("exact-v2 mandatory-gate surfaces disagree")
    if generation_summary["decision"] != decision:
        raise ValueError("exact-v2 decision surfaces disagree")
    expected_decision = (
        PROVEN_EVIDENCE_DECISION
        if mandatory_gate_passed
        else NO_GO_EVIDENCE_DECISION
    )
    if decision != expected_decision:
        raise ValueError("exact-v2 decision contradicts the mandatory gate")
    expected_definition_of_done = (
        "definition_of_done_ready"
        if mandatory_gate_passed
        else "definition_of_done_blocked"
    )
    if generation_summary["status"] != expected_definition_of_done:
        raise ValueError("exact-v2 definition-of-done status contradicts the mandatory gate")

    written: list[str] = []
    for relative_path, content in payloads.items():
        target = generated_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(relative_path)
    return {
        "status": "MATERIALIZED",
        "project_root": str(root),
        "application_root": str(generated_root),
        "written_paths": written,
        "requirements_schema": REQUIREMENTS_SCHEMA,
        "supplied_pdf_sha256": REQUIREMENTS_PDF_SHA256,
        "supplied_text_sha256": REQUIREMENTS_TEXT_SHA256,
        "rejected_projection_sha256": REJECTED_PROJECTION_SHA256,
        "decision": decision,
        "mandatory_gate_passed": mandatory_gate_passed,
        "definition_of_done_status": generation_summary["status"],
        **_authority_fields(),
        "exact_v2_evidence_decision": decision,
        "exact_v2_evidence_authority": EVIDENCE_AUTHORITY,
        "exact_v2_mandatory_gate_passed": mandatory_gate_passed,
    }
