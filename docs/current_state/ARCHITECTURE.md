# Current Architecture

> **Status:** Canonical current-state documentation
> **Purpose:** Describe the current factory and engineered-application architecture using stakeholder-oriented views derived from executable truth.
> **Audience:** architects, principal engineers, developers, security reviewers, SRE/operators, testers and recipients
> **Authority:** implementation, tests, runtime/configuration contracts, generated artifacts and governed evidence at the checked-out revision. This document does not override executable behavior.

## Standards and practice alignment

- ISO/IEC/IEEE 42010:2022; C4/arc42 pragmatic modeling practices
- ISO/IEC 25010:2023
- NIST SP 800-218 SSDF 1.1; OWASP ASVS 5.0.0 verification reference

Alignment is an engineering documentation practice, **not** a claim of certification, formal conformity assessment, production approval, or regulatory approval.


## Architectural goals and constraints

- Lightweight and local-first; no Kubernetes requirement.
- Deterministic/mock-safe acceptance route.
- Explicit human approval at protected engineering/release boundaries.
- Every `CURRENT_AND_VERIFIED` generated application profile is independently reproducible from its source bundle and owned locks/contracts.
- External payment/provider behavior is mocked or disabled in accepted default operation.
- Architecture documentation distinguishes current executable product code from tests, tooling and historical workspace copies.
- API documentation uses the semantically normalized **123** authoritative unique route keys rather than the raw AST count of 312.

## View 1 — system context

```mermaid
flowchart LR
    Operator["Operator / Reviewer / Recipient"]
    Factory["UPI App Factory"]
    Generated["Current Reference Generated Application<br/>upi_dispute_resolution"]
    GitHub["Git + GitHub / Governed CI"]
    MockUPI["Mock payment / banking ecosystem"]
    LLM["Optional LLM provider boundary<br/>disabled by default"]
    Operator -->|"requirements, approvals, operations"| Factory
    Factory -->|"engineers, validates, publishes"| Generated
    Factory -->|"source, PRs, evidence, CI"| GitHub
    Generated -->|"mock-only integration calls"| MockUPI
    Factory -.->|"policy-gated; default off"| LLM
```

## View 2 — factory containers / major subsystems

```mermaid
flowchart TB
    UI["Operator Portal / HTTP API"]
    Intake["Requirements Intake & Validation"]
    Plan["Planning & Human Approval"]
    Engineer["Application Engineering / Materialization"]
    Validate["Validators, Tests & Acceptance"]
    Evidence["Evidence / Provenance / Downloads"]
    Portfolio["Portfolio & Runtime Supervisor"]
    State["Local .var State"]
    Gen["Generated Application Bundle"]
    UI --> Intake --> Plan --> Engineer --> Validate
    Validate -->|"GO"| Gen
    Engineer --> Evidence
    Validate --> Evidence
    UI --> Portfolio --> Gen
    UI --> State
    Portfolio --> State
    Evidence --> State
```

## View 3 — current reference generated application structure

```mermaid
flowchart TB
    API["Interfaces / FastAPI"]
    Application["Application Services / Use Cases"]
    Domain["Domain Model / Policies"]
    Infra["Infrastructure / Persistence / Adapters"]
    Tests["Generated Tests"]
    Locks["Owned Bootstrap + Runtime/Test Locks"]
    Contract["Dependency Contract + Validator"]
    API --> Application --> Domain
    Application --> Infra
    Tests --> API
    Tests --> Application
    Locks --> Contract
    Contract --> API
```

Current reference generated application (`upi_dispute_resolution`) layer evidence: `{"application": 5, "control_plane": 1, "disputes": 4, "domain": 5, "infrastructure": 9, "interfaces": 3, "observability": 3, "runtime.py": 1, "security": 3, "tests": 14, "upi_dispute_app": 15}`.

## View 4 — governed application engineering flow

```mermaid
sequenceDiagram
    actor Operator
    participant Portal as Operator Portal
    participant Intake as Intake/Validation
    participant Plan as Planning/Governance
    participant Eng as Application Engineering
    participant QA as Validation/Tests
    participant Evidence as Evidence/Provenance
    participant Runtime as Portfolio/Runtime
    Operator->>Portal: Submit requirements
    Portal->>Intake: Validate bounded input
    Intake-->>Operator: Clarifications / accepted requirement set
    Operator->>Plan: Request plan
    Plan-->>Operator: Plan + protected approval
    Operator->>Eng: Explicit approval
    Eng->>QA: Materialize candidate + run validation
    QA-->>Eng: PASS or bounded diagnostic feedback
    QA->>Evidence: Store traceability/evidence
    Eng->>Runtime: Publish accepted local version
    Runtime-->>Operator: Health/scenario/evidence surfaces
```

## View 5 — deployment topology

```mermaid
flowchart LR
    Browser["Local browser/client"]
    Native["Native Linux recipient route<br/>run_factory.sh + .venv"]
    DockerHost["Host loopback"]
    Container["Docker factory-portal<br/>read-only root FS, non-root UID/GID"]
    Volume["Named .var volume"]
    Health["/health"]
    GeneratedRuntime["Generated runtime child process"]
    Browser -->|"127.0.0.1 / localhost"| Native
    Browser --> DockerHost --> Container
    Container --> Volume
    Native --> Health
    Container --> Health
    Native --> GeneratedRuntime
    Container --> GeneratedRuntime
```

The Docker route is a container portability route. **Do not use this route as evidence of native Windows or native macOS support.**

## View 6 — security and trust boundaries

```mermaid
flowchart LR
    User["Local operator"]
    Factory["Factory process"]
    Env["Child environment builder"]
    Child["Generated runtime"]
    Mock["Mock integrations"]
    External["Live provider/payment boundary<br/>not enabled by default"]
    User -->|"loopback HTTP + protected mutations"| Factory
    Factory -->|"parent environment"| Env
    Env -->|"credential-like keys stripped;<br/>safety flags reasserted"| Child
    Child --> Mock
    Child -.->|"prohibited/default-off"| External
```

## View 7 — evidence and provenance flow

```mermaid
flowchart LR
    Req["Requirements / run identity"]
    Plan["Plan + approval"]
    Source["Engineered source"]
    Tests["Tests / validators / OpenAPI"]
    Runtime["Runtime scenarios"]
    Evidence["Evidence manifests + logs + metrics"]
    Git["Commit / tree / CI identity"]
    Handover["Recipient handover bundle"]
    Req --> Plan --> Source --> Tests --> Runtime --> Evidence
    Source --> Git
    Tests --> Git
    Evidence --> Handover
    Git --> Handover
```

## View 8 — failure and recovery state model

```mermaid
stateDiagram-v2
    [*] --> Intake
    Intake --> Clarification: invalid / ambiguous
    Clarification --> Intake: corrected input
    Intake --> Planned: valid
    Planned --> Approved: explicit human approval
    Approved --> Engineering
    Engineering --> Validation
    Validation --> Repair: bounded repairable defect
    Repair --> Validation
    Validation --> Blocked: out-of-scope / unsafe / repeated failure
    Validation --> Accepted: all required gates pass
    Accepted --> Published
    Published --> Runtime
    Runtime --> Recovery: health/runtime failure
    Recovery --> Runtime: restored
    Blocked --> [*]
```

## Key source-truth references

- The native recipient launcher refuses non-loopback host values. — `run_factory.sh`:66
- The native recipient launcher explicitly disables real payment calls. — `run_factory.sh`:186
- The native recipient launcher explicitly disables factory LLM execution by default. — `run_factory.sh`:187
- The Docker factory-portal service runs with a read-only root filesystem. — `compose.yaml`:8
- Docker publishes the factory portal on loopback only. — `compose.yaml`:25
- Docker publishes the factory portal on loopback only. — `compose.yaml`:32
- Docker defines an explicit healthcheck against the factory health endpoint. — `compose.yaml`:28
- Docker explicitly disables real payment calls. — `compose.yaml`:20
- Docker explicitly disables real payment calls. — `compose.yaml`:21
- Docker explicitly disables factory LLM execution. — `compose.yaml`:18
- Docker explicitly disables factory LLM execution. — `compose.yaml`:19
- Generated runtime process environments are constructed by a dedicated boundary function. — `factory/application_engineering/portfolio.py`:118
- Generated runtime environment handling explicitly controls real-payment safety state. — `factory/application_engineering/portfolio.py`:132

## Architectural decisions and trade-offs

- **Local-first over platform complexity:** keeps the factory lightweight and reproducible; production orchestration is deliberately not claimed.
- **Exact dependency closure over permissive floating installs:** reduces recipient drift at the cost of deliberate lock maintenance.
- **Human approval over unconstrained autonomy:** protected actions require explicit governance rather than silent agent escalation.
- **Generated source bundle over opaque binary packaging:** favors inspectability and clean-room reproducibility.
- **Mock/provider boundaries over live external calls during acceptance:** preserves safety and determinism.
- **Git/evidence identity over narrative status claims:** acceptance is tied to exact artifacts and executable checks.

Historical ADRs remain evidence of how the architecture evolved; they do not override this current-state view.
