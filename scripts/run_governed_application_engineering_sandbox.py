#!/usr/bin/env python3
"""Run a local deterministic governed autonomous application engineering rehearsal."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


if __package__ in {None, ""}:
    project_root_for_path = Path(__file__).resolve().parents[1]
    project_root_text = str(project_root_for_path)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)


from scripts.rehearse_clean_slate_regeneration_sandbox import (  # noqa: E402
    build_sandbox_rehearsal_report,
)


APP_ID = "upi_dispute_resolution"
ENGINEERING_SANDBOX_RELATIVE_ROOT = Path(
    "workspace/factory_generated/upi_dispute_resolution/"
    "lifecycle_artifacts/phase13al/engineered_application_sandbox"
)
REAL_GENERATED_APPLICATION = Path(
    "workspace/factory_generated/upi_dispute_resolution/generated_application"
)

ENGINEERING_STAGES: tuple[str, ...] = (
    "requirements",
    "domain_model",
    "architecture",
    "design",
    "implementation",
    "tests",
    "security_policy",
    "certification",
    "evidence",
    "handoff",
)

ENGINEERING_ARTIFACTS: tuple[tuple[str, str, str], ...] = (
    (
        "requirements",
        "requirements/requirement_package.json",
        '{\n'
        '  "schema_version": "requirement-package.v1",\n'
        '  "app_id": "upi_dispute_resolution",\n'
        '  "capability": "upi_dispute_case_intake_and_status",\n'
        '  "engineering_mode": "SANDBOX_REHEARSAL"\n'
        '}\n',
    ),
    (
        "domain_model",
        "domain/domain_model.md",
        "# UPI Dispute Domain Model\n\nEntities: dispute case, payment reference, participant, evidence item, SLA clock.\n",
    ),
    (
        "architecture",
        "architecture/adr-0001.md",
        "# ADR-0001: Local Governed UPI Dispute Service\n\nUse a local FastAPI-style boundary with mocked ecosystem adapters.\n",
    ),
    (
        "design",
        "design/api_contract.md",
        "# API Contract\n\nEndpoints planned: health, create dispute, get dispute status, submit evidence.\n",
    ),
    (
        "implementation",
        "app/main.py",
        '"""Sandbox-only engineered application artifact."""\n\n'
        "def health() -> dict[str, str]:\n"
        '    return {"status": "ok", "mode": "sandbox-engineering"}\n',
    ),
    (
        "tests",
        "tests/test_health.py",
        "from app.main import health\n\n\n"
        "def test_health() -> None:\n"
        '    assert health()["status"] == "ok"\n',
    ),
    (
        "security_policy",
        "security/policy_checklist.json",
        '{\n'
        '  "pii_redaction_required": true,\n'
        '  "mock_ecosystem_only": true,\n'
        '  "live_provider_calls_allowed": false,\n'
        '  "external_system_calls_allowed": false\n'
        '}\n',
    ),
    (
        "certification",
        "certification/certification_summary.json",
        '{\n'
        '  "schema_version": "capability-certification-summary.v1",\n'
        '  "status": "SANDBOX_REHEARSAL_ONLY",\n'
        '  "requires_full_real_app_certification": true\n'
        '}\n',
    ),
    (
        "evidence",
        "evidence/evidence_manifest.json",
        '{\n'
        '  "schema_version": "engineering-evidence-manifest.v1",\n'
        '  "evidence_scope": "SANDBOX_ONLY",\n'
        '  "human_release_gate_preserved": true\n'
        '}\n',
    ),
    (
        "handoff",
        "handoff/README.md",
        "# Sandbox Handoff\n\nThis handoff is for Phase 13AL rehearsal only. It is not a production release.\n",
    ),
)


@dataclass(frozen=True)
class EngineeringArtifact:
    """One sandbox application engineering artifact."""

    stage: str
    relative_path: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "stage": self.stage,
        }


@dataclass(frozen=True)
class ApplicationEngineeringReport:
    """End-to-end sandbox application engineering rehearsal report."""

    app_id: str
    engineering_status: str
    preferred_term: str
    project_root: str
    sandbox_root: str
    real_generated_application_path: str
    sandbox_only: bool
    phase13ak_sandbox_rehearsal_ready: bool
    materialized_sandbox: bool
    real_generated_application_deleted: bool
    real_generated_application_overwritten: bool
    live_provider_calls_performed: bool
    external_system_calls_performed: bool
    auto_merge_performed: bool
    auto_tag_performed: bool
    auto_release_performed: bool
    stages: tuple[str, ...]
    artifacts: tuple[EngineeringArtifact, ...]
    manifest_digest: str
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.engineering_status == "APPLICATION_ENGINEERING_SANDBOX_READY"

    def to_audit_dict(self) -> dict[str, object]:
        return {
            "app_id": self.app_id,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "auto_merge_performed": self.auto_merge_performed,
            "auto_release_performed": self.auto_release_performed,
            "auto_tag_performed": self.auto_tag_performed,
            "engineering_status": self.engineering_status,
            "external_system_calls_performed": self.external_system_calls_performed,
            "live_provider_calls_performed": self.live_provider_calls_performed,
            "manifest_digest": self.manifest_digest,
            "materialized_sandbox": self.materialized_sandbox,
            "phase13ak_sandbox_rehearsal_ready": self.phase13ak_sandbox_rehearsal_ready,
            "preferred_term": self.preferred_term,
            "project_root": self.project_root,
            "ready": self.ready,
            "real_generated_application_deleted": self.real_generated_application_deleted,
            "real_generated_application_overwritten": self.real_generated_application_overwritten,
            "real_generated_application_path": self.real_generated_application_path,
            "reasons": list(self.reasons),
            "sandbox_only": self.sandbox_only,
            "sandbox_root": self.sandbox_root,
            "schema_version": "governed-autonomous-application-engineering-report.v1",
            "stages": list(self.stages),
        }


def _resolve_project_path(project_root: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _artifact_manifest() -> tuple[EngineeringArtifact, ...]:
    return tuple(
        EngineeringArtifact(
            stage=stage,
            relative_path=relative_path,
            size_bytes=len(content.encode("utf-8")),
            sha256=_sha256_text(content),
        )
        for stage, relative_path, content in ENGINEERING_ARTIFACTS
    )


def _manifest_digest(artifacts: Iterable[EngineeringArtifact]) -> str:
    payload = [artifact.to_dict() for artifact in artifacts]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_engineering_artifacts(sandbox_root: Path) -> None:
    for _stage, relative_path, content in ENGINEERING_ARTIFACTS:
        target = sandbox_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def build_application_engineering_report(
    project_root: Path,
    approval_token: Path | None = None,
    sandbox_root: Path = ENGINEERING_SANDBOX_RELATIVE_ROOT,
    materialize_sandbox: bool = False,
) -> ApplicationEngineeringReport:
    """Build a complete sandbox application engineering rehearsal report."""

    root = project_root.resolve()
    resolved_sandbox = _resolve_project_path(root, sandbox_root)
    approved_sandbox = _resolve_project_path(root, ENGINEERING_SANDBOX_RELATIVE_ROOT)
    real_generated_application = _resolve_project_path(root, REAL_GENERATED_APPLICATION)

    sandbox_only = resolved_sandbox == approved_sandbox and _is_relative_to(resolved_sandbox, root)
    reasons: list[str] = []

    if not sandbox_only:
        reasons.append("Application engineering sandbox path is not the approved Phase 13AL boundary.")

    sandbox_rehearsal = build_sandbox_rehearsal_report(root, approval_token)
    phase13ak_ready = sandbox_rehearsal.ready

    if not phase13ak_ready:
        reasons.append("Phase 13AK sandbox rehearsal is not ready; application engineering remains blocked.")
    else:
        reasons.append("Phase 13AK sandbox rehearsal is ready.")

    artifacts = _artifact_manifest()
    digest = _manifest_digest(artifacts)

    if materialize_sandbox and sandbox_only and phase13ak_ready:
        _write_engineering_artifacts(resolved_sandbox)
        reasons.append("Sandbox application engineering artifacts materialized under Phase 13AL only.")
    elif materialize_sandbox:
        reasons.append("Sandbox materialization skipped because safety preconditions were not met.")

    status = (
        "APPLICATION_ENGINEERING_SANDBOX_READY"
        if sandbox_only and phase13ak_ready
        else "APPLICATION_ENGINEERING_SANDBOX_BLOCKED"
    )

    return ApplicationEngineeringReport(
        app_id=APP_ID,
        engineering_status=status,
        preferred_term="application engineering",
        project_root=str(root),
        sandbox_root=str(resolved_sandbox),
        real_generated_application_path=str(real_generated_application),
        sandbox_only=sandbox_only,
        phase13ak_sandbox_rehearsal_ready=phase13ak_ready,
        materialized_sandbox=materialize_sandbox and sandbox_only and phase13ak_ready,
        real_generated_application_deleted=False,
        real_generated_application_overwritten=False,
        live_provider_calls_performed=False,
        external_system_calls_performed=False,
        auto_merge_performed=False,
        auto_tag_performed=False,
        auto_release_performed=False,
        stages=ENGINEERING_STAGES,
        artifacts=artifacts,
        manifest_digest=digest,
        reasons=tuple(reasons),
    )


def validate_application_engineering_report(report: ApplicationEngineeringReport) -> list[str]:
    """Validate sandbox application engineering safety and completeness."""

    failures: list[str] = []

    if report.preferred_term != "application engineering":
        failures.append("Preferred term must be application engineering")

    if not report.sandbox_only:
        failures.append("Application engineering rehearsal must remain sandbox-only")

    if report.real_generated_application_deleted:
        failures.append("Real generated application must not be deleted")

    if report.real_generated_application_overwritten:
        failures.append("Real generated application must not be overwritten")

    if report.live_provider_calls_performed:
        failures.append("Live provider calls must not occur in Phase 13AL")

    if report.external_system_calls_performed:
        failures.append("External system calls must not occur in Phase 13AL")

    if report.auto_merge_performed or report.auto_tag_performed or report.auto_release_performed:
        failures.append("Phase 13AL must not merge, tag, or release")

    if set(report.stages) != set(ENGINEERING_STAGES):
        failures.append("Engineering stages are incomplete")

    artifact_stages = {artifact.stage for artifact in report.artifacts}
    if set(report.stages) != artifact_stages:
        failures.append("Every engineering stage must produce a sandbox artifact")

    if len(report.manifest_digest) != 64:
        failures.append("Manifest digest must be SHA-256 hex")

    return failures


def write_application_engineering_report(report: ApplicationEngineeringReport, audit_out: Path) -> None:
    """Write deterministic JSON audit for an application engineering report."""

    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(
        json.dumps(report.to_audit_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run governed application engineering sandbox rehearsal.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--approval-token", type=Path)
    parser.add_argument("--sandbox-root", type=Path, default=ENGINEERING_SANDBOX_RELATIVE_ROOT)
    parser.add_argument("--materialize-sandbox", action="store_true")
    parser.add_argument("--audit-out", type=Path)
    args = parser.parse_args()

    report = build_application_engineering_report(
        project_root=args.project_root,
        approval_token=args.approval_token,
        sandbox_root=args.sandbox_root,
        materialize_sandbox=args.materialize_sandbox,
    )

    if args.audit_out is not None:
        write_application_engineering_report(report, args.audit_out)

    print(json.dumps(report.to_audit_dict(), indent=2, sort_keys=True))

    failures = validate_application_engineering_report(report)
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
