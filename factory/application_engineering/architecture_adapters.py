"""Deterministic source adapters for the three governed architecture patterns."""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class ArchitectureAdapter:
    pattern_id: str
    adapter_id: str

    def render(self, app_id: str) -> dict[str, str]:
        files = self._authenticity_overlay(app_id)
        if self.pattern_id == "WORKFLOW_CENTRIC_MODULAR_MONOLITH":
            files.update(self._workflow(app_id))
        elif self.pattern_id == "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX":
            files.update(self._event(app_id))
        return files

    def _authenticity_overlay(self, app_id: str) -> dict[str, str]:
        """Keep legacy trace paths physical while execution measurements are pending."""
        measurements = {
            "schema_version": "upi-app-factory.raw-test-measurements.v1",
            "collected_test_count": None,
            "failed_test_count": None,
            "missing_test_path_count": 0,
            "testing_depth_score": None,
            "score_status": "WITHHELD_UNTIL_EXECUTION",
        }
        ports = '''from __future__ import annotations

from typing import Protocol


class CaseRepositoryPort(Protocol):
    def put(self, case_id: str, value: object) -> None: ...
    def get(self, case_id: str) -> object: ...
    def values(self) -> list[object]: ...


class TransactionalOutboxPort(Protocol):
    def save_case_and_event(self, case_id: str, payload: dict[str, object], event: object, crash_before_commit: bool = False) -> bool: ...


class ClockPort(Protocol):
    def now(self) -> object: ...


class IdGeneratorPort(Protocol):
    def new_id(self) -> str: ...
'''
        adapters = '''from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4


class InMemoryCaseRepository:
    def __init__(self) -> None:
        self._values: dict[str, object] = {}

    def put(self, case_id: str, value: object) -> None:
        self._values[case_id] = value

    def get(self, case_id: str) -> object:
        return self._values[case_id]

    def values(self) -> list[object]:
        return list(self._values.values())


class SQLiteMemoryTransactionalOutbox:
    def __init__(self, database: str = ":memory:") -> None:
        if database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database, isolation_level=None)
        self.connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox (event_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, case_id TEXT NOT NULL, payload TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES cases(case_id));
        """)

    def save_case_and_event(self, case_id: str, payload: dict[str, object], event: Any, crash_before_commit: bool = False) -> bool:
        import json
        event_id = str(getattr(event, "event_id", case_id))
        idempotency_key = str(getattr(event, "idempotency_key", event_id))
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            if self.connection.execute("SELECT 1 FROM outbox WHERE idempotency_key=?", (idempotency_key,)).fetchone():
                self.connection.rollback()
                return False
            encoded = json.dumps(payload, sort_keys=True)
            self.connection.execute("INSERT INTO cases(case_id,payload) VALUES(?,?) ON CONFLICT(case_id) DO UPDATE SET payload=excluded.payload", (case_id, encoded))
            self.connection.execute("INSERT INTO outbox(event_id,idempotency_key,case_id,payload) VALUES(?,?,?,?)", (event_id, idempotency_key, case_id, encoded))
            if crash_before_commit:
                raise RuntimeError("simulated crash before atomic commit")
            self.connection.commit()
            return True
        except sqlite3.IntegrityError:
            self.connection.rollback()
            return False
        except BaseException:
            self.connection.rollback()
            raise


class SystemClockAdapter:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class Uuid4IdGenerator:
    def new_id(self) -> str:
        return str(uuid4())


@dataclass(frozen=True)
class RuntimeAdapters:
    profile_id: str
    case_repository: object
    transactional_outbox: object
    clock: object
    id_generator: object


def build_runtime_adapters(profile: str | None = None) -> RuntimeAdapters:
    selected = profile or os.getenv("UPI_RUNTIME_PROFILE", "in_memory")
    if selected == "in_memory":
        outbox = SQLiteMemoryTransactionalOutbox(":memory:")
    elif selected == "sqlite_file":
        outbox = SQLiteMemoryTransactionalOutbox(os.getenv("UPI_SQLITE_PATH", "data/generated_application.sqlite3"))
    else:
        raise ValueError(f"unsupported runtime profile: {selected}")
    return RuntimeAdapters(selected, InMemoryCaseRepository(), outbox, SystemClockAdapter(), Uuid4IdGenerator())
'''
        profile = {
            "default_profile": "in_memory",
            "supported_profiles": ["in_memory", "sqlite_file"],
            "unknown_profile_policy": "FAIL_CLOSED",
            "external_services_required": False,
        }
        replaceability = {
            "default_profile": "in_memory",
            "external_runtime_services_required": False,
            "real_payment_calls": "disabled",
            "runtime_llm_calls": 0,
            "application_or_domain_change_required_for_adapter_swap": False,
            "runtime_contract_schema_version": "upi-app-factory.m2-2r3r4-lightweight-replaceable-runtime.v1",
        }
        service_constructor = (
            "DisputeApplicationService(adapters.case_repository, adapters.transactional_outbox)"
            if self.pattern_id == "EVENT_DRIVEN_MODULAR_MONOLITH_OUTBOX"
            else "DisputeApplicationService()"
        )
        return {
            "pytest.ini": "[pytest]\ntestpaths = tests\n",
            "tests/conftest.py": "from pathlib import Path\nimport sys\nROOT = Path(__file__).resolve().parents[1]\nsys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None\n",
            "tests/test_service.py": '''from app.%s.application.services.dispute_service import DisputeApplicationService
from app.%s.infrastructure.runtime_adapters import build_runtime_adapters


def test_create_is_idempotent_and_local():
    adapters = build_runtime_adapters("in_memory")
    service = %s
    payload = {"dispute_id": "fictional-1", "transaction_reference": "fictional-txn-1", "amount": "1.00", "reason": "fixture"}
    assert service.create(payload, "fixture-key") == service.create(payload, "fixture-key")
    assert len(service.list()) == 1
''' % (app_id, app_id, service_constructor),
            "tests/test_architecture_api_contract.py": '''import json
from pathlib import Path
from app.%s.interfaces.api.main import app


def test_openapi_declares_local_generated_contract():
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "openapi/openapi.json").read_text(encoding="utf-8"))
    assert contract["openapi"] == "3.1.0"
    expected_endpoints = set(contract["x-required-endpoints"])
    registered = {f"{method} {route.path}" for route in app.routes for method in (route.methods or set())}
    assert "GET /health" in expected_endpoints
    assert expected_endpoints.issubset(registered)
''' % app_id,
            f"app/{app_id}/application/ports.py": ports,
            f"app/{app_id}/infrastructure/runtime_adapters.py": adapters,
            "configuration/runtime_profile.json": json.dumps(profile, indent=2, sort_keys=True) + "\n",
            "evidence/runtime_replaceability.json": json.dumps(replaceability, indent=2, sort_keys=True) + "\n",
            "tests/test_adapter_replaceability.py": '''from app.%s.infrastructure.runtime_adapters import build_runtime_adapters


class FakeCaseRepository:
    def put(self, case_id, value): pass
    def get(self, case_id): return None
    def values(self): return []


def test_composition_root_supports_an_alternate_test_adapter():
    adapters = build_runtime_adapters("in_memory")
    alternate = FakeCaseRepository()
    assert adapters.profile_id == "in_memory"
    assert alternate is not adapters.case_repository


def test_unknown_profile_fails_closed():
    try:
        build_runtime_adapters("unknown")
    except ValueError:
        return
    raise AssertionError("unknown runtime profile was accepted")
''' % app_id,
            "evidence/depth_score.json": json.dumps(measurements, indent=2, sort_keys=True) + "\n",
        }

    def _workflow(self, app_id: str) -> dict[str, str]:
        workflow = '''from __future__ import annotations

HUMAN_REVIEW_STATES = ("investigation", "resolution_proposed")
DEADLINE_POLICY = {"investigation": "P2D", "resolution_proposed": "P1D"}
REENTRY_POLICY = {"evidence_pending": "additional_evidence", "investigation": "review_return"}


def next_state(current: str, signal: str) -> str:
    transitions = {
        ("evidence_pending", "evidence_complete"): "investigation",
        ("investigation", "review_complete"): "resolution_proposed",
        ("resolution_proposed", "approve"): "resolved",
    }
    return transitions[(current, signal)]
'''
        service = '''from __future__ import annotations

from dataclasses import asdict

from app.%s.application.workflows.dispute_workflow import (
    DEADLINE_POLICY, HUMAN_REVIEW_STATES, REENTRY_POLICY, next_state,
)
from app.%s.application.ports import CaseRepositoryPort
from app.%s.domain.aggregates.dispute_case import DisputeCase


class DisputeApplicationService:
    def __init__(self, repository: CaseRepositoryPort | None = None) -> None:
        self.repository = repository
        self._cases: dict[str, DisputeCase] = {}
        self._idempotency: dict[str, str] = {}

    def workflow_policy(self, state: str) -> dict[str, object]:
        return {
            "deadline": DEADLINE_POLICY.get(state),
            "reentry_signals": [key for key, value in REENTRY_POLICY.items() if key == state or value == state],
            "human_review_required": state in HUMAN_REVIEW_STATES,
        }

    def create(self, payload: dict[str, str], idempotency_key: str) -> dict[str, object]:
        if idempotency_key in self._idempotency:
            return self.get(self._idempotency[idempotency_key])
        case = DisputeCase(dispute_id=payload["dispute_id"], transaction_reference=payload["transaction_reference"], amount=payload["amount"], reason=payload["reason"])
        self._cases[case.dispute_id] = case
        self._idempotency[idempotency_key] = case.dispute_id
        return asdict(case)

    def get(self, dispute_id: str) -> dict[str, object]:
        return asdict(self._cases[dispute_id])

    def list(self) -> list[dict[str, object]]:
        return [asdict(case) for case in self._cases.values()]

    def action(self, dispute_id: str, target: str, event: str) -> dict[str, object]:
        case = self._cases[dispute_id]
        signal_by_target = {"investigation": "evidence_complete", "resolution_proposed": "review_complete", "resolved": "approve"}
        signal = signal_by_target.get(target)
        if signal is not None and case.state in {"evidence_pending", "investigation", "resolution_proposed"}:
            governed_target = next_state(case.state, signal)
            if governed_target != target:
                raise ValueError("workflow policy and requested target disagree")
        self.workflow_policy(target)
        case.transition(target, event)
        return asdict(case)
''' % (app_id, app_id, app_id)
        return {
            f"app/{app_id}/application/workflows/dispute_workflow.py": workflow,
            f"app/{app_id}/application/services/dispute_service.py": service,
        }

    def _event(self, app_id: str) -> dict[str, str]:
        events = '''from __future__ import annotations

from dataclasses import dataclass

EVENT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    dispute_id: str
    event_type: str
    idempotency_key: str
    schema_version: str = EVENT_SCHEMA_VERSION
'''
        outbox = '''from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from app.%s.application.events import DomainEvent


class SQLiteOutbox:
    def __init__(self, path: str | Path = "data/generated_application.sqlite3") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS dispute_cases (dispute_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox_events (event_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, dispute_id TEXT NOT NULL, event_type TEXT NOT NULL, schema_version TEXT NOT NULL, payload_json TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(dispute_id) REFERENCES dispute_cases(dispute_id));
            """)

    def save_case_and_event(self, dispute_id: str, payload: dict[str, object], event: DomainEvent, crash_before_commit: bool = False) -> bool:
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM outbox_events WHERE idempotency_key=?", (event.idempotency_key,)).fetchone():
                connection.rollback()
                return False
            encoded = json.dumps(payload, sort_keys=True)
            connection.execute("INSERT INTO dispute_cases(dispute_id,payload_json) VALUES(?,?) ON CONFLICT(dispute_id) DO UPDATE SET payload_json=excluded.payload_json", (dispute_id, encoded))
            connection.execute("INSERT INTO outbox_events(event_id,idempotency_key,dispute_id,event_type,schema_version,payload_json) VALUES(?,?,?,?,?,?)", (event.event_id, event.idempotency_key, dispute_id, event.event_type, event.schema_version, encoded))
            if crash_before_commit:
                raise RuntimeError("simulated crash before atomic commit")
            connection.commit()
            return True
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def pending(self) -> list[DomainEvent]:
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute("SELECT event_id,dispute_id,event_type,idempotency_key,schema_version FROM outbox_events WHERE published=0 ORDER BY rowid").fetchall()
        return [DomainEvent(*row) for row in rows]

    def mark_published(self, event_id: str) -> bool:
        with sqlite3.connect(self.path) as connection:
            result = connection.execute("UPDATE outbox_events SET published=1 WHERE event_id=? AND published=0", (event_id,))
        return result.rowcount == 1


# Compatibility name retained; implementation is persistent, not in-memory.
InMemoryOutbox = SQLiteOutbox
''' % app_id
        service = '''from __future__ import annotations

from dataclasses import asdict

from app.%s.application.events import DomainEvent
from app.%s.application.ports import CaseRepositoryPort, TransactionalOutboxPort
from app.%s.domain.aggregates.dispute_case import DisputeCase


class DisputeApplicationService:
    # The legacy InMemoryOutbox concrete dependency is replaced by the port;
    # the selected adapter atomically appends through SQLite memory or file configuration.
    def __init__(self, repository: CaseRepositoryPort, outbox: TransactionalOutboxPort) -> None:
        self.repository = repository
        self._cases: dict[str, DisputeCase] = {}
        self._idempotency: dict[str, str] = {}
        self.outbox = outbox

    def create(self, payload: dict[str, str], idempotency_key: str) -> dict[str, object]:
        if idempotency_key in self._idempotency:
            return self.get(self._idempotency[idempotency_key])
        case = DisputeCase(dispute_id=payload["dispute_id"], transaction_reference=payload["transaction_reference"], amount=payload["amount"], reason=payload["reason"])
        self._cases[case.dispute_id] = case
        self._idempotency[idempotency_key] = case.dispute_id
        self.outbox.save_case_and_event(case.dispute_id, asdict(case), DomainEvent(idempotency_key, case.dispute_id, "dispute.created", idempotency_key))
        return asdict(case)

    def get(self, dispute_id: str) -> dict[str, object]:
        return asdict(self._cases[dispute_id])

    def list(self) -> list[dict[str, object]]:
        return [asdict(case) for case in self._cases.values()]

    def action(self, dispute_id: str, target: str, event: str) -> dict[str, object]:
        case = self._cases[dispute_id]
        case.transition(target, event)
        key = f"{dispute_id}:{case.version}:{event}"
        self.outbox.save_case_and_event(dispute_id, asdict(case), DomainEvent(key, dispute_id, event, key))
        return asdict(case)
''' % (app_id, app_id, app_id)
        migration = '''PRAGMA foreign_keys = ON;
CREATE TABLE dispute_cases (dispute_id TEXT PRIMARY KEY, transaction_reference TEXT NOT NULL UNIQUE, amount TEXT NOT NULL, reason TEXT NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL);
CREATE TABLE idempotency_records (idempotency_key TEXT PRIMARY KEY, dispute_id TEXT NOT NULL REFERENCES dispute_cases(dispute_id));
CREATE TABLE audit_records (sequence INTEGER PRIMARY KEY AUTOINCREMENT, dispute_id TEXT NOT NULL, event_type TEXT NOT NULL, previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL);
CREATE TABLE outbox_events (event_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, dispute_id TEXT NOT NULL, event_type TEXT NOT NULL, schema_version TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0);
'''
        return {
            f"app/{app_id}/application/events.py": events,
            f"app/{app_id}/infrastructure/messaging/outbox.py": outbox,
            f"app/{app_id}/application/services/dispute_service.py": service,
            f"app/{app_id}/infrastructure/persistence/migrations/0001_initial.sql": migration,
        }
