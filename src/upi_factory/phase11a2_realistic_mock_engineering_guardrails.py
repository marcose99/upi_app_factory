"""Phase 11A.2 realistic mock engineering guardrails.

This phase strengthens the prompts and guardrails before Phase 11B so that
future generated applications are:
- realistic while strictly mock-only
- locally runnable with lightweight defaults
- high-volume aware
- async, concurrent, and parallel where realistic
- observable with production-grade discipline
- designed for high availability, failover, and failback
- migration-ready toward true production infrastructure later

No LLM calls, network calls, implementation app generation, commits, merges,
tags, or pushes are performed here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PHASE = "Phase 11A.2"

PROMPT_MARKER = "<!-- PHASE_11A_2_REALISTIC_MOCK_ENGINEERING_GUARDRAILS -->"

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "realistic_mock_engineering_manifest.json",
    "realistic_mock_engineering_policy.md",
    "high_volume_async_concurrency_policy.md",
    "local_first_to_production_migration_plan.md",
    "ha_failover_failback_design_policy.md",
    "production_quality_observability_policy.md",
    "ecosystem_mock_application_policy.md",
    "phase11b_prompt_enhancement_contract.md",
    "phase11a2_validation_report.json",
)

TARGET_PROMPTS: tuple[str, ...] = (
    "prompts/phase11a/implementation_planner_agent.md",
    "prompts/phase11a/contract_model_agent.md",
    "prompts/phase11a/mock_adapter_agent.md",
    "prompts/phase11a/service_logic_agent.md",
    "prompts/phase11a/test_generation_agent.md",
    "prompts/phase11a/security_review_agent.md",
    "prompts/phase11a/observability_agent.md",
    "prompts/phase11a/documentation_agent.md",
    "prompts/phase11a/validation_agent.md",
    "prompts/phase11a/release_readiness_agent.md",
    "prompts/phase11a_1/essential_agentic_harness_hardening_prompt.md",
)

REQUIRED_LABELS: tuple[str, ...] = (
    "STRICT_MOCK_ONLY",
    "REALISTIC_MOCK_REQUIRED",
    "HIGH_VOLUME_ENGINEERING_REQUIRED",
    "ASYNC_CONCURRENCY_REQUIRED",
    "LOCAL_FIRST_LIGHTWEIGHT_RUNTIME",
    "PRODUCTION_MIGRATION_READY",
    "HA_FAILOVER_FAILBACK_DESIGN_REQUIRED",
    "PRODUCTION_QUALITY_OBSERVABILITY_REQUIRED",
    "STRONG_GUARDRAILS_REQUIRED",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
    "HUMAN_APPROVAL_REQUIRED",
    "DETERMINISTIC_VALIDATION_REQUIRED",
    "FAIL_CLOSED",
)

FORBIDDEN_UNSAFE_CLAIMS: tuple[str, ...] = (
    'production ready',
    'production compliant',
    'RBI certified',
    'NPCI certified',
    'live integration',
    "RBI-aligned mock evidence only",
    "NPCI-aligned mock evidence only",
    "officially certified",
    "guaranteed compliant",
    "100% compliant",
    "aligned with production-grade engineering discipline for mock-only evaluation",
    "suitable for mock-only deployment planning",
    "legal advice",
    "live NPCI integration",
    "live bank integration",
    "real customer-dispute processing",
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
    )


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"Missing JSON artifact: {path.name}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.name}: {exc}")
        return {}

    if not isinstance(loaded, dict):
        errors.append(f"JSON artifact must be an object: {path.name}")
        return {}

    return loaded


def _phase11a1_ready(phase11a1_dir: Path) -> tuple[bool, dict[str, Any]]:
    errors: list[str] = []
    report = _load_json(phase11a1_dir / "phase11a1_validation_report.json", errors)
    if errors:
        return False, {"passed": False, "errors": errors}
    return bool(report.get("passed")), report


def prompt_enhancement_block() -> str:
    return f"""
{PROMPT_MARKER}

## Phase 11A.2 Mandatory Realistic Mock Engineering Guardrails

Labels: STRICT_MOCK_ONLY, REALISTIC_MOCK_REQUIRED,
HIGH_VOLUME_ENGINEERING_REQUIRED, ASYNC_CONCURRENCY_REQUIRED,
LOCAL_FIRST_LIGHTWEIGHT_RUNTIME, PRODUCTION_MIGRATION_READY,
HA_FAILOVER_FAILBACK_DESIGN_REQUIRED,
PRODUCTION_QUALITY_OBSERVABILITY_REQUIRED, STRONG_GUARDRAILS_REQUIRED,
MOCK_BOUNDARY, SYNTHETIC_DATA, HUMAN_APPROVAL_REQUIRED,
DETERMINISTIC_VALIDATION_REQUIRED, FAIL_CLOSED

### Realistic but strictly mock

All generated application and ecosystem components must behave like realistic
enterprise payment-dispute software, but every external dependency remains a
mock adapter, simulator, fixture, or synthetic service. Do not add live bank,
NPCI, RBI, PSP, ledger, notification, ODR, merchant, customer, or account-system
integrations.

### High-volume engineering

Design request, event, batch, and replay paths to handle high data volume in a
local-first way. Use bounded queues, pagination, streaming-style processing,
chunking, idempotency keys, backpressure, rate limits, retries, timeouts, and
resource limits where applicable.

### Async, concurrency, and parallelism

Use async I/O, worker pools, task queues, concurrency limits, and parallel
validation where realistic. Avoid unbounded concurrency. Document why each
parallel path is safe, deterministic, idempotent, and locally runnable.

### Availability, failover, and failback

Architecture and design outputs must include high availability, failover,
failback, retry, circuit-breaker, degraded-mode, checkpoint, replay, and recovery
considerations. Locally, these may be simulated with lightweight mock services
and deterministic fault-injection tests.

### Production-quality observability

Add structured logs, metrics, traces, health checks, readiness checks, liveness
checks, audit events, correlation IDs, run IDs, decision IDs, retry counters,
queue-depth metrics, latency histograms, and error taxonomies where applicable.
Keep the implementation lightweight locally, but design adapters for later
migration to production observability systems.

### Local-first, migration-ready

Default runtime must use lightweight local tools. Every mock or local component
must have a clear migration seam so it can later be replaced one by one with
production infrastructure without changing business logic.

### Strong guardrails

Generated work must preserve mock boundaries, synthetic data labels, human
approval gates, deterministic validation, fail-closed behavior, secret blocking,
prompt-injection resistance, budget controls, and repair-loop limits.
"""


def apply_prompt_enhancements(project_root: Path) -> list[Path]:
    changed: list[Path] = []
    block = prompt_enhancement_block()

    for relative in TARGET_PROMPTS:
        path = project_root / relative
        if not path.exists():
            continue
        current = path.read_text(encoding="utf-8")
        if PROMPT_MARKER in current:
            continue
        _write_text(path, current.rstrip() + "\n\n" + block)
        changed.append(path)

    return changed


def _manifest(app_id: str, phase11a1_dir: Path) -> dict[str, Any]:
    ready, report = _phase11a1_ready(phase11a1_dir)
    return {
        "artifact": "realistic_mock_engineering_manifest.json",
        "phase": PHASE,
        "app_id": app_id,
        "phase11a1_readiness_passed": ready,
        "phase11a1_report_summary": {
            "passed": report.get("passed"),
            "errors": report.get("errors", []),
            "warnings": report.get("warnings", []),
        },
        "purpose": (
            "Strengthen prompts and guardrails for realistic, high-volume, "
            "locally runnable, migration-ready mock application generation."
        ),
        "labels": list(REQUIRED_LABELS),
        "strictly_mock": True,
        "llm_calls_made": 0,
        "network_calls_made": 0,
        "implementation_files_written": 0,
    }


def _realistic_mock_policy(app_id: str) -> str:
    return f"""
# Realistic Mock Engineering Policy — {app_id}

Labels: STRICT_MOCK_ONLY, REALISTIC_MOCK_REQUIRED, MOCK_BOUNDARY,
SYNTHETIC_DATA, STRONG_GUARDRAILS_REQUIRED

The generated system must simulate realistic enterprise payment-dispute behavior
without connecting to live external systems.

Required realistic mock capabilities:

- bank and PSP response simulators
- NPCI-like switch response simulator
- ledger event simulator
- merchant/acquirer response simulator
- customer notification simulator
- ODR/case-management simulator
- synthetic dispute, transaction, evidence, and SLA datasets
- deterministic positive, negative, timeout, duplicate, replay, and partial
  failure scenarios
- clear mock-boundary documentation for every dependency

Forbidden:

- live bank calls
- live NPCI calls
- live PSP calls
- live customer data
- live account data
- certification or compliance claims
"""


def _high_volume_policy(app_id: str) -> str:
    return f"""
# High-Volume, Async, Concurrency, and Parallelism Policy — {app_id}

Labels: HIGH_VOLUME_ENGINEERING_REQUIRED, ASYNC_CONCURRENCY_REQUIRED,
DETERMINISTIC_VALIDATION_REQUIRED, FAIL_CLOSED

Generated designs must support high-volume local simulation while remaining safe
on a laptop.

Required engineering patterns:

- bounded async queues for intake and worker paths
- configurable worker counts
- concurrency limits
- idempotency keys
- deduplication
- pagination
- chunked processing
- streaming-style file reads where useful
- retry with capped exponential backoff
- timeouts
- circuit breakers
- bulk validation
- deterministic replay tests
- load-shape configuration for local runs

Do not introduce unbounded threads, unbounded tasks, unbounded queues, or
unbounded memory growth.
"""


def _migration_plan(app_id: str) -> str:
    return f"""
# Local-First to Production Infrastructure Migration Plan — {app_id}

Labels: LOCAL_FIRST_LIGHTWEIGHT_RUNTIME, PRODUCTION_MIGRATION_READY,
VERSION_SPECIFIC_REVIEW_REQUIRED

Default local stack must stay lightweight. The design must define migration
seams so each local component can later be replaced independently.

Recommended local-first defaults:

- FastAPI or Python CLI for service boundary
- Pydantic models for contracts
- in-memory or SQLite state for local runs
- filesystem evidence store
- mock adapters for ecosystem dependencies
- standard logging and lightweight metrics files

Migration seams to document:

- SQLite to PostgreSQL
- filesystem evidence store to object storage
- in-process queue to Kafka-compatible messaging
- local scheduler to durable workflow engine
- simple metrics/log files to OpenTelemetry-compatible telemetry
- mock identity to enterprise identity provider
- local secrets placeholders to approved secret manager

This is deployment planning and migration readiness documentation. It must not
be represented as approved for live use.
"""


def _ha_policy(app_id: str) -> str:
    return f"""
# High Availability, Failover, and Failback Design Policy — {app_id}

Labels: HA_FAILOVER_FAILBACK_DESIGN_REQUIRED, REALISTIC_MOCK_REQUIRED,
MOCK_BOUNDARY

Architecture and design artifacts must include:

- active-active and active-passive deployment considerations
- stateless service boundary where practical
- durable state boundary
- idempotent retry behavior
- checkpoint and replay behavior
- failover simulation tests
- failback simulation tests
- partial dependency outage behavior
- degraded-mode behavior
- duplicate event protection
- recovery runbooks
- data consistency notes

Local implementation may simulate these with mock services, temporary state,
synthetic events, and deterministic fault-injection tests.
"""


def _observability_policy(app_id: str) -> str:
    return f"""
# Production-Quality Observability Policy — {app_id}

Labels: PRODUCTION_QUALITY_OBSERVABILITY_REQUIRED,
DETERMINISTIC_VALIDATION_REQUIRED, HUMAN_APPROVAL_REQUIRED

Generated applications and ecosystem mocks must expose production-grade
observability discipline while remaining lightweight locally.

Required telemetry concepts:

- structured JSON logs
- request_id, correlation_id, run_id, decision_id, and trace_id fields
- audit events for decisions and guardrail outcomes
- metrics for request counts, error counts, latency, retries, queue depth,
  worker counts, rejected work, duplicate work, and replay outcomes
- health, readiness, and liveness checks
- clear error taxonomy
- debug guide for local incident investigation
- production deployment observability document

Local output may be JSON log files and metrics snapshots. The design must include
adapters for later OpenTelemetry-compatible telemetry.
"""


def _ecosystem_policy(app_id: str) -> str:
    return f"""
# Ecosystem Mock Application Policy — {app_id}

Labels: STRICT_MOCK_ONLY, REALISTIC_MOCK_REQUIRED,
HIGH_VOLUME_ENGINEERING_REQUIRED, MOCK_BOUNDARY, SYNTHETIC_DATA

The factory must generate ecosystem mock applications or adapters where needed
to simulate realistic upstream and downstream behavior.

Required mock ecosystem categories:

- transaction source simulator
- bank/issuer/acquirer response simulator
- NPCI-like response simulator
- merchant response simulator
- ledger/accounting simulator
- evidence document simulator
- notification simulator
- ODR or case workflow simulator
- operations incident simulator
- SLA and escalation simulator

Each mock must support deterministic scenarios, high-volume synthetic data,
fault injection, latency injection, timeout simulation, and replay.
"""


def _prompt_contract(app_id: str) -> str:
    return f"""
# Phase 11B Prompt Enhancement Contract — {app_id}

Labels: STRICT_MOCK_ONLY, REALISTIC_MOCK_REQUIRED,
HIGH_VOLUME_ENGINEERING_REQUIRED, ASYNC_CONCURRENCY_REQUIRED,
PRODUCTION_QUALITY_OBSERVABILITY_REQUIRED, HA_FAILOVER_FAILBACK_DESIGN_REQUIRED,
LOCAL_FIRST_LIGHTWEIGHT_RUNTIME, PRODUCTION_MIGRATION_READY,
STRONG_GUARDRAILS_REQUIRED

Phase 11B prompts must require each agent to produce outputs that satisfy:

1. realistic mock behavior with explicit MOCK_BOUNDARY labels
2. high-volume local data handling design
3. async, concurrency, and parallelism where realistic
4. bounded resource usage
5. HA, failover, failback, degraded-mode, and recovery design
6. production-quality observability design
7. locally runnable lightweight defaults
8. migration seams to production infrastructure
9. deterministic validation and test evidence
10. human approval gates for protected writes

Any generated output that weakens the mock boundary, removes guardrails, or
claims certification/compliance must fail validation.
"""


def generate_phase11a2_artifacts(
    output_dir: Path,
    app_id: str = "upi_dispute_resolution",
    phase11a1_dir: Path | None = None,
) -> list[Path]:
    if phase11a1_dir is None:
        phase11a1_dir = Path(
            f"workspace/factory_generated/{app_id}/lifecycle_artifacts/phase11a_1"
        )

    ready, report = _phase11a1_ready(phase11a1_dir)
    if not ready:
        raise ValueError(
            "Phase 11A.2 generation blocked because Phase 11A.1 readiness "
            f"failed: {report.get('errors', [])}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, Any] | str] = {
        "realistic_mock_engineering_manifest.json": _manifest(app_id, phase11a1_dir),
        "realistic_mock_engineering_policy.md": _realistic_mock_policy(app_id),
        "high_volume_async_concurrency_policy.md": _high_volume_policy(app_id),
        "local_first_to_production_migration_plan.md": _migration_plan(app_id),
        "ha_failover_failback_design_policy.md": _ha_policy(app_id),
        "production_quality_observability_policy.md": _observability_policy(app_id),
        "ecosystem_mock_application_policy.md": _ecosystem_policy(app_id),
        "phase11b_prompt_enhancement_contract.md": _prompt_contract(app_id),
    }

    written: list[Path] = []
    for filename in REQUIRED_ARTIFACTS:
        if filename == "phase11a2_validation_report.json":
            continue
        path = output_dir / filename
        payload = artifacts[filename]
        if isinstance(payload, dict):
            _write_json(path, payload)
        else:
            _write_text(path, payload)
        written.append(path)

    report_payload = validate_phase11a2_artifacts(output_dir)
    report_path = output_dir / "phase11a2_validation_report.json"
    _write_json(report_path, report_payload)
    written.append(report_path)

    return written


def _safe_forbidden_line(line: str) -> bool:
    lowered = f" {line.strip().lower()} "
    safe_markers = (
        "must not",
        "do not",
        "forbidden",
        "blocked",
        "without",
        "not claim",
        "no ",
        "no_",
        "legal-advice",
    )
    return any(marker in lowered for marker in safe_markers)


def _combined_text(output_dir: Path, project_root: Path | None = None) -> str:
    parts: list[str] = []
    for filename in REQUIRED_ARTIFACTS:
        if filename == "phase11a2_validation_report.json":
            continue
        path = output_dir / filename
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))

    if project_root is not None:
        for relative in TARGET_PROMPTS:
            path = project_root / relative
            if path.exists():
                parts.append(path.read_text(encoding="utf-8"))

    return "\n".join(parts)


def validate_phase11a2_artifacts(
    output_dir: Path,
    project_root: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    checked_artifacts: list[str] = []
    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if path.exists():
            checked_artifacts.append(filename)
        else:
            errors.append(f"Missing Phase 11A.2 artifact: {filename}")

    manifest = _load_json(
        output_dir / "realistic_mock_engineering_manifest.json",
        errors,
    )
    if manifest:
        if manifest.get("phase11a1_readiness_passed") is not True:
            errors.append("Phase 11A.2 manifest must confirm Phase 11A.1 readiness.")
        if manifest.get("strictly_mock") is not True:
            errors.append("Phase 11A.2 manifest must enforce strict mock-only scope.")
        if manifest.get("implementation_files_written") != 0:
            errors.append("Phase 11A.2 must not write generated application files.")

    combined = _combined_text(output_dir, project_root)

    for label in REQUIRED_LABELS:
        if label not in combined:
            errors.append(f"Missing required Phase 11A.2 label: {label}")

    for line_number, line in enumerate(combined.splitlines(), start=1):
        for claim in FORBIDDEN_UNSAFE_CLAIMS:
            if claim.lower() in line.lower() and not _safe_forbidden_line(line):
                errors.append(
                    "Unsafe forbidden claim found: "
                    f"{claim} near combined line {line_number}: {line.strip()}"
                )

    prompt_files_with_marker: list[str] = []
    if project_root is not None:
        for relative in TARGET_PROMPTS:
            path = project_root / relative
            if not path.exists():
                errors.append(f"Missing target prompt file: {relative}")
                continue
            text = path.read_text(encoding="utf-8")
            if PROMPT_MARKER not in text:
                errors.append(f"Prompt enhancement marker missing from: {relative}")
            else:
                prompt_files_with_marker.append(relative)

    required_phrases = (
        "bounded async queues",
        "concurrency limits",
        "idempotency keys",
        "failover",
        "failback",
        "structured JSON logs",
        "migration seams",
        "synthetic",
    )
    for phrase in required_phrases:
        if phrase.lower() not in combined.lower():
            errors.append(f"Missing required engineering phrase: {phrase}")

    if not errors:
        warnings.append(
            "Phase 11A.2 is ready. The next generated application must remain "
            "strictly mock-only while using production-grade engineering discipline."
        )

    return {
        "artifact": "phase11a2_validation_report.json",
        "phase": PHASE,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": checked_artifacts,
        "checked_required_labels": list(REQUIRED_LABELS),
        "checked_prompt_files": prompt_files_with_marker,
    }
