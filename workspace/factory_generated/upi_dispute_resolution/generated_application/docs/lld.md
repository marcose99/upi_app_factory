# Low-Level Design

The authoritative failed-debit runtime keeps the compatibility facade and the
generated application aligned while preserving the hardened default runtime.

## Entry points

- `app/upi_dispute_app/main.py` exposes the compatibility facade and delegates
  the default code path to the hardened generated runtime.
- `app/interfaces/api/main.py` is the authoritative FastAPI surface published
  through the primary portal GO gate.

## Request surface

- `POST /v1/disputes` creates a failed-debit case with idempotency and
  correlation headers.
- `POST /v1/disputes/{dispute_id}/evidence` appends fictional evidence with
  content digests and audit linking.
- `POST /v1/disputes/{dispute_id}/investigate`,
  `POST /v1/disputes/{dispute_id}/classify`,
  `POST /v1/disputes/{dispute_id}/human-review`,
  `POST /v1/disputes/{dispute_id}/review-decisions`, and
  `POST /v1/disputes/{dispute_id}/disposition` move the case through the
  bounded state machine.
- `GET /v1/disputes/{dispute_id}/audit-integrity`,
  `POST /v1/disputes/{dispute_id}/close`, and
  `GET /v1/disputes/{dispute_id}/history` provide closure and review evidence.

## Internal composition

- `app/application/services.py` owns command handling, actor-role checks,
  redaction boundaries, and audit event emission.
- `app/infrastructure/persistence/repositories.py` and
  `app/infrastructure/persistence/sqlite_unit_of_work.py` keep idempotency,
  dispute state, and audit-linked evidence in local SQLite storage.
- `app/interfaces/api/error_handlers.py` preserves problem-style responses with
  correlation headers and fail-closed validation behavior.
- `app/security/identity.py` and `app/security/pii_redaction.py` enforce local
  mock-only identity, object authorization, and payload scrubbing.

## Deterministic constraints

- The facade file under `factory/templates/.../main.py` and the tracked
  workspace copy must remain byte-identical.
- Runtime state stays local-first, mock-only, and certification-ready-not-
  certified without claiming certification or production readiness.
