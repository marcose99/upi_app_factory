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
import tempfile
from typing import Final, Mapping, Sequence, TypedDict

APP_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
APPROVAL_TOKEN: Final[str] = "APPROVE_PORTAL_APPLICATION_ENGINEERING"
SUCCESS_STATUS: Final[str] = "PORTAL_REQUIREMENTS_DRIVEN_APPLICATION_ENGINEERING_COMPLETED"
PLAN_STATUS: Final[str] = "PORTAL_APPLICATION_ENGINEERING_PLAN_VALIDATED"
SCHEMA_VERSION: Final[str] = "1.0"


class AdapterError(RuntimeError):
    """Fail-closed adapter error."""


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
    engineering_profile: str = "compatibility"


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
        choices=("compatibility", "local-deep-v1"),
        default=os.getenv("FACTORY_ENGINEERING_PROFILE", "compatibility"),
        help="Use compatibility output or the Phase 56 versioned deep composer profile.",
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

    if not APP_ID_PATTERN.fullmatch(args.app_id):
        raise AdapterError(f"invalid app id: {args.app_id!r}")

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
        app_id=args.app_id,
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
    }

    files: dict[str, str] = {
        "requirements.md": requirements_text,
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
        f"app/{package}/interfaces/api/main.py": """from __future__ import annotations

from dataclasses import asdict
import os

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.upi_dispute_resolution.application.services import DisputeService
from app.upi_dispute_resolution.infrastructure.memory import (
    InMemoryDisputeRepository,
    InMemoryIdempotencyStore,
)

app = FastAPI(
    title="UPI Dispute Resolution",
    version="0.1.0",
)

service = DisputeService(
    repository=InMemoryDisputeRepository(),
    idempotency=InMemoryIdempotencyStore(),
)


class CreateDisputeRequest(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=3, max_length=500)
    amount_minor: int = Field(gt=0)


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
    create_dispute,
    health,
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
    requirements_sha: str,
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": PLAN_STATUS,
        "app_id": config.app_id,
        "requirements": str(config.requirements),
        "requirements_sha256": requirements_sha,
        "output_root": str(config.output_root),
        "evidence_root": str(config.evidence_root),
        "approval_mode": config.approval_mode,
        "mock_safe": config.mock_safe,
        "replace_existing": config.replace_existing,
        "engineering_profile": config.engineering_profile,
        "llm_calls": 0,
        "real_payment_calls": "disabled",
    }


def run(config: AdapterConfig) -> dict[str, object]:
    requirements_text, requirements_sha = _read_requirements(config.requirements)
    _validate_safety(config)
    _validate_approval(config)

    plan = _plan_payload(config, requirements_sha)
    if config.plan_only or config.approval_mode == "proposal-only":
        return plan

    if config.output_root.exists() and not config.replace_existing:
        raise AdapterError(
            f"output root already exists: {config.output_root}; "
            "use --replace-existing only after protected approval"
        )

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
        generated_tests = [
            item["path"]
            for item in manifest["file_manifest"]
            if "test" in item["path"]
        ]
        evidence_dir = config.evidence_root / (
            "portal_deep_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
            "actual_application_root": str(config.output_root / config.app_id),
            "evidence_directory": str(evidence_dir),
            "completed_at_utc": _utc_now(),
        }
        (evidence_dir / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return result

    run_id = (
        "portal_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + requirements_sha[:12]
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
        manifest_records = _manifest(staging)

        required_paths = {
            "pyproject.toml",
            "Dockerfile",
            "README.md",
            "requirements.md",
            "generation_metadata.json",
            "tests/test_service.py",
            "tests/test_api_contract.py",
            (f"app/{config.app_id}/interfaces/api/main.py"),
        }
        actual_paths: set[str] = {item["relative_path"] for item in manifest_records}
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
            "evidence_directory": str(evidence_dir),
            "completed_at_utc": _utc_now(),
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
