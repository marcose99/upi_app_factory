# Local-First to Production Infrastructure Migration Plan — upi_dispute_resolution

Labels: LOCAL_FIRST_LIGHTWEIGHT_RUNTIME, PRODUCTION_MIGRATION_READY,
VERSION_SPECIFIC_REVIEW_REQUIRED

Default local stack must stay lightweight. The design must define migration
seams so each local component can later be replaced independently.

Recommended local-first defaults:

- FastAPI or Python CLI for service boundary
- Pydantic models for contracts
- in-memory or SQLite state for local runs
- filesystem evidence store
- mock adapters for ecosystem dependencies
- standard logging and lightweight metrics files

Migration seams to document:

- SQLite to PostgreSQL
- filesystem evidence store to object storage
- in-process queue to Kafka-compatible messaging
- local scheduler to durable workflow engine
- simple metrics/log files to OpenTelemetry-compatible telemetry
- mock identity to enterprise identity provider
- local secrets placeholders to approved secret manager

This is deployment planning and migration readiness documentation. It must not
be represented as approved for live use.
