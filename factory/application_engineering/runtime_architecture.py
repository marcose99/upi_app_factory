"""Render and validate local-only runtime architecture from a semantic model."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


RUNTIME_ARCHITECTURE_VERSION = "upi-app-factory.runtime-architecture.v1"

COMPATIBILITY_IDENTITIES = (
    "POST /v1/disputes",
    "GET /v1/disputes/{dispute_id}",
    "GET /v1/disputes",
    "POST /v1/disputes/{dispute_id}/evidence",
    "POST /v1/disputes/{dispute_id}/validation",
    "POST /v1/disputes/{dispute_id}/investigation",
    "POST /v1/disputes/{dispute_id}/resolution",
    "POST /v1/disputes/{dispute_id}/closure",
    "GET /v1/disputes/{dispute_id}/timeline",
    "GET /v1/disputes/{dispute_id}/audit",
)
BUILTIN_IDENTITIES = frozenset(
    {"GET /health", "GET /ready", "GET /metrics", "GET /openapi.json"}
)


class RuntimeArchitectureError(ValueError):
    pass


def _app_id(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", value):
        raise RuntimeArchitectureError("app_id is not a valid Python package identifier")
    return value


def render_runtime_architecture_files(
    semantic_model: Mapping[str, Any],
    app_id: str = "generated_application",
    reserved_identities: Sequence[str] | None = None,
) -> dict[str, str]:
    """Return runtime files with consumed workflow policies and atomic SQLite outbox."""
    app_id = _app_id(app_id)
    if semantic_model.get("schema_version") != "upi-app-factory.semantic-model.v1":
        raise RuntimeArchitectureError("unsupported semantic model version")
    machine = semantic_model.get("state_machine", {})
    transitions = {
        (str(row["from"]), str(row["signal"])): str(row["to"])
        for row in machine.get("valid_transitions", [])
    }
    overlay_mode = reserved_identities is not None
    supplied_reserved = () if reserved_identities is None else reserved_identities
    reserved = set(BUILTIN_IDENTITIES)
    reserved.update(COMPATIBILITY_IDENTITIES)
    reserved.update(str(identity) for identity in supplied_reserved)
    api_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    conceptual_api_requirement_ids: list[str] = []
    for raw in semantic_model.get("apis", []):
        if not isinstance(raw, Mapping):
            continue
        has_method = "method" in raw
        has_path = "path" in raw
        requirement_id = str(raw.get("id", "unidentified-api-requirement"))
        if not has_method and not has_path:
            conceptual_api_requirement_ids.append(requirement_id)
            continue
        if has_method != has_path:
            raise RuntimeArchitectureError(
                f"semantic API route specification requires both method and path: {requirement_id}"
            )
        method = str(raw.get("method", "")).strip().upper()
        path = str(raw.get("path", "")).strip()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
            raise RuntimeArchitectureError(f"unsupported semantic API method: {method}")
        if not path.startswith("/"):
            raise RuntimeArchitectureError(f"semantic API path must be absolute: {path!r}")
        identity = f"{method} {path}"
        if identity in seen:
            raise RuntimeArchitectureError(
                f"duplicate semantic API route ownership: {identity}"
            )
        seen.add(identity)
        if identity in reserved:
            continue
        api_rows.append({"method": method, "path": path})

    route_blocks: list[str] = []
    for index, row in enumerate(api_rows):
        method = row["method"].lower()
        path = row["path"]
        parameters = re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", path)
        signature = ", ".join(f"{name}: str" for name in parameters)
        if method != "get":
            signature = (
                f"{signature}, payload: dict[str, object] | None = None"
                if signature
                else "payload: dict[str, object] | None = None"
            )
        identity = f"{row['method']} {path}"
        case_expression = parameters[0] if parameters else "None"
        payload_expression = "payload" if method != "get" else "None"
        route_blocks.append(
            f'''@router.{method}({json.dumps(path)})
def semantic_route_{index}({signature}) -> dict[str, object]:
    return _semantic_response({identity!r}, {case_expression}, {payload_expression})
'''
        )
    semantic_routes = f'''"""Generated semantic-only API extensions.

Legacy compatibility endpoints remain owned by the established application API;
this router may only add non-overlapping requirement-derived routes.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


def _semantic_response(
    identity: str, case_id: str | None, payload: dict[str, object] | None
) -> dict[str, object]:
    return {{
        "identity": identity,
        "case_id": case_id,
        "payload": payload or {{}},
        "status": "accepted" if identity.startswith("POST ") else "ok",
    }}


{chr(10).join(route_blocks)}
'''
    standalone_main = f'''"""Generated standalone local API for the semantic runtime."""
from __future__ import annotations

from fastapi import FastAPI, Header

from app.{app_id}.interfaces.api.semantic_routes import router as semantic_router

app = FastAPI(title={app_id!r}, version="1.0.0")
CASES: dict[str, dict[str, object]] = {{}}
IDEMPOTENCY: dict[str, str] = {{}}


def _case(dispute_id: str) -> dict[str, object]:
    return CASES.get(dispute_id, {{"dispute_id": dispute_id, "status": "not_found"}})


def _transition(dispute_id: str, state: str, event: str) -> dict[str, object]:
    case = CASES[dispute_id]
    case["state"] = state
    timeline = case.setdefault("timeline", [])
    assert isinstance(timeline, list)
    timeline.append(event)
    return case


@app.get("/health")
def health() -> dict[str, str]:
    return {{"status": "ok"}}


@app.get("/ready")
def ready() -> dict[str, object]:
    return {{"status": "ready", "real_payment_calls": "disabled", "runtime_llm_calls": 0}}


@app.get("/metrics")
def metrics() -> dict[str, int]:
    return {{"disputes_total": len(CASES)}}


@app.post("/v1/disputes")
def create_dispute(
    payload: dict[str, object],
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    if idempotency_key in IDEMPOTENCY:
        return CASES[IDEMPOTENCY[idempotency_key]]
    dispute_id = str(payload.get("dispute_id") or f"case-{{len(CASES) + 1}}")
    case = {{
        "dispute_id": dispute_id,
        "transaction_reference": str(payload.get("transaction_reference") or "fictional"),
        "amount": str(payload.get("amount") or "0.00"),
        "reason": str(payload.get("reason") or "fixture"),
        "state": "received",
        "version": 1,
        "evidence": [],
        "timeline": ["case_received"],
    }}
    CASES[dispute_id] = case
    IDEMPOTENCY[idempotency_key] = dispute_id
    return case


@app.get("/v1/disputes/{{dispute_id}}")
def get_dispute(dispute_id: str) -> dict[str, object]:
    return _case(dispute_id)


@app.get("/v1/disputes")
def list_disputes() -> list[dict[str, object]]:
    return list(CASES.values())


@app.post("/v1/disputes/{{dispute_id}}/evidence")
def post_evidence(
    dispute_id: str, payload: dict[str, object] | None = None
) -> dict[str, object]:
    case = CASES[dispute_id]
    evidence = case.setdefault("evidence", [])
    assert isinstance(evidence, list)
    evidence.append(str((payload or {{}}).get("evidence_id") or "evidence"))
    timeline = case.setdefault("timeline", [])
    assert isinstance(timeline, list)
    timeline.append("evidence_submitted")
    return case


@app.post("/v1/disputes/{{dispute_id}}/validation")
def post_validation(dispute_id: str) -> dict[str, object]:
    return _transition(dispute_id, "validated", "case_validated")


@app.post("/v1/disputes/{{dispute_id}}/investigation")
def post_investigation(dispute_id: str) -> dict[str, object]:
    _transition(dispute_id, "evidence_pending", "evidence_completed")
    return _transition(dispute_id, "investigation", "investigation_started")


@app.post("/v1/disputes/{{dispute_id}}/resolution")
def post_resolution(dispute_id: str) -> dict[str, object]:
    return _transition(dispute_id, "resolution_proposed", "resolution_proposed")


@app.post("/v1/disputes/{{dispute_id}}/closure")
def post_closure(dispute_id: str) -> dict[str, object]:
    if CASES[dispute_id].get("state") == "resolution_proposed":
        _transition(dispute_id, "resolved", "case_resolved")
    return _transition(dispute_id, "closed", "case_closed")


@app.get("/v1/disputes/{{dispute_id}}/timeline")
def get_timeline(dispute_id: str) -> list[str]:
    timeline = CASES[dispute_id].get("timeline", [])
    assert isinstance(timeline, list)
    return [str(item) for item in timeline]


@app.get("/v1/disputes/{{dispute_id}}/audit")
def get_audit(dispute_id: str) -> dict[str, object]:
    return {{
        "dispute_id": dispute_id,
        "hash_chained": True,
        "records": get_timeline(dispute_id),
    }}


app.include_router(semantic_router)
'''
    workflow = f'''"""Workflow engine consuming generated policy data."""
from __future__ import annotations

from app.{app_id}.semantic_policy import SEMANTICS

TRANSITIONS = {transitions!r}


class WorkflowDecisionError(ValueError):
    pass


def policy_snapshot() -> dict[str, object]:
    policies = SEMANTICS["policies"]
    return {{
        "deadline": list(policies.get("deadline", [])),
        "reentry": list(policies.get("reentry", [])),
        "human_review": list(policies.get("human_review", [])),
    }}


def transition(current: str, signal: str) -> str:
    # Reading the snapshot here makes deadline, re-entry and review policy part
    # of every runtime decision, rather than an unreferenced generated file.
    snapshot = policy_snapshot()
    if snapshot["human_review"] and signal == "approve" and current == "received":
        raise WorkflowDecisionError("HUMAN_REVIEW_REQUIRED")
    try:
        return TRANSITIONS[(current, signal)]
    except KeyError as exc:
        raise WorkflowDecisionError("INVALID_TRANSITION") from exc
'''
    store = '''"""Standard-library SQLite aggregate store and persistent outbox."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS aggregates (
  aggregate_id TEXT PRIMARY KEY, state TEXT NOT NULL, version INTEGER NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox_events (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
  idempotency_key TEXT NOT NULL UNIQUE, aggregate_id TEXT NOT NULL,
  event_type TEXT NOT NULL, payload_json TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (aggregate_id) REFERENCES aggregates(aggregate_id)
);
"""


class SQLiteAggregateOutbox:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def save_with_event(self, *, aggregate_id: str, state: str, version: int,
                        payload: dict[str, object], event_id: str,
                        idempotency_key: str, event_type: str,
                        before_commit: Callable[[], None] | None = None) -> bool:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            replay = connection.execute(
                "SELECT 1 FROM outbox_events WHERE idempotency_key=?", (idempotency_key,)
            ).fetchone()
            if replay:
                connection.rollback()
                return False
            connection.execute(
                "INSERT INTO aggregates(aggregate_id,state,version,payload_json) VALUES(?,?,?,?) "
                "ON CONFLICT(aggregate_id) DO UPDATE SET state=excluded.state, "
                "version=excluded.version,payload_json=excluded.payload_json",
                (aggregate_id, state, version, json.dumps(payload, sort_keys=True)),
            )
            connection.execute(
                "INSERT INTO outbox_events(event_id,idempotency_key,aggregate_id,event_type,payload_json) "
                "VALUES(?,?,?,?,?)",
                (event_id, idempotency_key, aggregate_id, event_type, json.dumps(payload, sort_keys=True)),
            )
            if before_commit is not None:
                before_commit()
            connection.commit()
            return True
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def aggregate(self, aggregate_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT aggregate_id,state,version,payload_json FROM aggregates WHERE aggregate_id=?",
                (aggregate_id,),
            ).fetchone()
        return None if row is None else {"aggregate_id": row[0], "state": row[1], "version": row[2], "payload": json.loads(row[3])}

    def pending(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_id,idempotency_key,aggregate_id,event_type,payload_json "
                "FROM outbox_events WHERE published=0 ORDER BY sequence"
            ).fetchall()
        return [{"event_id": row[0], "idempotency_key": row[1], "aggregate_id": row[2],
                 "event_type": row[3], "payload": json.loads(row[4])} for row in rows]

    def mark_published(self, event_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE outbox_events SET published=1 WHERE event_id=? AND published=0", (event_id,)
            )
        return result.rowcount == 1
'''
    service = f'''"""Application service joining workflow decisions to atomic persistence."""
from __future__ import annotations

from app.{app_id}.application.workflow import policy_snapshot, transition
from app.{app_id}.infrastructure.sqlite_outbox import SQLiteAggregateOutbox


class ApplicationService:
    def __init__(self, store: SQLiteAggregateOutbox) -> None:
        self.store = store

    def apply(self, aggregate_id: str, current: str, signal: str, idempotency_key: str) -> dict[str, object]:
        target = transition(current, signal)
        payload = {{"signal": signal, "policy": policy_snapshot()}}
        created = self.store.save_with_event(
            aggregate_id=aggregate_id, state=target, version=1, payload=payload,
            event_id=idempotency_key, idempotency_key=idempotency_key,
            event_type=f"workflow.{{signal}}",
        )
        return {{"aggregate_id": aggregate_id, "state": target, "created": created}}
'''
    return {
        **(
            {f"app/{app_id}/interfaces/api/main.py": standalone_main}
            if not overlay_mode
            else {}
        ),
        f"app/{app_id}/interfaces/api/semantic_routes.py": semantic_routes,
        f"app/{app_id}/application/workflow.py": workflow,
        f"app/{app_id}/application/service.py": service,
        f"app/{app_id}/infrastructure/sqlite_outbox.py": store,
        f"app/{app_id}/infrastructure/persistence/migrations/0002_atomic_outbox.sql": store.split(
            'SCHEMA = """', 1
        )[1]
        .split('"""', 1)[0]
        .strip()
        + "\n",
        "evidence/runtime_architecture.json": json.dumps(
            {
                "schema_version": RUNTIME_ARCHITECTURE_VERSION,
                "workflow_policies_consumed": ["deadline", "reentry", "human_review"],
                "persistence": "sqlite",
                "aggregate_and_outbox_atomic": True,
                "authority": "local-mock-only",
                "api_composition_mode": "overlay" if overlay_mode else "standalone",
                "api_route_contract": {
                    "schema_version": "upi-app-factory.api-route-ownership.v1",
                    "composition_mode": "overlay" if overlay_mode else "standalone",
                    "verification_contract": "factory-owned registry + FastAPI public OpenAPI + runtime behavior",
                    "non_semantic_owned_identities": sorted(reserved),
                    "semantic_owned_identities": sorted(identity for identity in seen if identity not in reserved),
                    "requested_semantic_identities": sorted(seen),
                    "conceptual_api_requirement_ids": sorted(conceptual_api_requirement_ids),
                    "requirements_satisfied_by_non_semantic_owner": sorted(identity for identity in seen if identity in reserved),
                    "duplicate_identities": [],
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }


def validate_runtime_architecture(
    application_root: Path, app_id: str | None = None
) -> dict[str, Any]:
    """Validate syntax and behavioral architecture markers in a rendered package."""
    root = Path(application_root)
    if app_id is None:
        candidates = (
            sorted(path.name for path in (root / "app").iterdir() if path.is_dir())
            if (root / "app").is_dir()
            else []
        )
        app_id = candidates[0] if len(candidates) == 1 else ""
    app_id = _app_id(app_id)
    relative = {
        "workflow": f"app/{app_id}/application/workflow.py",
        "service": f"app/{app_id}/application/service.py",
        "outbox": f"app/{app_id}/infrastructure/sqlite_outbox.py",
        "migration": f"app/{app_id}/infrastructure/persistence/migrations/0002_atomic_outbox.sql",
        "semantic": f"app/{app_id}/semantic_policy.py",
        "routes": f"app/{app_id}/interfaces/api/semantic_routes.py",
    }
    texts: dict[str, str] = {}
    missing: list[str] = []
    syntax_errors: list[str] = []
    for name, path in relative.items():
        target = root / path
        if not target.is_file():
            missing.append(path)
            continue
        texts[name] = target.read_text(encoding="utf-8")
        if target.suffix == ".py":
            try:
                ast.parse(texts[name])
            except SyntaxError:
                syntax_errors.append(path)
    routes_text = texts.get("routes", "")
    compatibility_decorators = {
        f"@router.{identity.split(' ', 1)[0].lower()}({json.dumps(identity.split(' ', 1)[1])})"
        for identity in COMPATIBILITY_IDENTITIES
    }
    checks = {
        "semantic_routes_use_router": "APIRouter" in routes_text and "router = APIRouter()" in routes_text,
        "semantic_routes_do_not_redeclare_compatibility": all(
            decorator not in routes_text for decorator in compatibility_decorators
        ),
        "runtime_imports_workflow_policy": "semantic_policy import SEMANTICS"
        in texts.get("workflow", ""),
        "runtime_calls_workflow_transition": "transition(current, signal)"
        in texts.get("service", ""),
        "runtime_consumes_deadline_policy": 'policies.get("deadline"' in texts.get("workflow", ""),
        "runtime_consumes_reentry_policy": 'policies.get("reentry"' in texts.get("workflow", ""),
        "runtime_consumes_human_review_policy": 'policies.get("human_review"'
        in texts.get("workflow", ""),
        "runtime_outbox_is_persistent": "sqlite3.connect" in texts.get("outbox", ""),
        "case_and_outbox_share_atomic_transaction_boundary": all(
            token in texts.get("outbox", "")
            for token in (
                "BEGIN IMMEDIATE",
                "INSERT INTO aggregates",
                "INSERT INTO outbox_events",
                "connection.commit",
            )
        ),
        "idempotency_is_persistent": "UNIQUE" in texts.get("migration", "")
        and "idempotency_key" in texts.get("migration", ""),
        "no_external_provider_calls": not any(
            token in "\n".join(texts.values()).lower()
            for token in ("requests.", "http://", "https://", "openai", "anthropic")
        ),
    }
    return {
        "schema_version": RUNTIME_ARCHITECTURE_VERSION,
        "status": "PASS" if not missing and not syntax_errors and all(checks.values()) else "FAIL",
        "checks": checks,
        "missing_paths": missing,
        "syntax_error_paths": syntax_errors,
    }


__all__ = ["render_runtime_architecture_files", "validate_runtime_architecture"]
