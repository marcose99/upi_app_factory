"""Phase 10 lifecycle artifact planner for UPI App Factory.

This module is intentionally deterministic, mock-safe, and beginner-readable.
It creates planning artifacts before any code generation step.

Important boundary:
- This is a synthetic planning model for a mock UPI dispute-resolution app.
- It must not claim RBI/NPCI certification, regulatory approval, or legal advice.
- Official-source gaps must be labelled instead of guessed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_ARTIFACTS: tuple[str, ...] = (
    "requirements_analysis.json",
    "domain_analysis.md",
    "architecture_options.md",
    "architecture_decision_record.md",
    "module_design.md",
    "hld.md",
    "lld.md",
    "work_breakdown_structure.json",
    "traceability_matrix.json",
    "planning_validation_report.json",
)

HONESTY_LABELS: tuple[str, ...] = (
    "MISSING_OFFICIAL_SOURCE",
    "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
    "MOCK_BOUNDARY",
    "SYNTHETIC_DATA",
)

OFFICIAL_REFERENCE_CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "id": "RBI_ODR_DIGITAL_PAYMENTS_2020",
        "authority": "Reserve Bank of India",
        "title": "Online Dispute Resolution system for digital payments",
        "url": "https://www.rbi.org.in/commonman/english/scripts/Notification.aspx?Id=3194",
        "use_in_phase10": (
            "ODR expectations, failed-transaction dispute scope, escalation posture"
        ),
        "script_status": "REFERENCE_ONLY_NOT_FETCHED_AT_RUNTIME",
    },
    {
        "id": "RBI_FAILED_TRANSACTION_TAT_2019",
        "authority": "Reserve Bank of India",
        "title": (
            "Harmonisation of Turn Around Time and customer compensation for "
            "failed transactions using authorised payment systems"
        ),
        "url": "https://www.rbi.org.in/commonman/English/scripts/Notification.aspx?Id=3074",
        "use_in_phase10": ("TAT awareness, compensation-risk awareness, no hard-coded live limits"),
        "script_status": "REFERENCE_ONLY_NOT_FETCHED_AT_RUNTIME",
    },
    {
        "id": "RBI_LIMITED_LIABILITY_2017",
        "authority": "Reserve Bank of India",
        "title": "Limiting liability of customers in unauthorised electronic banking transactions",
        "url": "https://www.rbi.org.in/commonman/english/scripts/Notification.aspx?Id=2336",
        "use_in_phase10": "Customer-liability awareness and escalation labelling",
        "script_status": "REFERENCE_ONLY_NOT_FETCHED_AT_RUNTIME",
    },
    {
        "id": "NPCI_UPI_PRODUCT_STATISTICS",
        "authority": "National Payments Corporation of India",
        "title": "UPI product statistics",
        "url": "https://www.npci.org.in/product/upi/product-statistics",
        "use_in_phase10": (
            "Volume/value sizing source candidate; exact current data is not "
            "embedded by this deterministic script"
        ),
        "script_status": "REFERENCE_ONLY_NOT_FETCHED_AT_RUNTIME",
    },
    {
        "id": "NPCI_UPI_HELP",
        "authority": "National Payments Corporation of India",
        "title": "UPI Help / dispute redressal mechanism",
        "url": "https://upihelp.npci.org.in/",
        "use_in_phase10": "Public complaint and transaction-status reference candidate",
        "script_status": "REFERENCE_ONLY_NOT_FETCHED_AT_RUNTIME",
    },
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _requirements(app_id: str) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = [
        {
            "id": "RQ-FUN-001",
            "title": "Capture a mock UPI dispute case",
            "type": "functional",
            "priority": "must",
            "description": (
                "Accept a synthetic dispute request with transaction, participant, "
                "amount, timestamps, status reason, and customer narrative."
            ),
            "acceptance_criteria": [
                "Reject missing required fields with clear beginner-readable errors.",
                "Mark every sample payload as SYNTHETIC_DATA.",
                "Never ingest or require real customer, bank, or NPCI credentials.",
            ],
            "honesty_labels": ["SYNTHETIC_DATA", "MOCK_BOUNDARY"],
        },
        {
            "id": "RQ-FUN-002",
            "title": "Classify dispute pathway deterministically",
            "type": "functional",
            "priority": "must",
            "description": (
                "Classify failed, pending, duplicate debit, refund pending, and "
                "unsupported scenarios using deterministic policy rules first."
            ),
            "acceptance_criteria": [
                "Produce the same output for the same input and policy version.",
                "Explain the matched rule and policy version.",
                "Escalate unsupported cases without hallucinating policy outcomes.",
            ],
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL"],
        },
        {
            "id": "RQ-FUN-003",
            "title": "Generate an evidence pack before decision output",
            "type": "functional",
            "priority": "must",
            "description": (
                "Create a traceable evidence pack containing input facts, matched "
                "rules, mock participant responses, and unresolved gaps."
            ),
            "acceptance_criteria": [
                "Evidence pack is append-only and hashable.",
                "Every decision cites evidence IDs.",
                "Missing official-rule details are labelled MISSING_OFFICIAL_SOURCE.",
            ],
            "honesty_labels": ["MISSING_OFFICIAL_SOURCE"],
        },
        {
            "id": "RQ-FUN-004",
            "title": "Use a mocked ecosystem for all external participants",
            "type": "functional",
            "priority": "must",
            "description": (
                "Represent customer app, remitter bank, beneficiary bank, PSP, "
                "NPCI/ODR, ledger, notification, and reconciliation services as "
                "mock adapters."
            ),
            "acceptance_criteria": [
                "No live network call to bank, NPCI, RBI, payment app, or customer system.",
                "All external calls go through replaceable mock adapters.",
                "Adapter contract tests cover positive, negative, and timeout scenarios.",
            ],
            "honesty_labels": ["MOCK_BOUNDARY"],
        },
        {
            "id": "RQ-GOV-001",
            "title": "Preserve governance, audit, and release readiness",
            "type": "governance",
            "priority": "must",
            "description": (
                "Planning artifacts must preserve existing governance dimensions: "
                "mock boundaries, evidence ledger, traceability, release readiness, "
                "debugging standards, and regeneration readiness."
            ),
            "acceptance_criteria": [
                "Traceability connects requirements to design and WBS tasks.",
                "Planning validation fails closed when required artifacts are missing.",
                "No generated claim states certification or official compliance approval.",
            ],
            "honesty_labels": [
                "MISSING_OFFICIAL_SOURCE",
                "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
            ],
        },
        {
            "id": "RQ-QUAL-001",
            "title": "Carry generated-application quality dimensions into planning",
            "type": "quality",
            "priority": "must",
            "description": (
                "Planning must explicitly account for reliability, security, "
                "observability, testability, maintainability, usability, performance, "
                "recoverability, and operability."
            ),
            "acceptance_criteria": [
                "HLD lists quality attributes and validation gates.",
                "LLD includes failure modes and debug guidance.",
                "WBS includes validation tasks for each major quality dimension.",
            ],
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL"],
        },
        {
            "id": "RQ-REG-001",
            "title": "Align with payment regulatory themes without overclaiming",
            "type": "regulatory_alignment",
            "priority": "must",
            "description": (
                "Planning must consider ODR, failed-transaction TAT, customer "
                "liability, security controls, data minimisation, audit evidence, "
                "and escalation workflows using official references where available."
            ),
            "acceptance_criteria": [
                "Official references are stored as reference candidates.",
                "Exact live regulatory limits are not invented.",
                "Unverified or absent source details are labelled MISSING_OFFICIAL_SOURCE.",
            ],
            "honesty_labels": ["MISSING_OFFICIAL_SOURCE"],
        },
        {
            "id": "RQ-ECO-001",
            "title": "Model factory economics before generation",
            "type": "economics",
            "priority": "must",
            "description": (
                "Estimate the economic effect of deterministic-first automation, "
                "agent run cost, review effort, rework cost, evidence creation, "
                "test automation, tool replacement, and technical debt."
            ),
            "acceptance_criteria": [
                "Architecture options compare cost-to-build and cost-to-change.",
                "WBS includes review and validation effort as first-class work.",
                "Prompt guidance avoids pretending exact ROI without measured data.",
            ],
            "honesty_labels": [
                "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
                "MISSING_OFFICIAL_SOURCE",
            ],
        },
        {
            "id": "RQ-ECO-002",
            "title": "Model application-level dispute economics",
            "type": "economics",
            "priority": "must",
            "description": (
                "Capture cost drivers for a UPI dispute operation: manual triage, "
                "case aging, compensation exposure, exception handling, customer "
                "trust, complaint re-open rate, refund leakage, false positives, "
                "false negatives, reconciliation effort, and support workload."
            ),
            "acceptance_criteria": [
                "No real bank pricing, NPCI fee, penalty, or TAT value is hard-coded.",
                "All live economic numbers require an official or user-provided source.",
                "Synthetic scenarios are separated from measurable production metrics.",
            ],
            "honesty_labels": [
                "SYNTHETIC_DATA",
                "MISSING_OFFICIAL_SOURCE",
                "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
            ],
        },
        {
            "id": "RQ-ECO-003",
            "title": "Design for safe cost-risk tradeoffs",
            "type": "economics",
            "priority": "should",
            "description": (
                "Prefer lower-cost deterministic checks for stable policy decisions, "
                "reserve LLM or human review for ambiguous cases, and expose economic "
                "risk from delayed or wrong decisions."
            ),
            "acceptance_criteria": [
                "Architecture decision explains deterministic-first cost control.",
                "Module design includes budget guardrails and escalation thresholds.",
                "LLD records where human review is economically justified.",
            ],
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL"],
        },
        {
            "id": "RQ-ECO-004",
            "title": "Keep tooling modular to manage vendor and switching economics",
            "type": "economics",
            "priority": "should",
            "description": (
                "Use adapters so LLM providers, workflow engines, storage layers, "
                "policy engines, vector stores, and observability tools can be "
                "replaced later without rewriting the factory."
            ),
            "acceptance_criteria": [
                "HLD shows replaceable interfaces.",
                "LLD defines ports/adapters rather than hard-wired vendors.",
                "WBS includes replacement-readiness and lock-in review tasks.",
            ],
            "honesty_labels": ["SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL"],
        },
    ]

    return {
        "artifact": "requirements_analysis.json",
        "app_id": app_id,
        "phase": "Phase 10",
        "purpose": "Requirement-to-Architecture-to-Plan pipeline before code generation",
        "determinism": {
            "runtime_timestamp_used": False,
            "generation_style": "static deterministic templates plus explicit traceability",
        },
        "safety_boundary": {
            "mock_safe": True,
            "no_live_payment_network_calls": True,
            "no_real_customer_data": True,
            "no_certification_claim": True,
        },
        "official_reference_candidates": list(OFFICIAL_REFERENCE_CANDIDATES),
        "requirements": requirements,
        "economics_guidance": {
            "factory_economics": [
                "agent/tool run cost",
                "human review effort",
                "validation automation effort",
                "rework and regeneration cost",
                "cost of quality and audit evidence",
                "switching cost and vendor lock-in risk",
                "onboarding and beginner-debuggability cost",
                "technical debt interest from weak planning",
            ],
            "application_economics": [
                "manual dispute handling effort",
                "case aging and escalation cost",
                "refund and compensation exposure",
                "false approval and false rejection cost",
                "customer trust and complaint re-open rate",
                "reconciliation effort",
                "support workload",
                "operational exception queues",
            ],
            "measurement_rule": (
                "Use synthetic values only for demo scenarios. Use official or "
                "user-provided data for real monetary, TAT, fee, penalty, volume, "
                "or ROI assertions."
            ),
        },
        "required_honesty_labels": list(HONESTY_LABELS),
    }


def _domain_analysis(app_id: str) -> str:
    return f"""
# Phase 10 Domain Analysis — {app_id}

## Scope

This is a governed, mock-safe, deterministic-first domain model for a UPI
dispute-resolution software factory. It prepares lifecycle artifacts before
any code generation.

The domain is intentionally limited to a mock dispute-resolution application.
It does not connect to real UPI rails, NPCI, RBI, banks, PSPs, TPAPs, customer
systems, or live ledgers. Every external participant must remain behind a
MOCK_BOUNDARY.

## Payment dispute domain concepts

- Customer dispute case
- UPI transaction reference
- Remitter participant
- Beneficiary participant
- PSP / app participant
- Mock NPCI/ODR participant
- Dispute reason
- Failed transaction
- Duplicate debit
- Refund pending
- Status inquiry
- Escalation
- Evidence pack
- Deterministic decision rule
- Human-review queue
- Release evidence

## Regulatory-alignment themes

The factory should reason about regulatory themes without overclaiming:
ODR, failed-transaction turn-around-time awareness, customer-liability
awareness, audit evidence, complaint escalation, security controls,
data minimisation, and operational resilience.

Exact legal interpretation, exact current TAT limits, exact compensation,
official certification status, and production compliance assessment must not
be invented. Use MISSING_OFFICIAL_SOURCE when the official source is absent,
stale, or not parsed into the evidence pack.

## Economics — factory level

Factory economics should be evaluated before code generation:

1. Build cost: prompts, deterministic templates, validators, tests, docs,
   review cycles, and integration work.
2. Run cost: LLM calls where used, local scripts, workflow orchestration,
   storage, trace generation, and validation time.
3. Rework cost: failed generation, missing traceability, weak requirements,
   unclear architecture, and human correction effort.
4. Cost of quality: tests, static checks, policy checks, evidence ledger,
   audit pack, and release-readiness gates.
5. Cost of poor quality: production incidents, rework, unclear ownership,
   audit failure, false claims, and support burden.
6. Switching economics: replaceable model providers, vector stores, policy
   engines, workflow engines, evidence stores, and observability systems.
7. Learning economics: beginner-readable code and debug guides reduce future
   maintenance and onboarding cost.

## Economics — application level

A UPI dispute-resolution application has operational economic drivers:

- manual triage effort per dispute
- aging queue cost
- customer support cost
- refund leakage
- compensation exposure
- false-positive and false-negative decision cost
- complaint re-open cost
- reconciliation effort
- trust/reputation impact
- escalation handling
- incident recovery cost
- audit and evidence production cost

All real economic values must be sourced. Synthetic values must be labelled
SYNTHETIC_DATA. Any unsupported claim about live fee, penalty, compensation,
or ROI must be labelled MISSING_OFFICIAL_SOURCE.

## Quality dimensions

The generated application must carry quality into design rather than bolting
it on later: reliability, security, maintainability, modularity, testability,
observability, explainability, operability, recoverability, performance,
usability, auditability, and controlled extensibility.

## Data classification

- Synthetic dispute request: SYNTHETIC_DATA
- Synthetic participant response: SYNTHETIC_DATA
- Mock policy scenario: SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- Missing current regulatory fact: MISSING_OFFICIAL_SOURCE
- Any bank/NPCI/RBI/external system interaction: MOCK_BOUNDARY
"""


def _architecture_options(app_id: str) -> str:
    return f"""
# Phase 10 Architecture Options — {app_id}

## Decision problem

Select a planning architecture that generates lifecycle artifacts before code
generation while preserving governance, traceability, mocked boundaries,
quality dimensions, regulatory-alignment themes, and economics.

## Option A — Single deterministic planner

### Summary

A single Python module generates all Phase 10 artifacts from deterministic
templates.

### Pros

- Lowest implementation complexity.
- Lowest runtime cost.
- Easy for beginners to debug.
- Strong reproducibility.
- Good for a capstone demonstration.

### Cons

- Limited flexibility for future complex requirement intake.
- Harder to scale to many domains.
- Less realistic for enterprise multi-agent planning.

### Economics

- Low build cost and low run cost.
- Low review cost for simple scenarios.
- Higher future change cost if requirements become diverse.

### Governance fit

Good for deterministic-first safety, but weaker for role separation.

## Option B — Event-driven multi-service planning pipeline

### Summary

Requirements, domain analysis, architecture, design, WBS, and traceability are
separate services connected by a message bus.

### Pros

- Closest to large enterprise topology.
- Strong separation of responsibilities.
- Easier to scale individual services.
- Natural fit for asynchronous review and event sourcing.

### Cons

- High implementation cost at this project stage.
- More infrastructure and operational complexity.
- Higher debugging burden.
- Higher cost for a laptop-based mock factory.

### Economics

- Higher build cost, run cost, and operational cost.
- Useful later when throughput, team ownership, and deployment isolation matter.
- Not cost-effective for the current deterministic capstone phase.

### Governance fit

Strong if implemented correctly, but risk of over-engineering now.

## Option C — Governed modular monolith with replaceable ports/adapters

### Summary

A deterministic planning core generates lifecycle artifacts. Each planner
capability is separated by module contracts and can later be replaced by
agents, workflow steps, policy engines, external stores, or human review.

### Pros

- Preserves deterministic-first behavior.
- Beginner-readable and debug-friendly.
- Supports future agent replacement without heavy infrastructure now.
- Keeps governance, validation, traceability, and economics visible.
- Suitable for repeated regeneration demos.

### Cons

- Not a full distributed enterprise platform yet.
- Requires discipline to keep ports/adapters clean.
- Some agent behavior remains synthetic until later phases.

### Economics

- Balanced build cost and future flexibility.
- Lower run cost than event-driven microservices.
- Lower change cost than a single hard-coded planner.
- Reduces vendor lock-in through replaceable interfaces.
- Keeps human review focused on high-risk ambiguity instead of mechanical work.

### Governance fit

Best fit for current project direction: mock-safe, deterministic-first,
evidence-driven, modular, and near-certifiable in posture without making
certification claims.

## Recommended selection

Select Option C.

Reason: Option C offers the best balance across safety, economics, governance,
debuggability, modularity, and future scalability. It supports the factory
vision without introducing avoidable infrastructure cost or false compliance
claims.

## Required honesty labels

- MISSING_OFFICIAL_SOURCE
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- MOCK_BOUNDARY
- SYNTHETIC_DATA
"""


def _adr(app_id: str) -> str:
    return f"""
# Architecture Decision Record — Phase 10 Planning Pipeline

## Status

Accepted for mock project evolution.

## Context

upi_app_factory / {app_id} needs a requirement-to-architecture-to-plan
pipeline before code generation. Previous phases established governance,
mock boundaries, regeneration, evidence, prompt quality, role simulation,
workflow orchestration, quality dimensions, and payment regulatory alignment.

The next phase must create structured lifecycle artifacts and validate them
before code is generated.

## Decision

Use a governed modular monolith with replaceable ports/adapters.

## Justification

This architecture is selected because it:

- keeps deterministic generation as the default
- remains beginner-readable and debug-friendly
- supports future agentic replacement of individual planners
- avoids heavy infrastructure too early
- keeps governance evidence close to the generated artifacts
- makes economics explicit before implementation
- avoids false compliance or certification claims
- preserves MOCK_BOUNDARY around all external payment participants

## Economic rationale

The selected option reduces immediate build and run cost compared with an
event-driven microservice topology while avoiding the future rigidity of a
single hard-coded generator. It improves cost-to-change through module
contracts and limits LLM/model/tool spend by reserving non-deterministic
reasoning for future controlled extension points.

At application level, the design supports later measurement of manual triage
cost, case aging, compensation exposure, re-open rate, false-positive cost,
false-negative cost, reconciliation effort, and support workload. No real
monetary value is asserted without a source. Unsupported economic claims must
be labelled MISSING_OFFICIAL_SOURCE.

## Consequences

Positive:

- Faster implementation of Phase 10.
- Strong deterministic validation.
- Clear traceability before coding.
- Easier demo regeneration.
- Easier future migration to agent/workflow services.

Negative:

- Not a fully distributed enterprise platform yet.
- Requires ongoing discipline to avoid hard-coded business conclusions.
- Some enterprise workflow behavior remains a
  SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL.

## Compliance posture

This ADR supports regulatory alignment and audit readiness as engineering
practices. It does not claim official RBI/NPCI compliance certification,
legal advice, or production readiness.

## Honesty labels

MISSING_OFFICIAL_SOURCE, SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY,
SYNTHETIC_DATA
"""


def _module_design(app_id: str) -> str:
    return f"""
# Phase 10 Module Design — {app_id}

## Module map

| Module | Responsibility | Inputs | Outputs | Economics handled |
|---|---|---|---|---|
| Requirement Analyzer | Converts project intent into structured requirements | Project direction, prior governance | requirements_analysis.json | Cost drivers, source gaps |
| Domain Analyzer | Explains payment dispute domain and boundaries | Requirements | domain_analysis.md | Manual ops, dispute economics |
| Architecture Optioner | Produces multiple architecture options | Requirements, domain | architecture_options.md | Build/run/change cost |
| ADR Writer | Selects architecture with justification | Options | architecture_decision_record.md | Cost-risk tradeoff |
| Module Designer | Defines modules and contracts | ADR | module_design.md | Modularity and replacement cost |
| HLD Generator | Produces high-level design | ADR, module design | hld.md | Runtime and operational cost |
| LLD Generator | Produces low-level design | HLD | lld.md | Debugging and rework cost |
| WBS Planner | Orders manageable tasks | Requirements/design | work_breakdown_structure.json | Effort and sequencing |
| Traceability Builder | Connects requirement to design to task | All artifacts | traceability_matrix.json | Audit/review cost |
| Planning Validator | Fails closed on missing evidence | All artifacts | planning_validation_report.json | Cost of poor planning |
| Economics Assessor | Makes economics explicit without inventing numbers | Requirements/domain | Embedded sections | ROI/source discipline |
| Mock Boundary Guard | Blocks live external dependencies | External adapter intents | Validation failures | Safety and incident cost |

## Design principles

1. Deterministic-first: stable policy, validation, and traceability are
   handled with deterministic logic before any future agent expansion.
2. Mock-safe: all bank, PSP, NPCI, RBI, notification, ledger, and customer
   channels are mock adapters.
3. Evidence-driven: every planning decision must point to a requirement,
   design section, or source-gap label.
4. Beginner-readable: plain names, small functions, clear errors, and
   direct validation reports.
5. Modular replacement: future phases can replace deterministic modules
   with governed agents one by one.
6. Economics-aware: build/run/change/rework/review/incident costs are
   considered before implementation.
7. Honest posture: MISSING_OFFICIAL_SOURCE is better than a guessed rule.

## Ports and adapters

- RequirementInputPort
- OfficialSourceReferencePort
- ArchitectureOptionPort
- DesignArtifactPort
- TraceabilityPort
- ValidationReportPort
- MockParticipantAdapterPort
- EconomicsAssessmentPort

## Mock external adapters

- MockCustomerAppAdapter
- MockRemitterBankAdapter
- MockBeneficiaryBankAdapter
- MockPspAdapter
- MockNpciOdrAdapter
- MockLedgerAdapter
- MockReconciliationAdapter
- MockNotificationAdapter

Every adapter is a MOCK_BOUNDARY.
"""


def _hld(app_id: str) -> str:
    return """
# High-Level Design — Phase 10 Planning Pipeline

## Goal

Generate and validate lifecycle artifacts before code generation for the
mock UPI dispute-resolution factory application.

## High-level flow

```text
Project Intent
  -> Requirement Analyzer
  -> Domain Analyzer
  -> Architecture Optioner
  -> ADR Writer
  -> Module Designer
  -> HLD Generator
  -> LLD Generator
  -> WBS Planner
  -> Traceability Builder
  -> Planning Validator
  -> Code Generation Readiness Gate
```

## Runtime deployment style

Current phase: local deterministic CLI/module execution.

Future-compatible style: each module may become a governed agent node,
workflow step, or service once the deterministic contracts are stable.

## Quality attributes

| Quality attribute | Design mechanism |
|---|---|
| Reliability | Fail-closed validation and deterministic artifacts |
| Security | No live payment calls; no real credentials; mock boundaries |
| Maintainability | Small module contracts and readable generated files |
| Testability | JSON/Markdown artifacts plus validator and pytest coverage |
| Observability | Validation report, traceability matrix, evidence-friendly IDs |
| Auditability | Requirement-to-design-to-task traceability |
| Operability | Simple scripts and clear failure messages |
| Recoverability | Git branch/tag restore points |
| Performance | Local static generation with no external runtime dependency |
| Cost control | Deterministic-first, source-gap labels, replaceable adapters |

## Economics design

Factory economics:

- deterministic checks reduce repeated agent/review cost
- validation early reduces late rework
- modular design reduces future replacement cost
- explicit traceability reduces audit preparation cost
- beginner readability reduces onboarding and maintenance cost

Application economics:

- dispute aging, manual triage, complaint re-open, refund leakage,
  reconciliation, customer trust, and escalation workload are represented
  as design concerns
- exact amounts, penalties, fees, transaction volumes, or ROI claims require
  official or user-provided sources
- unsupported values remain MISSING_OFFICIAL_SOURCE

## Governance

The HLD carries forward:

- generated-application quality dimensions
- software-engineering governance
- payment regulatory alignment
- mocked ecosystem boundaries
- honesty labels
- release-readiness posture
- regeneration-readiness posture

## Boundaries

No real UPI, bank, PSP, customer, NPCI, or RBI system is called.

Required labels: MISSING_OFFICIAL_SOURCE,
SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA.
"""


def _lld(app_id: str) -> str:
    return """
# Low-Level Design — Phase 10 Planning Pipeline

## Python module

`src/upi_factory/phase10_lifecycle_planner.py`

## Public functions

### generate_lifecycle_artifacts(output_dir: Path, app_id: str) -> list[Path]

Creates all required Phase 10 lifecycle artifacts in deterministic order.

### validate_lifecycle_artifacts(output_dir: Path) -> dict[str, Any]

Validates required files, JSON structure, traceability, architecture content,
and honesty labels.

## Artifact contracts

### requirements_analysis.json

Required keys:

- artifact
- app_id
- phase
- safety_boundary
- official_reference_candidates
- requirements
- economics_guidance
- required_honesty_labels

Each requirement needs:

- id
- title
- type
- priority
- description
- acceptance_criteria
- honesty_labels

### work_breakdown_structure.json

Each task needs:

- id
- sequence
- title
- requirement_ids
- design_refs
- validation_refs
- relative_effort_points
- relative_risk_points
- economics_notes
- done_when

### traceability_matrix.json

Each row needs:

- requirement_id
- requirement_title
- design_artifacts
- wbs_task_ids
- validation_refs
- economics_refs
- honesty_labels

### planning_validation_report.json

Required keys:

- passed
- errors
- warnings
- checked_artifacts
- checked_honesty_labels
- checked_traceability

## Failure modes and handling

| Failure mode | Handling |
|---|---|
| Missing artifact | Validator returns passed=false and lists file |
| Broken JSON | Validator returns exact JSON parse error |
| Requirement without task | Validator fails traceability |
| Missing honesty label | Validator fails content check |
| Architecture options missing pros/cons | Validator fails design completeness |
| Selected architecture absent | Validator fails ADR completeness |
| Official source missing | Do not guess; use MISSING_OFFICIAL_SOURCE |

## Debug guide

1. Run `python scripts/generate_phase10_lifecycle_artifacts.py`.
2. Run `python scripts/validate_phase10_lifecycle_artifacts.py`.
3. If validation fails, open `planning_validation_report.json`.
4. Fix the named artifact.
5. Re-run validator before committing.

## Economics implementation detail

The current implementation stores economic reasoning as structured text and
relative planning points. It does not compute real ROI, regulatory penalties,
bank fees, NPCI charges, model prices, or support costs. Those require
official or user-provided data.

## Security and privacy detail

The planner uses only local files and synthetic content. No live credentials,
payment identifiers, customer PII, or external API calls are required.

Honesty labels: MISSING_OFFICIAL_SOURCE,
SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL, MOCK_BOUNDARY, SYNTHETIC_DATA.
"""


def _wbs() -> dict[str, Any]:
    tasks: list[dict[str, Any]] = [
        {
            "id": "WBS-010-001",
            "sequence": 1,
            "title": "Create deterministic Phase 10 artifact contracts",
            "requirement_ids": ["RQ-GOV-001", "RQ-QUAL-001"],
            "design_refs": ["module_design.md", "lld.md"],
            "validation_refs": ["planning_validation_report.json"],
            "relative_effort_points": 3,
            "relative_risk_points": 2,
            "economics_notes": [
                "Prevents late rework by freezing artifact shape before code generation.",
                "Reduces audit preparation effort through standard file contracts.",
            ],
            "done_when": [
                "All required artifact names are declared.",
                "Validator checks all required files.",
            ],
        },
        {
            "id": "WBS-010-002",
            "sequence": 2,
            "title": "Generate requirements analysis with governance and economics",
            "requirement_ids": [
                "RQ-FUN-001",
                "RQ-FUN-002",
                "RQ-FUN-003",
                "RQ-FUN-004",
                "RQ-GOV-001",
                "RQ-ECO-001",
                "RQ-ECO-002",
            ],
            "design_refs": ["requirements_analysis.json", "domain_analysis.md"],
            "validation_refs": ["planning_validation_report.json"],
            "relative_effort_points": 5,
            "relative_risk_points": 3,
            "economics_notes": [
                "Captures cost drivers before implementation.",
                "Avoids fake ROI by requiring official or user-provided data.",
            ],
            "done_when": [
                "Every requirement has acceptance criteria.",
                "Economics requirements exist and are traceable.",
            ],
        },
        {
            "id": "WBS-010-003",
            "sequence": 3,
            "title": "Write domain analysis with payment and mock ecosystem boundaries",
            "requirement_ids": ["RQ-FUN-004", "RQ-REG-001", "RQ-ECO-002"],
            "design_refs": ["domain_analysis.md", "hld.md"],
            "validation_refs": ["planning_validation_report.json"],
            "relative_effort_points": 5,
            "relative_risk_points": 4,
            "economics_notes": [
                "Shows operational drivers such as triage, aging, re-open, and reconciliation.",
                "Prevents costly unsafe integration with live payment systems.",
            ],
            "done_when": [
                "Domain analysis includes MOCK_BOUNDARY.",
                "Domain analysis includes application economics.",
            ],
        },
        {
            "id": "WBS-010-004",
            "sequence": 4,
            "title": "Compare multiple architecture options",
            "requirement_ids": ["RQ-QUAL-001", "RQ-ECO-001", "RQ-ECO-003"],
            "design_refs": ["architecture_options.md"],
            "validation_refs": ["planning_validation_report.json"],
            "relative_effort_points": 5,
            "relative_risk_points": 3,
            "economics_notes": [
                "Compares build cost, run cost, future change cost, and over-engineering risk.",
                "Protects current laptop-scale project from premature heavy infrastructure.",
            ],
            "done_when": [
                "At least three options are documented.",
                "Each option has pros, cons, economics, and governance fit.",
            ],
        },
        {
            "id": "WBS-010-005",
            "sequence": 5,
            "title": "Record architecture decision with economic justification",
            "requirement_ids": ["RQ-ECO-001", "RQ-ECO-003", "RQ-ECO-004"],
            "design_refs": ["architecture_decision_record.md"],
            "validation_refs": ["planning_validation_report.json"],
            "relative_effort_points": 3,
            "relative_risk_points": 3,
            "economics_notes": [
                "Makes cost-risk tradeoff explicit.",
                "Keeps vendor/tool replacement economics visible.",
            ],
            "done_when": [
                "ADR selects one option.",
                "ADR explains consequences and no-certification posture.",
            ],
        },
        {
            "id": "WBS-010-006",
            "sequence": 6,
            "title": "Create module-level design with ports and adapters",
            "requirement_ids": [
                "RQ-FUN-004",
                "RQ-GOV-001",
                "RQ-ECO-004",
                "RQ-QUAL-001",
            ],
            "design_refs": ["module_design.md", "hld.md", "lld.md"],
            "validation_refs": ["planning_validation_report.json"],
            "relative_effort_points": 8,
            "relative_risk_points": 5,
            "economics_notes": [
                "Reduces switching cost and future refactoring cost.",
                "Keeps mock participants replaceable and safe.",
            ],
            "done_when": [
                "All external participants are mock adapters.",
                "Ports/adapters are named in module design.",
            ],
        },
        {
            "id": "WBS-010-007",
            "sequence": 7,
            "title": "Create HLD and LLD with quality and debugging details",
            "requirement_ids": ["RQ-QUAL-001", "RQ-GOV-001", "RQ-ECO-003"],
            "design_refs": ["hld.md", "lld.md"],
            "validation_refs": ["planning_validation_report.json"],
            "relative_effort_points": 8,
            "relative_risk_points": 4,
            "economics_notes": [
                "Early debug design reduces future maintenance cost.",
                "Quality attributes reduce incident and rework cost.",
            ],
            "done_when": [
                "HLD includes quality attributes.",
                "LLD includes failure modes and debug guide.",
            ],
        },
        {
            "id": "WBS-010-008",
            "sequence": 8,
            "title": "Build requirement-to-design-to-task traceability",
            "requirement_ids": ["RQ-GOV-001", "RQ-QUAL-001"],
            "design_refs": ["traceability_matrix.json"],
            "validation_refs": ["planning_validation_report.json"],
            "relative_effort_points": 5,
            "relative_risk_points": 4,
            "economics_notes": [
                "Reduces reviewer and audit navigation cost.",
                "Prevents orphan requirements and hidden scope creep.",
            ],
            "done_when": [
                "Every requirement maps to at least one design artifact.",
                "Every requirement maps to at least one WBS task.",
            ],
        },
        {
            "id": "WBS-010-009",
            "sequence": 9,
            "title": "Validate Phase 10 lifecycle planning readiness",
            "requirement_ids": [
                "RQ-GOV-001",
                "RQ-QUAL-001",
                "RQ-REG-001",
                "RQ-ECO-001",
                "RQ-ECO-002",
                "RQ-ECO-003",
                "RQ-ECO-004",
            ],
            "design_refs": ["planning_validation_report.json"],
            "validation_refs": ["scripts/validate_phase10_lifecycle_artifacts.py"],
            "relative_effort_points": 5,
            "relative_risk_points": 5,
            "economics_notes": [
                "Failing early is cheaper than generating code from weak planning.",
                "Validation gives a repeatable demo gate.",
            ],
            "done_when": [
                "Validator passes.",
                "Tests pass.",
                "No false certification claim exists.",
            ],
        },
    ]

    return {
        "artifact": "work_breakdown_structure.json",
        "phase": "Phase 10",
        "planning_model": "SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL",
        "task_order_rule": (
            "Design contracts and governance first, then domain and architecture, "
            "then module/HLD/LLD, then traceability and validation."
        ),
        "tasks": tasks,
    }


def _traceability(
    requirements_payload: dict[str, Any], wbs_payload: dict[str, Any]
) -> dict[str, Any]:
    tasks = wbs_payload["tasks"]
    rows: list[dict[str, Any]] = []

    for requirement in requirements_payload["requirements"]:
        req_id = str(requirement["id"])
        matched_tasks = [str(task["id"]) for task in tasks if req_id in task["requirement_ids"]]

        if requirement["type"] == "economics":
            economics_refs = [
                "requirements_analysis.json:economics_guidance",
                "domain_analysis.md:Economics",
                "architecture_options.md:Economics",
                "architecture_decision_record.md:Economic rationale",
            ]
        elif requirement["type"] == "regulatory_alignment":
            economics_refs = [
                "requirements_analysis.json:official_reference_candidates",
                "domain_analysis.md:Regulatory-alignment themes",
            ]
        else:
            economics_refs = [
                "architecture_options.md:Economics",
                "hld.md:Economics design",
            ]

        rows.append(
            {
                "requirement_id": req_id,
                "requirement_title": str(requirement["title"]),
                "requirement_type": str(requirement["type"]),
                "design_artifacts": [
                    "requirements_analysis.json",
                    "domain_analysis.md",
                    "architecture_options.md",
                    "architecture_decision_record.md",
                    "module_design.md",
                    "hld.md",
                    "lld.md",
                ],
                "wbs_task_ids": matched_tasks,
                "validation_refs": [
                    "planning_validation_report.json",
                    "tests/test_phase10_lifecycle_planner.py",
                ],
                "economics_refs": economics_refs,
                "honesty_labels": list(requirement["honesty_labels"]),
            }
        )

    return {
        "artifact": "traceability_matrix.json",
        "phase": "Phase 10",
        "traceability_rule": "Every requirement must map to design, WBS, validation, economics, and honesty labels.",
        "rows": rows,
    }


def generate_lifecycle_artifacts(
    output_dir: Path, app_id: str = "upi_dispute_resolution"
) -> list[Path]:
    """Generate all Phase 10 lifecycle artifacts.

    The output is deterministic and does not use wall-clock timestamps.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    requirements_payload = _requirements(app_id)
    wbs_payload = _wbs()
    traceability_payload = _traceability(requirements_payload, wbs_payload)

    files: dict[str, str | dict[str, Any]] = {
        "requirements_analysis.json": requirements_payload,
        "domain_analysis.md": _domain_analysis(app_id),
        "architecture_options.md": _architecture_options(app_id),
        "architecture_decision_record.md": _adr(app_id),
        "module_design.md": _module_design(app_id),
        "hld.md": _hld(app_id),
        "lld.md": _lld(app_id),
        "work_breakdown_structure.json": wbs_payload,
        "traceability_matrix.json": traceability_payload,
    }

    written: list[Path] = []
    for filename in REQUIRED_ARTIFACTS:
        if filename == "planning_validation_report.json":
            continue

        target = output_dir / filename
        payload = files[filename]
        if isinstance(payload, dict):
            _write_json(target, payload)
        else:
            _write_markdown(target, payload)
        written.append(target)

    validation_report = validate_lifecycle_artifacts(output_dir)
    report_path = output_dir / "planning_validation_report.json"
    _write_json(report_path, validation_report)
    written.append(report_path)

    return written


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path.name}: {exc}")
        return {}
    except FileNotFoundError:
        errors.append(f"Missing JSON artifact: {path.name}")
        return {}

    if not isinstance(loaded, dict):
        errors.append(f"JSON artifact must be an object: {path.name}")
        return {}

    return loaded


def validate_lifecycle_artifacts(output_dir: Path) -> dict[str, Any]:
    """Validate Phase 10 lifecycle artifacts and return a report."""

    errors: list[str] = []
    warnings: list[str] = []

    checked_files: list[str] = []
    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if not path.exists():
            errors.append(f"Missing required artifact: {filename}")
        else:
            checked_files.append(filename)

    req_payload = _load_json(output_dir / "requirements_analysis.json", errors)
    wbs_payload = _load_json(output_dir / "work_breakdown_structure.json", errors)
    trace_payload = _load_json(output_dir / "traceability_matrix.json", errors)

    text_cache: dict[str, str] = {}
    for filename in REQUIRED_ARTIFACTS:
        path = output_dir / filename
        if path.exists():
            text_cache[filename] = path.read_text(encoding="utf-8")

    combined_text = "\n".join(text_cache.values())

    missing_labels = [label for label in HONESTY_LABELS if label not in combined_text]
    for label in missing_labels:
        errors.append(f"Missing required honesty label in artifacts: {label}")

    # Architecture options are a critical planning artifact. They must carry
    # all honesty labels directly, not only rely on other files in the pack.
    architecture_text = text_cache.get("architecture_options.md", "")
    for label in HONESTY_LABELS:
        if label not in architecture_text:
            errors.append(f"Missing required honesty label in architecture_options.md: {label}")

    required_option_terms = (
        "Option A",
        "Option B",
        "Option C",
        "Pros",
        "Cons",
        "Economics",
        "Recommended selection",
    )
    architecture_text = text_cache.get("architecture_options.md", "")
    for term in required_option_terms:
        if term not in architecture_text:
            errors.append(f"architecture_options.md missing section/term: {term}")

    adr_text = text_cache.get("architecture_decision_record.md", "")
    if "Use a governed modular monolith with replaceable ports/adapters" not in adr_text:
        errors.append("ADR does not record the selected architecture clearly.")

    hld_text = text_cache.get("hld.md", "")
    for quality_term in ("Reliability", "Security", "Maintainability", "Auditability"):
        if quality_term not in hld_text:
            errors.append(f"hld.md missing quality term: {quality_term}")

    lld_text = text_cache.get("lld.md", "")
    for debug_term in ("Failure modes", "Debug guide", "Artifact contracts"):
        if debug_term not in lld_text:
            errors.append(f"lld.md missing design/debug term: {debug_term}")

    requirement_ids: set[str] = set()
    if req_payload:
        raw_reqs = req_payload.get("requirements", [])
        if not isinstance(raw_reqs, list) or not raw_reqs:
            errors.append("requirements_analysis.json must contain non-empty requirements list.")
        else:
            for req in raw_reqs:
                if not isinstance(req, dict):
                    errors.append("Each requirement must be an object.")
                    continue
                req_id = req.get("id")
                if not isinstance(req_id, str) or not req_id:
                    errors.append("Each requirement must have a non-empty string id.")
                    continue
                requirement_ids.add(req_id)
                if not req.get("acceptance_criteria"):
                    errors.append(f"Requirement missing acceptance criteria: {req_id}")
                if not req.get("honesty_labels"):
                    errors.append(f"Requirement missing honesty labels: {req_id}")

    task_ids: set[str] = set()
    task_req_ids: set[str] = set()
    if wbs_payload:
        raw_tasks = wbs_payload.get("tasks", [])
        if not isinstance(raw_tasks, list) or not raw_tasks:
            errors.append("work_breakdown_structure.json must contain non-empty tasks list.")
        else:
            previous_sequence = 0
            for task in raw_tasks:
                if not isinstance(task, dict):
                    errors.append("Each WBS task must be an object.")
                    continue
                task_id = task.get("id")
                sequence = task.get("sequence")
                if not isinstance(task_id, str) or not task_id:
                    errors.append("Each WBS task must have a non-empty string id.")
                    continue
                task_ids.add(task_id)
                if not isinstance(sequence, int):
                    errors.append(f"WBS task sequence must be an integer: {task_id}")
                elif sequence <= previous_sequence:
                    errors.append(f"WBS task sequence is not strictly increasing: {task_id}")
                else:
                    previous_sequence = sequence

                raw_task_reqs = task.get("requirement_ids", [])
                if not isinstance(raw_task_reqs, list) or not raw_task_reqs:
                    errors.append(f"WBS task must map to requirement_ids: {task_id}")
                else:
                    task_req_ids.update(str(req_id) for req_id in raw_task_reqs)

                if not task.get("economics_notes"):
                    errors.append(f"WBS task missing economics notes: {task_id}")

    trace_req_ids: set[str] = set()
    if trace_payload:
        raw_rows = trace_payload.get("rows", [])
        if not isinstance(raw_rows, list) or not raw_rows:
            errors.append("traceability_matrix.json must contain non-empty rows list.")
        else:
            for row in raw_rows:
                if not isinstance(row, dict):
                    errors.append("Each traceability row must be an object.")
                    continue
                req_id = row.get("requirement_id")
                if isinstance(req_id, str):
                    trace_req_ids.add(req_id)
                if not row.get("wbs_task_ids"):
                    errors.append(f"Traceability row missing WBS tasks: {req_id}")
                if not row.get("design_artifacts"):
                    errors.append(f"Traceability row missing design artifacts: {req_id}")
                if not row.get("economics_refs"):
                    errors.append(f"Traceability row missing economics refs: {req_id}")

    for req_id in sorted(requirement_ids):
        if req_id not in task_req_ids:
            errors.append(f"Requirement is not mapped to any WBS task: {req_id}")
        if req_id not in trace_req_ids:
            errors.append(f"Requirement is not mapped in traceability matrix: {req_id}")

    forbidden_claims = (
        "RBI certified",
        "NPCI certified",
        "officially certified",
        "guaranteed compliant",
        "100% compliant",
    )
    lower_combined = combined_text.lower()
    for claim in forbidden_claims:
        if claim.lower() in lower_combined:
            errors.append(f"Forbidden false compliance/certification claim found: {claim}")

    if "MISSING_OFFICIAL_SOURCE" in combined_text:
        warnings.append(
            "Official-source gaps are intentionally labelled. Replace with parsed "
            "official evidence only when a source is available and verified."
        )

    return {
        "artifact": "planning_validation_report.json",
        "phase": "Phase 10",
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_artifacts": checked_files,
        "checked_honesty_labels": list(HONESTY_LABELS),
        "checked_traceability": {
            "requirements_seen": sorted(requirement_ids),
            "tasks_seen": sorted(task_ids),
            "traceability_rows_seen": sorted(trace_req_ids),
        },
    }
