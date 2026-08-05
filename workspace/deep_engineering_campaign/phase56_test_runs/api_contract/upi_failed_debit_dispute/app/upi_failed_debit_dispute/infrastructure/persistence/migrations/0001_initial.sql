PRAGMA foreign_keys = ON;
CREATE TABLE dispute_cases (
  dispute_id TEXT PRIMARY KEY,
  transaction_reference TEXT NOT NULL UNIQUE,
  amount TEXT NOT NULL,
  reason TEXT NOT NULL,
  state TEXT NOT NULL,
  version INTEGER NOT NULL
);
CREATE TABLE idempotency_records (
  idempotency_key TEXT PRIMARY KEY,
  dispute_id TEXT NOT NULL REFERENCES dispute_cases(dispute_id)
);
CREATE TABLE audit_records (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  dispute_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  previous_hash TEXT NOT NULL,
  record_hash TEXT NOT NULL
);
CREATE TABLE outbox_events (
  event_id TEXT PRIMARY KEY,
  dispute_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  published INTEGER NOT NULL DEFAULT 0
);
