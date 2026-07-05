from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

PHASE = "Phase 11B"
DEFAULT_APP_ID = "upi_dispute_resolution"
GENERATION_MODE = "real_local_primary_payment_application_with_mock_ecosystem"

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "real_app_mock_ecosystem_boundary_manifest.json",
    "primary_application_engineering_policy.md",
    "mock_ecosystem_boundary_policy.md",
    "external_connectivity_fail_closed_policy.md",
    "requirement_front_matter_schema.md",
    "phase11b_requirement_intake_contract.md",
    "phase11b_boundary_validation_report.json",
)

REQUIRED_LABELS: tuple[str, ...] = (
    "PRIMARY_PAYMENT_APPLICATION_REAL_LOCAL_SOFTWARE",
    "EXTERNAL_ECOSYSTEM_MOCK_ONLY",
    "SYNTHETIC_DATA_ONLY",
    "REAL_PAYMENT_PROCESSING_FORBIDDEN",
    "EXTERNAL_CONNECTIVITY_FAIL_CLOSED",
    "PRODUCTION_CLAIMS_FORBIDDEN",
    "MIGRATION_SEAMS_ALLOWED",
    "DETERMINISTIC_VALIDATION_REQUIRED",
    "TRACEABILITY_REQUIRED",
    "QUALITY_GATES_REQUIRED",
)

FORBIDDEN_UNSAFE_CLAIMS: tuple[str, ...] = (
    "production ready",
    "production compliant",
    "rbi certified",
    "npci certified",
    "pci certified",
    "approved for live payment use",
    "connects to real npci",
    "connects to real rbi",
    "connects to real bank",
    "processes real payments",
    "uses real customer data",
)


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json_loads_dict(text: str) -> dict[str, Any]:
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("Expected a JSON object.")
    return cast(dict[str, Any], loaded)


def _find_forbidden_claims(text: str) -> list[str]:
    lowered = text.lower()
    return [claim for claim in FORBIDDEN_UNSAFE_CLAIMS if claim in lowered]


def _all_artifact_text(output_dir: Path) -> str:
    parts: list[str] = []
    for artifact_name in REQUIRED_ARTIFACTS:
        path = output_dir / artifact_name
        if path.exists():
            parts.append(_read_text(path))
    return "\n".join(parts)


def generate_phase11b_boundary_artifacts(
    output_dir: Path,
    app_id: str = DEFAULT_APP_ID,
) -> list[Path]:
    """Generate Phase 11B boundary artifacts.

    The boundary is intentionally precise:
    the primary payment application is real local software, while the
    surrounding ecosystem applications and external dependencies are simulated.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []

    manifest: dict[str, Any] = {
        "phase": PHASE,
        "app_id": app_id,
        "generation_mode": GENERATION_MODE,
        "primary_application_real": True,
        "external_ecosystem_mock_only": True,
        "synthetic_data_only": True,
        "external_payment_connectivity_allowed": False,
        "real_payment_processing_allowed": False,
        "production_claims_allowed": False,
        "required_labels": list(REQUIRED_LABELS),
        "boundary_summary": (
            "Generate the primary payment application as real local software. "
            "Generate banks, payment rails, networks, third-party systems, "
            "and upstream/downstream dependencies as simulated ecosystem apps."
        ),
    }
    generated.append(
        _write_json(
            output_dir / "real_app_mock_ecosystem_boundary_manifest.json",
            manifest,
        )
    )

    generated.append(
        _write_text(
            output_dir / "primary_application_engineering_policy.md",
            """
# Primary Application Engineering Policy

Labels:
- PRIMARY_PAYMENT_APPLICATION_REAL_LOCAL_SOFTWARE
- SYNTHETIC_DATA_ONLY
- REAL_PAYMENT_PROCESSING_FORBIDDEN
- PRODUCTION_CLAIMS_FORBIDDEN
- DETERMINISTIC_VALIDATION_REQUIRED
- TRACEABILITY_REQUIRED
- QUALITY_GATES_REQUIRED

The primary payment application must be generated as real local software.
It must include functioning APIs, domain models, validation, workflow logic,
persistence abstractions, audit events, structured logs, tests, and evidence.

The primary application must use synthetic data only. It must not process real
payments, use real customer information, or make external payment-network calls.

The correct positioning is: real local primary payment application, simulated
ecosystem, synthetic data, deployment planning, migration seams, deterministic
validation, and audit-friendly evidence.
""",
        )
    )

    generated.append(
        _write_text(
            output_dir / "mock_ecosystem_boundary_policy.md",
            """
# Mock Ecosystem Boundary Policy

Labels:
- EXTERNAL_ECOSYSTEM_MOCK_ONLY
- SYNTHETIC_DATA_ONLY
- EXTERNAL_CONNECTIVITY_FAIL_CLOSED
- MIGRATION_SEAMS_ALLOWED
- TRACEABILITY_REQUIRED

Only the surrounding ecosystem applications are simulated.

Examples:
- bank simulator
- payment-rail simulator
- PSP simulator
- merchant simulator
- customer-notification simulator
- ledger simulator
- reconciliation-source simulator
- fraud-score simulator
- audit-evidence sink

These simulated ecosystem applications may support success, rejection,
timeout, delay, duplicate, retry, failover, and recovery scenarios. They must
clearly mark all responses as synthetic or simulated.
""",
        )
    )

    generated.append(
        _write_text(
            output_dir / "external_connectivity_fail_closed_policy.md",
            """
# External Connectivity Fail-Closed Policy

Labels:
- EXTERNAL_CONNECTIVITY_FAIL_CLOSED
- REAL_PAYMENT_PROCESSING_FORBIDDEN
- PRODUCTION_CLAIMS_FORBIDDEN
- MIGRATION_SEAMS_ALLOWED
- DETERMINISTIC_VALIDATION_REQUIRED

The factory may generate adapter interfaces and migration seams. Those seams
must default to fail-closed behavior unless connected to local simulated
ecosystem applications.

The generated system must not include credentials, real payment endpoints,
real account data, real UPI handles, or calls to real payment institutions.

If a requirement asks for real external connectivity, the requirement intake
gate must reject that part or convert it into a simulated ecosystem boundary
with a documented gap.
""",
        )
    )

    generated.append(
        _write_text(
            output_dir / "requirement_front_matter_schema.md",
            """
# Requirement Front Matter Schema

Labels:
- PRIMARY_PAYMENT_APPLICATION_REAL_LOCAL_SOFTWARE
- EXTERNAL_ECOSYSTEM_MOCK_ONLY
- SYNTHETIC_DATA_ONLY
- REAL_PAYMENT_PROCESSING_FORBIDDEN
- PRODUCTION_CLAIMS_FORBIDDEN

Required front matter:

```yaml
requirement_id: REQ-PAYMENT-001
app_id: upi_dispute_resolution
domain: payments
generation_mode: real_local_primary_payment_application_with_mock_ecosystem
primary_application_real: true
external_ecosystem_mock_only: true
synthetic_data_only: true
external_payment_connectivity_allowed: false
real_payment_processing_allowed: false
production_claims_allowed: false
```

The requirement intake gate must reject documents that attempt to enable
external payment connectivity, real payment processing, real customer data,
or unsupported certification/readiness claims.
""",
        )
    )

    generated.append(
        _write_text(
            output_dir / "phase11b_requirement_intake_contract.md",
            """
# Phase 11B Requirement Intake Contract

Labels:
- PRIMARY_PAYMENT_APPLICATION_REAL_LOCAL_SOFTWARE
- EXTERNAL_ECOSYSTEM_MOCK_ONLY
- SYNTHETIC_DATA_ONLY
- EXTERNAL_CONNECTIVITY_FAIL_CLOSED
- MIGRATION_SEAMS_ALLOWED
- DETERMINISTIC_VALIDATION_REQUIRED
- TRACEABILITY_REQUIRED
- QUALITY_GATES_REQUIRED

Phase 11B must classify payment-domain requirements before generation.

The intake decision must identify:
1. Whether the primary application can be generated as real local software.
2. Which surrounding ecosystem applications must be simulated.
3. Whether all data can remain synthetic.
4. Whether any external connectivity request must be rejected or converted.
5. Which payment capability pack and application archetype are required.
6. Which requirement gaps must be reported before code generation.

The factory must produce a generation contract only when the requirement is
safe, traceable, and compatible with the real-primary-app and simulated-
ecosystem boundary.
""",
        )
    )

    validation_report = validate_phase11b_boundary_artifacts(output_dir)
    generated.append(
        _write_json(
            output_dir / "phase11b_boundary_validation_report.json",
            validation_report,
        )
    )

    return generated


def validate_phase11b_boundary_artifacts(
    output_dir: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    del project_root

    errors: list[str] = []
    warnings: list[str] = []

    missing = [
        artifact_name
        for artifact_name in REQUIRED_ARTIFACTS
        if not (output_dir / artifact_name).exists()
        and artifact_name != "phase11b_boundary_validation_report.json"
    ]
    for artifact_name in missing:
        errors.append(f"Missing required artifact: {artifact_name}")

    manifest_path = output_dir / "real_app_mock_ecosystem_boundary_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = _json_loads_dict(_read_text(manifest_path))
        except ValueError as exc:
            errors.append(f"Invalid manifest JSON: {exc}")

    expected_manifest_values: dict[str, Any] = {
        "generation_mode": GENERATION_MODE,
        "primary_application_real": True,
        "external_ecosystem_mock_only": True,
        "synthetic_data_only": True,
        "external_payment_connectivity_allowed": False,
        "real_payment_processing_allowed": False,
        "production_claims_allowed": False,
    }
    for key, expected in expected_manifest_values.items():
        if manifest and manifest.get(key) != expected:
            errors.append(
                f"Manifest field {key!r} must be {expected!r}; "
                f"found {manifest.get(key)!r}."
            )

    artifact_text = _all_artifact_text(output_dir)
    for label in REQUIRED_LABELS:
        if label not in artifact_text:
            errors.append(f"Missing required boundary label: {label}")

    forbidden_claims = _find_forbidden_claims(artifact_text)
    for claim in forbidden_claims:
        errors.append(f"Unsafe standalone claim found in artifacts: {claim}")

    if not errors:
        warnings.append(
            "Phase 11B boundary is ready: generate real local primary "
            "payment software while keeping the external ecosystem simulated."
        )

    return {
        "artifact": "phase11b_boundary_validation_report.json",
        "phase": PHASE,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": list(REQUIRED_ARTIFACTS),
        "checked_required_labels": list(REQUIRED_LABELS),
        "generation_mode": GENERATION_MODE,
    }
