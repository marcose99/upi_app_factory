from __future__ import annotations

import sqlite3

from generated_application.app.domain.entities import Dispute, DisputeState
from generated_application.app.domain.exceptions import OptimisticConcurrencyError
from generated_application.app.domain.value_objects import DisputeId, UpiTransactionRef
from generated_application.app.security.pii_redaction import stored_masked_upi, upi_storage_digest


class SqliteDisputeRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(
        self,
        dispute: Dispute,
        *,
        audit_link_hash: str | None = None,
        business_fingerprint: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            insert into disputes(
                dispute_id, transaction_ref, customer_upi, customer_upi_masked, reason, owner_subject, state, version, audit_link_hash, business_fingerprint
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dispute.dispute_id.value,
                dispute.transaction_ref.value,
                upi_storage_digest(dispute.customer_upi),
                stored_masked_upi(dispute.customer_upi),
                dispute.reason,
                dispute.owner_subject,
                dispute.state.value,
                dispute.version,
                audit_link_hash,
                business_fingerprint,
            ),
        )

    def exists_for_business_fingerprint(self, business_fingerprint: str) -> bool:
        row = self.connection.execute(
            "select 1 from disputes where business_fingerprint = ? limit 1",
            (business_fingerprint,),
        ).fetchone()
        return row is not None

    def get(self, dispute_id: str) -> Dispute | None:
        row = self.connection.execute(
            """
            select dispute_id, transaction_ref, customer_upi_masked, reason, owner_subject, state, version, audit_link_hash
            from disputes
            where dispute_id = ?
            """,
            (dispute_id,),
        ).fetchone()
        if row is None:
            return None
        dispute = Dispute(
            dispute_id=DisputeId(str(row[0])),
            transaction_ref=UpiTransactionRef(str(row[1])),
            customer_upi=str(row[2]),
            reason=str(row[3]),
            owner_subject=str(row[4]),
        )
        dispute.state = DisputeState(str(row[5]))
        dispute.version = int(row[6])
        dispute.audit_link_hash = None if row[7] is None else str(row[7])
        return dispute

    def list_page(self, *, limit: int, cursor: int) -> list[Dispute]:
        rows = self.connection.execute(
            """
            select dispute_id, transaction_ref, customer_upi_masked, reason, owner_subject, state, version, audit_link_hash
            from disputes
            order by rowid
            limit ? offset ?
            """,
            (limit, cursor),
        ).fetchall()
        disputes: list[Dispute] = []
        for row in rows:
            dispute = Dispute(
                dispute_id=DisputeId(str(row[0])),
                transaction_ref=UpiTransactionRef(str(row[1])),
                customer_upi=str(row[2]),
                reason=str(row[3]),
                owner_subject=str(row[4]),
            )
            dispute.state = DisputeState(str(row[5]))
            dispute.version = int(row[6])
            dispute.audit_link_hash = None if row[7] is None else str(row[7])
            disputes.append(dispute)
        return disputes

    def save(self, dispute: Dispute, *, expected_version: int) -> int:
        next_version = expected_version + 1
        cursor = self.connection.execute(
            """
            update disputes
            set state = ?, version = ?, audit_link_hash = ?
            where dispute_id = ? and version = ?
            """,
            (
                dispute.state.value,
                next_version,
                dispute.audit_link_hash,
                dispute.dispute_id.value,
                expected_version,
            ),
        )
        if cursor.rowcount != 1:
            raise OptimisticConcurrencyError("dispute stale write rejected")
        dispute.version = next_version
        return next_version
