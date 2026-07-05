# Phase 11 Entry Criteria — upi_dispute_resolution

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
