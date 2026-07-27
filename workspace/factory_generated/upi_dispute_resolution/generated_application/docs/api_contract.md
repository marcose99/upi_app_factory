# API Contract

- GET /health
- GET /startup
- GET /live
- GET /ready
- GET /metrics
- POST /disputes
- GET /disputes
- GET /disputes/{dispute_id}
- POST /drain
- GET /runtime/diagnostics

Protected operations require a signed local bearer token or an explicitly
enabled local header-principal test profile. This is a local mock/simulated API
contract and makes no certification, regulatory approval, deployment, production
readiness, live identity-provider, or live payment operation claim.
