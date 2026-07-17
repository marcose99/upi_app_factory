# Phase 54 Local Platform Kernel Architecture

Phase 54 adds a reusable, domain-independent local platform kernel under the
current application-engineering compatibility path:
`factory/application_engineering/local_platform_kernel.py`.

## Decisions

- Use Python 3.10 standard-library primitives only.
- Use `sqlite3` directly, with explicit transactions, foreign keys, ordered
  migrations, a migration ledger, and `PRAGMA integrity_check`.
- Keep real payment/provider calls disabled and default runtime LLM calls at
  zero.
- Model local principals through a fictional authorization adapter that is
  suitable for tests and local generated applications only.
- Keep evidence deterministic through canonical JSON hashing and file hashes.

## Kernel Capabilities

- Typed IDs, `Money`, clocks, and deterministic ID generation.
- Command/query base contracts.
- Repository and unit-of-work ports.
- SQLite connection factory, unit of work, migration ledger, rollback, foreign
  keys, integrity checks, and optimistic concurrency.
- Idempotency request/result replay records.
- Append-only hash-chained audit log with tamper verification.
- Transactional local outbox.
- In-memory repository adapter for tests.
- JSON logging with key-based redaction and correlation context.
- Local metrics registry with deterministic text exposition.
- Health/readiness contributor registry.
- Secret-free local configuration checks.
- Problem response contract.
- Fictional local principal and authorization port.
- Deterministic evidence and packaging helpers.

## Architecture Rules

- The kernel must remain in the compatibility application-engineering path.
- Runtime persistence must use standard-library `sqlite3`; no ORM is allowed.
- PostgreSQL, MySQL, Redis, Kafka, RabbitMQ, Elasticsearch, Kubernetes,
  Terraform, Docker, Node, or mandatory external platform dependencies must not
  be introduced for this kernel.
- Human-readable text uses application engineering terminology.
- No certification, production-readiness, or formal-conformance claim is made.
