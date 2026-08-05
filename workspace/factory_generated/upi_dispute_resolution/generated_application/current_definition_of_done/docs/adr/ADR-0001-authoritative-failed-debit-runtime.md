# ADR-0001: Authoritative Failed-Debit Runtime

## Status

Accepted

## Context

The exact v2 requirement package binds the canonical application identity
`upi_failed_debit_no_credit`, while the repository still tracks the generated
runtime under the governed compatibility identifier `upi_dispute_resolution`.
Traceability therefore has to preserve both identifiers without overclaiming
full exact-v2 support.

## Decision

Use a deterministic exact-input atomic obligation inventory as the source for
truthful traceability. Keep the authoritative failed-debit runtime as the
published implementation surface, keep compatibility mapping explicit in the
generated evidence, and derive GO or NO_GO from actual supported, partial, and
unsupported mandatory obligations.

## Consequences

- The canonical and compatibility identifiers are both recorded.
- Exact-input obligation coverage is computed rather than hard-coded.
- Any partial or unsupported mandatory obligation yields a governed NO_GO.
- Evidence references are verified before they are emitted.
