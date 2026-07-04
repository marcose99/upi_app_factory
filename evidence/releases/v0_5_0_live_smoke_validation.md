# v0.5.0 Live Smoke Validation

Status: PASSED

Validated on: 2026-07-04T13:07:31Z

Evidence labels:

- MISSING_OFFICIAL_SOURCE
- SYNTHETIC_ENTERPRISE_WORKFLOW_MODEL
- MOCK_BOUNDARY
- SYNTHETIC_DATA

## Scope

This validation confirms the live local API behavior after tag `v0.5.0-combined-mock-dispute-app`.

## Confirmed

- `/health` returned `status=ok`.
- `/ready` returned `status=ready`.
- `/ready` confirmed `real_payment_calls=disabled`.
- Synthetic failed transaction listing returned at least one event.
- A dispute case was created or idempotently returned from a synthetic failed transaction.
- The returned case contained required evidence labels.
- Mock evidence observations were attached.
- A reviewer action moved or kept the case in `IN_REVIEW`.
- The reviewer action generated an additional audit event identifier.
- Required evidence labels remained present after the reviewer action.

## Idempotency Note

The live API stores dispute cases in process memory. If the same running server has already executed a smoke test for the same synthetic transaction, `POST /disputes/cases/from-failed-transaction` may return an already-created case instead of a fresh `EVIDENCE_PENDING` case.

Observed idempotency mode:

```text
pre_existing_case_returned
```

Initial returned status:

```text
IN_REVIEW
```

## Smoke Test Details

Selected synthetic transaction:

```text
SYN-UPI-TXN-0001
```

Case:

```text
CASE-ccf1363e9ea9
```

Final status:

```text
IN_REVIEW
```

Audit event count before reviewer action:

```text
2
```

Audit event count after reviewer action:

```text
3
```

## Boundary Confirmation

No real UPI, NPCI, RBI, bank, PSP, switch, settlement, or customer notification system was called.

All external dependencies remain mock boundaries and all business data remains synthetic.
