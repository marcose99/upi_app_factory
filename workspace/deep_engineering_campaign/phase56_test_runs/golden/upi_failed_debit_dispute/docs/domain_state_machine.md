# Domain State Machine

States: received, validated, evidence_pending, investigation, resolution_proposed, resolved, rejected, closed

- GET /health
- GET /ready
- GET /metrics
- POST /v1/disputes
- GET /v1/disputes/{dispute_id}
- GET /v1/disputes
- POST /v1/disputes/{dispute_id}/evidence
- POST /v1/disputes/{dispute_id}/validation
- POST /v1/disputes/{dispute_id}/investigation
- POST /v1/disputes/{dispute_id}/resolution
- POST /v1/disputes/{dispute_id}/closure
- GET /v1/disputes/{dispute_id}/timeline
- GET /v1/disputes/{dispute_id}/audit
