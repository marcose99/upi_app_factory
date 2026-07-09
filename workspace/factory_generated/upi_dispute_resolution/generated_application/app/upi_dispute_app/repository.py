from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .errors import AppErrorCode, ApplicationError
from .models import DisputeRecord, DisputeStatus


class DuplicateClientRequestError(ApplicationError):
    def __init__(self, client_request_id: str) -> None:
        super().__init__(
            AppErrorCode.DUPLICATE_CLIENT_REQUEST,
            f"client_request_id already exists: {client_request_id}",
            http_status=409,
        )


class DisputeNotFoundError(ApplicationError):
    def __init__(self, dispute_id: str) -> None:
        super().__init__(
            AppErrorCode.DISPUTE_NOT_FOUND,
            f"dispute not found: {dispute_id}",
            http_status=404,
        )


class DisputeRepository:
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(db_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.create_schema()

    def create_schema(self) -> None:
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS disputes ("
            "dispute_id TEXT PRIMARY KEY, "
            "client_request_id TEXT NOT NULL UNIQUE, "
            "request_fingerprint TEXT, "
            "payload_json TEXT NOT NULL, "
            "status TEXT NOT NULL, "
            "created_at_utc TEXT NOT NULL, "
            "updated_at_utc TEXT NOT NULL)"
        )
        columns = {
            str(row["name"])
            for row in self.connection.execute("PRAGMA table_info(disputes)").fetchall()
        }
        if "request_fingerprint" not in columns:
            self.connection.execute("ALTER TABLE disputes ADD COLUMN request_fingerprint TEXT")
        self.connection.commit()

    def add(
        self,
        record: DisputeRecord,
        *,
        request_fingerprint: str | None = None,
    ) -> DisputeRecord:
        try:
            self.connection.execute(
                "INSERT INTO disputes VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record.dispute_id,
                    record.client_request_id,
                    request_fingerprint,
                    record.model_dump_json(),
                    record.status.value,
                    record.created_at_utc,
                    record.updated_at_utc,
                ),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateClientRequestError(record.client_request_id) from exc
        return record

    def get_by_client_request_id(self, client_request_id: str) -> DisputeRecord:
        row = self.connection.execute(
            "SELECT payload_json FROM disputes WHERE client_request_id = ?",
            (client_request_id,),
        ).fetchone()
        if row is None:
            raise DisputeNotFoundError(client_request_id)
        return DisputeRecord.model_validate_json(str(row["payload_json"]))

    def get_request_fingerprint(self, client_request_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT request_fingerprint FROM disputes WHERE client_request_id = ?",
            (client_request_id,),
        ).fetchone()
        if row is None:
            raise DisputeNotFoundError(client_request_id)
        fingerprint = row["request_fingerprint"]
        return str(fingerprint) if fingerprint is not None else None

    def get(self, dispute_id: str) -> DisputeRecord:
        row = self.connection.execute(
            "SELECT payload_json FROM disputes WHERE dispute_id = ?",
            (dispute_id,),
        ).fetchone()
        if row is None:
            raise DisputeNotFoundError(dispute_id)
        return DisputeRecord.model_validate_json(str(row["payload_json"]))

    def list_all(self) -> list[DisputeRecord]:
        rows: Iterable[sqlite3.Row] = self.connection.execute(
            "SELECT payload_json FROM disputes ORDER BY created_at_utc"
        ).fetchall()
        return [DisputeRecord.model_validate_json(str(row["payload_json"])) for row in rows]

    def update_status(
        self,
        *,
        dispute_id: str,
        status: DisputeStatus,
        updated_at_utc: str,
        note: str,
    ) -> DisputeRecord:
        record = self.get(dispute_id)
        updated = record.model_copy(
            update={
                "status": status,
                "updated_at_utc": updated_at_utc,
                "domain_notes": [*record.domain_notes, note],
            }
        )
        self.connection.execute(
            "UPDATE disputes SET payload_json = ?, status = ?, updated_at_utc = ? "
            "WHERE dispute_id = ?",
            (
                json.dumps(updated.model_dump(mode="json"), sort_keys=True),
                updated.status.value,
                updated.updated_at_utc,
                updated.dispute_id,
            ),
        )
        self.connection.commit()
        return updated
