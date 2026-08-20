from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from generated_application.app.domain.exceptions import (
    DomainError,
    OptimisticConcurrencyError,
)


NON_EXECUTION_NOTICE = (
    "Observation and review only; not a financial/accounting ledger and never "
    "executes payments, refunds, reversals, adjustments, or external actions."
)


@dataclass(frozen=True)
class Observation:
    source: str
    status: str
    value_minor: int
    currency: str
    product_leg: str
    control_state: str
    evidence_reference: str


@dataclass(frozen=True)
class Reconciliation:
    case_id: str
    version: int
    result_id: str
    observations: tuple[Observation, ...]
    conflicts: tuple[str, ...]
    equivalent: bool
    ledger_kind: str = "observation_only"
    financial_ledger: bool = False
    executes_remediation: bool = False
    live_provider_calls_allowed: bool = False
    boundary_notice: str = NON_EXECUTION_NOTICE


@dataclass(frozen=True)
class ResolutionProposal:
    proposal_id: str
    case_id: str
    bound_version: int
    recommended_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    rationale: str
    customer_message: str
    risk: str
    dependencies: tuple[str, ...]
    review_state: str
    event_id: str
    event_type: str = "reconciliation.resolution_proposed"
    executes_remediation: bool = False
    live_provider_calls_allowed: bool = False
    boundary_notice: str = NON_EXECUTION_NOTICE


class ReconciliationResolutionService:
    """Local observation/review boundary; it has no external-action adapter."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def reconcile(
        self, case_id: str, observations: Iterable[Observation]
    ) -> Reconciliation:
        normalized = tuple(sorted((self._normalize(item) for item in observations), key=self._key))
        if not case_id.strip() or not normalized:
            raise DomainError("case_id and at least one observation are required")
        canonical = self._json([asdict(item) for item in normalized])
        result_id = self._digest("reconciliation", case_id.strip(), canonical)
        conflicts = self._conflicts(normalized)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT version, canonical_observations FROM reconciliation_cases WHERE case_id = ?",
                (case_id.strip(),),
            ).fetchone()
            equivalent = row is not None and row[1] == canonical
            version = int(row[0]) if equivalent else (int(row[0]) + 1 if row else 1)
            if row is None:
                connection.execute(
                    "INSERT INTO reconciliation_cases(case_id, version, canonical_observations, result_id) VALUES (?, ?, ?, ?)",
                    (case_id.strip(), version, canonical, result_id),
                )
            elif not equivalent:
                changed = connection.execute(
                    "UPDATE reconciliation_cases SET version = ?, canonical_observations = ?, result_id = ? WHERE case_id = ? AND version = ?",
                    (version, canonical, result_id, case_id.strip(), int(row[0])),
                ).rowcount
                if changed != 1:
                    raise OptimisticConcurrencyError("reconciliation case changed concurrently")
            connection.execute(
                "INSERT OR IGNORE INTO reconciliation_results(result_id, case_id, version, canonical_observations, conflicts) VALUES (?, ?, ?, ?, ?)",
                (result_id, case_id.strip(), version, canonical, self._json(conflicts)),
            )
        return Reconciliation(case_id.strip(), version, result_id, normalized, conflicts, equivalent)

    def create_proposal(
        self,
        *,
        case_id: str,
        expected_version: int,
        recommended_actions: Sequence[str],
        prohibited_actions: Sequence[str],
        rationale: str,
        customer_message: str,
        risk: str,
        dependencies: Sequence[str],
    ) -> ResolutionProposal:
        fields = [rationale, customer_message, risk]
        if not recommended_actions or not prohibited_actions or not all(item.strip() for item in fields):
            raise DomainError("complete recommendation, prohibition, rationale, message, and risk are required")
        payload = {
            "case_id": case_id.strip(),
            "bound_version": expected_version,
            "recommended_actions": self._strings(recommended_actions),
            "prohibited_actions": self._strings(prohibited_actions),
            "rationale": rationale.strip(),
            "customer_message": customer_message.strip(),
            "risk": risk.strip(),
            "dependencies": self._strings(dependencies),
        }
        canonical = self._json(payload)
        proposal_id = self._digest("proposal", canonical)
        event_id = self._digest("event", proposal_id, str(expected_version))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_version(connection, case_id, expected_version)
            connection.execute(
                "INSERT OR IGNORE INTO resolution_proposals(proposal_id, case_id, bound_version, payload, event_id) VALUES (?, ?, ?, ?, ?)",
                (proposal_id, case_id.strip(), expected_version, canonical, event_id),
            )
            connection.execute(
                "INSERT OR IGNORE INTO proposal_reviews(proposal_id, sequence, state, reviewer, note) VALUES (?, 1, 'pending_review', 'system', 'created without execution')",
                (proposal_id,),
            )
            connection.execute(
                "INSERT OR IGNORE INTO resolution_events(event_id, proposal_id, case_id, bound_version, event_type, payload) VALUES (?, ?, ?, ?, 'reconciliation.resolution_proposed', ?)",
                (event_id, proposal_id, case_id.strip(), expected_version, canonical),
            )
        return self.get_proposal(proposal_id)

    def review_proposal(
        self, *, proposal_id: str, expected_version: int, state: str, reviewer: str, note: str
    ) -> ResolutionProposal:
        state = state.strip().lower()
        if state not in {"reviewed", "approved", "rejected"}:
            raise DomainError("review state must be reviewed, approved, or rejected")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT case_id, bound_version FROM resolution_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise DomainError("proposal not found")
            self._require_version(connection, str(row[0]), expected_version)
            if int(row[1]) != expected_version:
                raise OptimisticConcurrencyError(
                    "reviewed retry requires the latest/current case version and a version-bound proposal"
                )
            sequence = int(connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM proposal_reviews WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()[0])
            connection.execute(
                "INSERT INTO proposal_reviews(proposal_id, sequence, state, reviewer, note) VALUES (?, ?, ?, ?, ?)",
                (proposal_id, sequence, state, reviewer.strip(), note.strip()),
            )
        return self.get_proposal(proposal_id)

    def get_proposal(self, proposal_id: str) -> ResolutionProposal:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT case_id, bound_version, payload, event_id FROM resolution_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise DomainError("proposal not found")
            state = str(connection.execute(
                "SELECT state FROM proposal_reviews WHERE proposal_id = ? ORDER BY sequence DESC LIMIT 1",
                (proposal_id,),
            ).fetchone()[0])
        payload = json.loads(str(row[2]))
        return ResolutionProposal(
            proposal_id, str(row[0]), int(row[1]), tuple(payload["recommended_actions"]),
            tuple(payload["prohibited_actions"]), payload["rationale"], payload["customer_message"],
            payload["risk"], tuple(payload["dependencies"]), state, str(row[3])
        )

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS reconciliation_cases (
                    case_id TEXT PRIMARY KEY, version INTEGER NOT NULL CHECK(version > 0),
                    canonical_observations TEXT NOT NULL, result_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reconciliation_results (
                    result_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, version INTEGER NOT NULL,
                    canonical_observations TEXT NOT NULL, conflicts TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS resolution_proposals (
                    proposal_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, bound_version INTEGER NOT NULL,
                    payload TEXT NOT NULL, event_id TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS proposal_reviews (
                    proposal_id TEXT NOT NULL, sequence INTEGER NOT NULL, state TEXT NOT NULL,
                    reviewer TEXT NOT NULL, note TEXT NOT NULL, PRIMARY KEY(proposal_id, sequence));
                CREATE TABLE IF NOT EXISTS resolution_events (
                    event_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, case_id TEXT NOT NULL,
                    bound_version INTEGER NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL);
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _normalize(item: Observation) -> Observation:
        return Observation(
            source=item.source.strip().lower(), status=item.status.strip().lower(),
            value_minor=int(item.value_minor), currency=item.currency.strip().upper(),
            product_leg=item.product_leg.strip().lower(),
            control_state=item.control_state.strip().lower(),
            evidence_reference=item.evidence_reference.strip(),
        )

    @staticmethod
    def _key(item: Observation) -> tuple[object, ...]:
        return tuple(asdict(item).values())

    @staticmethod
    def _strings(items: Sequence[str]) -> list[str]:
        return sorted({item.strip() for item in items if item.strip()})

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @staticmethod
    def _digest(*parts: str) -> str:
        return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

    @staticmethod
    def _conflicts(items: tuple[Observation, ...]) -> tuple[str, ...]:
        names: Mapping[str, tuple[object, ...]] = {
            "status": tuple(item.status for item in items),
            "value": tuple((item.value_minor, item.currency) for item in items),
            "product_leg": tuple(item.product_leg for item in items),
            "control_state": tuple(item.control_state for item in items),
        }
        return tuple(name for name, values in names.items() if len(set(values)) > 1)

    @staticmethod
    def _require_version(connection: sqlite3.Connection, case_id: str, expected: int) -> None:
        row = connection.execute(
            "SELECT version FROM reconciliation_cases WHERE case_id = ?", (case_id.strip(),)
        ).fetchone()
        if row is None:
            raise DomainError("reconciliation case not found")
        if int(row[0]) != expected:
            raise OptimisticConcurrencyError(
                f"stale expected version {expected}; current version is {int(row[0])}"
            )
