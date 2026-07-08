from __future__ import annotations

import sqlite3

from generated_application.app.domain.entities import Dispute, DisputeState
from generated_application.app.domain.value_objects import DisputeId, UpiTransactionRef


class SqliteDisputeRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, dispute: Dispute) -> None:
        self.connection.execute(
            "insert into disputes(dispute_id, transaction_ref, customer_upi, reason, state) "
            "values (?, ?, ?, ?, ?)",
            (
                dispute.dispute_id.value,
                dispute.transaction_ref.value,
                dispute.customer_upi,
                dispute.reason,
                dispute.state.value,
            ),
        )

    def get(self, dispute_id: str) -> Dispute | None:
        row = self.connection.execute(
            "select dispute_id, transaction_ref, customer_upi, reason, state from disputes where dispute_id = ?",
            (dispute_id,),
        ).fetchone()
        if row is None:
            return None
        dispute = Dispute(
            dispute_id=DisputeId(str(row[0])),
            transaction_ref=UpiTransactionRef(str(row[1])),
            customer_upi=str(row[2]),
            reason=str(row[3]),
        )
        dispute.state = DisputeState(str(row[4]))
        return dispute
