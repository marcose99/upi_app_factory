# 18 — Human Approval Policy

Status: FINAL BASELINE v1.0

## 1. Purpose

Human approval ensures that risky, sensitive, irreversible, external, compliance-relevant, financial, legal, or production-impacting actions remain accountable.

## 2. Approval required

Approval is required for:

- R4 and R5 actions.
- Conditional R3 actions involving private, sensitive, paid, rate-limited, or customer-related systems.
- Production deployment.
- Real customer/user data processing.
- Financial movement or financial-state mutation.
- Legal/compliance/security claims.
- Disabling or weakening tests, audit, governance, policy, or security gates.
- Deleting files, history, evidence, or audit logs.
- External mutation such as sending emails, writing tickets, updating cloud resources, or calling production APIs.
- Irreversible/destructive commands.

## 3. Approval record

Every approval must include:

- `approval_id`
- Requesting actor
- Action requested
- Risk tier
- Scope
- Evidence reviewed
- Validation status
- Rollback/recovery plan
- Approver name/role
- Decision
- Timestamp UTC
- Expiry/validity window
- Conditions or limitations

## 4. Approval decisions

Allowed decisions:

- `APPROVED`
- `DENIED`
- `APPROVED_WITH_LIMITATIONS`
- `NEEDS_MORE_EVIDENCE`
- `EXPIRED`

## 5. Approval cannot override everything

Human approval cannot authorize hidden evidence deletion, audit tampering, illegal action, credential exposure, or a compliance claim without evidence.

## 6. Emergency handling

If urgent action is needed:

1. Prefer read-only diagnosis.
2. Capture current state.
3. Get explicit approval before mutation.
4. Make the smallest reversible change.
5. Preserve evidence.
6. Validate after action.
7. Create post-incident review.
