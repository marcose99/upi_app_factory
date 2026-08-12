#!/usr/bin/env python3
"""Governed portal adapter for deterministic UPI application engineering.

This module is the stable command boundary between the operator portal and the
local UPI App Factory. It is deliberately deterministic by default:

* requirements are read, validated, copied, and SHA-256 hashed;
* a human approval token is required for execution;
* output and evidence roots must remain inside the selected factory workspace;
* real payment/provider calls are prohibited;
* LLM use is disabled unless a future separately governed capability enables it;
* no Git, release, deployment, or external-system operation is performed.

The current deterministic generator creates a production-shaped local FastAPI
application with domain/application/infrastructure/interface separation,
idempotency controls, mock-safe dispute processing, health/readiness endpoints,
tests, Docker assets, and checksummed evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Final, Mapping, Sequence, TypedDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.application_engineering.portfolio import (  # noqa: E402
    PortfolioCatalogue,
    PortfolioStore,
    RegistrationRequest,
)
from factory.operator_portal.state_roots import resolve_portfolio_state_root  # noqa: E402
from factory.debugging import write_generated_application_debug_plan  # noqa: E402
from factory.native_capability_prerun import (  # noqa: E402
    NativeCapabilityError,
    PreRunConfig,
    run_capability_prerun,
)
from factory.generated_application_artifacts import (  # noqa: E402
    DIAGNOSTIC_PROJECTION_USED,
    EVIDENCE_AUTHORITY,
    NO_GO_EVIDENCE_DECISION,
    PROVEN_EVIDENCE_DECISION,
    PUBLICATION_AUTHORITY,
    QUARANTINED_APPLICATION_SUBTREE,
    REQUIRED_ARTIFACT_RELATIVE_PATHS,
    is_quarantined_application_path,
    materialize_generated_application_artifacts,
)
from factory.token_economics import classify_generated_application_token_economics  # noqa: E402

APP_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
APPROVAL_TOKEN: Final[str] = "APPROVE_PORTAL_APPLICATION_ENGINEERING"
SUCCESS_STATUS: Final[str] = "PORTAL_REQUIREMENTS_DRIVEN_APPLICATION_ENGINEERING_COMPLETED"
PLAN_STATUS: Final[str] = "PORTAL_APPLICATION_ENGINEERING_PLAN_VALIDATED"
SCHEMA_VERSION: Final[str] = "1.0"
AUTHORITATIVE_FAILED_DEBIT_CAPABILITIES: Final[tuple[str, ...]] = (
    "failed_debit_disputes",
    "evidence_collection",
    "investigation",
    "human_review",
    "disposition",
    "audit_integrity",
    "closure",
    "health",
    "echo",
    "ready",
)


class AdapterError(RuntimeError):
    """Fail-closed adapter error."""


def _validate_exact_v2_publication_authority(
    materialization: Mapping[str, Any],
) -> dict[str, Any]:
    expected_authority = {
        "evidence_authority": EVIDENCE_AUTHORITY,
        "publication_authority": PUBLICATION_AUTHORITY,
        "diagnostic_projection_used": DIAGNOSTIC_PROJECTION_USED,
    }
    for field, expected in expected_authority.items():
        if materialization.get(field) != expected:
            raise AdapterError(
                f"exact-v2 publication authority is invalid: {field}"
            )

    decision = materialization.get("exact_v2_evidence_decision")
    mandatory_gate_passed = materialization.get(
        "exact_v2_mandatory_gate_passed"
    )
    if materialization.get("exact_v2_evidence_authority") != EVIDENCE_AUTHORITY:
        raise AdapterError("exact-v2 evidence authority is invalid")
    if not isinstance(mandatory_gate_passed, bool):
        raise AdapterError("exact-v2 mandatory gate status is invalid")
    expected_decision = (
        PROVEN_EVIDENCE_DECISION
        if mandatory_gate_passed
        else NO_GO_EVIDENCE_DECISION
    )
    if decision != expected_decision:
        raise AdapterError("exact-v2 evidence decision contradicts the mandatory gate")
    expected_definition_of_done = (
        "definition_of_done_ready"
        if mandatory_gate_passed
        else "definition_of_done_blocked"
    )
    if materialization.get("definition_of_done_status") != expected_definition_of_done:
        raise AdapterError("exact-v2 definition-of-done status contradicts the mandatory gate")
    application_root = materialization.get("application_root")
    project_root = materialization.get("project_root")
    if not isinstance(application_root, str) or not isinstance(project_root, str):
        raise AdapterError("exact-v2 materialization roots are invalid")
    if is_quarantined_application_path(
        Path(application_root),
        project_root=Path(project_root),
    ):
        raise AdapterError(
            "quarantined current_definition_of_done cannot have publication authority"
        )

    return {
        **expected_authority,
        "exact_v2_evidence_decision": decision,
        "exact_v2_evidence_authority": EVIDENCE_AUTHORITY,
        "exact_v2_mandatory_gate_passed": mandatory_gate_passed,
    }


class ManifestRecord(TypedDict):
    """Typed generated-file manifest entry."""

    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class AdapterConfig:
    requirements: Path
    app_id: str
    output_root: Path
    evidence_root: Path
    approval_mode: str
    approval_token: str | None
    mock_safe: bool
    plan_only: bool
    replace_existing: bool
    factory_root: Path
    workspace_root: Path
    portfolio_state_root: Path | None = None
    engineering_profile: str = "compatibility"
    register_with_portfolio: bool = True


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _normalized_distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _generated_application_dependency_inputs(
    application_root: Path,
) -> tuple[dict[str, tuple[str, str]], dict[str, Any], str, str]:
    lock_path = application_root / "requirements.lock"
    contract_path = application_root / "dependency_contract.json"
    if not lock_path.is_file() or not contract_path.is_file():
        raise AdapterError("generated application dependency inputs are missing")
    locked: dict[str, tuple[str, str]] = {}
    for line_number, raw_line in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)",
            line,
        )
        if match is None:
            raise AdapterError(f"requirements.lock line {line_number} is not an exact pin")
        name, version = match.groups()
        normalized = _normalized_distribution_name(name)
        if normalized in locked:
            raise AdapterError(f"requirements.lock has duplicate distribution {normalized}")
        locked[normalized] = (name, version)
    if not locked:
        raise AdapterError("requirements.lock has no exact dependency pins")
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AdapterError("dependency_contract.json is not valid JSON") from exc
    if not isinstance(contract, dict):
        raise AdapterError("dependency_contract.json must contain an object")
    lock_sha256 = _sha256_file(lock_path)
    if contract.get("requirements_lock_sha256") != lock_sha256:
        raise AdapterError("dependency contract lock digest does not match requirements.lock")
    if contract.get("locked_distribution_count") != len(locked):
        raise AdapterError("dependency contract locked distribution count does not match")
    direct = contract.get("direct_distributions")
    if not isinstance(direct, list) or not all(isinstance(item, str) for item in direct):
        raise AdapterError("dependency contract direct distributions are malformed")
    normalized_direct = {_normalized_distribution_name(item) for item in direct}
    if not normalized_direct.issubset(locked):
        raise AdapterError("dependency contract direct distributions are not present in the lock")
    return locked, contract, lock_sha256, _sha256_file(contract_path)


def build_generated_application_cyclonedx(application_root: Path) -> dict[str, Any]:
    locked, contract, lock_sha256, contract_sha256 = (
        _generated_application_dependency_inputs(application_root)
    )
    direct = {
        _normalized_distribution_name(str(item))
        for item in contract["direct_distributions"]
    }
    components = []
    for normalized, (name, version) in sorted(locked.items()):
        components.append(
            {
                "type": "library",
                "bom-ref": f"pkg:pypi/{normalized}@{version}",
                "name": name,
                "version": version,
                "scope": "required",
                "properties": [
                    {
                        "name": "upi_app_factory:identity_source",
                        "value": "requirements.lock exact pin",
                    },
                    {
                        "name": "upi_app_factory:dependency_class",
                        "value": "direct" if normalized in direct else "transitive",
                    },
                    {
                        "name": "upi_app_factory:requirements_lock_sha256",
                        "value": lock_sha256,
                    },
                ],
            }
        )
    application_id = str(contract.get("application_id", "")).strip()
    if not APP_ID_PATTERN.fullmatch(application_id):
        raise AdapterError("dependency contract application_id is invalid")
    serial = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"upi-app-factory:{application_id}:{lock_sha256}:{contract_sha256}",
    )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.7",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": f"{application_id}_generated_application",
            },
            "properties": [
                {
                    "name": "upi_app_factory:claim",
                    "value": "generated SBOM evidence; schema validation is local structural validation only",
                },
                {
                    "name": "upi_app_factory:source_lockfile",
                    "value": "requirements.lock",
                },
                {
                    "name": "upi_app_factory:requirements_lock_sha256",
                    "value": lock_sha256,
                },
                {
                    "name": "upi_app_factory:dependency_contract",
                    "value": "dependency_contract.json",
                },
                {
                    "name": "upi_app_factory:dependency_contract_sha256",
                    "value": contract_sha256,
                },
                {
                    "name": "upi_app_factory:live_payment_calls_allowed",
                    "value": "false",
                },
            ],
        },
        "components": components,
        "unresolved_risks": [
            {
                "risk_id": "LOCK-001",
                "owner": "factory_governance_owner",
                "risk": "Wheel hashes remain blocked until an offline wheelhouse is supplied; exact generated-application pins are recorded.",
            }
        ],
    }


def validate_generated_application_cyclonedx(application_root: Path) -> dict[str, Any]:
    expected = build_generated_application_cyclonedx(application_root)
    sbom_path = application_root / "evidence/assurance/cyclonedx_1_7_sbom.json"
    if not sbom_path.is_file():
        raise AdapterError("generated application CycloneDX SBOM is missing")
    try:
        observed = json.loads(sbom_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AdapterError("generated application CycloneDX SBOM is not valid JSON") from exc
    if observed != expected:
        raise AdapterError(
            "generated application CycloneDX SBOM does not exactly match its lock and dependency contract"
        )
    return {
        "application_root": str(application_root.resolve()),
        "component_count": len(expected["components"]),
        "requirements_lock_sha256": next(
            item["value"]
            for item in expected["metadata"]["properties"]
            if item["name"] == "upi_app_factory:requirements_lock_sha256"
        ),
        "status": "valid",
    }


def materialize_generated_application_cyclonedx(application_root: Path) -> dict[str, Any]:
    payload = build_generated_application_cyclonedx(application_root)
    destination = application_root / "evidence/assurance/cyclonedx_1_7_sbom.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    validate_generated_application_cyclonedx(application_root)
    return payload


def validate_app_id(value: str) -> str:
    app_id = value.strip()
    if not APP_ID_PATTERN.fullmatch(app_id):
        raise AdapterError("invalid app id")
    if app_id in {".", ".."} or any(separator in app_id for separator in ("/", "\\")):
        raise AdapterError("invalid app id")
    if app_id != value or not app_id.isascii():
        raise AdapterError("invalid app id")
    return app_id


def _source_commit(factory_root: Path) -> str:
    injected = os.getenv("UPI_APP_FACTORY_SOURCE_COMMIT")
    if injected:
        return injected
    try:
        completed = subprocess.run(
            ["git", "-C", str(factory_root), "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        completed = None
    if completed is not None:
        commit = completed.stdout.strip()
        if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", commit):
            return commit
    manifest_path = factory_root / "FACTORY_EXPORT_MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AdapterError("FACTORY_EXPORT_MANIFEST.json is not valid JSON") from exc
        if not isinstance(manifest, dict):
            raise AdapterError("FACTORY_EXPORT_MANIFEST.json must contain an object")
        repository_commit = manifest.get("repository_commit")
        if isinstance(repository_commit, str) and re.fullmatch(r"[0-9a-f]{40}", repository_commit):
            return repository_commit
        raise AdapterError("FACTORY_EXPORT_MANIFEST.json repository_commit is invalid")
    return "unavailable:deterministic_non_git_non_manifest_source_root"


def _deterministic_version_id(*, app_id: str, run_id: str, requirements_sha256: str) -> str:
    material = f"{app_id}\n{run_id}\n{requirements_sha256}".encode("utf-8")
    return "v1_" + _sha256_bytes(material)[:16]


def _token_economics_contract(requirements_text: str) -> dict[str, object]:
    applicability = classify_generated_application_token_economics(
        requirements_text=requirements_text,
        runtime_llm_calls_default=0,
    )
    return {
        "policy_version": "2026-07-29.v1",
        "applicability": applicability,
        "rate_card_registry_path": "config/token_economics/rate_cards",
        "budget_envelope_path": "config/token_economics/budgets/default_stage_budget.json",
        "artifact_ownership_registry_path": "config/token_economics/artifact_ownership_registry.json",
        "provider_native_usage_retained": applicability["status"] == "APPLICABLE",
        "mock_only": True,
    }


def _resolve_under(path: Path, root: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve()
    resolved_root = root.expanduser().resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise AdapterError(f"{label} must be inside {resolved_root}: {resolved}") from exc
    return resolved


def _read_requirements(path: Path) -> tuple[str, str]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise AdapterError(f"requirements file does not exist: {resolved}")
    text = resolved.read_text(encoding="utf-8")
    if len(text.strip()) < 80:
        raise AdapterError("requirements input is too small to be authoritative")
    return text, _sha256_bytes(text.encode("utf-8"))


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic, governed, requirements-driven application "
            "engineering for the operator portal."
        )
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=None,
        help="Authoritative requirements Markdown path.",
    )
    parser.add_argument(
        "--app-id",
        default=os.getenv("FACTORY_APP_ID", "upi_dispute_resolution"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Canonical generated-application output root.",
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=None,
        help="Timestamped evidence parent root.",
    )
    parser.add_argument(
        "--approval-mode",
        choices=("human-gated", "proposal-only"),
        default="human-gated",
    )
    parser.add_argument(
        "--approval-token",
        default=os.getenv("FACTORY_PORTAL_APPROVAL_TOKEN"),
        help="Exact non-secret human approval token.",
    )
    parser.add_argument(
        "--mock-safe",
        action="store_true",
        default=os.getenv("MOCK_BOUNDARY", "0") == "1",
    )
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument(
        "--engineering-profile",
        choices=("compatibility", "local-deep-v1", "authoritative-failed-debit-v1"),
        default=os.getenv("FACTORY_ENGINEERING_PROFILE", "compatibility"),
        help="Use compatibility output, the Phase 56 deep profile, or the authoritative failed-debit runtime wrapper.",
    )
    parser.add_argument(
        "--portfolio-state-root",
        type=Path,
        default=None,
        help="Portfolio catalogue state root; defaults under the factory worktree.",
    )
    return parser.parse_args(argv)


def _configuration(args: argparse.Namespace) -> AdapterConfig:
    factory_root = Path(os.getenv("UPI_APP_FACTORY_ROOT", Path.cwd())).expanduser().resolve()
    workspace_root = (
        Path(
            os.getenv(
                "UPI_APP_FACTORY_WORKSPACE_ROOT",
                factory_root / "workspace",
            )
        )
        .expanduser()
        .resolve()
    )

    requirements = args.requirements or Path(
        os.getenv(
            "FACTORY_REQUIREMENTS_PATH",
            os.getenv(
                "FACTORY_PORTAL_REQUIREMENTS_PATH",
                "",
            ),
        )
    )
    if not str(requirements):
        raise AdapterError(
            "requirements path is required via --requirements or FACTORY_REQUIREMENTS_PATH"
        )

    output_root = args.output_root or Path(
        os.getenv(
            "FACTORY_OUTPUT_ROOT",
            workspace_root / "factory_generated" / args.app_id / "generated_application",
        )
    )
    evidence_root = args.evidence_root or Path(
        os.getenv(
            "UPI_APP_FACTORY_EVIDENCE_ROOT",
            workspace_root / "portal_generation_evidence",
        )
    )
    portfolio_state_root = resolve_portfolio_state_root(
        project_root=factory_root,
        portfolio_state_root=args.portfolio_state_root,
    )

    app_id = validate_app_id(args.app_id)

    output_root = _resolve_under(
        output_root,
        workspace_root,
        label="output root",
    )
    evidence_root = _resolve_under(
        evidence_root,
        workspace_root,
        label="evidence root",
    )

    return AdapterConfig(
        requirements=Path(requirements).expanduser().resolve(),
        app_id=app_id,
        output_root=output_root,
        evidence_root=evidence_root,
        approval_mode=args.approval_mode,
        approval_token=args.approval_token,
        mock_safe=bool(args.mock_safe),
        plan_only=bool(args.plan_only),
        replace_existing=bool(args.replace_existing),
        engineering_profile=args.engineering_profile,
        factory_root=factory_root,
        workspace_root=workspace_root,
        portfolio_state_root=portfolio_state_root,
    )


def _parameterize_generated_python_imports(
    files: Mapping[str, str],
    package: str,
) -> dict[str, str]:
    # Render generated Python imports for the requested application package.
    source_prefix = "app.upi_dispute_resolution"
    target_prefix = f"app.{package}"
    return {
        relative: (
            content.replace(source_prefix, target_prefix)
            if relative.endswith(".py")
            else content
        )
        for relative, content in files.items()
    }


def _project_files(
    config: AdapterConfig,
    requirements_text: str,
    requirements_sha: str,
) -> Mapping[str, str]:
    package = config.app_id
    generated_at = _utc_now()
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "app_id": config.app_id,
        "human_name": "UPI Dispute Resolution",
        "requirements_sha256": requirements_sha,
        "generated_at_utc": generated_at,
        "mode": "mock-safe-local",
        "real_payment_calls": "disabled",
        "llm_calls": 0,
        "certification_posture": "certification-ready-not-certified",
        "token_economics": _token_economics_contract(requirements_text),
    }

    files: dict[str, str] = {
        "requirements.md": requirements_text,
        "conftest.py": """from __future__ import annotations

from pathlib import Path


collect_ignore_glob = (
    ["tests/test_*.py"]
    if Path.cwd().resolve() != Path(__file__).resolve().parent
    else []
)
""",
        "app/__init__.py": "",
        "tests/__init__.py": "",
        "generation_metadata.json": (json.dumps(metadata, indent=2, sort_keys=True) + "\n"),
        "README.md": f"""# UPI Dispute Resolution

Deterministically engineered by UPI App Factory from the authoritative
requirements input.

## Safety boundary

- Local and mock-safe.
- No live bank, NPCI, PSP, UPI-rail, or payment-switch calls.
- No production deployment.
- Certification-ready-not-certified.

## Run

```bash
python -m uvicorn app.{package}.interfaces.api.main:app --reload
```

The application writes one JSON log object per line to stdout by default. Use
UPI_APP_FACTORY_LOG_LEVEL, UPI_APP_FACTORY_LOG_FORMAT=json|console,
UPI_APP_FACTORY_LOG_FILE, UPI_APP_FACTORY_LOG_MAX_BYTES,
UPI_APP_FACTORY_LOG_BACKUP_COUNT, and
UPI_APP_FACTORY_LOG_INCLUDE_STACKTRACE=false to control local logging.

## Validate

```bash
python -m pytest -q
```
""",
        "pyproject.toml": f"""[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "{config.app_id.replace("_", "-")}"
version = "0.1.0"
description = "Mock-safe UPI dispute resolution application"
requires-python = ">=3.10"
dependencies = [
  "fastapi>=0.100",
  "pydantic>=1.10",
  "uvicorn>=0.22",
]

[project.optional-dependencies]
test = ["pytest>=8", "httpx>=0.24"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
""",
        "Dockerfile": f"""FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.{package}.interfaces.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
""",
        "docker-compose.yml": """services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      REAL_PAYMENT_CALLS: disabled
      MOCK_BOUNDARY: "1"
""",
        f"app/{package}/__init__.py": ('"""UPI dispute resolution generated application."""\n'),
        f"app/{package}/domain/__init__.py": "",
        f"app/{package}/domain/entities.py": """from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class DisputeStatus(str, Enum):
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class Dispute:
    dispute_id: str
    transaction_id: str
    reason: str
    amount_minor: int
    status: DisputeStatus
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        transaction_id: str,
        reason: str,
        amount_minor: int,
    ) -> "Dispute":
        if not transaction_id.strip():
            raise ValueError("transaction_id is required")
        if len(reason.strip()) < 3:
            raise ValueError("reason must contain at least three characters")
        if amount_minor <= 0:
            raise ValueError("amount_minor must be positive")
        return cls(
            dispute_id=str(uuid4()),
            transaction_id=transaction_id.strip(),
            reason=reason.strip(),
            amount_minor=amount_minor,
            status=DisputeStatus.RECEIVED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
""",
        f"app/{package}/application/__init__.py": "",
        f"app/{package}/application/ports.py": """from __future__ import annotations

from typing import Protocol

from app.upi_dispute_resolution.domain.entities import Dispute


class DisputeRepository(Protocol):
    def add(self, dispute: Dispute) -> None: ...
    def get(self, dispute_id: str) -> Dispute | None: ...


class IdempotencyStore(Protocol):
    def get(self, key: str) -> str | None: ...
    def put(self, key: str, dispute_id: str) -> None: ...
""",
        f"app/{package}/application/services.py": """from __future__ import annotations

from dataclasses import dataclass

from app.upi_dispute_resolution.application.ports import (
    DisputeRepository,
    IdempotencyStore,
)
from app.upi_dispute_resolution.domain.entities import Dispute


@dataclass
class DisputeService:
    repository: DisputeRepository
    idempotency: IdempotencyStore

    def create(
        self,
        *,
        idempotency_key: str,
        transaction_id: str,
        reason: str,
        amount_minor: int,
    ) -> tuple[Dispute, bool]:
        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        existing_id = self.idempotency.get(idempotency_key)
        if existing_id:
            existing = self.repository.get(existing_id)
            if existing is None:
                raise RuntimeError("idempotency record is inconsistent")
            return existing, True

        dispute = Dispute.create(
            transaction_id=transaction_id,
            reason=reason,
            amount_minor=amount_minor,
        )
        self.repository.add(dispute)
        self.idempotency.put(idempotency_key, dispute.dispute_id)
        return dispute, False

    def get(self, dispute_id: str) -> Dispute | None:
        return self.repository.get(dispute_id)
""",
        f"app/{package}/infrastructure/__init__.py": "",
        f"app/{package}/infrastructure/memory.py": """from __future__ import annotations

from dataclasses import dataclass, field

from app.upi_dispute_resolution.domain.entities import Dispute


@dataclass
class InMemoryDisputeRepository:
    values: dict[str, Dispute] = field(default_factory=dict)

    def add(self, dispute: Dispute) -> None:
        self.values[dispute.dispute_id] = dispute

    def get(self, dispute_id: str) -> Dispute | None:
        return self.values.get(dispute_id)


@dataclass
class InMemoryIdempotencyStore:
    values: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def put(self, key: str, dispute_id: str) -> None:
        self.values[key] = dispute_id
""",
        f"app/{package}/interfaces/__init__.py": "",
        f"app/{package}/interfaces/api/__init__.py": "",
        f"app/{package}/observability/__init__.py": """from app.upi_dispute_resolution.observability.structured_logging import configure_logging, get_logger, logging_context, trace_context_from_traceparent

__all__ = ["configure_logging", "get_logger", "logging_context", "trace_context_from_traceparent"]
""",
        f"app/{package}/observability/structured_logging.py": '''from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
import re
import secrets
import sys
import time
from typing import Any, Iterator

SCHEMA_VERSION = "upi-app-factory.log.v1"
SERVICE_INSTANCE_ID = secrets.token_hex(16)
TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")
SENSITIVE_KEY_RE = re.compile(
    r"authorization|cookie|token|secret|password|api_key|credential|account|vpa|mobile|phone|email|pan|aadhaar|card|cvv|payload|body|content",
    re.IGNORECASE,
)
CONTROL_RE = re.compile(r"[\\x00-\\x1f\\x7f]")
SEVERITY_NUMBERS = {"DEBUG": 5, "INFO": 9, "WARNING": 13, "ERROR": 17, "CRITICAL": 21}
_context: ContextVar[dict[str, str]] = ContextVar("upi_generated_log_context", default={})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _clean(value: str, limit: int = 800) -> str:
    cleaned = CONTROL_RE.sub(" ", value).replace("\\r", " ").replace("\\n", " ")
    return cleaned[:limit] + "...[truncated]" if len(cleaned) > limit else cleaned


def _redact(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "[REDACTED:MAX_DEPTH]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 80:
                result["[truncated]"] = "max_items"
                break
            key_text = _clean(str(key), 120)
            result[key_text] = "[REDACTED]" if SENSITIVE_KEY_RE.search(key_text) else _redact(item, depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_redact(item, depth + 1) for item in list(value)[:80]]
    if isinstance(value, str):
        return _clean(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return f"[{type(value).__name__}]"


def trace_context_from_traceparent(traceparent: str | None, request_id: str | None = None) -> dict[str, str]:
    if traceparent:
        match = TRACEPARENT_RE.fullmatch(traceparent.strip())
        if match and int(match.group(1), 16) != 0 and int(match.group(2), 16) != 0:
            return {
                "trace_id": match.group(1),
                "span_id": secrets.token_hex(8),
                "trace_flags": match.group(3),
                "request_id": request_id or secrets.token_hex(16),
            }
    return {
        "trace_id": secrets.token_hex(16),
        "span_id": secrets.token_hex(8),
        "trace_flags": "01",
        "request_id": request_id or secrets.token_hex(16),
    }


@contextmanager
def logging_context(**values: str | None) -> Iterator[None]:
    merged = {**_context.get()}
    for key, value in values.items():
        if value is not None:
            merged[key] = str(value)
    token = _context.set(merged)
    try:
        yield
    finally:
        _context.reset(token)


class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str, service_version: str) -> None:
        super().__init__()
        self.service_name = service_name
        self.service_version = service_version

    def format(self, record: logging.LogRecord) -> str:
        timestamp = _now()
        attributes = _redact(getattr(record, "attributes", {}) or {})
        if not isinstance(attributes, dict):
            attributes = {"attributes": attributes}
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": timestamp,
            "observed_timestamp": timestamp,
            "severity_text": record.levelname,
            "severity_number": SEVERITY_NUMBERS.get(record.levelname, record.levelno),
            "body": _clean(record.getMessage()),
            "event_name": _clean(str(getattr(record, "event_name", record.name)), 180),
            "service.name": self.service_name,
            "service.namespace": "upi_app_factory.engineered_applications",
            "service.version": self.service_version,
            "service.instance.id": SERVICE_INSTANCE_ID,
            "deployment.environment.name": os.getenv("UPI_APP_FACTORY_ENVIRONMENT", "local"),
            "source": _clean(record.name, 180),
        }
        envelope.update({key: _clean(value) for key, value in _context.get().items()})
        envelope.update({key: value for key, value in attributes.items() if value is not None})
        return json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))


def configure_logging(service_name: str, service_version: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if os.getenv("UPI_APP_FACTORY_LOG_FORMAT", "json").lower() == "console":
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    else:
        handler.setFormatter(JsonFormatter(service_name, service_version))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, os.getenv("UPI_APP_FACTORY_LOG_LEVEL", "INFO").upper(), logging.INFO))
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


async def request_logging_middleware(request: Any, call_next: Any, *, logger: logging.Logger) -> Any:
    started = time.perf_counter()
    context = trace_context_from_traceparent(request.headers.get("traceparent"), request.headers.get("x-request-id"))
    with logging_context(**context, correlation_id=context["request_id"]):
        response = await call_next(request)
        response.headers["traceparent"] = f"00-{context['trace_id']}-{context['span_id']}-{context['trace_flags']}"
        response.headers["x-request-id"] = context["request_id"]
        logger.info(
            "Request completed.",
            extra={
                "event_name": "http.request.completed",
                "attributes": {
                    "http.request.method": request.method,
                    "url.path": request.url.path,
                    "http.response.status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "outcome": "success" if response.status_code < 500 else "failure",
                },
            },
        )
        return response
''',
        f"app/{package}/interfaces/api/main.py": """from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
import os
from typing import AsyncIterator

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.upi_dispute_resolution.application.services import DisputeService
from app.upi_dispute_resolution.infrastructure.memory import (
    InMemoryDisputeRepository,
    InMemoryIdempotencyStore,
)
from app.upi_dispute_resolution.observability.structured_logging import (
    configure_logging,
    get_logger,
    request_logging_middleware,
)

SERVICE_VERSION = "0.1.0"
configure_logging(service_name=\"""" + config.app_id + """\", service_version=SERVICE_VERSION)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Generated application startup.",
        extra={"event_name": "generated_application.startup", "attributes": {"outcome": "success"}},
    )
    try:
        yield
    finally:
        logger.info(
            "Generated application shutdown.",
            extra={"event_name": "generated_application.shutdown", "attributes": {"outcome": "success"}},
        )


app = FastAPI(
    title="UPI Dispute Resolution",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

service = DisputeService(
    repository=InMemoryDisputeRepository(),
    idempotency=InMemoryIdempotencyStore(),
)


@app.middleware("http")
async def generated_request_logging(request: Request, call_next):
    return await request_logging_middleware(request, call_next, logger=logger)


class CreateDisputeRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=500)
    amount_minor: int = Field(gt=0)


class EchoScenarioRequest(BaseModel):
    client_request_id: str = Field(min_length=1, max_length=128)
    amount: int = Field(ge=0)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {
        "status": "ready",
        "mode": "mock-safe-local",
        "real_payment_calls": os.getenv(
            "REAL_PAYMENT_CALLS",
            "disabled",
        ),
    }


@app.get("/runtime/health")
def runtime_health() -> dict[str, str]:
    return {"status": "passed", "mode": "mock-safe-local"}


@app.get("/capabilities")
def capabilities() -> dict[str, object]:
    return {
        "mock_only": True,
        "capabilities": ["health", "echo"],
        "live_provider_calls_allowed": False,
        "default_runtime_llm_calls": 0,
    }


@app.post("/scenario/echo", response_model=None)
async def scenario_echo(request: Request) -> object:
    payload = await request.json()
    try:
        scenario = EchoScenarioRequest(**payload)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error"}},
        )
    return {
        "accepted": True,
        "client_request_id": scenario.client_request_id,
        "amount": scenario.amount,
        "replay_status": 200,
    }


@app.get("/missing")
def missing() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": {"code": "not_found"}})


@app.post("/v1/disputes", status_code=status.HTTP_201_CREATED)
def create_dispute(
    request: CreateDisputeRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    dispute, replayed = service.create(
        idempotency_key=idempotency_key,
        transaction_id=request.transaction_id,
        reason=request.reason,
        amount_minor=request.amount_minor,
    )
    payload = asdict(dispute)
    payload["idempotent_replay"] = replayed
    return payload


@app.get("/v1/disputes/{dispute_id}")
def get_dispute(dispute_id: str) -> dict[str, object]:
    dispute = service.get(dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="dispute not found")
    return asdict(dispute)
""",
        "tests/test_service.py": """from app.upi_dispute_resolution.application.services import DisputeService
from app.upi_dispute_resolution.infrastructure.memory import (
    InMemoryDisputeRepository,
    InMemoryIdempotencyStore,
)


def test_create_and_idempotent_replay() -> None:
    service = DisputeService(
        repository=InMemoryDisputeRepository(),
        idempotency=InMemoryIdempotencyStore(),
    )
    first, replayed_first = service.create(
        idempotency_key="idem-1",
        transaction_id="txn-1",
        reason="cash not received",
        amount_minor=1000,
    )
    second, replayed_second = service.create(
        idempotency_key="idem-1",
        transaction_id="txn-1",
        reason="cash not received",
        amount_minor=1000,
    )
    assert replayed_first is False
    assert replayed_second is True
    assert first.dispute_id == second.dispute_id
""",
        "tests/test_api_contract.py": """from app.upi_dispute_resolution.interfaces.api.main import (
    CreateDisputeRequest,
    EchoScenarioRequest,
    capabilities,
    create_dispute,
    health,
    runtime_health,
    ready,
)


def test_health() -> None:
    assert health() == {"status": "ok"}


def test_ready() -> None:
    assert ready() == {
        "status": "ready",
        "mode": "mock-safe-local",
        "real_payment_calls": "disabled",
    }


def test_portfolio_scenario_contracts() -> None:
    assert runtime_health()["status"] == "passed"
    assert capabilities()["mock_only"] is True
    assert EchoScenarioRequest(client_request_id="scenario-1", amount=0).amount == 0


def test_create_dispute_and_replay() -> None:
    payload = CreateDisputeRequest(
        transaction_id="txn-api-1",
        reason="beneficiary did not receive funds",
        amount_minor=2500,
    )
    first = create_dispute(payload, idempotency_key="idem-api-1")
    second = create_dispute(payload, idempotency_key="idem-api-1")
    assert first["dispute_id"] == second["dispute_id"]
    assert second["idempotent_replay"] is True
""",
    }
    return _parameterize_generated_python_imports(files, package)


def _write_tree(root: Path, files: Mapping[str, str]) -> None:
    for relative, content in sorted(files.items()):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def _manifest(root: Path) -> list[ManifestRecord]:
    records: list[ManifestRecord] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        records.append(
            {
                "relative_path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return records


def _validate_publication_manifest_quarantine(
    records: Sequence[ManifestRecord],
) -> None:
    quarantine_root = (
        Path("generated_application") / QUARANTINED_APPLICATION_SUBTREE
    ).as_posix()
    leaked = sorted(
        record["relative_path"]
        for record in records
        if record["relative_path"] == quarantine_root
        or record["relative_path"].startswith(quarantine_root + "/")
    )
    if leaked:
        raise AdapterError(
            "publication manifest contains quarantined current_definition_of_done paths: "
            + ", ".join(leaked)
        )


def _redact_output(text: str) -> str:
    patterns = (
        re.compile(r"(?i)(approval[_-]?token|api[_-]?key|secret|password|token)=\S+"),
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    )
    redacted = text.replace("\r", "\\r")
    for pattern in patterns:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted[:8000]


def _pytest_counts(output: str) -> dict[str, int]:
    counts = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "warnings": 0,
        "collected": 0,
    }
    collected = re.search(r"collected\s+(\d+)\s+items?", output)
    if collected:
        counts["collected"] = int(collected.group(1))
    for name in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed", "warnings"):
        matches = re.findall(rf"(\d+)\s+{name}\b", output)
        if matches:
            counts[name] = int(matches[-1])
    if counts["collected"] == 0:
        counts["collected"] = sum(counts[name] for name in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed"))
    return counts


def _generated_test_inventory(root: Path) -> dict[str, Any]:
    test_files = sorted(path.relative_to(root).as_posix() for path in (root / "tests").glob("test_*.py"))
    return {
        "present": {
            "api": [path for path in test_files if "api" in path or "contract" in path],
            "ui": [path for path in test_files if "ui" in path or "browser" in path],
            "other": [path for path in test_files if not ("api" in path or "contract" in path or "ui" in path or "browser" in path)],
            "all": test_files,
            "count": len(test_files),
        },
    }


def _execute_generated_tests(
    *,
    app_root: Path,
    app_id: str,
    version_id: str,
    run_id: str,
    requirements_sha256: str,
) -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[1]
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--disable-warnings",
        f"--rootdir={project_root}",
        str(app_root / "tests"),
    ]
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(
                part
                for part in (str(app_root), str(project_root), env.get("PYTHONPATH", ""))
                if part
            ),
            "REAL_PAYMENT_CALLS": "disabled",
            "MOCK_BOUNDARY": "1",
            "FACTORY_LLM_ENABLED": "0",
        }
    )
    completed = subprocess.run(
        argv,
        cwd=app_root,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    combined_output = (completed.stdout or "") + (completed.stderr or "")
    inventory = _generated_test_inventory(app_root)
    executed = list(inventory["present"]["all"]) if completed.returncode == 0 else []
    counts = _pytest_counts(combined_output)
    report = {
        "schema_version": "generated-application-test-execution.v1",
        "app_id": app_id,
        "version_id": version_id,
        "run_id": run_id,
        "requirements_sha256": requirements_sha256,
        "argv": argv,
        "argv_sha256": _sha256_bytes(json.dumps(argv, separators=(",", ":")).encode("utf-8")),
        "cwd": str(app_root),
        "exit_code": completed.returncode,
        "counts": counts,
        "tests_present": inventory["present"],
        "tests_executed": {
            "api": [path for path in executed if "api" in path or "contract" in path],
            "ui": [path for path in executed if "ui" in path or "browser" in path],
            "other": [path for path in executed if not ("api" in path or "contract" in path or "ui" in path or "browser" in path)],
            "all": executed,
            "count": len(executed),
        },
        "output_sha256": _sha256_bytes(combined_output.encode("utf-8")),
        "redacted_output": _redact_output(combined_output),
        "go_gate": "GO" if completed.returncode == 0 and counts["collected"] > 0 else "NO-GO",
        "fail_closed": completed.returncode != 0 or counts["collected"] <= 0,
    }
    return report


def _capture_openapi(
    *,
    app_root: Path,
    app_id: str,
    version_id: str,
    run_id: str,
    requirements_sha256: str,
    module: str | None = None,
    pythonpath_root: Path | None = None,
) -> dict[str, Any]:
    module_name = module or f"app.{app_id}.interfaces.api.main"
    code = (
        "import json;"
        f"from {module_name} import app;"
        "print(json.dumps(app.openapi(), sort_keys=True, separators=(',', ':')))"
    )
    argv = [sys.executable, "-c", code]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{pythonpath_root or app_root}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(
        os.pathsep
    )
    completed = subprocess.run(argv, cwd=app_root, env=env, capture_output=True, check=False, text=True, timeout=15)
    if completed.returncode != 0:
        raise AdapterError("generated application OpenAPI capture failed")
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterError("generated application OpenAPI output was not valid JSON") from exc
    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise AdapterError("generated application OpenAPI paths are missing")
    http_methods = {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
    endpoint_inventory = [
        {"method": method.upper(), "path": path}
        for path, methods in sorted(paths.items())
        if isinstance(path, str) and path.startswith("/") and isinstance(methods, dict)
        for method in sorted(methods)
        if isinstance(method, str) and method.lower() in http_methods
    ]
    if not endpoint_inventory:
        raise AdapterError("generated application OpenAPI endpoint inventory is empty")
    document_sha256 = _sha256_bytes(json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    inventory = {
        "schema_version": "generated-application-openapi-inventory.v1",
        "app_id": app_id,
        "version_id": version_id,
        "run_id": run_id,
        "requirements_sha256": requirements_sha256,
        "openapi_sha256": document_sha256,
        "title": document.get("info", {}).get("title", ""),
        "version": document.get("info", {}).get("version", ""),
        "endpoint_inventory": endpoint_inventory,
        "source": "generated_application_fastapi_app.openapi",
        "catalogue_only_fallback_used": False,
    }
    return {"document": document, "inventory": inventory}


def _remove_generated_python_caches(root: Path) -> None:
    for path in sorted(root.rglob("__pycache__")):
        if path.is_dir():
            shutil.rmtree(path)
    pytest_cache = root / ".pytest_cache"
    if pytest_cache.is_dir():
        shutil.rmtree(pytest_cache)


PRIMARY_PORTAL_RUNTIME_TEST = "tests/test_failed_debit_primary_runtime.py"
PRIMARY_PORTAL_WRAPPER_TEST_SIGNATURES: Final[dict[str, str]] = {
    "tests/test_api_contract.py": "test_wrapper_openapi_exposes_authoritative_failed_debit_surface",
    "tests/test_service.py": "test_wrapper_entrypoint_and_nested_runtime_assets_exist",
}
PRIMARY_PORTAL_WRAPPER_FILE_SIGNATURES: Final[dict[str, str]] = {
    "interfaces/api/main.py": "from generated_application.app.interfaces.api.main import app",
}


def _copy_tree_contents(source_root: Path, destination_root: Path) -> None:
    quarantine_root = Path(QUARANTINED_APPLICATION_SUBTREE)
    for path in sorted(source_root.rglob("*")):
        relative = path.relative_to(source_root)
        if relative == quarantine_root or quarantine_root in relative.parents:
            continue
        destination = destination_root / relative
        if path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _prune_empty_directories(start: Path, *, stop_at: Path) -> None:
    current = start
    while current != stop_at and current.exists():
        if any(current.iterdir()):
            return
        current.rmdir()
        current = current.parent


def _remove_signed_wrapper_file(root: Path, relative_path: str, signature: str) -> bool:
    target = root / relative_path
    if not target.is_file():
        return False
    if signature not in target.read_text(encoding="utf-8"):
        return False
    target.unlink()
    _prune_empty_directories(target.parent, stop_at=root)
    return True


def _sanitize_nested_authoritative_runtime_copy(root: Path, app_id: str) -> None:
    for relative_path, signature in PRIMARY_PORTAL_WRAPPER_TEST_SIGNATURES.items():
        _remove_signed_wrapper_file(root, relative_path, signature)
    wrapper_root = root / "app" / app_id
    for relative_path, signature in PRIMARY_PORTAL_WRAPPER_FILE_SIGNATURES.items():
        _remove_signed_wrapper_file(wrapper_root, relative_path, signature)
    if wrapper_root.exists():
        _prune_empty_directories(wrapper_root, stop_at=root / "app")


def _copy_authoritative_runtime_into_publication(
    *,
    source_root: Path,
    destination_root: Path,
    app_id: str,
) -> None:
    _copy_tree_contents(source_root, destination_root)
    _sanitize_nested_authoritative_runtime_copy(destination_root, app_id)
    if (destination_root / QUARANTINED_APPLICATION_SUBTREE).exists():
        raise AdapterError("quarantined current_definition_of_done entered publication copy")


def _authoritative_runtime_template_root(config: AdapterConfig) -> Path:
    root = (
        config.factory_root
        / "workspace"
        / "factory_generated"
        / "upi_dispute_resolution"
        / "generated_application"
    )
    if not root.is_dir():
        raise AdapterError("authoritative failed-debit runtime template is missing")
    return root


def _primary_runtime_wrapper_files(app_id: str, requirements_text: str) -> dict[str, str]:
    return {
        "conftest.py": """from __future__ import annotations

from pathlib import Path


collect_ignore_glob = (
    ["tests/test_*.py"]
    if Path.cwd().resolve() != Path(__file__).resolve().parent
    else []
)
""",
        "app/__init__.py": "",
        f"app/{app_id}/__init__.py": "",
        f"app/{app_id}/interfaces/__init__.py": "",
        f"app/{app_id}/interfaces/api/__init__.py": "",
        f"app/{app_id}/interfaces/api/main.py": (
            "from generated_application.app.interfaces.api.main import app\n\n"
            "__all__ = [\"app\"]\n"
        ),
        "pyproject.toml": f"""[project]
name = "{app_id}"
version = "0.1.0"
requires-python = ">=3.11"
description = "Portal-published authoritative failed-debit runtime wrapper"
""",
        "Dockerfile": (
            "FROM python:3.12-slim\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            f'CMD ["python", "-m", "uvicorn", "app.{app_id}.interfaces.api.main:app", "--host", "127.0.0.1", "--port", "18042"]\n'
        ),
        "README.md": (
            f"# {app_id}\n\n"
            "Primary portal publication for the authoritative failed-debit runtime.\n\n"
            "This package wraps the nested `generated_application` runtime, preserves local-only\n"
            "mock boundaries, and exposes the portal-registered entrypoint\n"
            f"`app.{app_id}.interfaces.api.main:app`.\n\n"
            "## Requirements Snapshot\n\n"
            f"{requirements_text.strip()}\n"
        ),
        "requirements.md": requirements_text,
        "tests/test_api_contract.py": f"""from __future__ import annotations

from app.{app_id}.interfaces.api.main import app


def test_wrapper_openapi_exposes_authoritative_failed_debit_surface() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    required = {{
        "/health",
        "/ready",
        "/v1/disputes",
        "/v1/disputes/{{dispute_id}}/evidence",
        "/v1/disputes/{{dispute_id}}/investigate",
        "/v1/disputes/{{dispute_id}}/classify",
        "/v1/disputes/{{dispute_id}}/human-review",
        "/v1/disputes/{{dispute_id}}/review-decisions",
        "/v1/disputes/{{dispute_id}}/disposition",
        "/v1/disputes/{{dispute_id}}/audit-integrity",
        "/v1/disputes/{{dispute_id}}/close",
        "/v1/disputes/{{dispute_id}}/history",
    }}
    assert required.issubset(paths)
""",
        "tests/test_service.py": f"""from __future__ import annotations

from pathlib import Path

from app.{app_id}.interfaces.api.main import app


def test_wrapper_entrypoint_and_nested_runtime_assets_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "app" / "{app_id}" / "interfaces" / "api" / "main.py").is_file()
    assert (root / "generated_application" / "app" / "interfaces" / "api" / "main.py").is_file()
    assert app.openapi()["info"]["title"]
""",
        PRIMARY_PORTAL_RUNTIME_TEST: """from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from generated_application.app.interfaces.api import main
from generated_application.app.runtime import RuntimeLifecycle
from generated_application.app.security.identity import issue_local_test_token


async def _request(
    app: Any,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://primary-portal-runtime") as client:
        return await client.request(method, path, json=payload, headers=headers)


def request(
    app: Any,
    method: str,
    path: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return asyncio.run(_request(app, method, path, payload=payload, headers=headers))


def token(subject: str, scopes: tuple[str, ...], roles: tuple[str, ...]) -> str:
    return cast(str, issue_local_test_token(subject=subject, scopes=scopes, roles=roles))


def auth(subject: str, scopes: tuple[str, ...], roles: tuple[str, ...]) -> dict[str, str]:
    return {"Authorization": "Bearer " + token(subject, scopes, roles)}


def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    database = tmp_path / "primary_portal_runtime.sqlite3"
    monkeypatch.setattr(main, "DATABASE_PATH", database)
    monkeypatch.setattr(main, "RUNTIME", RuntimeLifecycle(database))
    main.app.state.database_path = database
    return main.app


def test_primary_portal_runtime_proves_failed_debit_lifecycle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = make_client(tmp_path, monkeypatch)
    support_headers = auth(
        "support-portal",
        ("dispute:create", "dispute:evidence:write", "dispute:read", "dispute:read:any"),
        ("customer_support_agent",),
    )
    analyst_headers = auth(
        "analyst-portal",
        (
            "dispute:investigation:write",
            "dispute:classify:write",
            "dispute:review:write",
            "dispute:read",
            "dispute:read:any",
        ),
        ("dispute_operations_analyst",),
    )
    supervisor_headers = auth(
        "supervisor-portal",
        ("dispute:review:write", "dispute:disposition:write", "dispute:close:write", "dispute:read"),
        ("supervisor_approver",),
    )
    audit_headers = auth(
        "audit-portal",
        ("dispute:history:read", "dispute:audit:read"),
        ("audit_reviewer",),
    )

    created = request(
        app,
        "POST",
        "/v1/disputes",
        payload={
            "transaction_ref": "TXN-PORTAL-PRIMARY-001",
            "customer_upi": "portal.primary@upi",
            "amount": "1250.00",
            "reason_code": "beneficiary_not_credited",
        },
        headers={**support_headers, "Idempotency-Key": "portal-primary-create", "X-Correlation-Id": "portal-primary-create"},
    )
    assert created.status_code == 201, created.text
    dispute_id = created.json()["dispute_id"]
    version = int(created.json()["version"])

    evidence_items = [
        ("switch_failure", "EVD-PORTAL-SWITCH", "2026-07-31T04:15:00Z"),
        ("core_ledger", "EVD-PORTAL-LEDGER", "2026-07-31T04:16:00Z"),
        ("customer_statement", "EVD-PORTAL-STATEMENT", "2026-07-31T04:17:00Z"),
    ]
    for index, (evidence_type, evidence_id, observed_at_utc) in enumerate(evidence_items, start=1):
        attached = request(
            app,
            "POST",
            f"/v1/disputes/{dispute_id}/evidence",
            payload={
                "evidence_id": evidence_id,
                "evidence_type": evidence_type,
                "source": f"synthetic_{evidence_type}",
                "summary": f"Synthetic {evidence_type} evidence for the primary portal flow.",
                "observed_at_utc": observed_at_utc,
                "expected_version": version,
            },
            headers={
                **support_headers,
                "Idempotency-Key": f"portal-primary-evidence-{index}",
                "X-Correlation-Id": f"portal-primary-evidence-{index}",
            },
        )
        assert attached.status_code == 200, attached.text
        version = int(attached.json()["version"])

    investigation = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/investigate",
        payload={
            "analyst_notes": "Deterministic investigation confirms the beneficiary remained uncredited.",
            "simulated_bank_status": "beneficiary_not_credited",
            "expected_version": version,
        },
        headers={**analyst_headers, "Idempotency-Key": "portal-primary-investigate", "X-Correlation-Id": "portal-primary-investigate"},
    )
    assert investigation.status_code == 200, investigation.text
    version = int(investigation.json()["version"])

    classification = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/classify",
        payload={"expected_version": version},
        headers={**analyst_headers, "Idempotency-Key": "portal-primary-classify", "X-Correlation-Id": "portal-primary-classify"},
    )
    assert classification.status_code == 200, classification.text
    version = int(classification.json()["version"])

    review = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/human-review",
        payload={
            "reason_code": "HIGH_IMPACT_CASE",
            "rationale": "Primary portal GO gate requires explicit human review evidence.",
            "expected_version": version,
        },
        headers={**analyst_headers, "Idempotency-Key": "portal-primary-review-request", "X-Correlation-Id": "portal-primary-review-request"},
    )
    assert review.status_code == 200, review.text
    version = int(review.json()["version"])
    review_id = review.json()["pending_review_id"]

    review_decision = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/review-decisions",
        payload={
            "decision": "APPROVED",
            "reason_code": "SUPERVISOR_APPROVED",
            "rationale": "Supervisor approves the governed disposition.",
            "review_id": review_id,
            "approved_disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
            "expected_version": version,
        },
        headers={**supervisor_headers, "Idempotency-Key": "portal-primary-review-decision", "X-Correlation-Id": "portal-primary-review-decision"},
    )
    assert review_decision.status_code == 200, review_decision.text
    version = int(review_decision.json()["version"])

    disposition = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/disposition",
        payload={
            "disposition": "CONFIRM_FAILURE_FOR_MANUAL_FOLLOW_UP",
            "reason_code": "FAILED_DEBIT_CONFIRMED",
            "rationale": "Governed local-only operational conclusion.",
            "expected_version": version,
        },
        headers={**supervisor_headers, "Idempotency-Key": "portal-primary-disposition", "X-Correlation-Id": "portal-primary-disposition"},
    )
    assert disposition.status_code == 200, disposition.text

    audit = request(
        app,
        "GET",
        f"/v1/disputes/{dispute_id}/audit-integrity",
        headers={**audit_headers, "X-Correlation-Id": "portal-primary-audit"},
    )
    assert audit.status_code == 200, audit.text
    assert audit.json()["passed"] is True
    version = int(audit.json()["version"])

    closed = request(
        app,
        "POST",
        f"/v1/disputes/{dispute_id}/close",
        payload={
            "reason_code": "CASE_COMPLETE",
            "rationale": "Primary portal closure after audit verification.",
            "expected_version": version,
        },
        headers={**supervisor_headers, "Idempotency-Key": "portal-primary-close", "X-Correlation-Id": "portal-primary-close"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["state"] == "closed"

    history = request(app, "GET", f"/v1/disputes/{dispute_id}/history", headers=audit_headers)
    assert history.status_code == 200, history.text
    event_types = [item["event_type"] for item in history.json()["timeline"]]
    assert "FailedDebitEvidenceAttached" in event_types
    assert "FailedDebitInvestigationRecorded" in event_types
    assert "FailedDebitHumanReviewRequested" in event_types
    assert "FailedDebitReviewDecisionRecorded" in event_types
    assert "FailedDebitDispositionRecorded" in event_types
    assert "FailedDebitAuditIntegrityVerified" in event_types
    assert "FailedDebitCaseClosed" in event_types
""",
    }


def _has_required_failed_debit_endpoints(openapi_inventory: Mapping[str, object]) -> bool:
    inventory = openapi_inventory.get("endpoint_inventory")
    if not isinstance(inventory, list):
        return False
    observed = {
        (str(item.get("method", "")), str(item.get("path", "")))
        for item in inventory
        if isinstance(item, Mapping)
    }
    required = {
        ("POST", "/v1/disputes"),
        ("POST", "/v1/disputes/{dispute_id}/evidence"),
        ("POST", "/v1/disputes/{dispute_id}/investigate"),
        ("POST", "/v1/disputes/{dispute_id}/classify"),
        ("POST", "/v1/disputes/{dispute_id}/human-review"),
        ("POST", "/v1/disputes/{dispute_id}/review-decisions"),
        ("POST", "/v1/disputes/{dispute_id}/disposition"),
        ("GET", "/v1/disputes/{dispute_id}/audit-integrity"),
        ("POST", "/v1/disputes/{dispute_id}/close"),
        ("GET", "/v1/disputes/{dispute_id}/history"),
    }
    return required.issubset(observed)


def _canonical_deep_generated_root(config: AdapterConfig) -> Path:
    return (
        config.factory_root
        / "workspace"
        / "deep_engineering_campaign"
        / "generated_app"
        / config.app_id
    ).resolve()


def _mirror_deep_generated_app(*, config: AdapterConfig, app_root: Path) -> Path:
    canonical_app_root = _canonical_deep_generated_root(config)
    if app_root.resolve() == canonical_app_root:
        return canonical_app_root

    workspace_root = (config.factory_root / "workspace").resolve()
    try:
        canonical_app_root.relative_to(workspace_root)
    except ValueError as exc:
        raise AdapterError("canonical deep generated application root must stay in workspace") from exc

    if canonical_app_root.exists():
        shutil.rmtree(canonical_app_root)
    canonical_app_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app_root, canonical_app_root, symlinks=False)
    return canonical_app_root


def _register_generated_application(
    *,
    config: AdapterConfig,
    run_id: str,
    requirements_text: str,
    requirements_sha: str,
    final_manifest: list[ManifestRecord],
    evidence_dir: Path,
    exact_v2_publication: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    version_id = _deterministic_version_id(
        app_id=config.app_id,
        run_id=run_id,
        requirements_sha256=requirements_sha,
    )
    source_commit = _source_commit(config.factory_root)
    openapi_path = config.output_root / "docs" / "openapi.json"
    openapi_inventory_path = config.output_root / "evidence" / "openapi_inventory.json"
    if not openapi_path.is_file() or not openapi_inventory_path.is_file():
        raise AdapterError("generated OpenAPI evidence is required for portfolio registration")
    openapi_document = json.loads(openapi_path.read_text(encoding="utf-8"))
    openapi_inventory = json.loads(openapi_inventory_path.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "app_id": config.app_id,
        "version_id": version_id,
        "generated_run_id": run_id,
        "source_run_id": run_id,
        "requirements_sha256": requirements_sha,
        "source_commit": source_commit,
        "files": final_manifest,
        "openapi": openapi_document,
        "openapi_inventory": openapi_inventory,
        "token_economics": _token_economics_contract(requirements_text),
        **dict(exact_v2_publication or {}),
    }
    generation_manifest_path = config.output_root / "generation_manifest.json"
    generation_manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "portfolio_registration_evidence",
        "app_id": config.app_id,
        "version_id": version_id,
        "generated_run_id": run_id,
        "source_run_id": run_id,
        "requirements_sha256": requirements_sha,
        "source_commit": source_commit,
        "application_root": str(config.output_root),
        "generation_manifest_sha256": _sha256_file(generation_manifest_path),
        "openapi_sha256": openapi_inventory.get("openapi_sha256"),
        "mock_boundary": "enforced",
        "real_payment_calls": "disabled",
        "certification_posture": "certification-ready-not-certified",
        "token_economics": _token_economics_contract(requirements_text),
        **dict(exact_v2_publication or {}),
    }
    store = PortfolioStore(
        project_root=config.factory_root,
        state_root=resolve_portfolio_state_root(
            project_root=config.factory_root,
            portfolio_state_root=config.portfolio_state_root,
        ),
    )
    catalogue = PortfolioCatalogue(store=store)
    version = catalogue.register(
        RegistrationRequest(
            app_id=config.app_id,
            version_id=version_id,
            generated_run_id=run_id,
            requirements=requirements_text,
            source_commit=source_commit,
            evidence=evidence,
            manifest=manifest,
            entrypoint=f"app.{config.app_id}.interfaces.api.main:app",
            application_root=config.output_root,
            capabilities=AUTHORITATIVE_FAILED_DEBIT_CAPABILITIES,
        )
    )
    registration = {
        **evidence,
        "catalogue_path": str(store.catalogue_path),
        "catalogue_sha256": catalogue.catalogue()["catalogue_sha256"],
        "version_identity_sha256": version.identity_sha256,
    }
    (evidence_dir / "portfolio_registration.json").write_text(
        json.dumps(registration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metadata_path = config.output_root / "generation_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(
        {
            "version_id": version_id,
            "source_run_id": run_id,
            "source_commit": source_commit,
            "application_root": str(config.output_root),
            "portfolio_registration": registration,
        }
    )
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return registration


def _validate_approval(config: AdapterConfig) -> None:
    if config.plan_only or config.approval_mode == "proposal-only":
        return
    expected = os.getenv("UPI_APP_FACTORY_PORTAL_APPROVAL_TOKEN", APPROVAL_TOKEN)
    if config.approval_token != expected:
        raise AdapterError("human approval token is required for execution")


def _validate_safety(config: AdapterConfig) -> None:
    if not config.mock_safe:
        raise AdapterError("--mock-safe is mandatory")
    if os.getenv("REAL_PAYMENT_CALLS", "disabled").lower() != "disabled":
        raise AdapterError("REAL_PAYMENT_CALLS must be disabled")
    if os.getenv("FACTORY_LLM_ENABLED", "0") not in {"0", "false", "False"}:
        raise AdapterError("FACTORY_LLM_ENABLED must remain disabled")


def _plan_payload(
    config: AdapterConfig,
    requirements_text: str,
    requirements_sha: str,
    native_capability_pre_run: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": PLAN_STATUS,
        "app_id": config.app_id,
        "requirements": str(config.requirements),
        "requirements_sha256": requirements_sha,
        "output_root": str(config.output_root),
        "evidence_root": str(config.evidence_root),
        "portfolio_state_root": str(
            resolve_portfolio_state_root(
                project_root=config.factory_root,
                portfolio_state_root=config.portfolio_state_root,
            )
        ),
        "approval_mode": config.approval_mode,
        "mock_safe": config.mock_safe,
        "replace_existing": config.replace_existing,
        "engineering_profile": config.engineering_profile,
        "register_with_portfolio": config.register_with_portfolio,
        "native_capability_pre_run": native_capability_pre_run,
        "token_economics": _token_economics_contract(requirements_text),
        "llm_calls": 0,
        "real_payment_calls": "disabled",
    }


def _native_capability_output_root(config: AdapterConfig, requirements_sha: str) -> Path:
    return (
        config.evidence_root
        / "native_capability_pre_run"
        / config.app_id
        / requirements_sha
    )


def _run_native_capability_gate(config: AdapterConfig, requirements_sha: str) -> dict[str, object]:
    evidence_factory_root = (
        config.factory_root
        if (config.factory_root / "scripts" / "run_portal_requirements_driven_application_engineering.py").is_file()
        else PROJECT_ROOT
    )
    try:
        report = run_capability_prerun(
            PreRunConfig(
                requirements_document=config.requirements,
                application_id=config.app_id,
                output_root=_native_capability_output_root(config, requirements_sha),
                factory_root=evidence_factory_root,
                expected_requirements_sha256=requirements_sha,
            )
        )
    except NativeCapabilityError as exc:
        raise AdapterError(f"native capability pre-run failed closed: {exc}") from exc
    return {
        "decision": report["decision"],
        "mandatory_gate_passed": report["mandatory_gate_passed"],
        "requirements_sha256": report["requirements_sha256"],
        "obligation_count": report["obligation_count"],
        "summary": report["summary"],
        "artifact_root": str(_native_capability_output_root(config, requirements_sha)),
        "artifact_checksums": report.get("artifact_checksums", {}),
    }


def run(config: AdapterConfig) -> Mapping[str, Any]:
    requirements_text, requirements_sha = _read_requirements(config.requirements)
    _validate_safety(config)
    _validate_approval(config)

    native_capability_pre_run = _run_native_capability_gate(config, requirements_sha)
    plan = _plan_payload(config, requirements_text, requirements_sha, native_capability_pre_run)
    if config.plan_only or config.approval_mode == "proposal-only":
        return plan
    if native_capability_pre_run["mandatory_gate_passed"] is not True:
        raise AdapterError(
            "native capability pre-run did not prove 100 percent capability; "
            f"see {native_capability_pre_run['artifact_root']}"
        )

    if config.output_root.exists() and not config.replace_existing:
        raise AdapterError(
            f"output root already exists: {config.output_root}; "
            "use --replace-existing only after protected approval"
        )

    if config.engineering_profile == "authoritative-failed-debit-v1":
        if config.output_root.exists():
            shutil.rmtree(config.output_root)
        run_id = (
            "portal_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + "_"
            + requirements_sha[:12]
            + "_"
            + _sha256_bytes(str(config.workspace_root).encode("utf-8"))[:8]
        )
        evidence_dir = config.evidence_root / run_id
        evidence_dir.mkdir(parents=True, exist_ok=False)
        staging_parent = config.output_root.parent
        staging_parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{config.output_root.name}.staging.",
                dir=staging_parent,
            )
        )
        try:
            authoritative_root = _authoritative_runtime_template_root(config)
            (staging / "generated_application").mkdir(parents=True, exist_ok=True)
            _copy_authoritative_runtime_into_publication(
                source_root=authoritative_root,
                destination_root=staging / "generated_application",
                app_id=config.app_id,
            )
            exact_v2_materialization = materialize_generated_application_artifacts(
                project_root=config.factory_root,
                application_root=staging / "generated_application",
            )
            exact_v2_publication = _validate_exact_v2_publication_authority(
                exact_v2_materialization
            )
            materialize_generated_application_cyclonedx(staging / "generated_application")
            _write_tree(staging, _primary_runtime_wrapper_files(config.app_id, requirements_text))
            version_id = _deterministic_version_id(
                app_id=config.app_id,
                run_id=run_id,
                requirements_sha256=requirements_sha,
            )
            metadata = {
                "app_id": config.app_id,
                "version_id": version_id,
                "run_id": run_id,
                "requirements_sha256": requirements_sha,
                "entrypoint": f"app.{config.app_id}.interfaces.api.main:app",
                "source_template_root": str(authoritative_root),
                "primary_runtime_control_plane": "portfolio_authoritative",
                **exact_v2_publication,
            }
            (staging / "generation_metadata.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            write_generated_application_debug_plan(
                staging,
                app_id=config.app_id,
                version_id=version_id,
                run_id=run_id,
                requirements_sha256=requirements_sha,
                source_commit=_source_commit(config.factory_root),
            )
            openapi_capture = _capture_openapi(
                app_root=staging,
                app_id=config.app_id,
                version_id=version_id,
                run_id=run_id,
                requirements_sha256=requirements_sha,
            )
            (staging / "docs").mkdir(parents=True, exist_ok=True)
            (staging / "evidence").mkdir(parents=True, exist_ok=True)
            (staging / "docs" / "openapi.json").write_text(
                json.dumps(openapi_capture["document"], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (staging / "evidence" / "openapi_inventory.json").write_text(
                json.dumps(openapi_capture["inventory"], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (evidence_dir / "openapi.json").write_text(
                json.dumps(openapi_capture["document"], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (evidence_dir / "openapi_inventory.json").write_text(
                json.dumps(openapi_capture["inventory"], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            test_execution = _execute_generated_tests(
                app_root=staging,
                app_id=config.app_id,
                version_id=version_id,
                run_id=run_id,
                requirements_sha256=requirements_sha,
            )
            (staging / "evidence" / "generated_test_execution.json").write_text(
                json.dumps(test_execution, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (evidence_dir / "generated_test_execution.json").write_text(
                json.dumps(test_execution, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if test_execution["go_gate"] != "GO":
                raise AdapterError("generated application tests failed or collected zero tests")
            _remove_generated_python_caches(staging)
            manifest_records = _manifest(staging)
            _validate_publication_manifest_quarantine(manifest_records)
            required_paths = {
                "Dockerfile",
                "README.md",
                "conftest.py",
                "generation_metadata.json",
                "pyproject.toml",
                "requirements.md",
                "docs/DEBUG_PLAN.md",
                "docs/openapi.json",
                "evidence/debug_plan.json",
                "evidence/generated_test_execution.json",
                "evidence/openapi_inventory.json",
                PRIMARY_PORTAL_RUNTIME_TEST,
                "tests/test_api_contract.py",
                "tests/test_service.py",
                f"app/{config.app_id}/interfaces/api/main.py",
                "generated_application/app/interfaces/api/main.py",
                "generated_application/evidence/generation_summary.json",
            }
            required_paths.update(
                f"generated_application/{relative_path}"
                for relative_path in REQUIRED_ARTIFACT_RELATIVE_PATHS
            )
            forbidden_paths = {
                "generated_application/tests/test_api_contract.py",
                "generated_application/tests/test_service.py",
                f"generated_application/app/{config.app_id}/interfaces/api/main.py",
            }
            actual_paths = {item["relative_path"] for item in manifest_records}
            missing = sorted(required_paths - actual_paths)
            if missing:
                raise AdapterError("generated output contract is incomplete: " + ", ".join(missing))
            unexpected = sorted(forbidden_paths & actual_paths)
            if unexpected:
                raise AdapterError(
                    "generated output retained portal wrapper artifacts inside nested runtime: "
                    + ", ".join(unexpected)
                )
            if config.output_root.exists():
                shutil.rmtree(config.output_root)
            staging.replace(config.output_root)
            final_manifest = _manifest(config.output_root)
            _validate_publication_manifest_quarantine(final_manifest)
            registration = (
                _register_generated_application(
                    config=config,
                    run_id=run_id,
                    requirements_text=requirements_text,
                    requirements_sha=requirements_sha,
                    final_manifest=final_manifest,
                    evidence_dir=evidence_dir,
                    exact_v2_publication=exact_v2_publication,
                )
                if config.register_with_portfolio
                else None
            )
            manifest_text = "".join(
                f"{item['sha256']}  {item['relative_path']}\n" for item in final_manifest
            )
            (evidence_dir / "manifest.sha256").write_text(manifest_text, encoding="utf-8")
            (evidence_dir / "requirements.sha256").write_text(
                f"{requirements_sha}  {config.requirements.name}\n",
                encoding="utf-8",
            )
            (evidence_dir / "requirements.md").write_text(requirements_text, encoding="utf-8")
            runtime_contract = _has_required_failed_debit_endpoints(openapi_capture["inventory"])
            primary_flow_test = PRIMARY_PORTAL_RUNTIME_TEST in test_execution["tests_executed"]["all"]
            result = {
                **plan,
                "status": SUCCESS_STATUS,
                "run_id": run_id,
                "application_root": str(config.output_root),
                "output_root": str(config.output_root),
                "entrypoint": f"app.{config.app_id}.interfaces.api.main:app",
                "capabilities": list(AUTHORITATIVE_FAILED_DEBIT_CAPABILITIES),
                "generated_file_count": len(final_manifest),
                "health_contract": True,
                "ready_contract": True,
                "generated_tests": test_execution["tests_present"]["all"],
                "generated_test_execution": test_execution,
                "tests_executed": test_execution["tests_executed"],
                "tests_present": test_execution["tests_present"],
                "openapi": openapi_capture["document"],
                "openapi_inventory": openapi_capture["inventory"],
                "evidence_directory": str(evidence_dir),
                "failed_debit_runtime_contract": runtime_contract,
                "failed_debit_primary_flow_test": primary_flow_test,
                "primary_runtime_control_plane": "portfolio_authoritative",
                **exact_v2_publication,
                "version_id": registration["version_id"] if registration else version_id,
                "source_commit": (
                    registration["source_commit"]
                    if registration
                    else _source_commit(config.factory_root)
                ),
                "portfolio_registration": registration,
                "completed_at_utc": _utc_now(),
                "llm_calls": 0,
                "real_payment_calls": "disabled",
                "mock_boundary": True,
                "token_economics": _token_economics_contract(requirements_text),
            }
            (evidence_dir / "result.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return result
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    if config.engineering_profile == "local-deep-v1":
        from factory.application_engineering.deep_composer import DeepApplicationComposer
        from factory.application_engineering.requirements_compiler import compile_requirements

        requirements_ir = compile_requirements([config.requirements], config.factory_root)
        manifest = DeepApplicationComposer(config.factory_root).compose(
            requirements_ir=requirements_ir,
            output_root=config.output_root,
            app_id=config.app_id,
            replace_existing=config.replace_existing,
        )
        actual_application_root = config.output_root / config.app_id
        canonical_application_root = _mirror_deep_generated_app(
            config=config,
            app_root=actual_application_root,
        )
        generated_tests = [
            item["path"]
            for item in manifest["file_manifest"]
            if "test" in item["path"]
        ]
        evidence_dir = config.evidence_root / (
            "portal_deep_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + "_"
            + requirements_sha[:12]
        )
        evidence_dir.mkdir(parents=True, exist_ok=False)
        result = {
            **plan,
            "status": SUCCESS_STATUS,
            "composer_profile": manifest["composer_profile"],
            "generated_file_count": manifest["file_count"],
            "health_contract": "GET /health" in manifest["endpoints"],
            "ready_contract": "GET /ready" in manifest["endpoints"],
            "generated_tests": generated_tests,
            "actual_application_root": str(actual_application_root),
            "canonical_application_root": str(canonical_application_root),
            "evidence_directory": str(evidence_dir),
            "completed_at_utc": _utc_now(),
            "token_economics": _token_economics_contract(requirements_text),
        }
        (evidence_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return result

    run_id = (
        "portal_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "_"
        + requirements_sha[:12]
        + "_"
        + _sha256_bytes(str(config.workspace_root).encode("utf-8"))[:8]
    )
    evidence_dir = config.evidence_root / run_id
    evidence_dir.mkdir(parents=True, exist_ok=False)

    staging_parent = config.output_root.parent
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{config.output_root.name}.staging.",
            dir=staging_parent,
        )
    )

    try:
        files = _project_files(
            config,
            requirements_text,
            requirements_sha,
        )
        _write_tree(staging, files)
        version_id = _deterministic_version_id(
            app_id=config.app_id,
            run_id=run_id,
            requirements_sha256=requirements_sha,
        )
        write_generated_application_debug_plan(
            staging,
            app_id=config.app_id,
            version_id=version_id,
            run_id=run_id,
            requirements_sha256=requirements_sha,
            source_commit=_source_commit(config.factory_root),
        )
        openapi_capture = _capture_openapi(
            app_root=staging,
            app_id=config.app_id,
            version_id=version_id,
            run_id=run_id,
            requirements_sha256=requirements_sha,
        )
        (staging / "docs").mkdir(parents=True, exist_ok=True)
        (staging / "evidence").mkdir(parents=True, exist_ok=True)
        (staging / "docs" / "openapi.json").write_text(
            json.dumps(openapi_capture["document"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (staging / "evidence" / "openapi_inventory.json").write_text(
            json.dumps(openapi_capture["inventory"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "openapi.json").write_text(
            json.dumps(openapi_capture["document"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "openapi_inventory.json").write_text(
            json.dumps(openapi_capture["inventory"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        test_execution = _execute_generated_tests(
            app_root=staging,
            app_id=config.app_id,
            version_id=version_id,
            run_id=run_id,
            requirements_sha256=requirements_sha,
        )
        (staging / "evidence" / "generated_test_execution.json").write_text(
            json.dumps(test_execution, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (evidence_dir / "generated_test_execution.json").write_text(
            json.dumps(test_execution, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if test_execution["go_gate"] != "GO":
            raise AdapterError("generated application tests failed or collected zero tests")
        _remove_generated_python_caches(staging)
        manifest_records = _manifest(staging)

        required_paths = {
            "pyproject.toml",
            "Dockerfile",
            "README.md",
            "requirements.md",
            "generation_metadata.json",
            "docs/DEBUG_PLAN.md",
            "docs/openapi.json",
            "evidence/debug_plan.json",
            "evidence/generated_test_execution.json",
            "evidence/openapi_inventory.json",
            "tests/test_service.py",
            "tests/test_api_contract.py",
            (f"app/{config.app_id}/interfaces/api/main.py"),
        }
        actual_paths = {item["relative_path"] for item in manifest_records}
        missing = sorted(required_paths - actual_paths)
        if missing:
            raise AdapterError("generated output contract is incomplete: " + ", ".join(missing))

        api_text = (staging / "app" / config.app_id / "interfaces" / "api" / "main.py").read_text(
            encoding="utf-8"
        )
        if '"/health"' not in api_text or '"/ready"' not in api_text:
            raise AdapterError("health/readiness contracts are missing")

        if config.output_root.exists():
            shutil.rmtree(config.output_root)
        staging.replace(config.output_root)

        final_manifest = _manifest(config.output_root)
        registration = (
            _register_generated_application(
                config=config,
                run_id=run_id,
                requirements_text=requirements_text,
                requirements_sha=requirements_sha,
                final_manifest=final_manifest,
                evidence_dir=evidence_dir,
            )
            if config.register_with_portfolio
            else None
        )
        manifest_text = "".join(
            f"{item['sha256']}  {item['relative_path']}\n" for item in final_manifest
        )
        (evidence_dir / "manifest.sha256").write_text(
            manifest_text,
            encoding="utf-8",
        )
        (evidence_dir / "requirements.sha256").write_text(
            f"{requirements_sha}  {config.requirements.name}\n",
            encoding="utf-8",
        )
        (evidence_dir / "requirements.md").write_text(
            requirements_text,
            encoding="utf-8",
        )
        result = {
            **plan,
            "status": SUCCESS_STATUS,
            "run_id": run_id,
            "generated_file_count": len(final_manifest),
            "health_contract": True,
            "ready_contract": True,
            "generated_tests": [
                "tests/test_service.py",
                "tests/test_api_contract.py",
            ],
            "generated_test_execution": test_execution,
            "tests_executed": test_execution["tests_executed"],
            "tests_present": test_execution["tests_present"],
            "openapi": openapi_capture["document"],
            "openapi_inventory": openapi_capture["inventory"],
            "evidence_directory": str(evidence_dir),
            "version_id": registration["version_id"] if registration else None,
            "source_commit": registration["source_commit"] if registration else _source_commit(config.factory_root),
            "application_root": str(config.output_root),
            "portfolio_registration": registration,
            "completed_at_utc": _utc_now(),
            "token_economics": _token_economics_contract(requirements_text),
        }
        (evidence_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        config = _configuration(args)
        result = run(config)
    except (AdapterError, OSError, ValueError) as exc:
        error = {
            "schema_version": SCHEMA_VERSION,
            "status": "PORTAL_APPLICATION_ENGINEERING_FAILED_CLOSED",
            "error": str(exc),
            "llm_calls": 0,
            "real_payment_calls": "disabled",
        }
        print(json.dumps(error, indent=2, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
