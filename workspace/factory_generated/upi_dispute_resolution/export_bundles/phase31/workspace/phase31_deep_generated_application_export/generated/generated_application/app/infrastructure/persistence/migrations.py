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
        "audit_log_actor_role",
        """
        alter table audit_records add column actor_role text not null default 'unknown';
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
