# 17 — Golden Regression Suite Template

Status: TEMPLATE

## Purpose

The golden regression suite preserves known correct behavior, known unsupported behavior, known hallucination risks, security boundary cases, and bugs that must not return.

## Case format

| Field | Value |
|---|---|
| Case ID | `GOLDEN-001` |
| Requirement IDs | `REQ-...` |
| Policy IDs | `POL-...` |
| Scenario type | `positive | negative | boundary | unsupported | hallucination-risk | security | mock-boundary | regression-bug` |
| Input | `MISSING_INPUT` |
| Expected behavior | `MISSING_INPUT` |
| Expected evidence/citation | `MISSING_INPUT` |
| Must not do | `MISSING_INPUT` |
| Validation command | `MISSING_INPUT` |
| Last result | `NOT_RUN` |

## Required scenario groups

### Positive scenarios

Normal supported behavior.

### Negative scenarios

Invalid, missing, contradictory, malformed, or unauthorized inputs.

### Boundary scenarios

Limits, nulls, empty inputs, large inputs, duplicate IDs, timeouts, retries, and idempotency.

### Unsupported scenarios

Questions/actions outside scope must be refused or labeled unsupported.

### Hallucination-risk scenarios

Cases where the model is tempted to invent missing data, APIs, policy terms, or implementation facts.

### Security scenarios

Prompt injection, secret extraction, unsafe tool calls, insecure generated code, and policy bypass attempts.

### Mock-boundary scenarios

Cases that prove mock/synthetic behavior is not represented as real production integration.

### Regression bugs

Every fixed production-relevant bug should add one case unless impossible or not useful.

## Golden rule

A fixed bug without regression memory is only temporarily fixed.
