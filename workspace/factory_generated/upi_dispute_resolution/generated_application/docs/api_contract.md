# API Contract

- GET /health
- GET /startup
- GET /live
- GET /ready
- GET /metrics
- POST /disputes
- GET /disputes
- GET /disputes/{dispute_id}
- POST /v1/disputes
- GET /v1/disputes
- GET /v1/disputes/{dispute_id}
- GET /v1/disputes/{dispute_id}/history
- POST /v1/disputes/{dispute_id}/evidence
- POST /v1/disputes/{dispute_id}/investigate
- POST /v1/disputes/{dispute_id}/classify
- POST /v1/disputes/{dispute_id}/human-review
- POST /v1/disputes/{dispute_id}/review-decisions
- POST /v1/disputes/{dispute_id}/disposition
- POST /v1/disputes/{dispute_id}/close
- POST /v1/disputes/{dispute_id}/quarantine
- GET /v1/disputes/{dispute_id}/audit-integrity
- POST /drain
- GET /runtime/diagnostics

Protected operations require a signed local bearer token or an explicitly
enabled local header-principal test profile. This is a local mock/simulated API
contract and makes no certification, regulatory approval, deployment, production
readiness, live identity-provider, or live payment operation claim.

The versioned `/v1/disputes` surface is the authoritative failed-debit runtime
workflow used for deterministic case intake, search by transaction reference,
required-evidence progression, local-only investigation, deterministic
classification, explicit human-review initiation and durable decisions,
governed disposition, audit-integrity verification, quarantine, closure, and
history queries. Deprecated compatibility aliases remain available for the old
`/investigation`, `/resolution`, and `/timeline` paths but are not the
authoritative contract.
