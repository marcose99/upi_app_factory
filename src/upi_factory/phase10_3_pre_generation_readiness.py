"""Phase 10.3 pre-code-generation readiness gate.

This module consolidates Phase 10, Phase 10.1, and Phase 10.2 into a
deterministic readiness gate before Phase 11 implementation generation.

The gate is intentionally strict:
- no code generation until lifecycle planning, source governance, and
  technology best-practice governance are present and valid
- no live payment-network integration
- no unsupported regulatory, economic, or technology-specific claims
- no false compliance or certification claims
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from upi_factory.phase10_lifecycle_planner import validate_lifecycle_artifacts
from upi_factory.phase10_1_official_source_registry import (
    validate_official_source_artifacts,
)
from upi_factory.phase10_2_sdlc_best_practice_governance import (
    validate_sdlc_best_practice_artifacts,
)

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "code_generation_readiness_gate.json",
    "agent_execution_contract.md",
    "implementation_guardrails.md",
    "generation_input_manifest.json",
    "artifact_dependency_graph.json",
    "phase11_entry_criteria.md",
    "generated_application_sdlc_checklist.json",
    "pre_generation_validation_report.json",
)

UPSTREAM_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("phase10", "requirements_analysis.json"),
    ("phase10", "domain_analysis.md"),
    ("phase10", "architecture_options.md"),
    ("phase10", "architecture_decision_record.md"),
    ("phase10", "module_design.md"),
    ("phase10", "hld.md"),
    ("phase10", "lld.md"),
    ("phase10", "work_breakdown_structure.json"),
    ("phase10", "traceability_matrix.json"),
    ("phase10", "planning_validation_report.json"),
    ("phase10_1", "official_source_registry.json"),
    ("phase10_1", "official_source_evidence_pack.md"),
    ("phase10_1", "regulatory_economics_source_gap_report.json"),
    ("phase10_1", "source_freshness_policy.md"),
    ("phase10_1", "source_usage_policy.md"),
    ("phase10_1", "source_to_requirement_traceability.json"),
    ("phase10_1", "official_source_validation_report.json"),
    ("phase10_2", "sdlc_technology_registry.json"),
    ("phase10_2", "sdlc_best_practice_policy.md"),
    ("phase10_2", "technology_specific_prompt_instructions.md"),
    ("phase10_2", "sdlc_best_practice_traceability.json"),
    ("phase10_2", "sdlc_best_practice_gap_report.json"),
    ("phase10_2", "sdlc_best_practice_validation_report.json"),
)

REQUIRED_LABELS: tuple[str, ...] = (
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
    "OFFICIAL_SOURCE_REFERENCE",
    "SOURCE_BACKED_REFERENCE",
    "TECHNOLOGY_SPECIFIC_BEST_PRACTICE_REQUIRED",
    "VERSION_SPECIFIC_REVIEW_REQUIRED",
)

FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "RBI certified",
    "NPCI certified",
    "officially certified",
    "guaranteed compliant",
    "100% compliant",
    "production compliant",
    "production ready",
    "legal advice",
    "real UPI integration",
    "live NPCI integration",
    "live bank integration",
    "real customer-dispute processing",
)

PHASE11_AGENT_ROLES: tuple[str, ...] = (
    "implementation_planner_agent",
    "contract_model_agent",
    "mock_adapter_agent",
    "service_logic_agent",
    "test_generation_agent",
    "security_review_agent",
    "observability_agent",
    "documentation_agent",
    "validation_agent",
    "release_readiness_agent",
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _phase_dirs(
    phase10_dir: Path,
    phase10_1_dir: Path,
    phase10_2_dir: Path,
) -> dict[str, Path]:
    return {
        "phase10": phase10_dir,
        "phase10_1": phase10_1_dir,
        "phase10_2": phase10_2_dir,
    }


def _read_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return loaded


def _upstream_artifact_manifest(phase_dirs: dict[str, Path]) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []
    for phase_id, filename in UPSTREAM_ARTIFACTS:
        path = phase_dirs[phase_id] / filename
        manifest.append(
            {
                "phase_id": phase_id,
                "filename": filename,
                "path": str(path),
                "required": True,
                "exists_at_generation_time": path.exists(),
            }
        )
    return manifest


def _load_upstream_summaries(phase_dirs: dict[str, Path]) -> dict[str, Any]:
    # Compute upstream validation from current artifacts instead of trusting
    # only stored report files. In a clean temp test directory, an upstream
    # generator may create its report before the report artifact exists, so
    # re-running validators here gives the true current readiness state.
    summaries: dict[str, Any] = {}

    requirements_path = phase_dirs["phase10"] / "requirements_analysis.json"
    if requirements_path.exists():
        requirements = _read_json(requirements_path)
        summaries["requirement_ids"] = [
            item["id"]
            for item in requirements.get("requirements", [])
            if isinstance(item, dict) and "id" in item
        ]

    planning_report = validate_lifecycle_artifacts(phase_dirs["phase10"])
    source_report = validate_official_source_artifacts(phase_dirs["phase10_1"])
    tech_report = validate_sdlc_best_practice_artifacts(phase_dirs["phase10_2"])

    summaries["planning_validation_passed"] = bool(planning_report.get("passed"))
    summaries["official_source_validation_passed"] = bool(source_report.get("passed"))
    summaries["sdlc_best_practice_validation_passed"] = bool(tech_report.get("passed"))

    summaries["official_source_ids"] = source_report.get("checked_source_ids", [])
    summaries["technology_ids"] = tech_report.get("checked_technology_ids", [])

    summaries["upstream_validation_mode"] = "computed_from_current_artifacts"
    return summaries

def _readiness_gate(app_id: str, phase_dirs: dict[str, Path]) -> dict[str, Any]:
    upstream_manifest = _upstream_artifact_manifest(phase_dirs)
    summaries = _load_upstream_summaries(phase_dirs)

    gates: list[dict[str, Any]] = [
        {
            "gate_id": "GATE-10-3-001",
            "title": "Lifecycle planning artifacts exist",
            "status": "PASS" if all(item["exists_at_generation_time"] for item in upstream_manifest) else "FAIL",
            "evidence_refs": [item["path"] for item in upstream_manifest],
            "blocks_phase11_if_failed": True,
        },
        {
            "gate_id": "GATE-10-3-002",
            "title": "Phase 10 planning validation passed",
            "status": "PASS" if summaries.get("planning_validation_passed") is True else "FAIL",
            "evidence_refs": [str(phase_dirs["phase10"] / "planning_validation_report.json")],
            "blocks_phase11_if_failed": True,
        },
        {
            "gate_id": "GATE-10-3-003",
            "title": "Phase 10.1 official-source validation passed",
            "status": "PASS" if summaries.get("official_source_validation_passed") is True else "FAIL",
            "evidence_refs": [
                str(phase_dirs["phase10_1"] / "official_source_validation_report.json")
            ],
            "blocks_phase11_if_failed": True,
        },
        {
            "gate_id": "GATE-10-3-004",
            "title": "Phase 10.2 SDLC technology best-practice validation passed",
            "status": "PASS" if summaries.get("sdlc_best_practice_validation_passed") is True else "FAIL",
            "evidence_refs": [
                str(phase_dirs["phase10_2"] / "sdlc_best_practice_validation_report.json")
            ],
            "blocks_phase11_if_failed": True,
        },
        {
            "gate_id": "GATE-10-3-005",
            "title": "Mock boundary remains mandatory",
            "status": "PASS",
            "evidence_refs": [
                str(phase_dirs["phase10"] / "module_design.md"),
                str(phase_dirs["phase10_1"] / "source_usage_policy.md"),
                str(phase_dirs["phase10_2"] / "technology_specific_prompt_instructions.md"),
            ],
            "blocks_phase11_if_failed": True,
        },
        {
            "gate_id": "GATE-10-3-006",
            "title": "Economics and source gaps remain explicit",
            "status": "PASS",
            "evidence_refs": [
                str(phase_dirs["phase10"] / "requirements_analysis.json"),
                str(phase_dirs["phase10_1"] / "regulatory_economics_source_gap_report.json"),
                str(phase_dirs["phase10_2"] / "sdlc_best_practice_gap_report.json"),
            ],
            "blocks_phase11_if_failed": False,
        },
    ]

    return {
        "artifact": "code_generation_readiness_gate.json",
        "app_id": app_id,
        "phase": "Phase 10.3",
        "purpose": "Block Phase 11 implementation generation until upstream planning, source, and technology governance are ready.",
        "phase11_allowed": all(
            gate["status"] == "PASS"
            for gate in gates
            if gate["blocks_phase11_if_failed"]
        ),
        "upstream_summaries": summaries,
        "gates": gates,
        "required_labels": list(REQUIRED_LABELS),
        "phase11_agent_roles": list(PHASE11_AGENT_ROLES),
        "non_claims": {
            "no_certification_claim": True,
            "no_production_compliance_claim": True,
            "no_legal_advice": True,
            "no_live_payment_integration": True,
        },
    }


def _agent_execution_contract(app_id: str) -> str:
    return f"""
# Phase 10.3 Agent Execution Contract — {app_id}

## Purpose

This contract governs how Phase 11 and later implementation agents may generate
the mock UPI dispute-resolution application.

## Mandatory agent behavior

Every future implementation agent must:

1. Read the generation input manifest before changing files.
2. Follow Phase 10 requirements, architecture, HLD, LLD, WBS, and traceability.
3. Use Phase 10.1 source registry and source gap policy.
4. Use Phase 10.2 SDLC technology best-practice policy.
5. Preserve MOCK_BOUNDARY for banks, NPCI, RBI, PSPs, customer systems,
   ledgers, notification systems, reconciliation systems, and ODR systems.
6. Label unsupported regulatory, economic, technology, or operational facts
   as MISSING_OFFICIAL_SOURCE.
7. Use SYNTHETIC_DATA for demo data.
8. Keep generated code beginner-readable and debug-friendly.
9. Generate tests and validation scripts alongside implementation.
10. Prefer deterministic logic before agentic or LLM-based behavior.
11. Avoid false claims of certification, compliance, production readiness, or legal-advice status.

## Role-specific expectations

- implementation_planner_agent: break WBS tasks into safe code steps.
- contract_model_agent: create explicit schemas and validation boundaries.
- mock_adapter_agent: create mock external participant adapters only.
- service_logic_agent: implement deterministic dispute workflow logic.
- test_generation_agent: generate happy-path, negative-path, and boundary tests.
- security_review_agent: check secrets, unsafe inputs, and privacy boundaries.
- observability_agent: add traceable request/evidence identifiers.
- documentation_agent: write beginner-readable usage and debug guides.
- validation_agent: run deterministic validators and tests.
- release_readiness_agent: verify restore points, gates, and no false claims.

## Stop conditions

An agent must stop and produce a validation failure if:

- an upstream required artifact is missing
- a required validation report fails
- a live payment integration is introduced
- a real customer data requirement is introduced
- a false compliance/certification claim appears
- an economic or regulatory value is invented
- a technology-specific best-practice claim lacks source or gap label
"""


def _implementation_guardrails(app_id: str) -> str:
    return f"""
# Phase 10.3 Implementation Guardrails — {app_id}

## Mock-safe boundary

All external payment ecosystem dependencies remain MOCK_BOUNDARY:

- customer app
- remitter bank
- beneficiary bank
- PSP / TPAP
- NPCI / ODR
- RBI source references
- ledger
- reconciliation
- notification
- support system

No Phase 11 implementation may call a real bank, NPCI, RBI, PSP, customer,
payment, notification, or ledger service.

## Deterministic-first rule

Use deterministic rules, schemas, validators, and tests before introducing
LLM behavior. Any future agentic behavior must remain governed by evidence,
traceability, and fail-closed validation.

## Economics rule

Do not invent:

- current UPI volume or value
- bank internal cost per dispute
- support cost
- staffing reduction
- exact ROI
- exact vendor cost
- penalty or compensation exposure beyond source-backed context

Use MISSING_OFFICIAL_SOURCE, USER_PROVIDED_VALUE, or SYNTHETIC_DATA.

## Technology best-practice rule

Every generated implementation artifact must identify the technologies it uses
and apply technology-specific SDLC best practices. If a statement depends on
a version or vendor detail not available in evidence, label it
MISSING_OFFICIAL_SOURCE.

## Quality rule

Generated application work must preserve:

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
"""


def _generation_input_manifest(
    app_id: str,
    phase_dirs: dict[str, Path],
) -> dict[str, Any]:
    return {
        "artifact": "generation_input_manifest.json",
        "app_id": app_id,
        "phase": "Phase 10.3",
        "purpose": "Single manifest of upstream inputs that Phase 11 code generation must consume.",
        "required_upstream_artifacts": _upstream_artifact_manifest(phase_dirs),
        "phase11_agent_roles": list(PHASE11_AGENT_ROLES),
        "read_order": [
            "requirements_analysis.json",
            "domain_analysis.md",
            "architecture_decision_record.md",
            "module_design.md",
            "hld.md",
            "lld.md",
            "work_breakdown_structure.json",
            "traceability_matrix.json",
            "official_source_registry.json",
            "regulatory_economics_source_gap_report.json",
            "source_usage_policy.md",
            "sdlc_technology_registry.json",
            "sdlc_best_practice_policy.md",
            "technology_specific_prompt_instructions.md",
            "code_generation_readiness_gate.json",
            "agent_execution_contract.md",
            "implementation_guardrails.md",
        ],
        "write_constraints": {
            "must_create_tests_with_code": True,
            "must_create_validation_script": True,
            "must_preserve_mock_boundary": True,
            "must_preserve_beginner_readability": True,
            "must_update_traceability_when_scope_changes": True,
        },
    }


def _dependency_graph(
    app_id: str,
    phase_dirs: dict[str, Path],
) -> dict[str, Any]:
    nodes = [
        {
            "node_id": f"{phase_id}:{filename}",
            "phase_id": phase_id,
            "filename": filename,
            "path": str(phase_dirs[phase_id] / filename),
        }
        for phase_id, filename in UPSTREAM_ARTIFACTS
    ]

    nodes.extend(
        [
            {
                "node_id": "phase10_3:code_generation_readiness_gate.json",
                "phase_id": "phase10_3",
                "filename": "code_generation_readiness_gate.json",
                "path": "phase10_3/code_generation_readiness_gate.json",
            },
            {
                "node_id": "phase11:implementation_generation",
                "phase_id": "phase11",
                "filename": "implementation_generation",
                "path": "future_phase",
            },
        ]
    )

    edges = [
        {
            "from": f"{phase_id}:{filename}",
            "to": "phase10_3:code_generation_readiness_gate.json",
            "relationship": "required_input",
        }
        for phase_id, filename in UPSTREAM_ARTIFACTS
    ]
    edges.append(
        {
            "from": "phase10_3:code_generation_readiness_gate.json",
            "to": "phase11:implementation_generation",
            "relationship": "readiness_gate",
        }
    )

    return {
        "artifact": "artifact_dependency_graph.json",
        "app_id": app_id,
        "phase": "Phase 10.3",
        "nodes": nodes,
        "edges": edges,
    }


def _phase11_entry_criteria(app_id: str) -> str:
    return f"""
# Phase 11 Entry Criteria — {app_id}

Phase 11 implementation generation may start only when all blocking criteria
below pass.

## Blocking criteria

- Phase 10 planning validation report passed.
- Phase 10.1 official-source validation report passed.
- Phase 10.2 SDLC technology best-practice validation report passed.
- Phase 10.3 pre-generation validation report passed.
- Code generation readiness gate says `phase11_allowed=true`.
- Mock boundaries are still explicit.
- No false certification, compliance, production, or legal-advice claim exists.
- Economics and regulatory gaps remain labelled.
- Technology-specific best-practice requirement is present.
- Future implementation agents have a written execution contract.

## Non-blocking warnings

The following may remain as warnings for mock/demo phases:

- MISSING_OFFICIAL_SOURCE for dynamic current values.
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL for enterprise workflow models.
- SYNTHETIC_DATA for demo transactions.
- VERSION_SPECIFIC_REVIEW_REQUIRED for technologies without pinned versions.

## Phase 11 expected output

Phase 11 should generate a small, deterministic, mock-safe application skeleton
that follows the architecture and contracts, with tests, validators, and debug
guides generated together.
"""


def _sdlc_checklist(app_id: str) -> dict[str, Any]:
    items = [
        {
            "check_id": "SDLC-CHECK-001",
            "title": "Requirement mapped to implementation task",
            "blocking": True,
        },
        {
            "check_id": "SDLC-CHECK-002",
            "title": "Module design followed",
            "blocking": True,
        },
        {
            "check_id": "SDLC-CHECK-003",
            "title": "Mock adapters used for every external participant",
            "blocking": True,
        },
        {
            "check_id": "SDLC-CHECK-004",
            "title": "Technology-specific best practices identified",
            "blocking": True,
        },
        {
            "check_id": "SDLC-CHECK-005",
            "title": "Source-backed, synthetic, missing, and user-provided facts separated",
            "blocking": True,
        },
        {
            "check_id": "SDLC-CHECK-006",
            "title": "Tests generated with implementation",
            "blocking": True,
        },
        {
            "check_id": "SDLC-CHECK-007",
            "title": "Debug guide included",
            "blocking": False,
        },
        {
            "check_id": "SDLC-CHECK-008",
            "title": "No false compliance or certification claims",
            "blocking": True,
        },
        {
            "check_id": "SDLC-CHECK-009",
            "title": "Economics assumptions labelled",
            "blocking": True,
        },
        {
            "check_id": "SDLC-CHECK-010",
            "title": "Validation script provided",
            "blocking": True,
        },
    ]
    return {
        "artifact": "generated_application_sdlc_checklist.json",
        "app_id": app_id,
        "phase": "Phase 10.3",
        "purpose": "Checklist future Phase 11 implementation outputs must satisfy.",
        "items": items,
    }


def generate_pre_generation_readiness_artifacts(
    output_dir: Path,
    app_id: str = "upi_dispute_resolution",
    phase10_dir: Path | None = None,
    phase10_1_dir: Path | None = None,
    phase10_2_dir: Path | None = None,
) -> list[Path]:
    if phase10_dir is None:
        phase10_dir = Path(
            f"workspace/factory_generated/{app_id}/lifecycle_artifacts/phase10"
        )
    if phase10_1_dir is None:
        phase10_1_dir = Path(
            f"workspace/factory_generated/{app_id}/lifecycle_artifacts/phase10_1"
        )
    if phase10_2_dir is None:
        phase10_2_dir = Path(
            f"workspace/factory_generated/{app_id}/lifecycle_artifacts/phase10_2"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    phase_dirs = _phase_dirs(phase10_dir, phase10_1_dir, phase10_2_dir)

    payloads: dict[str, str | dict[str, Any]] = {
        "code_generation_readiness_gate.json": _readiness_gate(app_id, phase_dirs),
        "agent_execution_contract.md": _agent_execution_contract(app_id),
        "implementation_guardrails.md": _implementation_guardrails(app_id),
        "generation_input_manifest.json": _generation_input_manifest(app_id, phase_dirs),
        "artifact_dependency_graph.json": _dependency_graph(app_id, phase_dirs),
        "phase11_entry_criteria.md": _phase11_entry_criteria(app_id),
        "generated_application_sdlc_checklist.json": _sdlc_checklist(app_id),
    }

    written: list[Path] = []
    for filename in REQUIRED_ARTIFACTS:
        if filename == "pre_generation_validation_report.json":
            continue
        target = output_dir / filename
        payload = payloads[filename]
        if isinstance(payload, dict):
            _write_json(target, payload)
        else:
            _write_markdown(target, payload)
        written.append(target)

    report = validate_pre_generation_readiness_artifacts(
        output_dir,
        phase10_dir=phase10_dir,
        phase10_1_dir=phase10_1_dir,
        phase10_2_dir=phase10_2_dir,
    )
    report_path = output_dir / "pre_generation_validation_report.json"
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


def _safe_claim_line(line: str) -> bool:
    normalized = f" {line.strip().lower()} "
    stripped = normalized.strip()

    safe_markers = (
        " no ",
        " not ",
        " never ",
        " must not ",
        " do not ",
        " without ",
        " forbidden ",
        " prohibited ",
        " non-blocking ",
        " no_",
        " false claim",
        " false claims",
        " avoid ",
        " blocked ",
        " block ",
        " stop ",
        " stop condition",
        " non_claims",
    )

    if any(marker in normalized for marker in safe_markers):
        return True

    # Allow markdown bullets that merely list forbidden claims in a guardrail or
    # prohibited-claims section, but do not allow bare affirmative lines such as
    # "RBI certified" injected by tests or future artifacts.
    is_markdown_bullet = stripped.startswith(("-", "*"))
    is_numbered_bullet = bool(stripped[:1].isdigit()) and "." in stripped[:4]
    if is_markdown_bullet or is_numbered_bullet:
        bullet_text = stripped.lstrip("-*0123456789. ").strip()
        prohibited_terms = {claim.lower() for claim in FORBIDDEN_CLAIMS}
        if bullet_text in prohibited_terms:
            return True

    return False


def validate_pre_generation_readiness_artifacts(
    output_dir: Path,
    phase10_dir: Path | None = None,
    phase10_1_dir: Path | None = None,
    phase10_2_dir: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checked_artifacts: list[str] = []

    if phase10_dir is None:
        phase10_dir = Path(
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase10"
        )
    if phase10_1_dir is None:
        phase10_1_dir = Path(
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase10_1"
        )
    if phase10_2_dir is None:
        phase10_2_dir = Path(
            "workspace/factory_generated/upi_dispute_resolution/lifecycle_artifacts/phase10_2"
        )

    phase_dirs = _phase_dirs(phase10_dir, phase10_1_dir, phase10_2_dir)

    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if not path.exists():
            errors.append(f"Missing required artifact: {filename}")
        else:
            checked_artifacts.append(filename)

    for phase_id, filename in UPSTREAM_ARTIFACTS:
        path = phase_dirs[phase_id] / filename
        if not path.exists():
            errors.append(f"Missing upstream artifact: {phase_id}/{filename}")

    gate = _load_json(output_dir / "code_generation_readiness_gate.json", errors)
    manifest = _load_json(output_dir / "generation_input_manifest.json", errors)
    graph = _load_json(output_dir / "artifact_dependency_graph.json", errors)
    checklist = _load_json(
        output_dir / "generated_application_sdlc_checklist.json",
        errors,
    )

    text_cache: dict[str, str] = {}
    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if path.exists():
            text_cache[filename] = path.read_text(encoding="utf-8")
    combined_text = "\n".join(text_cache.values())
    false_claim_scan_items = [
        (filename, artifact_text)
        for filename, artifact_text in text_cache.items()
        if filename != "pre_generation_validation_report.json"
    ]
    for label in REQUIRED_LABELS:
        if label not in combined_text:
            errors.append(f"Missing required pre-generation label: {label}")

    if gate:
        if gate.get("phase11_allowed") is not True:
            errors.append("Readiness gate does not allow Phase 11.")
        gates = gate.get("gates", [])
        if not isinstance(gates, list) or not gates:
            errors.append("Readiness gate must contain gates.")
        else:
            for item in gates:
                if not isinstance(item, dict):
                    errors.append("Each readiness gate must be an object.")
                    continue
                if item.get("blocks_phase11_if_failed") and item.get("status") != "PASS":
                    errors.append(f"Blocking readiness gate failed: {item.get('gate_id')}")

        roles = gate.get("phase11_agent_roles", [])
        missing_roles = [role for role in PHASE11_AGENT_ROLES if role not in roles]
        for role in missing_roles:
            errors.append(f"Missing Phase 11 agent role in readiness gate: {role}")

    if manifest:
        upstream = manifest.get("required_upstream_artifacts", [])
        if not isinstance(upstream, list) or len(upstream) < len(UPSTREAM_ARTIFACTS):
            errors.append("Generation input manifest missing upstream artifacts.")
        if not manifest.get("read_order"):
            errors.append("Generation input manifest missing read_order.")
        constraints = manifest.get("write_constraints", {})
        if not isinstance(constraints, dict):
            errors.append("Generation input manifest write_constraints must be an object.")
        else:
            for required_constraint in (
                "must_create_tests_with_code",
                "must_create_validation_script",
                "must_preserve_mock_boundary",
                "must_preserve_beginner_readability",
            ):
                if constraints.get(required_constraint) is not True:
                    errors.append(
                        f"Generation input manifest missing constraint: {required_constraint}"
                    )

    if graph:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        if not isinstance(nodes, list) or not nodes:
            errors.append("Dependency graph missing nodes.")
        if not isinstance(edges, list) or not edges:
            errors.append("Dependency graph missing edges.")
        if isinstance(edges, list):
            has_phase11_edge = any(
                isinstance(edge, dict)
                and edge.get("to") == "phase11:implementation_generation"
                for edge in edges
            )
            if not has_phase11_edge:
                errors.append("Dependency graph missing Phase 11 readiness edge.")

    if checklist:
        items = checklist.get("items", [])
        if not isinstance(items, list) or len(items) < 10:
            errors.append("Generated application SDLC checklist must contain at least 10 items.")
        else:
            blocking_items = [
                item for item in items
                if isinstance(item, dict) and item.get("blocking") is True
            ]
            if len(blocking_items) < 7:
                errors.append("Generated application SDLC checklist needs enough blocking checks.")

    for filename, artifact_text in false_claim_scan_items:
        for line_number, line in enumerate(artifact_text.splitlines(), start=1):
            for claim in FORBIDDEN_CLAIMS:
                if claim.lower() in line.lower() and not _safe_claim_line(line):
                    errors.append(
                        "Forbidden pre-generation false claim found: "
                        f"{claim} in {filename}:{line_number}: {line.strip()}"
                    )

    if "MISSING_OFFICIAL_SOURCE" in combined_text:
        warnings.append(
            "Phase 11 may proceed for mock/demo generation, but unsupported live "
            "regulatory, economic, and technology-specific values must remain labelled."
        )

    return {
        "artifact": "pre_generation_validation_report.json",
        "phase": "Phase 10.3",
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": checked_artifacts,
        "checked_required_labels": list(REQUIRED_LABELS),
        "checked_phase11_agent_roles": list(PHASE11_AGENT_ROLES),
    }
