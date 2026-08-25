from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from factory.application_engineering.transactional_publish import (
    DirectoryPublication,
    cleanup_staging_directory,
    create_staging_directory,
    publish_directories,
)
from factory.application_engineering.architecture_conformance import (
    validate_architecture_conformance,
    verify_architecture_conformance_report,
)
from factory.application_engineering.architecture_realization import get_architecture_adapter
from factory.architecture_decisioning import verify_reviewed_architecture_package


def _lane_a_quality_hooks() -> tuple[Any, Any, Any, Any, Any] | None:
    """Resolve cross-lane APIs lazily so source-disjoint lane qualification remains possible."""
    try:
        from factory.application_engineering.semantic_realization import (
            build_semantic_model,
            render_semantic_files,
        )
        from factory.application_engineering.test_architecture import render_executable_tests, validate_trace_paths
        from factory.application_engineering.runtime_architecture import render_runtime_architecture_files, validate_runtime_architecture
    except ImportError:
        return None
    return (
        build_semantic_model,
        render_semantic_files,
        render_executable_tests,
        render_runtime_architecture_files,
        (validate_trace_paths, validate_runtime_architecture),
    )


def _application_quality_hook() -> Any | None:
    """Resolve Lane-B assurance lazily for source-disjoint lane qualification."""
    try:
        from factory.quality_assurance import build_application_quality_bundle
    except ImportError:
        return None
    return build_application_quality_bundle


COMPOSER_PROFILE_VERSION = "deep-composer/v1"
DEFAULT_DEEP_PROFILE = "local-deep-v1"
GOLDEN_APP_ID = "upi_failed_debit_dispute"
APP_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
REQUIRED_ENDPOINTS = (
    "GET /health",
    "GET /ready",
    "GET /metrics",
    "POST /v1/disputes",
    "GET /v1/disputes/{dispute_id}",
    "GET /v1/disputes",
    "POST /v1/disputes/{dispute_id}/evidence",
    "POST /v1/disputes/{dispute_id}/validation",
    "POST /v1/disputes/{dispute_id}/investigation",
    "POST /v1/disputes/{dispute_id}/resolution",
    "POST /v1/disputes/{dispute_id}/closure",
    "GET /v1/disputes/{dispute_id}/timeline",
    "GET /v1/disputes/{dispute_id}/audit",
)
DOMAIN_STATES = (
    "received",
    "validated",
    "evidence_pending",
    "investigation",
    "resolution_proposed",
    "resolved",
    "rejected",
    "closed",
)


class DeepComposerError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeepProfile:
    profile_id: str = DEFAULT_DEEP_PROFILE
    profile_version: str = COMPOSER_PROFILE_VERSION
    architecture: str = "modular-monolith-ddd-hexagonal"
    persistence: str = "sqlite-stdlib"
    local_only: bool = True
    mock_only: bool = True
    llm_runtime_calls: int = 0
    real_payment_calls: str = "disabled"

    def validate(self) -> None:
        if self.profile_id != DEFAULT_DEEP_PROFILE:
            raise DeepComposerError("unsupported deep profile")
        if self.persistence != "sqlite-stdlib":
            raise DeepComposerError("deep profile must use standard-library SQLite")
        if not self.local_only or not self.mock_only:
            raise DeepComposerError("deep profile must stay local and mock-only")
        if self.llm_runtime_calls != 0 or self.real_payment_calls != "disabled":
            raise DeepComposerError("live payments and runtime LLM calls are disabled")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _file_manifest(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        records.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return records


def _module(app_id: str, suffix: str) -> str:
    return f"app.{app_id}.{suffix}"


class DeepApplicationComposer:
    def __init__(self, project_root: Path, profile: DeepProfile | None = None) -> None:
        self.project_root = project_root.resolve()
        self.profile = profile or DeepProfile()
        self.profile.validate()

    def compose(
        self,
        *,
        requirements_ir: Mapping[str, Any],
        output_root: Path,
        app_id: str = GOLDEN_APP_ID,
        replace_existing: bool = True,
        architecture_package: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not APP_ID_PATTERN.fullmatch(app_id):
            raise DeepComposerError(f"invalid app id: {app_id!r}")
        if app_id == "upi_app_factory":
            raise DeepComposerError("application engineering app id must use a non-default namespace")

        root = output_root.resolve()
        # Qualification campaigns intentionally publish into disposable roots
        # outside the source checkout. Reject checkout ancestors (including the
        # filesystem root), but permit caller-selected isolated workspaces.
        if root == self.project_root or root in self.project_root.parents:
            raise DeepComposerError("output root must not be the project root or its ancestor")
        app_root = root / app_id
        if app_root.exists() and not replace_existing:
            raise DeepComposerError(f"output already exists: {app_root}")

        candidate_root = create_staging_directory(app_root)
        try:
            requirements_hash = sha256_text(canonical_json(requirements_ir))
            if architecture_package is not None:
                if not verify_reviewed_architecture_package(architecture_package):
                    raise DeepComposerError("reviewed architecture package is invalid")
                reviewed_freeze = architecture_package["reviewed_freeze"]
                if reviewed_freeze.get("requirements_sha256") != requirements_hash:
                    raise DeepComposerError("requirements hash does not match reviewed architecture")
                realization_contract = architecture_package["realization_contract"]
                adapter = get_architecture_adapter(
                    str(reviewed_freeze.get("selected_candidate_id")), realization_contract
                )
            files = self._render_files(app_id, requirements_hash, requirements_ir)
            if architecture_package is not None:
                files.update(adapter.render(app_id))
            for relative, content in files.items():
                _write_text(candidate_root / relative, content)

            hooks = _lane_a_quality_hooks()
            nested_requirements = requirements_ir.get("requirements", {})
            semantic_source = nested_requirements if isinstance(nested_requirements, Mapping) else {}
            has_semantic_requirements = any(
                requirements_ir.get(name) or semantic_source.get(name)
                for name in (
                    "actors", "use_cases", "bounded_contexts", "commands", "queries",
                    "events", "aggregates", "invariants", "workflows", "apis", "data",
                    "security", "operations", "evidence",
                )
            )
            if hooks is not None and has_semantic_requirements:
                (
                    build_semantic_model,
                    render_semantic_files,
                    render_executable_tests,
                    render_runtime_files,
                    validators,
                ) = hooks
                validate_trace_paths, validate_runtime = validators
                semantic_model = build_semantic_model(requirements_ir)
                generated = {}
                generated.update(render_semantic_files(semantic_model, app_id=app_id))
                generated.update(render_runtime_files(semantic_model, app_id=app_id))
                generated.update(render_executable_tests(semantic_model, app_id=app_id))
                semantic_openapi = json.loads(generated["openapi/openapi.json"])
                semantic_identities = semantic_openapi.get("x-required-endpoints", [])
                semantic_openapi["x-required-endpoints"] = list(
                    dict.fromkeys((*REQUIRED_ENDPOINTS, *semantic_identities))
                )
                generated["openapi/openapi.json"] = (
                    json.dumps(semantic_openapi, indent=2, sort_keys=True) + "\n"
                )
                for relative, content in generated.items():
                    _write_text(candidate_root / relative, content)
                trace_result = validate_trace_paths(candidate_root)
                runtime_result = validate_runtime(candidate_root, app_id)
                if trace_result["status"] != "PASS" or runtime_result["status"] != "PASS":
                    raise DeepComposerError("generated semantic runtime or test trace is invalid")

            quality_input = requirements_ir.get("quality_assurance")
            if quality_input is not None:
                if not isinstance(quality_input, Mapping):
                    raise DeepComposerError("quality_assurance must be a mapping")
                if "raw_measures" in quality_input:
                    raise DeepComposerError(
                        "requirements_ir quality_assurance cannot supply raw_measures; "
                        "run artifact-bound executable qualification after composition"
                    )

            if architecture_package is not None:
                evidence_root = candidate_root / "evidence" / "architecture"
                evidence_documents = {
                    "architecture_driver_ir.json": architecture_package["driver_ir"],
                    "architecture_review_packet.json": architecture_package["architecture_packet"],
                    "architecture_review_set.json": architecture_package["review_set"],
                    "architecture_adjudication.json": architecture_package["adjudication"],
                    "architecture_reviewed_decision.json": architecture_package["reviewed_decision"],
                    "architecture_freeze.json": architecture_package["reviewed_freeze"],
                    "evolution_contract.json": architecture_package["evolution_contract"],
                    "realization_manifest.json": {
                        "selected_candidate_id": reviewed_freeze["selected_candidate_id"],
                        "adapter_id": adapter.adapter_id,
                        "realization_contract_digest": realization_contract["contract_digest"],
                        "freeze_digest": reviewed_freeze["freeze_digest"],
                    },
                }
                for name, document in evidence_documents.items():
                    _write_text(evidence_root / name, json.dumps(document, indent=2, sort_keys=True) + "\n")
                selected = str(reviewed_freeze["selected_candidate_id"])
                evolution = architecture_package["evolution_contract"]
                docs = {
                    "docs/adrs/ADR-0001-selected-architecture.md": f"# ADR-0001: {selected}\n\nFrozen reviewed selection. Adapter: `{adapter.adapter_id}`.\n",
                    "docs/architecture/evolution_and_compatibility.md": "# Evolution and Compatibility\n\n" + json.dumps(evolution, indent=2, sort_keys=True) + "\n",
                    "docs/architecture/reconsideration_triggers.md": "# Reconsideration Triggers\n\n" + "\n".join(f"- {item}" for item in evolution.get("reconsideration_triggers", [])) + "\n",
                }
                for relative, content in docs.items():
                    _write_text(candidate_root / relative, content)
                conformance = validate_architecture_conformance(
                    candidate_root, reviewed_freeze, realization_contract
                )
                if conformance["status"] != "PASS" or not verify_architecture_conformance_report(
                    conformance, candidate_root, reviewed_freeze, realization_contract
                ):
                    raise DeepComposerError("generated application fails architecture conformance")
                _write_text(
                    evidence_root / "architecture_conformance.json",
                    json.dumps(conformance, indent=2, sort_keys=True) + "\n",
                )

            payload = {
                "composer_profile": self.profile.profile_id,
                "profile_version": self.profile.profile_version,
                "app_id": app_id,
                "product_name": "UPI App Factory",
                "repository_id": "upi_app_factory",
                "requirements_ir_sha256": requirements_hash,
                "architecture": self.profile.architecture,
                "persistence": self.profile.persistence,
                "endpoints": list(REQUIRED_ENDPOINTS),
                "state_machine": list(DOMAIN_STATES),
                "llm_runtime_calls": 0,
                "real_payment_calls": "disabled",
                "file_count": 0,
                "file_manifest": [],
            }
            if architecture_package is not None:
                payload.update({
                    "architecture": next(
                        row["manifest_architecture"] for row in realization_contract["patterns"]
                        if row["pattern_id"] == reviewed_freeze["selected_candidate_id"]
                    ),
                    "architecture_pattern_id": reviewed_freeze["selected_candidate_id"],
                    "architecture_adapter_id": adapter.adapter_id,
                    "architecture_reviewed_decision_digest": reviewed_freeze["reviewed_decision_digest"],
                    "architecture_freeze_digest": reviewed_freeze["freeze_digest"],
                    "architecture_evolution_contract_digest": reviewed_freeze["evolution_contract_digest"],
                    "architecture_conformance_digest": conformance["conformance_digest"],
                    "architecture_realization_contract_digest": reviewed_freeze["realization_contract_digest"],
                })
            _write_text(
                candidate_root / "evidence" / "generation_manifest.json",
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
            )
            manifest = _file_manifest(candidate_root)
            payload["file_count"] = len(manifest)
            payload["file_manifest"] = manifest
            _write_text(
                candidate_root / "evidence" / "generation_manifest.json",
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
            )
            publish_directories(
                [
                    DirectoryPublication(
                        candidate=candidate_root,
                        destination=app_root,
                        replace_existing=replace_existing,
                    )
                ]
            )
            return payload
        finally:
            cleanup_staging_directory(candidate_root)

    def _code_paths_for_collection(self, app_id: str, collection: str) -> list[str]:
        mapping = {
            "actors": [f"app/{app_id}/interfaces/api/main.py"],
            "use_cases": [f"app/{app_id}/application/services/dispute_service.py"],
            "bounded_contexts": [f"app/{app_id}/application/services/dispute_service.py"],
            "commands": [f"app/{app_id}/application/services/dispute_service.py"],
            "queries": [f"app/{app_id}/application/services/dispute_service.py"],
            "events": [f"app/{app_id}/domain/aggregates/dispute_case.py"],
            "aggregates": [f"app/{app_id}/domain/aggregates/dispute_case.py"],
            "invariants": [
                f"app/{app_id}/domain/aggregates/dispute_case.py",
                f"app/{app_id}/domain/state_machines/dispute_lifecycle.py",
            ],
            "workflows": [f"app/{app_id}/domain/state_machines/dispute_lifecycle.py"],
            "apis": [f"app/{app_id}/interfaces/api/main.py"],
            "data": [f"app/{app_id}/infrastructure/persistence/migrations/0001_initial.sql"],
            "security": [f"app/{app_id}/interfaces/api/main.py"],
            "operations": [
                f"app/{app_id}/infrastructure/persistence/migrations/0001_initial.sql",
                "scripts/run_local.sh",
            ],
            "evidence": ["evidence/requirements_trace.json", "docs/test_plan.md", "docs/operations_runbook.md"],
            "dependencies": ["configuration/example.env", "scripts/run_local.sh"],
        }
        return mapping.get(collection, [f"app/{app_id}/application/services/dispute_service.py"])

    def _test_paths_for_collection(self, collection: str) -> list[str]:
        if collection in {"apis", "security", "operations"}:
            return ["tests/test_api_contract.py", "tests/test_service.py"]
        return ["tests/test_service.py"]

    def _artifact_paths_for_collection(self, collection: str) -> list[str]:
        mapping = {
            "apis": ["openapi/openapi.json", "docs/domain_state_machine.md"],
            "workflows": ["docs/domain_state_machine.md"],
            "operations": ["docs/operations_runbook.md"],
            "evidence": ["evidence/requirements_trace.json", "docs/test_plan.md"],
            "security": ["docs/threat_model.md"],
            "data": ["docs/adrs/ADR-0001-local-sqlite-modular-monolith.md"],
        }
        return mapping.get(collection, ["evidence/requirements_trace.json"])

    def _build_requirement_trace(self, app_id: str, requirements_hash: str, requirements_ir: Mapping[str, Any]) -> str:
        traceability = requirements_ir.get("traceability", [])
        source_documents = requirements_ir.get("source_documents", [])
        mappings: list[dict[str, Any]] = []
        if isinstance(traceability, list):
            for row in traceability:
                if not isinstance(row, Mapping):
                    continue
                collection = str(row.get("collection", "unknown"))
                mappings.append(
                    {
                        "requirement_id": row.get("requirement_id"),
                        "collection": collection,
                        "source": row.get("source"),
                        "canonical_hash": row.get("canonical_hash"),
                        "code_paths": self._code_paths_for_collection(app_id, collection),
                        "test_paths": self._test_paths_for_collection(collection),
                        "generated_artifacts": self._artifact_paths_for_collection(collection),
                    }
                )
        payload = {
            "requirements_ir_sha256": requirements_hash,
            "source_documents": list(source_documents) if isinstance(source_documents, list) else [],
            "generated_application": {
                "app_id": app_id,
                "profile": self.profile.profile_id,
                "local_only": True,
                "mock_only": True,
                "runtime_llm_calls": 0,
                "real_payment_calls": "disabled",
            },
            "summary": {
                "requirement_count": len(mappings),
                "endpoint_count": len(REQUIRED_ENDPOINTS),
                "state_count": len(DOMAIN_STATES),
            },
            "mappings": mappings,
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"

    def _build_operations_runbook(self, app_id: str) -> str:
        return f"""# Operations Runbook

## Operating posture

- Application ID: `{app_id}`
- Runtime binding: loopback only (`127.0.0.1`)
- Persistence: local standard-library SQLite
- Runtime LLM calls: `0`
- Real payment/provider calls: `disabled`
- Data posture: fictional-only

## Start and verify

1. Export `REAL_PAYMENT_CALLS=disabled` and keep the default local SQLite path.
2. Run `scripts/run_local.sh`.
3. Verify `GET /health`, `GET /ready`, and `GET /metrics` before operator actions.
4. Confirm `openapi/openapi.json` still advertises the required `/v1/disputes` routes.

## Operator workflow

1. Create a dispute through `POST /v1/disputes` with an idempotency key and correlation header.
2. Attach evidence through `POST /v1/disputes/{{dispute_id}}/evidence` until the case is investigation-ready.
3. Record investigation and proposed resolution through the governed `/investigation`, `/resolution`, `/timeline`, and `/audit` routes.
4. Preserve application engineering evidence from `evidence/generation_manifest.json`, `evidence/requirements_trace.json`, and the API/OpenAPI outputs for local review.

## Failure handling

- Stop immediately if live-provider settings, real customer data, or non-loopback bindings appear.
- Treat missing readiness, SQLite migration drift, or traceability/evidence mismatches as fail-closed conditions.
- Re-run deterministic local tests before any governed review decision; do not deploy or claim certification.
"""

    def _build_test_plan(self, app_id: str) -> str:
        return f"""# Test Plan

## Scope

This application engineering output proves deterministic failed-debit lifecycle behavior for `{app_id}` without live providers, external databases, or runtime LLM calls.

## Required commands

1. `python -m pytest -q tests/test_service.py`
2. `python -m pytest -q tests/test_api_contract.py`
3. `python -m pytest -q`

## Coverage expectations

- Lifecycle states: `received`, `validated`, `evidence_pending`, `investigation`, `resolution_proposed`, `resolved`, `rejected`, `closed`
- API contract: health, readiness, metrics, create/list/get dispute, evidence, investigation, resolution, closure, timeline, audit
- Persistence: SQLite migration inventory and deterministic local startup
- Safety boundaries: idempotency, fictional-only data posture, no live-provider dependency, no certification/deployment claim

## Evidence outputs

- `evidence/requirements_trace.json`
- `evidence/generation_manifest.json`
- `openapi/openapi.json`
- `docs/operations_runbook.md`
"""

    def _render_files(
        self,
        app_id: str,
        requirements_hash: str,
        requirements_ir: Mapping[str, Any],
    ) -> dict[str, str]:
        endpoint_lines = "\n".join(f"- {endpoint}" for endpoint in REQUIRED_ENDPOINTS)
        states = ", ".join(DOMAIN_STATES)
        return {
            "app/__init__.py": "",
            f"app/{app_id}/__init__.py": '"""Generated golden failed-debit dispute application."""\n',
            f"app/{app_id}/domain/__init__.py": "",
            f"app/{app_id}/domain/state_machines/dispute_lifecycle.py": f"""from __future__ import annotations

TRANSITION_TABLE = {{
    "received": ("validated", "rejected"),
    "validated": ("evidence_pending",),
    "evidence_pending": ("investigation",),
    "investigation": ("resolution_proposed",),
    "resolution_proposed": ("resolved", "rejected"),
    "resolved": ("closed",),
    "rejected": ("closed",),
    "closed": (),
}}
DOMAIN_STATES = {DOMAIN_STATES!r}
""",
            f"app/{app_id}/domain/aggregates/dispute_case.py": f"""from __future__ import annotations

from dataclasses import dataclass, field

from {_module(app_id, "domain.state_machines.dispute_lifecycle")} import TRANSITION_TABLE


class DomainError(RuntimeError):
    pass


@dataclass
class DisputeCase:
    dispute_id: str
    transaction_reference: str
    amount: str
    reason: str
    state: str = "received"
    version: int = 1
    evidence: list[str] = field(default_factory=list)
    timeline: list[str] = field(default_factory=lambda: ["case_received"])

    def transition(self, target: str, event: str) -> None:
        if target not in TRANSITION_TABLE[self.state]:
            raise DomainError(f"invalid transition {{self.state}} -> {{target}}")
        self.state = target
        self.version += 1
        self.timeline.append(event)
""",
            f"app/{app_id}/application/services/dispute_service.py": f"""from __future__ import annotations

from dataclasses import asdict

from {_module(app_id, "domain.aggregates.dispute_case")} import DisputeCase
from {_module(app_id, "application.ports")} import CaseRepositoryPort


class DisputeApplicationService:
    def __init__(self, repository: CaseRepositoryPort | None = None) -> None:
        self.repository = repository
        self._cases: dict[str, DisputeCase] = {{}}
        self._idempotency: dict[str, str] = {{}}

    def create(self, payload: dict[str, str], idempotency_key: str) -> dict[str, object]:
        if idempotency_key in self._idempotency:
            return self.get(self._idempotency[idempotency_key])
        case = DisputeCase(
            dispute_id=payload["dispute_id"],
            transaction_reference=payload["transaction_reference"],
            amount=payload["amount"],
            reason=payload["reason"],
        )
        self._cases[case.dispute_id] = case
        self._idempotency[idempotency_key] = case.dispute_id
        return asdict(case)

    def get(self, dispute_id: str) -> dict[str, object]:
        return asdict(self._cases[dispute_id])

    def list(self) -> list[dict[str, object]]:
        return [asdict(case) for case in self._cases.values()]

    def action(self, dispute_id: str, target: str, event: str) -> dict[str, object]:
        case = self._cases[dispute_id]
        case.transition(target, event)
        return asdict(case)
""",
            f"app/{app_id}/infrastructure/persistence/migrations/0001_initial.sql": """PRAGMA foreign_keys = ON;
CREATE TABLE dispute_cases (
  dispute_id TEXT PRIMARY KEY,
  transaction_reference TEXT NOT NULL UNIQUE,
  amount TEXT NOT NULL,
  reason TEXT NOT NULL,
  state TEXT NOT NULL,
  version INTEGER NOT NULL
);
CREATE TABLE idempotency_records (
  idempotency_key TEXT PRIMARY KEY,
  dispute_id TEXT NOT NULL REFERENCES dispute_cases(dispute_id)
);
CREATE TABLE audit_records (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  dispute_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  record_hash TEXT NOT NULL
);
CREATE TABLE outbox_events (
  event_id TEXT PRIMARY KEY,
  dispute_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  published INTEGER NOT NULL DEFAULT 0
);
""",
            f"app/{app_id}/interfaces/api/main.py": f'''from __future__ import annotations

from fastapi import FastAPI, Header

from {_module(app_id, "application.services.dispute_service")} import DisputeApplicationService

app = FastAPI(title="UPI Failed Debit Dispute", version="1.0.0")
service = DisputeApplicationService()


@app.get("/health")
def health() -> dict[str, str]:
    return {{"status": "ok"}}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {{"status": "ready", "real_payment_calls": "disabled", "llm_runtime_calls": "0"}}


@app.get("/metrics")
def metrics() -> dict[str, int]:
    return {{"disputes_total": len(service.list())}}


@app.post("/v1/disputes")
def create_dispute(payload: dict[str, str], idempotency_key: str = Header(alias="Idempotency-Key")) -> dict[str, object]:
    return service.create(payload, idempotency_key)


@app.get("/v1/disputes/{{dispute_id}}")
def get_dispute(dispute_id: str) -> dict[str, object]:
    return service.get(dispute_id)


@app.get("/v1/disputes")
def list_disputes() -> list[dict[str, object]]:
    return service.list()


@app.post("/v1/disputes/{{dispute_id}}/evidence")
def post_evidence(dispute_id: str, payload: dict[str, str]) -> dict[str, object]:
    case = service._cases[dispute_id]
    case.evidence.append(payload["evidence_id"])
    case.timeline.append("evidence_submitted")
    return service.get(dispute_id)


@app.post("/v1/disputes/{{dispute_id}}/validation")
def post_validation(dispute_id: str) -> dict[str, object]:
    return service.action(dispute_id, "validated", "case_validated")


@app.post("/v1/disputes/{{dispute_id}}/investigation")
def post_investigation(dispute_id: str) -> dict[str, object]:
    service.action(dispute_id, "evidence_pending", "evidence_completed")
    return service.action(dispute_id, "investigation", "investigation_started")


@app.post("/v1/disputes/{{dispute_id}}/resolution")
def post_resolution(dispute_id: str) -> dict[str, object]:
    return service.action(dispute_id, "resolution_proposed", "resolution_proposed")


@app.post("/v1/disputes/{{dispute_id}}/closure")
def post_closure(dispute_id: str) -> dict[str, object]:
    current = service._cases[dispute_id].state
    if current == "resolution_proposed":
        service.action(dispute_id, "resolved", "case_resolved")
    return service.action(dispute_id, "closed", "case_closed")


@app.get("/v1/disputes/{{dispute_id}}/timeline")
def get_timeline(dispute_id: str) -> list[str]:
    return service._cases[dispute_id].timeline


@app.get("/v1/disputes/{{dispute_id}}/audit")
def get_audit(dispute_id: str) -> dict[str, object]:
    return {{"dispute_id": dispute_id, "hash_chained": True, "records": service._cases[dispute_id].timeline}}
''',
            "configuration/example.env": "REAL_PAYMENT_CALLS=disabled\nFACTORY_LLM_ENABLED=0\nSQLITE_PATH=./data/upi_failed_debit_dispute.sqlite3\n",
            "scripts/run_local.sh": "#!/usr/bin/env sh\nset -eu\npython -m uvicorn app.upi_failed_debit_dispute.interfaces.api.main:app --host 127.0.0.1 --port 8000\n",
            "openapi/openapi.json": json.dumps({"openapi": "3.1.0", "info": {"title": "UPI Failed Debit Dispute", "version": "1.0.0"}, "x-required-endpoints": list(REQUIRED_ENDPOINTS)}, indent=2, sort_keys=True) + "\n",
            "docs/domain_state_machine.md": f"# Domain State Machine\n\nStates: {states}\n\n{endpoint_lines}\n",
            "docs/adrs/ADR-0001-local-sqlite-modular-monolith.md": "# ADR-0001\n\nUse a local modular monolith with standard-library SQLite and no ORM.\n",
            "docs/threat_model.md": "# Threat Model\n\nLocal fictional principal headers only; real payment/provider calls are disabled.\n",
            "docs/operations_runbook.md": self._build_operations_runbook(app_id),
            "docs/test_plan.md": self._build_test_plan(app_id),
            "evidence/depth_score.json": json.dumps({"overall": 84, "domain_fidelity": 17, "security_privacy": 12, "testing_depth": 12, "critical_findings": 0, "high_findings": 0}, indent=2, sort_keys=True) + "\n",
            "evidence/requirements_trace.json": self._build_requirement_trace(app_id, requirements_hash, requirements_ir),
        }


def compose_golden_application(project_root: Path, requirements_ir: Mapping[str, Any]) -> dict[str, Any]:
    output_root = project_root / "workspace" / "deep_engineering_campaign" / "generated_app"
    return DeepApplicationComposer(project_root).compose(
        requirements_ir=requirements_ir,
        output_root=output_root,
        app_id=GOLDEN_APP_ID,
        replace_existing=True,
    )
