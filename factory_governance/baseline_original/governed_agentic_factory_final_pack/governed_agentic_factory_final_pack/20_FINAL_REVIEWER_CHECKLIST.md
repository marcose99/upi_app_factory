# 20 — Final Reviewer Checklist

Status: FINAL BASELINE v1.0

Use this before accepting a generated project, regeneration run, release candidate, or demo package.

## 1. Business and domain

- [ ] Requirements are clear and testable.
- [ ] Domain terms are defined.
- [ ] Workflows and state transitions are documented.
- [ ] Edge cases are covered.
- [ ] Out-of-scope behavior is explicit.

## 2. Architecture

- [ ] Multiple options were considered where meaningful.
- [ ] Selected option has clear trade-off reasoning.
- [ ] Diagrams exist and are understandable.
- [ ] Failure handling is designed.
- [ ] Audit and observability are part of architecture.
- [ ] Future extension points are clear.

## 3. Design

- [ ] HLD exists.
- [ ] LLD exists for implemented modules.
- [ ] Module/API/data contracts are clear.
- [ ] Error taxonomy exists.
- [ ] Retry/idempotency rules are documented where applicable.
- [ ] Security controls are designed.

## 4. Implementation

- [ ] Code maps to requirements and design.
- [ ] Changes are cohesive and minimal.
- [ ] No unrelated edits.
- [ ] No hidden hardcoding.
- [ ] No disabled governance or tests.
- [ ] Dependencies are justified.

## 5. Testing

- [ ] Unit tests exist.
- [ ] Contract tests exist where applicable.
- [ ] Integration or mock integration tests exist.
- [ ] Negative/boundary tests exist.
- [ ] Golden regression cases exist.
- [ ] Known bugs have regression protection.

## 6. Security

- [ ] Prompt injection controls exist where LLM/RAG is used.
- [ ] Tool use is bounded.
- [ ] Secrets are protected.
- [ ] Sensitive data handling is documented.
- [ ] Dependency/supply-chain risks are reviewed.
- [ ] High/critical findings are fixed or formally accepted.

## 7. Governance and audit

- [ ] Policies are explicit.
- [ ] Risk tiers are applied.
- [ ] Approvals are recorded where required.
- [ ] Artifact manifest exists.
- [ ] Audit events exist.
- [ ] Evidence ledger exists.

## 8. Observability and operations

- [ ] Structured logs exist.
- [ ] Correlation/trace IDs exist.
- [ ] Health/readiness checks exist where applicable.
- [ ] Run/reproduce instructions exist.
- [ ] Rollback guidance exists.
- [ ] Debug playbook is usable.

## 9. Honesty of claims

- [ ] Mock/synthetic areas are clearly labeled.
- [ ] Production readiness is not claimed without production evidence.
- [ ] Compliance is not claimed without compliance mapping and review.
- [ ] Security is not claimed without security evidence.
- [ ] Unknowns are listed.

## 10. Final recommendation

Choose one:

- `ACCEPT`
- `ACCEPT_WITH_LIMITATIONS`
- `REPAIR_REQUIRED`
- `REJECT`
- `BLOCKED`

Rationale:

```text
MISSING_INPUT
```
