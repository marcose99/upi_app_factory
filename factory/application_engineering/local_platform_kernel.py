from __future__ import annotations

import contextvars
import dataclasses
import datetime as dt
import decimal
import hashlib
import hmac
import json
import logging
import re
import secrets
import sqlite3
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, Protocol, TypeVar


T = TypeVar("T")
REDACTED = "[REDACTED]"
SENSITIVE_PATTERN = re.compile(r"(secret|token|password|authorization|api[_-]?key)", re.I)


class KernelError(RuntimeError):
    pass


class OptimisticConcurrencyError(KernelError):
    pass


class AuthorizationDenied(KernelError):
    pass


@dataclasses.dataclass(frozen=True)
class TypedId:
    namespace: str
    value: str

    def __post_init__(self) -> None:
        if not self.namespace or not re.fullmatch(r"[a-z][a-z0-9_]*", self.namespace):
            raise ValueError("TypedId namespace must be lower snake case")
        if not self.value or not re.fullmatch(r"[A-Za-z0-9_.:-]+", self.value):
            raise ValueError("TypedId value contains unsupported characters")

    def __str__(self) -> str:
        return f"{self.namespace}:{self.value}"


@dataclasses.dataclass(frozen=True)
class Money:
    amount: decimal.Decimal
    currency: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise ValueError("currency must be ISO-like uppercase 3-letter code")
        quantized = self.amount.quantize(decimal.Decimal("0.01"))
        if quantized < decimal.Decimal("0.00"):
            raise ValueError("money amount cannot be negative")
        object.__setattr__(self, "amount", quantized)

    @classmethod
    def of(cls, amount: str | int | decimal.Decimal, currency: str) -> Money:
        return cls(decimal.Decimal(str(amount)), currency)


class Clock(Protocol):
    def now(self) -> dt.datetime: ...


class SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)


@dataclasses.dataclass
class FixedClock:
    instant: dt.datetime

    def now(self) -> dt.datetime:
        return self.instant


class DeterministicIdGenerator:
    def __init__(self, seed: str) -> None:
        self._seed = seed
        self._counters: dict[str, int] = defaultdict(int)

    def new_id(self, namespace: str) -> TypedId:
        self._counters[namespace] += 1
        raw = f"{self._seed}:{namespace}:{self._counters[namespace]}".encode()
        return TypedId(namespace, hashlib.sha256(raw).hexdigest()[:24])


@dataclasses.dataclass(frozen=True)
class Command:
    command_id: TypedId
    correlation_id: str


@dataclasses.dataclass(frozen=True)
class Query:
    query_id: TypedId
    correlation_id: str


class RepositoryPort(Protocol[T]):
    def get(self, item_id: TypedId) -> T | None: ...

    def save(self, item: T, expected_version: int | None = None) -> None: ...


class UnitOfWorkPort(Protocol):
    def __enter__(self) -> UnitOfWorkPort: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...

    @property
    def connection(self) -> sqlite3.Connection: ...


@dataclasses.dataclass(frozen=True)
class LocalPlatformConfig:
    database_path: Path
    environment: str = "local"
    service_name: str = "upi_app_factory"
    runtime_llm_calls_default: int = 0
    real_payment_calls: str = "disabled"

    def __post_init__(self) -> None:
        for value in dataclasses.asdict(self).values():
            if isinstance(value, str) and SENSITIVE_PATTERN.search(value):
                raise ValueError("configuration must not contain secret-bearing fields")
        if self.runtime_llm_calls_default != 0:
            raise ValueError("default runtime LLM calls must be zero")
        if self.real_payment_calls != "disabled":
            raise ValueError("real payment/provider calls must remain disabled")


class SQLiteConnectionFactory:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection


@dataclasses.dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


KERNEL_MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        "kernel_ledger",
        """
        CREATE TABLE IF NOT EXISTS kernel_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        """,
    ),
    Migration(
        2,
        "idempotency",
        """
        CREATE TABLE IF NOT EXISTS idempotency_records (
            request_key TEXT PRIMARY KEY,
            request_hash TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """,
    ),
    Migration(
        3,
        "audit_log",
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL UNIQUE
        );
        """,
    ),
    Migration(
        4,
        "outbox",
        """
        CREATE TABLE IF NOT EXISTS outbox_messages (
            message_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            published_at TEXT
        );
        """,
    ),
    Migration(
        5,
        "versioned_items",
        """
        CREATE TABLE IF NOT EXISTS kernel_items (
            item_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            version INTEGER NOT NULL
        );
        """,
    ),
)


class SQLiteMigrator:
    def __init__(self, migrations: Iterable[Migration] = KERNEL_MIGRATIONS) -> None:
        self.migrations = tuple(sorted(migrations, key=lambda migration: migration.version))

    def apply(self, connection: sqlite3.Connection, clock: Clock) -> None:
        with connection:
            connection.execute(KERNEL_MIGRATIONS[0].sql)
            rows = connection.execute(
                "SELECT version, checksum FROM kernel_migrations ORDER BY version"
            ).fetchall()
            applied = {int(row["version"]): str(row["checksum"]) for row in rows}
            for migration in self.migrations:
                checksum = hashlib.sha256(migration.sql.encode("utf-8")).hexdigest()
                if migration.version in applied:
                    if not hmac.compare_digest(applied[migration.version], checksum):
                        raise KernelError(f"migration checksum drift: {migration.version}")
                    continue
                connection.executescript(migration.sql)
                connection.execute(
                    "INSERT INTO kernel_migrations(version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                    (migration.version, migration.name, checksum, clock.now().isoformat()),
                )
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                raise KernelError(f"sqlite integrity check failed: {result}")


class SQLiteUnitOfWork:
    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self._factory = factory
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise KernelError("unit of work is not active")
        return self._connection

    def __enter__(self) -> SQLiteUnitOfWork:
        self._connection = self._factory.connect()
        self._connection.execute("BEGIN")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        assert self._connection is not None
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
            self._connection = None


class SQLiteVersionedRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def get(self, item_id: TypedId) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT payload_json, version FROM kernel_items WHERE item_id = ?", (str(item_id),)
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise KernelError("stored kernel item payload must be a JSON object")
        payload["version"] = int(row["version"])
        return payload

    def save(self, item_id: TypedId, payload: dict[str, Any], expected_version: int | None = None) -> int:
        current = self.get(item_id)
        if current is None:
            if expected_version not in (None, 0):
                raise OptimisticConcurrencyError("item does not exist at expected version")
            self.connection.execute(
                "INSERT INTO kernel_items(item_id, payload_json, version) VALUES (?, ?, 1)",
                (str(item_id), json.dumps(payload, sort_keys=True)),
            )
            return 1
        current_version = int(current["version"])
        if expected_version is not None and current_version != expected_version:
            raise OptimisticConcurrencyError("optimistic concurrency conflict")
        next_version = current_version + 1
        self.connection.execute(
            "UPDATE kernel_items SET payload_json = ?, version = ? WHERE item_id = ? AND version = ?",
            (json.dumps(payload, sort_keys=True), next_version, str(item_id), current_version),
        )
        if self.connection.total_changes < 1:
            raise OptimisticConcurrencyError("optimistic update failed")
        return next_version


class IdempotencyStore:
    def __init__(self, connection: sqlite3.Connection, clock: Clock) -> None:
        self.connection = connection
        self.clock = clock

    def replay_or_record(
        self, request_key: str, request_body: dict[str, Any], handler: Callable[[], dict[str, Any]]
    ) -> tuple[dict[str, Any], bool]:
        request_hash = hashlib.sha256(json.dumps(request_body, sort_keys=True).encode()).hexdigest()
        row = self.connection.execute(
            "SELECT request_hash, result_json FROM idempotency_records WHERE request_key = ?",
            (request_key,),
        ).fetchone()
        if row is not None:
            if not hmac.compare_digest(str(row["request_hash"]), request_hash):
                raise KernelError("idempotency key reused with different request")
            return json.loads(row["result_json"]), True
        result = handler()
        self.connection.execute(
            """
            INSERT INTO idempotency_records(request_key, request_hash, result_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                request_key,
                request_hash,
                json.dumps(result, sort_keys=True),
                self.clock.now().isoformat(),
            ),
        )
        return result, False


class AuditLog:
    GENESIS = "0" * 64

    def __init__(self, connection: sqlite3.Connection, clock: Clock) -> None:
        self.connection = connection
        self.clock = clock

    def append(self, actor_id: str, action: str, target: str, payload: dict[str, Any]) -> str:
        previous = self.connection.execute(
            "SELECT record_hash FROM audit_log ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        previous_hash = self.GENESIS if previous is None else str(previous["record_hash"])
        occurred_at = self.clock.now().isoformat()
        payload_json = json.dumps(payload, sort_keys=True)
        body = "|".join([occurred_at, actor_id, action, target, payload_json, previous_hash])
        record_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        self.connection.execute(
            """
            INSERT INTO audit_log(
                occurred_at, actor_id, action, target, payload_json, previous_hash, record_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (occurred_at, actor_id, action, target, payload_json, previous_hash, record_hash),
        )
        return record_hash

    def verify(self) -> bool:
        previous_hash = self.GENESIS
        rows = self.connection.execute(
            "SELECT * FROM audit_log ORDER BY sequence"
        ).fetchall()
        for row in rows:
            body = "|".join(
                [
                    str(row["occurred_at"]),
                    str(row["actor_id"]),
                    str(row["action"]),
                    str(row["target"]),
                    str(row["payload_json"]),
                    previous_hash,
                ]
            )
            expected = hashlib.sha256(body.encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous_hash or row["record_hash"] != expected:
                return False
            previous_hash = str(row["record_hash"])
        return True


class TransactionalOutbox:
    def __init__(self, connection: sqlite3.Connection, clock: Clock) -> None:
        self.connection = connection
        self.clock = clock

    def enqueue(self, message_id: TypedId, topic: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT INTO outbox_messages(message_id, topic, payload_json, occurred_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(message_id), topic, json.dumps(payload, sort_keys=True), self.clock.now().isoformat()),
        )

    def pending(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT message_id, topic, payload_json FROM outbox_messages WHERE published_at IS NULL ORDER BY occurred_at"
        ).fetchall()
        return [
            {"message_id": row["message_id"], "topic": row["topic"], "payload": json.loads(row["payload_json"])}
            for row in rows
        ]


@dataclasses.dataclass(frozen=True)
class Principal:
    principal_id: str
    roles: frozenset[str]


class AuthorizationPort(Protocol):
    def require(self, principal: Principal, permission: str, resource: str) -> None: ...


class FictionalLocalAuthorizer:
    def __init__(self, grants: dict[str, set[str]]) -> None:
        self.grants = grants

    def require(self, principal: Principal, permission: str, resource: str) -> None:
        allowed = set()
        for role in principal.roles:
            allowed.update(self.grants.get(role, set()))
        if permission not in allowed:
            raise AuthorizationDenied(f"principal {principal.principal_id} cannot {permission} {resource}")


_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "phase54_correlation_id", default="missing"
)


class CorrelationContext:
    def __init__(self, correlation_id: str) -> None:
        self.correlation_id = correlation_id
        self._token: contextvars.Token[str] | None = None

    def __enter__(self) -> CorrelationContext:
        self._token = _correlation_id.set(self.correlation_id)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._token is not None:
            _correlation_id.reset(self._token)

    @staticmethod
    def current() -> str:
        return _correlation_id.get()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if SENSITIVE_PATTERN.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class JsonRedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "correlation_id": CorrelationContext.current(),
        }
        extra = getattr(record, "payload", None)
        if isinstance(extra, dict):
            payload["payload"] = redact(extra)
        return json.dumps(payload, sort_keys=True)


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)

    def increment(self, name: str, amount: float = 1.0, **labels: str) -> None:
        self._counters[self._key(name, labels)] += amount

    def get(self, name: str, **labels: str) -> float:
        return self._counters[self._key(name, labels)]

    def expose_text(self) -> str:
        lines = []
        for key in sorted(self._counters):
            lines.append(f"{key} {self._counters[key]:g}")
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        rendered = ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))
        return f"{name}{{{rendered}}}"


@dataclasses.dataclass(frozen=True)
class HealthContribution:
    name: str
    healthy: bool
    detail: str


class HealthRegistry:
    def __init__(self) -> None:
        self._contributors: dict[str, Callable[[], HealthContribution]] = {}

    def register(self, name: str, contributor: Callable[[], HealthContribution]) -> None:
        self._contributors[name] = contributor

    def report(self) -> dict[str, Any]:
        contributions = [contributor() for _, contributor in sorted(self._contributors.items())]
        return {
            "status": "ready" if all(item.healthy for item in contributions) else "not_ready",
            "contributors": [dataclasses.asdict(item) for item in contributions],
        }


@dataclasses.dataclass(frozen=True)
class ProblemResponse:
    type: str
    title: str
    status: int
    detail: str
    correlation_id: str

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class InMemoryRepository(Generic[T]):
    def __init__(self) -> None:
        self.items: dict[str, tuple[T, int]] = {}

    def get(self, item_id: TypedId) -> T | None:
        item = self.items.get(str(item_id))
        return None if item is None else item[0]

    def save(self, item_id: TypedId, item: T, expected_version: int | None = None) -> int:
        current = self.items.get(str(item_id))
        if current is None:
            if expected_version not in (None, 0):
                raise OptimisticConcurrencyError("missing item")
            self.items[str(item_id)] = (item, 1)
            return 1
        if expected_version is not None and current[1] != expected_version:
            raise OptimisticConcurrencyError("in-memory concurrency conflict")
        version = current[1] + 1
        self.items[str(item_id)] = (item, version)
        return version


def canonical_json_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deterministic_evidence_bundle(paths: Iterable[Path]) -> dict[str, Any]:
    entries = [{"path": str(path), "sha256": file_hash(path)} for path in sorted(paths)]
    return {"format": "phase54-evidence/v1", "files": entries, "bundle_hash": canonical_json_hash({"files": entries})}


def make_temp_database() -> Path:
    name = f"upi_app_factory_phase54_{secrets.token_hex(8)}.sqlite3"
    return Path(tempfile.gettempdir()) / name


def sqlite_ready_contribution(factory: SQLiteConnectionFactory) -> HealthContribution:
    started = time.monotonic()
    try:
        with factory.connect() as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return HealthContribution("sqlite", result == "ok", f"integrity={result};elapsed_ms={elapsed_ms}")
    except sqlite3.Error as exc:
        return HealthContribution("sqlite", False, exc.__class__.__name__)
