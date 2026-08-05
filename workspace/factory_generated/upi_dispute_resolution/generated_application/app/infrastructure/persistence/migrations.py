from __future__ import annotations

import hashlib
import hmac
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from generated_application.app.domain.exceptions import MigrationDriftError


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        "migration_ledger",
        """
        create table if not exists schema_migrations(
          version integer primary key,
          name text not null,
          checksum text not null,
          applied_at_utc text not null
        );
        """,
    ),
    Migration(
        2,
        "dispute_integrity",
        """
        create table if not exists disputes(
          dispute_id text primary key,
          transaction_ref text not null,
          customer_upi text not null,
          reason text not null,
          state text not null,
          version integer not null,
          audit_link_hash text
        );
        """,
    ),
    Migration(
        3,
        "idempotency",
        """
        create table if not exists idempotency_keys(
          key text primary key,
          result text not null
        );
        """,
    ),
    Migration(
        4,
        "audit_log",
        """
        create table if not exists audit_records(
          sequence integer primary key autoincrement,
          occurred_at_utc text not null,
          actor_id text not null,
          action text not null,
          target text not null,
          payload_json text not null,
          previous_hash text not null,
          record_hash text not null unique
        );
        """,
    ),
    Migration(
        5,
        "transactional_outbox",
        """
        create table if not exists outbox(
          id integer primary key autoincrement,
          message_id text not null unique,
          event_type text not null,
          aggregate_id text not null,
          aggregate_version integer not null,
          envelope_json text not null,
          payload_sha256 text not null,
          dispatched integer not null default 0,
          dispatched_at_utc text
        );
        """,
    ),
    Migration(
        6,
        "consumer_inbox",
        """
        create table if not exists inbox(
          message_id text primary key,
          consumed_at_utc text not null
        );
        """,
    ),
    Migration(
        7,
        "dispute_owner_subject",
        """
        alter table disputes add column owner_subject text not null default 'local-system';
        """,
    ),
    Migration(
        8,
        "dispute_upi_minimization",
        """
        alter table disputes add column customer_upi_masked text not null default '[redacted]';
        update disputes
        set
          customer_upi_masked = case
            when instr(customer_upi, '@') > 1
            then substr(customer_upi, 1, 2) || '***@' || substr(customer_upi, instr(customer_upi, '@') + 1)
            else '[redacted]'
          end,
          customer_upi = '[redacted-legacy-upi]'
        where customer_upi not like 'sha256:%';
        """,
    ),
    Migration(
        9,
        "idempotency_request_fingerprint",
        """
        alter table idempotency_keys add column request_fingerprint text not null default 'legacy-unbound';
        """,
    ),
    Migration(
        10,
        "dispute_business_fingerprint",
        """
        alter table disputes add column business_fingerprint text;
        create unique index if not exists idx_disputes_business_fingerprint
          on disputes(business_fingerprint)
          where business_fingerprint is not null;
        """,
    ),
    Migration(
        11,
        "failed_debit_cases",
        """
        create table if not exists failed_debit_cases(
          dispute_id text primary key,
          transaction_ref text not null,
          customer_upi_digest text not null,
          customer_upi_masked text not null,
          amount_minor integer not null,
          currency text not null,
          reason_code text not null,
          case_type text not null,
          owner_subject text not null,
          assigned_analyst text not null,
          state text not null,
          version integer not null,
          resolution_kind text,
          resolution_reason_code text,
          resolution_amount_minor integer,
          resolution_rationale text,
          resolution_status text not null,
          latest_investigation_payload_json text,
          created_at_utc text not null,
          updated_at_utc text not null,
          last_correlation_id text not null,
          audit_link_hash text not null,
          business_fingerprint text not null unique
        );
        create index if not exists idx_failed_debit_cases_state on failed_debit_cases(state);
        create index if not exists idx_failed_debit_cases_transaction_ref on failed_debit_cases(transaction_ref);
        create index if not exists idx_failed_debit_cases_resolution_status on failed_debit_cases(resolution_status);
        """,
    ),
    Migration(
        12,
        "failed_debit_evidence",
        """
        create table if not exists failed_debit_evidence(
          sequence integer primary key autoincrement,
          dispute_id text not null references failed_debit_cases(dispute_id) on delete cascade,
          evidence_id text not null,
          evidence_type text not null,
          source text not null,
          summary text not null,
          observed_at_utc text not null,
          attached_by text not null,
          attached_at_utc text not null,
          content_sha256 text not null,
          audit_link_hash text not null,
          unique(dispute_id, evidence_id)
        );
        create index if not exists idx_failed_debit_evidence_dispute on failed_debit_evidence(dispute_id, sequence);
        """,
    ),
    Migration(
        13,
        "failed_debit_timeline",
        """
        create table if not exists failed_debit_timeline(
          sequence integer primary key autoincrement,
          event_id text not null unique,
          dispute_id text not null references failed_debit_cases(dispute_id) on delete cascade,
          event_type text not null,
          state text not null,
          aggregate_version integer not null,
          actor_subject text not null,
          occurred_at_utc text not null,
          correlation_id text not null,
          payload_json text not null,
          audit_link_hash text not null
        );
        create index if not exists idx_failed_debit_timeline_dispute on failed_debit_timeline(dispute_id, sequence);
        """,
    ),
    Migration(
        14,
        "failed_debit_case_governance_fields",
        """
        alter table failed_debit_cases add column latest_classification_payload_json text;
        alter table failed_debit_cases add column human_review_required integer not null default 0;
        alter table failed_debit_cases add column human_review_status text not null default 'NOT_REQUIRED';
        alter table failed_debit_cases add column proposed_disposition text;
        alter table failed_debit_cases add column approved_disposition text;
        alter table failed_debit_cases add column latest_disposition_payload_json text;
        alter table failed_debit_cases add column pending_review_id text;
        alter table failed_debit_cases add column review_requested_by text;
        alter table failed_debit_cases add column review_requested_at_utc text;
        alter table failed_debit_cases add column last_audit_check_status text not null default 'not_run';
        alter table failed_debit_cases add column last_audit_check_payload_json text;
        alter table failed_debit_cases add column closed_at_utc text;
        alter table failed_debit_cases add column closed_by text;
        alter table failed_debit_cases add column quarantined_at_utc text;
        alter table failed_debit_cases add column quarantined_by text;
        alter table failed_debit_cases add column quarantine_reason_code text;
        alter table failed_debit_cases add column quarantine_reason text;
        create index if not exists idx_failed_debit_cases_review_status
          on failed_debit_cases(human_review_status);
        """,
    ),
    Migration(
        15,
        "failed_debit_review_decisions",
        """
        create table if not exists failed_debit_review_decisions(
          sequence integer primary key autoincrement,
          review_event_id text not null unique,
          dispute_id text not null references failed_debit_cases(dispute_id) on delete cascade,
          review_id text not null,
          decision_status text not null,
          actor_subject text not null,
          reason_code text not null,
          rationale text not null,
          approved_disposition text,
          occurred_at_utc text not null,
          correlation_id text not null,
          audit_link_hash text not null
        );
        create index if not exists idx_failed_debit_review_decisions_dispute
          on failed_debit_review_decisions(dispute_id, sequence);
        """,
    ),
    Migration(
        16,
        "failed_debit_audit_checks",
        """
        create table if not exists failed_debit_audit_checks(
          sequence integer primary key autoincrement,
          verification_id text not null unique,
          dispute_id text not null references failed_debit_cases(dispute_id) on delete cascade,
          actor_subject text not null,
          verification_status text not null,
          quarantine_applied integer not null default 0,
          verified_at_utc text not null,
          correlation_id text not null,
          details_json text not null,
          audit_link_hash text not null
        );
        create index if not exists idx_failed_debit_audit_checks_dispute
          on failed_debit_audit_checks(dispute_id, sequence);
        """,
    ),
    Migration(
        17,
        "audit_log_actor_role",
        """
        alter table audit_records add column actor_role text not null default 'unknown';
        """,
    ),
    Migration(
        18,
        "failed_debit_review_decision_actor_role",
        """
        alter table failed_debit_review_decisions add column actor_role text not null default 'unknown';
        """,
    ),
    Migration(
        19,
        "failed_debit_audit_check_actor_role",
        """
        alter table failed_debit_audit_checks add column actor_role text not null default 'unknown';
        """,
    ),
)


def apply_migrations(connection: sqlite3.Connection, migrations: tuple[Migration, ...] = MIGRATIONS) -> None:
    connection.execute(MIGRATIONS[0].sql)
    rows = connection.execute("select version, checksum from schema_migrations order by version").fetchall()
    applied = {int(row[0]): str(row[1]) for row in rows}
    for migration in sorted(migrations, key=lambda item: item.version):
        if migration.version in applied:
            if not hmac.compare_digest(applied[migration.version], migration.checksum):
                raise MigrationDriftError(f"migration checksum drift: {migration.version}")
            continue
        connection.executescript(migration.sql)
        connection.execute(
            "insert into schema_migrations(version, name, checksum, applied_at_utc) values (?, ?, ?, ?)",
            (migration.version, migration.name, migration.checksum, datetime.now(timezone.utc).isoformat()),
        )
    result = connection.execute("pragma integrity_check").fetchone()[0]
    if result != "ok":
        raise MigrationDriftError(f"sqlite integrity check failed: {result}")
