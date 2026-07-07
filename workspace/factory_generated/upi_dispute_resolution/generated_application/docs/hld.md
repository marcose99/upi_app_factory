# High-Level Design

The app accepts a synthetic/local dispute request, validates it, persists a local
record, writes an audit event, and uses mock ecosystem adapters to simulate checks.
