# 01 — Project Charter Template

Status: TEMPLATE  
Fill this before serious implementation or regeneration.

## 1. Project identity

- Project name: `MISSING_INPUT`
- Repository: `MISSING_INPUT`
- Business domain: `MISSING_INPUT`
- Application purpose: `MISSING_INPUT`
- Primary users: `MISSING_INPUT`
- System owner: `MISSING_INPUT`
- Technical owner: `MISSING_INPUT`
- Risk owner: `MISSING_INPUT`
- Data owner: `MISSING_INPUT`

## 2. Target maturity

Select one:

- `L0_CONCEPT`
- `L1_LOCAL_DEMO`
- `L2_GOVERNED_DEMO`
- `L3_REPEATABLE_REGENERATION`
- `L4_PRE_PRODUCTION_CANDIDATE`
- `L5_PRODUCTION_CANDIDATE`
- `L6_AUDITED_PRODUCTION_OPERATION`

Target maturity: `MISSING_INPUT`

## 3. Domain boundaries

### In scope

- `MISSING_INPUT`

### Out of scope

- `MISSING_INPUT`

### Mock/synthetic-only boundaries

- `MISSING_INPUT`

### Real-world integrations allowed?

- Default: `NO`
- Allowed integrations: `MISSING_INPUT`
- Approval required: `YES`

## 4. Approved stack

- Language/runtime: `MISSING_INPUT`
- Frameworks: `MISSING_INPUT`
- Database/storage: `MISSING_INPUT`
- Messaging/eventing: `MISSING_INPUT`
- LLM/model providers: `MISSING_INPUT`
- Agent/orchestration framework: `MISSING_INPUT`
- CI/CD: `MISSING_INPUT`
- Observability: `MISSING_INPUT`

## 5. Approved tools

| Tool | Purpose | Read-only or mutating | Approval tier | Notes |
|---|---|---:|---:|---|
| `MISSING_INPUT` | `MISSING_INPUT` | `MISSING_INPUT` | `MISSING_INPUT` | `MISSING_INPUT` |

## 6. Disallowed actions

- Access real customer data without explicit approval.
- Call production systems without explicit approval.
- Move money, alter financial state, or trigger external actions without explicit approval.
- Delete evidence or audit trails.
- Disable validation gates to pass.
- Hardcode expected answers unless the requirement is explicitly deterministic rule logic.
- Claim compliance, production readiness, or security certification without evidence.

## 7. Evidence sources

| Source ID | Source name | Type | Owner | Version/date | Trust level | Notes |
|---|---|---|---|---|---|---|
| `SRC-001` | `MISSING_INPUT` | `MISSING_INPUT` | `MISSING_INPUT` | `MISSING_INPUT` | `MISSING_INPUT` | `MISSING_INPUT` |

## 8. Quality gates

- Formatting: `MISSING_INPUT`
- Static analysis: `MISSING_INPUT`
- Type checks: `MISSING_INPUT`
- Unit tests: `MISSING_INPUT`
- Contract tests: `MISSING_INPUT`
- Integration tests: `MISSING_INPUT`
- Security checks: `MISSING_INPUT`
- Policy checks: `MISSING_INPUT`
- Regression tests: `MISSING_INPUT`
- Release evidence checks: `MISSING_INPUT`

## 9. Human approval policy

- Risk tier requiring human approval: `R3` and above by default.
- Production/customer/financial/legal/security-impacting action: approval required.
- Evidence deletion: blocked unless approved by system owner and risk owner.

## 10. Definition of done

A task is done only when:

- Requirements are linked.
- Policies are linked.
- Design is linked.
- Tests are added or explicitly justified as not applicable.
- Validation commands are executed and recorded.
- Evidence is captured.
- Risks and limitations are documented.
- No open blocker remains.
