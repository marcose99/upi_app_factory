"""Phase 10.2 SDLC technology best-practice governance.

This module generates deterministic governance artifacts requiring future
agents to apply best practices appropriate to every software technology used
in the generated application's SDLC.

Boundary:
- Official documentation links are reference candidates, not fetched at runtime.
- Version-specific claims require verified official documentation.
- Unsupported technology guidance must be labelled MISSING_OFFICIAL_SOURCE.
- This is a mock-safe governance pack and does not claim certification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "sdlc_technology_registry.json",
    "sdlc_best_practice_policy.md",
    "technology_specific_prompt_instructions.md",
    "sdlc_best_practice_traceability.json",
    "sdlc_best_practice_gap_report.json",
    "sdlc_best_practice_validation_report.json",
)

REQUIRED_LABELS: tuple[str, ...] = (
    "OFFICIAL_DOC_REFERENCE_CANDIDATE",
    "MISSING_OFFICIAL_SOURCE",
    "TECHNOLOGY_SPECIFIC_BEST_PRACTICE_REQUIRED",
    "VERSION_SPECIFIC_REVIEW_REQUIRED",
    "MOCK_BOUNDARY",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
)

REQUIRED_TECHNOLOGY_IDS: tuple[str, ...] = (
    "python",
    "bash",
    "git",
    "github",
    "json",
    "markdown",
    "pytest",
    "ruff",
    "mypy",
    "fastapi",
    "pydantic",
    "sqlite",
    "postgresql",
    "docker",
    "opentelemetry",
    "opa_conftest",
)

FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "100% best practice",
    "guaranteed secure",
    "guaranteed compliant",
    "production certified",
    "officially certified",
    "rbi certified",
    "npci certified",
)

SDLC_PHASES: tuple[str, ...] = (
    "requirements",
    "architecture",
    "design",
    "implementation",
    "testing",
    "security",
    "observability",
    "release",
    "operations",
    "maintenance",
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _technology_entry(
    technology_id: str,
    name: str,
    category: str,
    official_doc_url: str,
    lifecycle_phases: list[str],
    best_practice_controls: list[str],
    generated_app_usage: str,
) -> dict[str, Any]:
    return {
        "technology_id": technology_id,
        "name": name,
        "category": category,
        "official_doc_url": official_doc_url,
        "source_status": "OFFICIAL_DOC_REFERENCE_CANDIDATE",
        "runtime_fetch": False,
        "freshness_rule": (
            "Verify official documentation and exact version before making "
            "version-specific, security-sensitive, performance-sensitive, "
            "or production-readiness claims."
        ),
        "generated_app_usage": generated_app_usage,
        "lifecycle_phases": lifecycle_phases,
        "best_practice_controls": best_practice_controls,
        "required_labels": [
            "TECHNOLOGY_SPECIFIC_BEST_PRACTICE_REQUIRED",
            "VERSION_SPECIFIC_REVIEW_REQUIRED",
        ],
    }


def _technology_registry(app_id: str) -> dict[str, Any]:
    common_python_controls = [
        "clear module boundaries",
        "type hints for public interfaces",
        "small beginner-readable functions",
        "explicit exceptions and helpful error messages",
        "deterministic tests before generation is trusted",
        "avoid hidden runtime network calls in governance scripts",
    ]

    technologies = [
        _technology_entry(
            "python",
            "Python",
            "programming_language",
            "https://docs.python.org/3/",
            [
                "implementation",
                "testing",
                "release",
                "operations",
                "maintenance",
            ],
            common_python_controls
            + [
                "pin or document supported interpreter version",
                "avoid version-specific syntax unless supported by project Python",
            ],
            "Primary implementation language for deterministic factory scripts and validators.",
        ),
        _technology_entry(
            "bash",
            "Bash",
            "scripting",
            "https://www.gnu.org/software/bash/manual/",
            ["release", "operations", "maintenance"],
            [
                "use set -euo pipefail",
                "quote variables",
                "fail closed on unsafe preflight conditions",
                "print clear step banners",
                "avoid destructive commands unless explicitly guarded",
                "make reruns idempotent where practical",
            ],
            "Runnable automation scripts for patch, validation, merge, tag, and push.",
        ),
        _technology_entry(
            "git",
            "Git",
            "version_control",
            "https://git-scm.com/docs",
            ["release", "maintenance"],
            [
                "use clean-working-tree preflight",
                "use branches for phases",
                "use tags as restore points",
                "avoid rewriting shared history",
                "show staged files before commit",
            ],
            "Branch, merge, restore-point, and traceability management.",
        ),
        _technology_entry(
            "github",
            "GitHub",
            "source_hosting",
            "https://docs.github.com/",
            ["release", "operations", "maintenance"],
            [
                "push branches and tags explicitly",
                "keep remote restore points",
                "avoid exposing secrets in repository artifacts",
                "use pull requests when human review is required",
            ],
            "Remote repository hosting for the mock factory project.",
        ),
        _technology_entry(
            "json",
            "JSON",
            "data_format",
            "https://www.json.org/json-en.html",
            [
                "requirements",
                "architecture",
                "design",
                "testing",
                "release",
                "maintenance",
            ],
            [
                "stable keys",
                "deterministic ordering when generated",
                "machine-validated required fields",
                "no comments inside JSON",
                "separate synthetic values from source-backed values",
            ],
            "Structured lifecycle, traceability, registry, and validation artifacts.",
        ),
        _technology_entry(
            "markdown",
            "Markdown",
            "documentation_format",
            "https://www.markdownguide.org/basic-syntax/",
            [
                "requirements",
                "architecture",
                "design",
                "release",
                "operations",
                "maintenance",
            ],
            [
                "clear headings",
                "explicit boundaries",
                "tables for comparisons",
                "copy-paste runnable commands where applicable",
                "avoid ambiguous compliance wording",
            ],
            "Human-readable architecture, design, policy, and prompt artifacts.",
        ),
        _technology_entry(
            "pytest",
            "pytest",
            "testing_framework",
            "https://docs.pytest.org/",
            ["testing", "release", "maintenance"],
            [
                "test happy path and negative path",
                "use tmp_path for generated artifacts",
                "assert validation failures explicitly",
                "keep tests deterministic and fast",
                "avoid network-dependent tests in governance modules",
            ],
            "Deterministic unit tests for generators and validators.",
        ),
        _technology_entry(
            "ruff",
            "Ruff",
            "linting",
            "https://docs.astral.sh/ruff/",
            ["implementation", "testing", "release"],
            [
                "run on changed Python scripts and tests",
                "treat lint failures as quality-gate failures",
                "prefer explicit fixes over suppressions",
            ],
            "Python lint quality gate.",
        ),
        _technology_entry(
            "mypy",
            "Mypy",
            "static_type_checking",
            "https://mypy.readthedocs.io/",
            ["implementation", "testing", "release"],
            [
                "type-check source scripts before release",
                "prefer explicit return types",
                "avoid Any unless it is controlled at JSON boundaries",
            ],
            "Static typing quality gate for deterministic Python modules.",
        ),
        _technology_entry(
            "fastapi",
            "FastAPI",
            "web_framework_candidate",
            "https://fastapi.tiangolo.com/",
            ["architecture", "design", "implementation", "testing", "operations"],
            [
                "use explicit request and response models",
                "separate routers, services, and adapters",
                "validate inputs at boundaries",
                "use dependency injection for replaceable components",
                "document mock boundaries for external systems",
            ],
            "Candidate web API framework for future generated mock application services.",
        ),
        _technology_entry(
            "pydantic",
            "Pydantic",
            "data_validation_candidate",
            "https://docs.pydantic.dev/",
            ["design", "implementation", "testing"],
            [
                "use explicit schemas for API and artifact contracts",
                "forbid or handle extra fields intentionally",
                "use clear validation errors",
                "keep source-backed, synthetic, and missing values distinct",
            ],
            "Candidate schema validation layer for future generated application contracts.",
        ),
        _technology_entry(
            "sqlite",
            "SQLite",
            "database_candidate",
            "https://www.sqlite.org/docs.html",
            ["architecture", "design", "implementation", "testing"],
            [
                "use only for local deterministic demos unless justified",
                "document migration path to PostgreSQL if durability/concurrency grow",
                "avoid treating local demo storage as production storage",
            ],
            "Candidate lightweight local persistence for deterministic demos.",
        ),
        _technology_entry(
            "postgresql",
            "PostgreSQL",
            "database_candidate",
            "https://www.postgresql.org/docs/",
            ["architecture", "design", "implementation", "operations"],
            [
                "use migrations for schema evolution",
                "separate transactional data from evidence artifacts where appropriate",
                "define indexes from access patterns",
                "do not claim production sizing without measured workload",
            ],
            "Candidate relational store for future durable evidence and application state.",
        ),
        _technology_entry(
            "docker",
            "Docker",
            "runtime_packaging_candidate",
            "https://docs.docker.com/",
            ["implementation", "testing", "release", "operations"],
            [
                "keep images minimal",
                "avoid embedding secrets",
                "document build and run commands",
                "separate dev/demo configuration from production-like configuration",
            ],
            "Candidate packaging/runtime layer for future demos.",
        ),
        _technology_entry(
            "opentelemetry",
            "OpenTelemetry",
            "observability_candidate",
            "https://opentelemetry.io/docs/",
            ["architecture", "implementation", "observability", "operations"],
            [
                "define trace/span boundaries before instrumentation",
                "avoid logging secrets or personal data",
                "correlate request ids and evidence ids",
                "keep observability vendor-neutral where practical",
            ],
            "Candidate observability standard for future generated app tracing.",
        ),
        _technology_entry(
            "opa_conftest",
            "OPA / Conftest",
            "policy_as_code_candidate",
            "https://www.openpolicyagent.org/docs/latest/",
            ["security", "testing", "release"],
            [
                "encode release policies as deterministic checks",
                "treat policy failure as fail-closed",
                "keep policy inputs explicit and auditable",
            ],
            "Candidate policy-as-code gate for future governance expansion.",
        ),
    ]

    return {
        "artifact": "sdlc_technology_registry.json",
        "app_id": app_id,
        "phase": "Phase 10.2",
        "purpose": (
            "Ensure every future generated application component follows "
            "technology-specific SDLC best practices instead of generic advice."
        ),
        "runtime_network_access": False,
        "governance_boundary": {
            "mock_safe": True,
            "deterministic_first": True,
            "no_certification_claim": True,
            "official_docs_not_fetched_at_runtime": True,
        },
        "required_labels": list(REQUIRED_LABELS),
        "technologies": technologies,
    }


def _policy_markdown(app_id: str) -> str:
    return f"""
# Phase 10.2 SDLC Technology Best-Practice Policy — {app_id}

## Purpose

Every future generated application artifact must identify the software
technologies involved and follow best practices appropriate to each one.

This applies to:

- programming languages
- frameworks
- libraries
- databases
- messaging systems
- workflow engines
- testing tools
- static-analysis tools
- security tools
- policy-as-code tools
- observability tools
- build tools
- packaging tools
- deployment and runtime technologies
- documentation and data formats

## Mandatory rule

A future agent must not produce generic advice when a technology-specific rule
is required. It must either:

1. use source-backed official documentation,
2. use a project policy already validated by the factory,
3. use USER_PROVIDED_VALUE when the user supplies it,
4. use SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL for mock/demo reasoning, or
5. mark the point MISSING_OFFICIAL_SOURCE.

## Engineering controls

Future generated code and artifacts must prefer:

- small beginner-readable modules
- explicit contracts and schemas
- deterministic validation where practical
- clear error messages
- idempotent scripts
- secure defaults
- least privilege
- dependency and version discipline
- traceable decisions
- tests covering happy and negative paths
- observable request/evidence correlation
- rollback and restore-point planning
- modular ports/adapters to reduce replacement cost

## Economics alignment

Technology choices must consider:

- build cost
- run cost
- review cost
- replacement cost
- vendor lock-in cost
- debugging and onboarding cost
- operational cost
- cost of poor quality
- cost of security or compliance mistakes

Exact monetary claims require official or user-provided data.

## Boundary

This policy does not claim production readiness, certification, official
compliance, or security guarantees.
"""


def _prompt_instructions(app_id: str) -> str:
    return f"""
# Phase 10.2 Technology-Specific Prompt Instructions — {app_id}

## Mandatory instruction for future agents

Before generating application code, tests, design documents, deployment
artifacts, or operations scripts, identify every software technology involved
in the SDLC step.

For each identified technology, state:

- technology name
- role in the SDLC
- exact version if known
- official documentation reference candidate
- best-practice controls applied
- source status
- freshness requirement
- validation method
- gaps or assumptions

## Best-practice application rule

Apply best practices appropriate to each software, framework, library, tool,
language, database, messaging system, workflow engine, testing tool, security
tool, observability tool, build tool, deployment tool, and runtime technology
involved.

## Source rule

If a technology-specific best-practice statement depends on a specific version,
current vendor behavior, current security guidance, or production deployment
rules, do not guess. Use MISSING_OFFICIAL_SOURCE unless the evidence pack
contains a verified source.

## Generated application quality rule

Carry these dimensions into future generated application work:

- reliability
- security
- maintainability
- modularity
- testability
- observability
- auditability
- usability
- performance awareness
- recoverability
- operability
- economic sustainability

## Mock-safe rule

No future agent may introduce live bank, NPCI, RBI, PSP, customer, payment,
notification, or ledger integration without an explicit future production
authorization artifact. Until then, all such interactions remain MOCK_BOUNDARY.
"""


def _gap_report(app_id: str) -> dict[str, Any]:
    gaps = [
        {
            "gap_id": "SDLC-GAP-001",
            "title": "Exact technology versions for future generated application",
            "risk": "Version-specific guidance may be wrong if versions are unknown.",
            "required_resolution": "Record exact version or mark MISSING_OFFICIAL_SOURCE.",
            "blocked_claims": [
                "latest best practice confirmed",
                "version-specific behavior guaranteed",
            ],
        },
        {
            "gap_id": "SDLC-GAP-002",
            "title": "Current security guidance for each selected technology",
            "risk": "Security guidance changes over time.",
            "required_resolution": "Verify official security documentation before release.",
            "blocked_claims": [
                "guaranteed secure",
                "no vulnerabilities",
            ],
        },
        {
            "gap_id": "SDLC-GAP-003",
            "title": "Production deployment topology",
            "risk": "Demo-local best practices may not match production topology.",
            "required_resolution": "Keep deployment guidance mock/demo-scoped until topology is supplied.",
            "blocked_claims": [
                "production certified",
                "production compliant",
            ],
        },
        {
            "gap_id": "SDLC-GAP-004",
            "title": "Technology cost model",
            "risk": "Cost statements may become stale or vendor-specific.",
            "required_resolution": "Use official vendor pricing or USER_PROVIDED_VALUE.",
            "blocked_claims": [
                "guaranteed cheapest",
                "exact run cost",
            ],
        },
    ]

    return {
        "artifact": "sdlc_best_practice_gap_report.json",
        "app_id": app_id,
        "phase": "Phase 10.2",
        "purpose": "Prevent unsupported SDLC best-practice and technology claims.",
        "gaps": gaps,
    }


def _traceability(app_id: str, registry: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for technology in registry["technologies"]:
        technology_id = str(technology["technology_id"])
        rows.append(
            {
                "technology_id": technology_id,
                "name": technology["name"],
                "lifecycle_phases": technology["lifecycle_phases"],
                "best_practice_controls": technology["best_practice_controls"],
                "prompt_refs": [
                    "technology_specific_prompt_instructions.md",
                    "prompts/phase10/requirement_to_architecture_to_plan_prompt.md",
                    "prompts/phase10_1/official_source_evidence_registry_prompt.md",
                ],
                "validation_refs": [
                    "sdlc_best_practice_validation_report.json",
                    "tests/test_phase10_2_sdlc_best_practice_governance.py",
                ],
                "source_refs": [
                    "sdlc_technology_registry.json",
                    "sdlc_best_practice_gap_report.json",
                ],
                "required_labels": technology["required_labels"],
            }
        )

    return {
        "artifact": "sdlc_best_practice_traceability.json",
        "app_id": app_id,
        "phase": "Phase 10.2",
        "traceability_rule": (
            "Each SDLC technology must map to lifecycle phases, controls, "
            "prompt instructions, validation, source references, and labels."
        ),
        "rows": rows,
    }


def generate_sdlc_best_practice_artifacts(
    output_dir: Path,
    app_id: str = "upi_dispute_resolution",
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    registry = _technology_registry(app_id)
    traceability = _traceability(app_id, registry)

    payloads: dict[str, str | dict[str, Any]] = {
        "sdlc_technology_registry.json": registry,
        "sdlc_best_practice_policy.md": _policy_markdown(app_id),
        "technology_specific_prompt_instructions.md": _prompt_instructions(app_id),
        "sdlc_best_practice_traceability.json": traceability,
        "sdlc_best_practice_gap_report.json": _gap_report(app_id),
    }

    written: list[Path] = []
    for filename in REQUIRED_ARTIFACTS:
        if filename == "sdlc_best_practice_validation_report.json":
            continue
        target = output_dir / filename
        payload = payloads[filename]
        if isinstance(payload, dict):
            _write_json(target, payload)
        else:
            _write_markdown(target, payload)
        written.append(target)

    report = validate_sdlc_best_practice_artifacts(output_dir)
    report_path = output_dir / "sdlc_best_practice_validation_report.json"
    _write_json(report_path, report)
    written.append(report_path)
    return written


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


def validate_sdlc_best_practice_artifacts(output_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked_artifacts: list[str] = []

    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if not path.exists():
            errors.append(f"Missing required artifact: {filename}")
        else:
            checked_artifacts.append(filename)

    registry = _load_json(output_dir / "sdlc_technology_registry.json", errors)
    gap_report = _load_json(output_dir / "sdlc_best_practice_gap_report.json", errors)
    traceability = _load_json(
        output_dir / "sdlc_best_practice_traceability.json",
        errors,
    )

    text_cache: dict[str, str] = {}
    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if path.exists():
            text_cache[filename] = path.read_text(encoding="utf-8")

    combined_text = "\n".join(text_cache.values())

    for label in REQUIRED_LABELS:
        if label not in combined_text:
            errors.append(f"Missing required SDLC label: {label}")

    technology_ids: set[str] = set()
    if registry:
        technologies = registry.get("technologies", [])
        if not isinstance(technologies, list) or not technologies:
            errors.append("sdlc_technology_registry.json must contain technologies.")
        else:
            for technology in technologies:
                if not isinstance(technology, dict):
                    errors.append("Each technology must be an object.")
                    continue

                technology_id = technology.get("technology_id")
                if not isinstance(technology_id, str) or not technology_id:
                    errors.append("Each technology must have a technology_id.")
                    continue
                technology_ids.add(technology_id)

                doc_url = technology.get("official_doc_url")
                if not isinstance(doc_url, str) or not doc_url.startswith("https://"):
                    errors.append(f"Technology missing https official_doc_url: {technology_id}")

                phases = technology.get("lifecycle_phases", [])
                if not isinstance(phases, list) or not phases:
                    errors.append(f"Technology missing lifecycle phases: {technology_id}")
                else:
                    unknown_phases = [
                        str(phase)
                        for phase in phases
                        if str(phase) not in SDLC_PHASES
                    ]
                    if unknown_phases:
                        errors.append(
                            f"Technology has unknown lifecycle phases {unknown_phases}: "
                            f"{technology_id}"
                        )

                controls = technology.get("best_practice_controls", [])
                if not isinstance(controls, list) or len(controls) < 3:
                    errors.append(
                        f"Technology needs at least three best-practice controls: "
                        f"{technology_id}"
                    )

                if technology.get("source_status") != "OFFICIAL_DOC_REFERENCE_CANDIDATE":
                    errors.append(
                        f"Technology must be an official-doc reference candidate: "
                        f"{technology_id}"
                    )

                if not technology.get("freshness_rule"):
                    errors.append(f"Technology missing freshness_rule: {technology_id}")

    for technology_id in REQUIRED_TECHNOLOGY_IDS:
        if technology_id not in technology_ids:
            errors.append(f"Missing required technology id: {technology_id}")

    trace_ids: set[str] = set()
    if traceability:
        rows = traceability.get("rows", [])
        if not isinstance(rows, list) or not rows:
            errors.append("sdlc_best_practice_traceability.json must contain rows.")
        else:
            for row in rows:
                if not isinstance(row, dict):
                    errors.append("Each traceability row must be an object.")
                    continue

                technology_id = row.get("technology_id")
                if isinstance(technology_id, str):
                    trace_ids.add(technology_id)

                for required_key in (
                    "lifecycle_phases",
                    "best_practice_controls",
                    "prompt_refs",
                    "validation_refs",
                    "source_refs",
                    "required_labels",
                ):
                    if not row.get(required_key):
                        errors.append(
                            f"Traceability row missing {required_key}: "
                            f"{technology_id}"
                        )

    for technology_id in sorted(technology_ids):
        if technology_id not in trace_ids:
            errors.append(f"Technology missing traceability row: {technology_id}")

    if gap_report:
        gaps = gap_report.get("gaps", [])
        if not isinstance(gaps, list) or not gaps:
            errors.append("sdlc_best_practice_gap_report.json must contain gaps.")
        else:
            for gap in gaps:
                if not isinstance(gap, dict):
                    errors.append("Each SDLC gap must be an object.")
                    continue
                if not gap.get("gap_id"):
                    errors.append("Each SDLC gap must have a gap_id.")
                if not gap.get("blocked_claims"):
                    errors.append(f"SDLC gap missing blocked_claims: {gap.get('gap_id')}")

    lower_text = combined_text.lower()
    for claim in FORBIDDEN_CLAIMS:
        if claim in lower_text:
            if "blocked_claims" in lower_text or "does not claim" in lower_text:
                continue
            errors.append(f"Forbidden SDLC false claim found: {claim}")

    if "MISSING_OFFICIAL_SOURCE" in combined_text:
        warnings.append(
            "Unsupported version-specific, security-sensitive, production, or cost "
            "claims must remain MISSING_OFFICIAL_SOURCE."
        )

    return {
        "artifact": "sdlc_best_practice_validation_report.json",
        "phase": "Phase 10.2",
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": checked_artifacts,
        "checked_technology_ids": sorted(technology_ids),
        "checked_required_labels": list(REQUIRED_LABELS),
    }
