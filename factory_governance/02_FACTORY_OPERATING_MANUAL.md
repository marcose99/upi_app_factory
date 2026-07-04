# 02 — Factory Operating Manual

Status: FINAL BASELINE v1.0

## 1. Operating philosophy

A governed agentic software factory is not a chatbot that writes files. It is a controlled engineering system where agents operate inside a policy-governed lifecycle.

The correct control flow is:

```text
Requirement intake
  -> Evidence and policy grounding
  -> Architecture options and decision
  -> High-level and low-level design
  -> Work breakdown
  -> Agent execution
  -> Deterministic file application
  -> Validation gates
  -> Review council
  -> Debug/repair loop if needed
  -> Release evidence pack
```

## 2. Required repositories/folders

```text
factory_governance/
requirements/
evidence/
architecture/
design/
task_manifests/
agent_runs/
validation_reports/
audit/
debug_cases/
release_evidence/
generated_artifacts/
mock_ecosystem/
golden_regression_suite/
```

## 3. Required identifiers

Every serious run must use:

- `run_id`
- `task_id`
- `agent_id`
- `artifact_id`
- `requirement_id`
- `policy_id`
- `source_id`
- `approval_id`
- `validation_id`
- `debug_case_id` when applicable
- `input_hash`
- `output_hash`

## 4. Requirement intake

Every requirement must include:

- Requirement ID
- Source
- Business purpose
- Functional behavior
- Non-functional behavior
- Data involved
- Actors involved
- Preconditions
- Postconditions
- Acceptance criteria
- Out-of-scope conditions
- Risk tier
- Approval requirement
- Testability

Requirements that cannot be tested must be refined before implementation.

## 5. Evidence and policy grounding

Before architecture or coding, collect:

- Business rules
- Regulatory references
- Domain rules
- API contracts
- Data dictionaries
- Mock boundaries
- Architecture standards
- Security standards
- Approved assumptions
- Explicit no-go areas

Every policy must define:

- Policy ID
- Rule
- Rationale
- Enforcement point
- Validation method
- Failure behavior
- Evidence required
- Approval condition

Default policy behavior: fail closed.

## 6. Architecture phase

The Architect Agent should produce multiple options for non-trivial systems:

- Option A: simplest safe architecture
- Option B: modular scalable architecture
- Option C: future-ready extensible architecture

Each option must be reviewed for:

- Business fit
- Security
- Compliance/gov controls
- Maintainability
- Testability
- Debuggability
- Observability
- Operational complexity
- Cost/latency
- Regeneration friendliness

Required architecture artifacts:

- Context diagram
- Container/component diagram
- Agent orchestration diagram
- Sequence diagram for key flow
- Failure/repair loop diagram
- Data lineage diagram
- Audit/evidence flow diagram
- Architecture Decision Records

## 7. Design phase

Required design output:

- High-level design
- Low-level design
- Module contracts
- API contracts
- Data model
- State model
- Error taxonomy
- Retry/idempotency rules
- Security controls
- Audit event design
- Observability design
- Test strategy
- Operational runbook hooks

No coding task should be created without a linked design section.

## 8. Work breakdown phase

Task ordering should normally be:

1. Contracts
2. Policies
3. Data models
4. Deterministic validators
5. Mock ecosystem
6. Core implementation
7. Tests
8. Observability
9. Documentation
10. Release evidence
11. Demo narrative

Each task must have:

- Task ID
- Requirement IDs
- Policy IDs
- Design references
- Files expected to change
- Tests expected
- Validation commands
- Rollback guidance
- Risk tier
- Approval requirement
- Definition of done

## 9. Implementation phase

Coding agents must:

- Read linked requirements, policies, and design before changing files.
- Make small cohesive changes.
- Avoid unrelated edits.
- Add or update tests.
- Avoid hardcoded behavior unless explicitly specified as deterministic rule logic.
- Never weaken validation to pass.
- Never disable audit, safety, or security gates to pass.
- Capture changed files, rationale, tests, risks, and validation status.

## 10. Validation phase

Run gates in this order unless project-specific policy overrides:

1. Formatting
2. Static analysis
3. Type checks
4. Unit tests
5. Contract tests
6. Integration tests
7. Negative tests
8. Security checks
9. Policy checks
10. Mock boundary checks
11. Regression tests
12. Evidence completeness checks
13. Release readiness checks

## 11. Review phase

Reviewer Council roles:

- Business reviewer
- Domain reviewer
- Architecture reviewer
- Security reviewer
- Testing reviewer
- Operations reviewer
- Governance/audit reviewer
- Maintainability reviewer
- Human-understandability reviewer

Findings:

- `BLOCKER`
- `HIGH`
- `MEDIUM`
- `LOW`
- `OBSERVATION`

No release readiness claim is allowed with open blockers.

## 12. Release phase

The release evidence pack must include:

- What was built
- What was not built
- What is mocked/synthetic
- What was validated
- What failed
- What remains unknown
- How to reproduce
- How to regenerate
- How to debug
- How to rollback
- Evidence links
- Test summary
- Risk summary
- Approval summary
- Known limitations

## 13. Operating modes

Use the smallest safe mode:

| Mode | Use case | Required rigor |
|---|---|---|
| `FAST_SAFE` | local doc/code clarification, no mutation or low-risk patch | basic evidence and validation |
| `GOVERNED_BUILD` | normal serious factory work | full requirement-policy-task-test traceability |
| `PRODUCTION_CONTROLLED` | release, compliance, customer data, external integrations | full approval, validation, evidence, audit, rollback |

## 14. Stop conditions

Stop or escalate when:

- Required input is missing for a high-risk decision.
- Policy and requirement conflict.
- Validation fails and root cause is unknown.
- A tool would perform a risky action without approval.
- Evidence is insufficient for a compliance/production/security claim.
- The model or agent is asked to override safety/governance rules.
