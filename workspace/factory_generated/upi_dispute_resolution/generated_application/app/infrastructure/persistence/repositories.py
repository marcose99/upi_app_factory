from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

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


class SqliteFailedDebitRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_case(self, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """
            insert into failed_debit_cases(
                dispute_id, transaction_ref, customer_upi_digest, customer_upi_masked,
                amount_minor, currency, reason_code, case_type, owner_subject,
                assigned_analyst, state, version, resolution_kind, resolution_reason_code,
                resolution_amount_minor, resolution_rationale, resolution_status,
                latest_investigation_payload_json, created_at_utc, updated_at_utc,
                last_correlation_id, audit_link_hash, business_fingerprint,
                latest_classification_payload_json, human_review_required, human_review_status,
                proposed_disposition, approved_disposition, latest_disposition_payload_json,
                pending_review_id, review_requested_by, review_requested_at_utc,
                last_audit_check_status, last_audit_check_payload_json, closed_at_utc,
                closed_by, quarantined_at_utc, quarantined_by, quarantine_reason_code,
                quarantine_reason
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["dispute_id"],
                payload["transaction_ref"],
                payload["customer_upi_digest"],
                payload["customer_upi_masked"],
                int(payload["amount_minor"]),
                payload["currency"],
                payload["reason_code"],
                payload["case_type"],
                payload["owner_subject"],
                payload["assigned_analyst"],
                payload["state"],
                int(payload["version"]),
                payload["resolution_kind"],
                payload["resolution_reason_code"],
                payload["resolution_amount_minor"],
                payload["resolution_rationale"],
                payload["resolution_status"],
                payload["latest_investigation_payload_json"],
                payload["created_at_utc"],
                payload["updated_at_utc"],
                payload["last_correlation_id"],
                payload["audit_link_hash"],
                payload["business_fingerprint"],
                payload["latest_classification_payload_json"],
                1 if payload["human_review_required"] else 0,
                payload["human_review_status"],
                payload["proposed_disposition"],
                payload["approved_disposition"],
                payload["latest_disposition_payload_json"],
                payload["pending_review_id"],
                payload["review_requested_by"],
                payload["review_requested_at_utc"],
                payload["last_audit_check_status"],
                payload["last_audit_check_payload_json"],
                payload["closed_at_utc"],
                payload["closed_by"],
                payload["quarantined_at_utc"],
                payload["quarantined_by"],
                payload["quarantine_reason_code"],
                payload["quarantine_reason"],
            ),
        )

    def get_case(self, dispute_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            select dispute_id, transaction_ref, customer_upi_digest, customer_upi_masked,
                   amount_minor, currency, reason_code, case_type, owner_subject,
                   assigned_analyst, state, version, resolution_kind,
                   resolution_reason_code, resolution_amount_minor, resolution_rationale,
                   resolution_status, latest_investigation_payload_json, created_at_utc,
                   updated_at_utc, last_correlation_id, audit_link_hash, business_fingerprint,
                   latest_classification_payload_json, human_review_required, human_review_status,
                   proposed_disposition, approved_disposition, latest_disposition_payload_json,
                   pending_review_id, review_requested_by, review_requested_at_utc,
                   last_audit_check_status, last_audit_check_payload_json, closed_at_utc,
                   closed_by, quarantined_at_utc, quarantined_by, quarantine_reason_code,
                   quarantine_reason
            from failed_debit_cases
            where dispute_id = ?
            """,
            (dispute_id,),
        ).fetchone()
        return None if row is None else self._case_from_row(row)

    def get_case_detail(self, dispute_id: str) -> dict[str, Any] | None:
        case = self.get_case(dispute_id)
        if case is None:
            return None
        evidence = self.list_evidence(dispute_id)
        missing_types = self.missing_evidence_types(dispute_id)
        investigation_payload = case.get("latest_investigation_payload_json")
        latest_investigation = None
        if isinstance(investigation_payload, str) and investigation_payload:
            latest_investigation = json.loads(investigation_payload)
        classification_payload = case.get("latest_classification_payload_json")
        latest_classification = None
        if isinstance(classification_payload, str) and classification_payload:
            latest_classification = json.loads(classification_payload)
        disposition_payload = case.get("latest_disposition_payload_json")
        latest_disposition = None
        if isinstance(disposition_payload, str) and disposition_payload:
            latest_disposition = json.loads(disposition_payload)
        audit_payload = case.get("last_audit_check_payload_json")
        last_audit_check = None
        if isinstance(audit_payload, str) and audit_payload:
            last_audit_check = json.loads(audit_payload)
        return {
            "dispute_id": case["dispute_id"],
            "transaction_ref": case["transaction_ref"],
            "masked_customer_upi": case["customer_upi_masked"],
            "amount": self._minor_to_amount(int(case["amount_minor"])),
            "currency": case["currency"],
            "reason_code": case["reason_code"],
            "case_type": case["case_type"],
            "owner_subject": case["owner_subject"],
            "assigned_analyst": case["assigned_analyst"],
            "state": case["state"],
            "version": int(case["version"]),
            "resolution_status": case["resolution_status"],
            "classification": latest_classification,
            "human_review_required": bool(case["human_review_required"]),
            "human_review_status": case["human_review_status"],
            "pending_review_id": case["pending_review_id"],
            "proposed_disposition": case["proposed_disposition"],
            "approved_disposition": case["approved_disposition"],
            "required_evidence_types": sorted(missing_types.union({item["evidence_type"] for item in evidence})),
            "missing_evidence_types": sorted(missing_types),
            "evidence_count": len(evidence),
            "evidence": evidence,
            "latest_investigation": latest_investigation,
            "latest_resolution": latest_disposition or self._resolution_payload(case),
            "latest_disposition": latest_disposition,
            "review_history": self.list_review_decisions(dispute_id),
            "audit_integrity_checks": self.list_audit_checks(dispute_id),
            "last_audit_integrity_status": case["last_audit_check_status"],
            "last_audit_integrity": last_audit_check,
            "closed_at_utc": case["closed_at_utc"],
            "closed_by": case["closed_by"],
            "quarantined_at_utc": case["quarantined_at_utc"],
            "quarantined_by": case["quarantined_by"],
            "quarantine_reason_code": case["quarantine_reason_code"],
            "quarantine_reason": case["quarantine_reason"],
            "created_at_utc": case["created_at_utc"],
            "updated_at_utc": case["updated_at_utc"],
            "last_correlation_id": case["last_correlation_id"],
            "audit_link_hash": case["audit_link_hash"],
            "timeline": self.list_events(dispute_id),
            "history": self.list_events(dispute_id),
            "certification_boundary": "certification_ready_not_certified",
        }

    def has_open_transaction_ref(self, transaction_ref: str) -> bool:
        row = self.connection.execute(
            """
            select 1
            from failed_debit_cases
            where transaction_ref = ?
              and state in (
                'received', 'validated', 'investigating', 'awaiting_evidence',
                'awaiting_human_review', 'decision_recorded', 'resolved'
              )
            limit 1
            """,
            (transaction_ref,),
        ).fetchone()
        return row is not None

    def add_evidence(self, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """
            insert into failed_debit_evidence(
                dispute_id, evidence_id, evidence_type, source, summary, observed_at_utc,
                attached_by, attached_at_utc, content_sha256, audit_link_hash
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["dispute_id"],
                payload["evidence_id"],
                payload["evidence_type"],
                payload["source"],
                payload["summary"],
                payload["observed_at_utc"],
                payload["attached_by"],
                payload["attached_at_utc"],
                payload["content_sha256"],
                payload["audit_link_hash"],
            ),
        )

    def list_evidence(self, dispute_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            select evidence_id, evidence_type, source, summary, observed_at_utc,
                   attached_by, attached_at_utc, content_sha256, audit_link_hash
            from failed_debit_evidence
            where dispute_id = ?
            order by sequence
            """,
            (dispute_id,),
        ).fetchall()
        return [
            {
                "evidence_id": str(row[0]),
                "evidence_type": str(row[1]),
                "source": str(row[2]),
                "summary": str(row[3]),
                "observed_at_utc": str(row[4]),
                "attached_by": str(row[5]),
                "attached_at_utc": str(row[6]),
                "content_sha256": str(row[7]),
                "audit_link_hash": str(row[8]),
            }
            for row in rows
        ]

    def missing_evidence_types(
        self,
        dispute_id: str,
        *,
        required_types: frozenset[str] = frozenset(
            {"switch_failure", "core_ledger", "customer_statement"}
        ),
    ) -> set[str]:
        rows = self.connection.execute(
            """
            select evidence_type
            from failed_debit_evidence
            where dispute_id = ?
            """,
            (dispute_id,),
        ).fetchall()
        present = {str(row[0]) for row in rows}
        return set(required_types - present)

    def update_case(
        self,
        dispute_id: str,
        *,
        expected_version: int,
        updates: dict[str, Any],
    ) -> int:
        next_version = expected_version + 1
        fields = ["version = ?"]
        values: list[Any] = [next_version]
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            values.append(value)
        values.extend([dispute_id, expected_version])
        cursor = self.connection.execute(
            f"""
            update failed_debit_cases
            set {", ".join(fields)}
            where dispute_id = ? and version = ?
            """,
            tuple(values),
        )
        if cursor.rowcount != 1:
            raise OptimisticConcurrencyError("failed-debit case stale write rejected")
        return next_version

    def add_event(self, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """
            insert into failed_debit_timeline(
                event_id, dispute_id, event_type, state, aggregate_version,
                actor_subject, occurred_at_utc, correlation_id, payload_json, audit_link_hash
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["event_id"],
                payload["dispute_id"],
                payload["event_type"],
                payload["state"],
                int(payload["aggregate_version"]),
                payload["actor_subject"],
                payload["occurred_at_utc"],
                payload["correlation_id"],
                payload["payload_json"],
                payload["audit_link_hash"],
            ),
        )

    def list_events(self, dispute_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            select event_id, event_type, state, aggregate_version, actor_subject,
                   occurred_at_utc, correlation_id, payload_json, audit_link_hash
            from failed_debit_timeline
            where dispute_id = ?
            order by sequence
            """,
            (dispute_id,),
        ).fetchall()
        return [
            {
                "event_id": str(row[0]),
                "event_type": str(row[1]),
                "state": str(row[2]),
                "aggregate_version": int(row[3]),
                "actor_subject": str(row[4]),
                "occurred_at_utc": str(row[5]),
                "correlation_id": str(row[6]),
                "payload": json.loads(str(row[7])),
                "audit_link_hash": str(row[8]),
            }
            for row in rows
        ]

    def list_cases(
        self,
        *,
        limit: int,
        cursor: int,
        transaction_reference: str | None = None,
        state: str | None = None,
        age_bucket: str | None = None,
        analyst: str | None = None,
        resolution_status: str | None = None,
        classification: str | None = None,
        human_review_status: str | None = None,
    ) -> dict[str, Any]:
        rows = self.connection.execute(
            """
            select dispute_id, transaction_ref, customer_upi_digest, customer_upi_masked,
                   amount_minor, currency, reason_code, case_type, owner_subject,
                   assigned_analyst, state, version, resolution_kind,
                   resolution_reason_code, resolution_amount_minor, resolution_rationale,
                   resolution_status, latest_investigation_payload_json, created_at_utc,
                   updated_at_utc, last_correlation_id, audit_link_hash, business_fingerprint,
                   latest_classification_payload_json, human_review_required, human_review_status,
                   proposed_disposition, approved_disposition, latest_disposition_payload_json,
                   pending_review_id, review_requested_by, review_requested_at_utc,
                   last_audit_check_status, last_audit_check_payload_json, closed_at_utc,
                   closed_by, quarantined_at_utc, quarantined_by, quarantine_reason_code,
                   quarantine_reason
            from failed_debit_cases
            order by created_at_utc, dispute_id
            """
        ).fetchall()
        filtered: list[dict[str, Any]] = []
        for row in rows:
            case = self._case_from_row(row)
            if transaction_reference and case["transaction_ref"] != transaction_reference:
                continue
            if state and case["state"] != state:
                continue
            if analyst and case["assigned_analyst"] != analyst:
                continue
            if resolution_status and case["resolution_status"] != resolution_status:
                continue
            if classification:
                classification_payload = case["latest_classification_payload_json"]
                classification_name = None
                if classification_payload:
                    classification_name = json.loads(classification_payload).get("classification")
                if classification_name != classification:
                    continue
            if human_review_status and case["human_review_status"] != human_review_status:
                continue
            if age_bucket and self._age_bucket(str(case["created_at_utc"])) != age_bucket:
                continue
            filtered.append(case)
        page = filtered[cursor : cursor + limit]
        items = []
        for case in page:
            detail = self.get_case_detail(str(case["dispute_id"]))
            if detail is not None:
                items.append(detail)
        next_cursor = cursor + len(items) if cursor + len(items) < len(filtered) else None
        return {
            "items": items,
            "limit": limit,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "filters": {
                "transaction_reference": transaction_reference,
                "state": state,
                "age_bucket": age_bucket,
                "analyst": analyst,
                "resolution_status": resolution_status,
                "classification": classification,
                "human_review_status": human_review_status,
            },
        }

    def add_review_decision(self, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """
            insert into failed_debit_review_decisions(
                review_event_id, dispute_id, review_id, decision_status, actor_subject,
                actor_role, reason_code, rationale, approved_disposition, occurred_at_utc,
                correlation_id, audit_link_hash
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["review_event_id"],
                payload["dispute_id"],
                payload["review_id"],
                payload["decision_status"],
                payload["actor_subject"],
                payload["actor_role"],
                payload["reason_code"],
                payload["rationale"],
                payload["approved_disposition"],
                payload["occurred_at_utc"],
                payload["correlation_id"],
                payload["audit_link_hash"],
            ),
        )

    def list_review_decisions(self, dispute_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            select review_event_id, review_id, decision_status, actor_subject, actor_role, reason_code,
                   rationale, approved_disposition, occurred_at_utc, correlation_id, audit_link_hash
            from failed_debit_review_decisions
            where dispute_id = ?
            order by sequence
            """,
            (dispute_id,),
        ).fetchall()
        return [
            {
                "review_event_id": str(row[0]),
                "review_id": str(row[1]),
                "decision_status": str(row[2]),
                "actor_subject": str(row[3]),
                "actor_role": str(row[4]),
                "reason_code": str(row[5]),
                "rationale": str(row[6]),
                "approved_disposition": None if row[7] is None else str(row[7]),
                "occurred_at_utc": str(row[8]),
                "correlation_id": str(row[9]),
                "audit_link_hash": str(row[10]),
            }
            for row in rows
        ]

    def add_audit_check(self, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """
            insert into failed_debit_audit_checks(
                verification_id, dispute_id, actor_subject, actor_role, verification_status,
                quarantine_applied, verified_at_utc, correlation_id, details_json, audit_link_hash
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["verification_id"],
                payload["dispute_id"],
                payload["actor_subject"],
                payload["actor_role"],
                payload["verification_status"],
                1 if payload["quarantine_applied"] else 0,
                payload["verified_at_utc"],
                payload["correlation_id"],
                payload["details_json"],
                payload["audit_link_hash"],
            ),
        )

    def list_audit_checks(self, dispute_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            select verification_id, actor_subject, actor_role, verification_status, quarantine_applied,
                   verified_at_utc, correlation_id, details_json, audit_link_hash
            from failed_debit_audit_checks
            where dispute_id = ?
            order by sequence
            """,
            (dispute_id,),
        ).fetchall()
        return [
            {
                "verification_id": str(row[0]),
                "actor_subject": str(row[1]),
                "actor_role": str(row[2]),
                "verification_status": str(row[3]),
                "quarantine_applied": bool(int(row[4])),
                "verified_at_utc": str(row[5]),
                "correlation_id": str(row[6]),
                "details": json.loads(str(row[7])),
                "audit_link_hash": str(row[8]),
            }
            for row in rows
        ]

    @staticmethod
    def _case_from_row(row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
        return {
            "dispute_id": str(row[0]),
            "transaction_ref": str(row[1]),
            "customer_upi_digest": str(row[2]),
            "customer_upi_masked": str(row[3]),
            "amount_minor": int(row[4]),
            "currency": str(row[5]),
            "reason_code": str(row[6]),
            "case_type": str(row[7]),
            "owner_subject": str(row[8]),
            "assigned_analyst": str(row[9]),
            "state": str(row[10]),
            "version": int(row[11]),
            "resolution_kind": None if row[12] is None else str(row[12]),
            "resolution_reason_code": None if row[13] is None else str(row[13]),
            "resolution_amount_minor": None if row[14] is None else int(row[14]),
            "resolution_rationale": None if row[15] is None else str(row[15]),
            "resolution_status": str(row[16]),
            "latest_investigation_payload_json": None if row[17] is None else str(row[17]),
            "created_at_utc": str(row[18]),
            "updated_at_utc": str(row[19]),
            "last_correlation_id": str(row[20]),
            "audit_link_hash": str(row[21]),
            "business_fingerprint": str(row[22]),
            "latest_classification_payload_json": None if row[23] is None else str(row[23]),
            "human_review_required": bool(int(row[24])),
            "human_review_status": str(row[25]),
            "proposed_disposition": None if row[26] is None else str(row[26]),
            "approved_disposition": None if row[27] is None else str(row[27]),
            "latest_disposition_payload_json": None if row[28] is None else str(row[28]),
            "pending_review_id": None if row[29] is None else str(row[29]),
            "review_requested_by": None if row[30] is None else str(row[30]),
            "review_requested_at_utc": None if row[31] is None else str(row[31]),
            "last_audit_check_status": str(row[32]),
            "last_audit_check_payload_json": None if row[33] is None else str(row[33]),
            "closed_at_utc": None if row[34] is None else str(row[34]),
            "closed_by": None if row[35] is None else str(row[35]),
            "quarantined_at_utc": None if row[36] is None else str(row[36]),
            "quarantined_by": None if row[37] is None else str(row[37]),
            "quarantine_reason_code": None if row[38] is None else str(row[38]),
            "quarantine_reason": None if row[39] is None else str(row[39]),
        }

    @staticmethod
    def _resolution_payload(case: dict[str, Any]) -> dict[str, Any] | None:
        if case["resolution_kind"] is None:
            return None
        return {
            "resolution_kind": case["resolution_kind"],
            "reason_code": case["resolution_reason_code"],
            "amount": SqliteFailedDebitRepository._minor_to_amount(
                int(case["resolution_amount_minor"])
            )
            if case["resolution_amount_minor"] is not None
            else None,
            "rationale": case["resolution_rationale"],
            "status": case["resolution_status"],
        }

    @staticmethod
    def _minor_to_amount(amount_minor: int) -> str:
        sign = "-" if amount_minor < 0 else ""
        absolute_minor = abs(amount_minor)
        units, cents = divmod(absolute_minor, 100)
        return f"{sign}{units}.{cents:02d}"

    @staticmethod
    def _age_bucket(created_at_utc: str) -> str:
        created = datetime.fromisoformat(created_at_utc.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        if age_hours < 24:
            return "lt_24h"
        if age_hours < 72:
            return "24h_to_72h"
        return "gt_72h"
