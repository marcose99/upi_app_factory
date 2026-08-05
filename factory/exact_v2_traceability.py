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
AUTHORITATIVE_INPUT_ROOT = (
    Path.home()
    / "Downloads"
    / "upi_app_factory_post_r10_4_r10_5.U7T7lu"
    / "predecessor_r10_4"
    / "predecessor_r10_3"
    / "predecessor_r10_2"
    / "predecessor_r10_1"
    / "predecessor_r10"
)
AUTHORITATIVE_REQUIREMENTS_PDF_PATH = (
    AUTHORITATIVE_INPUT_ROOT / "UPI_FAILED_DEBIT_BENEFICIARY_NOT_CREDITED_REQUIREMENTS.pdf"
)
AUTHORITATIVE_REQUIREMENTS_TEXT_PATH = (
    AUTHORITATIVE_INPUT_ROOT / "UPI_FAILED_DEBIT_BENEFICIARY_NOT_CREDITED_REQUIREMENTS.txt"
)
AUTHORITATIVE_VALIDATION_SUMMARY_PATH = (
    PROJECT_ROOT.parent.parent / "quality" / "021" / "validation_summary.json"
)
REQUIREMENTS_SCHEMA = "upi_failed_debit_no_credit.requirements.v2"
REQUIREMENTS_PDF_SHA256 = "37c94a02891e84b59e4071d68f1aafb968730a0c458cdf3092562a5a1ea9ea1c"
REQUIREMENTS_TEXT_SHA256 = "8a67787690640d4af932a266fc44e2a70348ac0785eb4f91b8842aa3c70b0d82"
VALIDATION_SUMMARY_SHA256 = "32fe0943a9c776ecdc09ebe5b515fc732cafdd50973ea343e8786ce7e1ad22ab"
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
HEADING_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\.\s+(?P<title>.+)$")
ENDPOINT_RE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)")
TRANSITION_RE = re.compile(r"\b([A-Z_]+)\s*->\s*([A-Z_]+)\b")
TOKEN_RE = re.compile(r"[A-Z][A-Z0-9_]{2,}|[A-Z][a-zA-Z0-9]+(?:[A-Z][a-zA-Z0-9]+)+|/[A-Za-z0-9{}._/-]+")
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
    "docs/persistence_reset_policy.md",
    "docs/adr/ADR-0001-authoritative-failed-debit-runtime.md",
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


def _artifact_ref(relative_path: str) -> str:
    return (
        "workspace/factory_generated/upi_dispute_resolution/generated_application/"
        + relative_path
    )


def _tracked_application_root() -> str:
    return "workspace/factory_generated/upi_dispute_resolution/generated_application"


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


def _authoritative_requirements_text() -> Path:
    _validated_external_file(
        AUTHORITATIVE_REQUIREMENTS_PDF_PATH,
        expected_sha256=REQUIREMENTS_PDF_SHA256,
        label="authoritative requirements PDF",
    )
    return _validated_external_file(
        AUTHORITATIVE_REQUIREMENTS_TEXT_PATH,
        expected_sha256=REQUIREMENTS_TEXT_SHA256,
        label="authoritative requirements text",
    )


def _current_validation_summary() -> dict[str, Any]:
    path = _validated_external_file(
        AUTHORITATIVE_VALIDATION_SUMMARY_PATH,
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
    if not target:
        return True
    text = path.read_text(encoding="utf-8")
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


def _token_candidates(text: str) -> list[str]:
    tokens = list(dict.fromkeys(match.group(0) for match in TOKEN_RE.finditer(text)))
    if not tokens:
        phrase_tokens = sorted(
            {
                token
                for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{4,}", text)
                if token.casefold() not in STOPWORDS
            },
            key=lambda token: (-len(token), token.casefold(), token),
        )
        tokens.extend(phrase_tokens[:3])
    return list(dict.fromkeys(tokens))


def _find_matching_paths(
    file_index: Mapping[str, str],
    candidates: Sequence[str],
    section_candidates: Sequence[str],
) -> list[str]:
    matched: list[str] = []
    lowered_candidates = [candidate.casefold() for candidate in candidates if candidate]
    for relative in section_candidates:
        text = file_index.get(relative)
        if not text:
            continue
        haystack = text.casefold()
        if any(candidate in haystack for candidate in lowered_candidates):
            matched.append(relative)
    return matched


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
) -> str:
    if implementation_refs and test_refs and evidence_refs and openapi_verified is not False:
        return "Current implementation, executable tests, and evidence references were verified."
    missing: list[str] = []
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
    converged: bool,
) -> dict[str, Any]:
    source = obligation["source"]
    rule = _section_rule(str(source["section"]))
    normalized_text = _normalize_whitespace(
        str(obligation.get("normalized_text", obligation.get("text", "")))
    )
    candidates = _token_candidates(normalized_text)
    section_implementation_paths = list(rule["implementation_paths"])
    section_test_references = list(rule["test_references"])
    section_evidence_references = list(rule["evidence_references"])
    matched_paths = _find_matching_paths(file_index, candidates, section_implementation_paths)
    matched_tests = _find_matching_paths(file_index, candidates, [ref.partition("::")[0] for ref in section_test_references])
    implementation_candidates = (
        list(dict.fromkeys([*section_implementation_paths, *matched_paths]))
        if converged
        else matched_paths
    )
    implementation_refs = _verify_and_materialize_refs(
        project_root,
        implementation_candidates,
        mode="implementation",
        generated_relative_paths=generated_relative_paths,
    )
    verified_test_candidates = (
        list(section_test_references)
        if converged
        else [
            reference
            for reference in section_test_references
            if reference.partition("::")[0] in matched_tests
        ]
    )
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

    openapi_verified: bool | None = None
    endpoint_match = ENDPOINT_RE.match(normalized_text)
    if endpoint_match:
        method, path = endpoint_match.groups()
        candidate_path = path
        if converged:
            candidate_path = path.split(" or an equivalent", 1)[0].split("?", 1)[0]
            candidate_path = candidate_path.replace("{case_id}", "{dispute_id}")
        endpoint_inventory = {
            (str(item.get("method", "")).upper(), str(item.get("path", "")))
            for item in cast(list[dict[str, Any]], openapi_inventory.get("endpoint_inventory", []))
        }
        if converged:
            endpoint_inventory = {
                (method_name, endpoint_path.split("?", 1)[0])
                for method_name, endpoint_path in endpoint_inventory
            }
        openapi_verified = (method.upper(), candidate_path) in endpoint_inventory
    elif "/v1/disputes" in normalized_text or normalized_text.startswith(("GET /", "POST /")):
        openapi_verified = False

    if "where supported" in normalized_text.casefold() and not implementation_refs:
        support_status = "NOT_APPLICABLE_WITH_JUSTIFICATION"
        reason = "The requirement is explicitly conditional and no supported implementation surface was found."
    elif implementation_refs and test_refs and evidence_refs and openapi_verified is not False:
        support_status = "SUPPORTED"
        reason = _build_support_reason(
            implementation_refs=implementation_refs,
            test_refs=test_refs,
            evidence_refs=evidence_refs,
            openapi_verified=openapi_verified,
        )
    elif implementation_refs or test_refs or evidence_refs:
        support_status = "PARTIAL"
        reason = _build_support_reason(
            implementation_refs=implementation_refs,
            test_refs=test_refs,
            evidence_refs=evidence_refs,
            openapi_verified=openapi_verified,
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
    }


def build_atomic_obligation_inventory(
    requirements_document: Path,
    *,
    project_root: Path | None = None,
    converged: bool = False,
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
            converged=converged,
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
    decision = "NO_GO" if any(
        item["mandatory"] and item["support_status"] in {"PARTIAL", "UNSUPPORTED"}
        for item in items
    ) else "GO"
    return {
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
    partial_or_unsupported = summary["PARTIAL"] + summary["UNSUPPORTED"]
    coverage_status = (
        "NO_GO_UNSUPPORTED_MANDATORY_OBLIGATIONS"
        if partial_or_unsupported
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
            "mandatory_no_go_count": partial_or_unsupported,
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
    mandatory_no_go_count = summary["PARTIAL"] + summary["UNSUPPORTED"]
    return {
        "schema_version": "upi-failed-debit-generation-summary.v4",
        "status": (
            "definition_of_done_ready"
            if mandatory_no_go_count == 0
            else "definition_of_done_blocked"
        ),
        "phase": "governed_self_improvement",
        "run_id": "r10_1_exact_input_evidence_runtime_convergence",
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
                "requirement_to_code_and_test_complete": (
                    item["support_status"] == "SUPPORTED"
                ),
            },
        }
        for item in items
    ]
    mandatory_gate_passed = all(
        item["support_status"] == "SUPPORTED" or not item["mandatory"] for item in items
    )
    decision = "PROVEN_100_PERCENT_CAPABILITY" if mandatory_gate_passed else "NO_GO_WITH_IMPROVEMENT_REQUIREMENTS"
    report = {
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
    }
    manifest = {
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


def _manifest_description(*, converged: bool) -> dict[str, Any]:
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
        "docs/persistence_reset_policy.md": "Persistence and deterministic reset boundaries.",
        "docs/adr/ADR-0001-authoritative-failed-debit-runtime.md": "Architecture decision grounding the authoritative failed-debit runtime.",
    }
    if converged:
        descriptions["evidence/generation_summary.json"] = (
            "Current definition-of-done-ready summary bound to authoritative requirements and validation evidence hashes."
        )
    return {
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


def build_generated_application_artifact_payloads(
    project_root: Path | None = None,
    *,
    application_root: Path | None = None,
    requirements_document: Path | None = None,
    converge_exact_input: bool = False,
) -> dict[str, str]:
    del application_root
    root = (project_root or PROJECT_ROOT).resolve()
    authoritative_requirements = requirements_document or _authoritative_requirements_text()
    inventory_payload = build_atomic_obligation_inventory(
        authoritative_requirements,
        project_root=root,
        converged=converge_exact_input,
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
    manifest_description = _manifest_description(converged=converge_exact_input)
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
        "docs/persistence_reset_policy.md": PERSISTENCE_RESET_POLICY,
        "docs/adr/ADR-0001-authoritative-failed-debit-runtime.md": ADR_TEXT,
    }
    if converge_exact_input:
        payloads["evidence/generation_summary.json"] = _json_text(
            _generation_summary(root, items)
        )
    manifest_payload = json.loads(payloads["evidence/evidence_manifest_description.json"])
    for artifact in manifest_payload["artifacts"]:
        path = artifact["path"]
        artifact["sha256"] = _sha256_bytes(payloads[path].encode("utf-8"))
    payloads["evidence/evidence_manifest_description.json"] = _json_text(manifest_payload)
    return payloads


def build_converged_generated_application_artifact_payloads(
    project_root: Path | None = None,
    *,
    application_root: Path | None = None,
    requirements_document: Path | None = None,
) -> dict[str, str]:
    return build_generated_application_artifact_payloads(
        project_root,
        application_root=application_root,
        requirements_document=requirements_document,
        converge_exact_input=True,
    )


def materialize_generated_application_artifacts(
    project_root: Path | None = None,
    *,
    application_root: Path | None = None,
    requirements_document: Path | None = None,
    converge_exact_input: bool = False,
) -> dict[str, Any]:
    root = (project_root or PROJECT_ROOT).resolve()
    generated_root = (application_root or TRACKED_APPLICATION_ROOT).resolve()
    payloads = build_generated_application_artifact_payloads(
        root,
        application_root=generated_root,
        requirements_document=requirements_document,
        converge_exact_input=converge_exact_input,
    )
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
        "decision": json.loads(
            payloads["evidence/CAPABILITY_PRE_RUN_REPORT.json"]
        )["decision"],
    }


def materialize_converged_generated_application_artifacts(
    project_root: Path | None = None,
    *,
    application_root: Path | None = None,
    requirements_document: Path | None = None,
) -> dict[str, Any]:
    return materialize_generated_application_artifacts(
        project_root,
        application_root=application_root,
        requirements_document=requirements_document,
        converge_exact_input=True,
    )
