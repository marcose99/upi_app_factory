"""Executable, hermetic test generation for the versioned finite semantic model."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from typing import Any, Mapping


TEST_MODEL_VERSION = "upi-app-factory.executable-test-model.v1"


class TestArchitectureError(ValueError):
    pass


def _safe_app_id(value: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", value):
        raise TestArchitectureError("invalid generated application id")
    return value


def render_executable_tests(
    semantic_model: Mapping[str, Any], app_id: str = "generated_application"
) -> dict[str, str]:
    """Render substantive pytest modules whose obligations come from the finite model."""
    app_id = _safe_app_id(app_id)
    if semantic_model.get("schema_version") != "upi-app-factory.semantic-model.v1":
        raise TestArchitectureError("unsupported semantic model")
    machine = semantic_model.get("state_machine", {})
    transitions = list(machine.get("valid_transitions", []))
    invalid = list(machine.get("invalid_transitions", []))
    requirements = list(semantic_model.get("requirements", []))
    fingerprint = str(semantic_model.get("semantic_fingerprint", ""))
    prefix = f"app.{app_id}"
    required_runtime_paths = [
        f"app/{app_id}/semantic_policy.py",
        f"app/{app_id}/application/workflow.py",
        f"app/{app_id}/application/service.py",
        f"app/{app_id}/infrastructure/sqlite_outbox.py",
        f"app/{app_id}/interfaces/api/semantic_routes.py",
    ]
    api_identities: list[str] = []
    for row in semantic_model.get("apis", []):
        if not isinstance(row, Mapping):
            continue
        has_method = "method" in row
        has_path = "path" in row
        if not has_method and not has_path:
            continue
        if has_method != has_path:
            raise TestArchitectureError("semantic API route specification requires both method and path")
        method = str(row.get("method", "")).strip().upper()
        path = str(row.get("path", "")).strip()
        if not method or not path.startswith("/"):
            raise TestArchitectureError("semantic API route specification is invalid")
        api_identities.append(f"{method} {path}")
    compatibility_identities = [
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
    ]
    builtin_identities = ["GET /health", "GET /ready", "GET /metrics", "GET /openapi.json"]
    reserved_identities = set(compatibility_identities) | set(builtin_identities)
    custom_execution_identities = [
        identity for identity in dict.fromkeys(api_identities) if identity not in reserved_identities
    ]
    files: dict[str, str] = {
        "pytest.ini": "[pytest]\ntestpaths = tests\naddopts = --strict-markers\n",
        "tests/conftest.py": """from __future__ import annotations
import sys
from pathlib import Path
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
""",
        "tests/test_unit_semantics.py": f"""from {prefix}.semantic_policy import SEMANTIC_FINGERPRINT, SEMANTICS

def test_semantic_identity_is_bound_to_package():
    assert SEMANTIC_FINGERPRINT == {fingerprint!r}
    assert SEMANTICS["authority"] == {{"local_only": True, "mock_only": True, "real_payment_calls": "disabled", "runtime_llm_calls": 0}}
""",
        "tests/test_invariants.py": f"""from {prefix}.application.workflow import TRANSITIONS

def test_transition_pairs_are_deterministic_and_targets_are_known():
    expected = {[(row["from"], row["signal"], row["to"]) for row in transitions]!r}
    assert sorted((source, signal, target) for (source, signal), target in TRANSITIONS.items()) == sorted(expected)
    assert len(TRANSITIONS) == len(expected)
""",
        "tests/test_state_transitions.py": f"""import pytest
from {prefix}.application.workflow import WorkflowDecisionError, transition

@pytest.mark.parametrize("source,signal,target", {[(row["from"], row["signal"], row["to"]) for row in transitions]!r})
def test_every_valid_transition(source, signal, target):
    assert transition(source, signal) == target

@pytest.mark.parametrize("source,signal", {[(row["from"], row["signal"]) for row in invalid]!r})
def test_every_declared_invalid_transition(source, signal):
    with pytest.raises(WorkflowDecisionError, match="INVALID_TRANSITION"):
        transition(source, signal)
""",
        "tests/test_scenario_paths.py": f"""import pytest
from {prefix}.application.workflow import WorkflowDecisionError, transition
from {prefix}.semantic_policy import SEMANTICS

def test_happy_path_uses_a_finite_model_transition():
    source, signal, target = {transitions[0]!r}.values()
    assert transition(source, signal) == target

def test_negative_or_cannot_determine_fails_closed():
    with pytest.raises(WorkflowDecisionError, match="INVALID_TRANSITION"):
        transition("unknown", "cannot_determine")

def test_invalid_transition_contract_is_stable_in_source():
    from pathlib import Path
    import {prefix}.application.workflow as workflow_module
    import {prefix}.semantic_policy as semantic_module
    source = Path(workflow_module.__file__).read_text(encoding="utf-8")
    semantic_source = Path(semantic_module.__file__).read_text(encoding="utf-8")
    assert 'WorkflowDecisionError("INVALID_TRANSITION")' in source
    assert "MUTANT_INVALID_TRANSITION" not in source + semantic_source

def test_human_review_cannot_be_bypassed():
    original = list(SEMANTICS["policies"]["human_review"])
    SEMANTICS["policies"]["human_review"][:] = [{{"required": True}}]
    try:
        with pytest.raises(WorkflowDecisionError, match="HUMAN_REVIEW_REQUIRED"):
            transition("received", "approve")
    finally:
        SEMANTICS["policies"]["human_review"][:] = original
""",
        "tests/test_api_contract.py": f"""import json
from pathlib import Path
from fastapi.testclient import TestClient
from {prefix}.semantic_policy import SEMANTICS
from {prefix}.interfaces.api.main import app

CUSTOM_EXECUTION_IDENTITIES = {custom_execution_identities!r}
HTTP_METHODS = {{"get", "post", "put", "patch", "delete", "options", "head"}}

def _path(identity, case_id):
    return identity.split(" ", 1)[1].replace("{{case_id}}", case_id).replace("{{dispute_id}}", case_id)

def _public_openapi_identities():
    schema = app.openapi()
    return {{
        f"{{method.upper()}} {{path}}"
        for path, item in schema.get("paths", {{}}).items()
        if isinstance(item, dict)
        for method in item
        if method.lower() in HTTP_METHODS
    }}

def test_api_contract_is_factory_owned_and_publicly_materialized():
    root = Path(__file__).resolve().parents[1]
    declared_contract = json.loads((root / "openapi/openapi.json").read_text(encoding="utf-8"))
    runtime_evidence = json.loads((root / "evidence/runtime_architecture.json").read_text(encoding="utf-8"))
    ownership = runtime_evidence["api_route_contract"]
    required_identities = set(declared_contract["x-required-endpoints"])
    requested_identities = {api_identities!r}
    owned = set(ownership["non_semantic_owned_identities"]) | set(ownership["semantic_owned_identities"])
    assert ownership["duplicate_identities"] == []
    assert set(requested_identities).issubset(owned)
    assert required_identities.issubset(owned)
    framework_runtime_only = {{"GET /openapi.json"}}
    assert (required_identities - framework_runtime_only).issubset(_public_openapi_identities())
    assert (set(requested_identities) - framework_runtime_only).issubset(_public_openapi_identities())
    assert SEMANTICS["authority"]["real_payment_calls"] == "disabled"

def test_every_custom_semantic_api_identity_executes_through_the_mounted_router():
    client = TestClient(app)
    for identity in CUSTOM_EXECUTION_IDENTITIES:
        method = identity.split(" ", 1)[0]
        case_id = "semantic-generated-test"
        response = client.request(method, _path(identity, case_id), json={{"case_id": case_id}})
        assert response.status_code < 400, identity
        body = response.json()
        assert not (isinstance(body, dict) and body.get("status") == "not_found"), identity

def test_legacy_dispute_behavior_survives_semantic_overlay():
    client = TestClient(app)
    case_id = "dispute-generated-test"
    payload = {{
        "dispute_id": case_id,
        "transaction_reference": "txn-generated-test",
        "amount": "125.00",
        "reason": "no_credit_after_debit",
    }}
    headers = {{"Idempotency-Key": "idem-generated-test"}}
    created = client.post("/v1/disputes", json=payload, headers=headers)
    replay = client.post("/v1/disputes", json=payload, headers=headers)
    assert created.status_code < 400 and replay.status_code < 400
    assert created.json() == replay.json()
    listed = client.get("/v1/disputes")
    assert listed.status_code == 200 and isinstance(listed.json(), list)
    evidence = client.post(f"/v1/disputes/{{case_id}}/evidence", json={{"evidence_id": "ev-generated"}})
    assert evidence.status_code == 200
    validated = client.post(f"/v1/disputes/{{case_id}}/validation")
    investigated = client.post(f"/v1/disputes/{{case_id}}/investigation")
    resolved = client.post(f"/v1/disputes/{{case_id}}/resolution")
    closed = client.post(f"/v1/disputes/{{case_id}}/closure")
    assert validated.json()["state"] == "validated"
    assert investigated.json()["state"] == "investigation"
    assert resolved.json()["state"] == "resolution_proposed"
    assert closed.json()["state"] == "closed"
    timeline = client.get(f"/v1/disputes/{{case_id}}/timeline").json()
    assert isinstance(timeline, list) and timeline[-1] == "case_closed"
    audit = client.get(f"/v1/disputes/{{case_id}}/audit").json()
    assert audit["hash_chained"] is True
    assert audit["records"] == timeline
""",
        "tests/test_persistence.py": f"""from {prefix}.infrastructure.sqlite_outbox import SQLiteAggregateOutbox

def test_state_and_event_persist_together(tmp_path):
    store = SQLiteAggregateOutbox(tmp_path / "app.sqlite3")
    assert store.save_with_event(aggregate_id="a1", state="received", version=1, payload={{"safe": True}}, event_id="e1", idempotency_key="k1", event_type="created")
    assert store.aggregate("a1")["state"] == "received"
    assert [row["event_id"] for row in store.pending()] == ["e1"]
""",
        "tests/test_idempotency_concurrency.py": f"""from {prefix}.infrastructure.sqlite_outbox import SQLiteAggregateOutbox

def test_idempotent_replay_does_not_duplicate_state_or_event(tmp_path):
    store = SQLiteAggregateOutbox(tmp_path / "app.sqlite3")
    args = dict(aggregate_id="a1", state="received", version=1, payload={{}}, event_id="e1", idempotency_key="same", event_type="created")
    assert store.save_with_event(**args) is True
    assert store.save_with_event(**args) is False
    assert len(store.pending()) == 1

def test_idempotency_is_a_persistent_database_constraint(tmp_path):
    store = SQLiteAggregateOutbox(tmp_path / "app.sqlite3")
    with store._connect() as connection:
        schema = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='outbox_events'").fetchone()[0]
    assert "event_id TEXT NOT NULL UNIQUE" in schema
    assert "idempotency_key TEXT NOT NULL UNIQUE" in schema

def test_duplicate_replay_explicitly_rolls_back_the_transaction():
    import inspect
    source = inspect.getsource(SQLiteAggregateOutbox.save_with_event)
    replay_branch = source[source.index("if replay:"):source.index("INSERT INTO aggregates")]
    assert "connection.rollback()" in replay_branch
    assert "connection.commit()" not in replay_branch
""",
        "tests/test_outbox_atomicity.py": f"""import pytest
from {prefix}.infrastructure.sqlite_outbox import SQLiteAggregateOutbox

def test_crash_before_commit_rolls_back_aggregate_and_outbox(tmp_path):
    store = SQLiteAggregateOutbox(tmp_path / "app.sqlite3")
    def crash(): raise RuntimeError("simulated crash")
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.save_with_event(aggregate_id="a1", state="received", version=1, payload={{}}, event_id="e1", idempotency_key="k1", event_type="created", before_commit=crash)
    assert store.aggregate("a1") is None
    assert store.pending() == []

def test_publish_replay_is_idempotent(tmp_path):
    store = SQLiteAggregateOutbox(tmp_path / "app.sqlite3")
    store.save_with_event(aggregate_id="a1", state="received", version=1, payload={{}}, event_id="e1", idempotency_key="k1", event_type="created")
    assert store.mark_published("e1") is True
    assert store.mark_published("e1") is False
""",
        "tests/test_workflow_policy.py": f"""from {prefix}.application.workflow import policy_snapshot

def test_deadline_reentry_and_human_review_policy_is_consumed():
    snapshot = policy_snapshot()
    assert set(snapshot) == {{"deadline", "reentry", "human_review"}}
    assert snapshot == {{"deadline": {list(semantic_model.get("policies", {}).get("deadline", []))!r}, "reentry": {list(semantic_model.get("policies", {}).get("reentry", []))!r}, "human_review": {list(semantic_model.get("policies", {}).get("human_review", []))!r}}}
""",
        "tests/test_security_boundaries.py": f"""from {prefix}.semantic_policy import SEMANTICS

def test_local_mock_authority_boundary():
    authority = SEMANTICS["authority"]
    assert authority["local_only"] and authority["mock_only"]
    assert authority["runtime_llm_calls"] == 0
    assert authority["real_payment_calls"] == "disabled"
""",
        "tests/test_observability.py": f"""from {prefix}.application.service import ApplicationService
from {prefix}.infrastructure.sqlite_outbox import SQLiteAggregateOutbox

def test_decision_result_exposes_stable_state_and_replay_status(tmp_path):
    service = ApplicationService(SQLiteAggregateOutbox(tmp_path / "app.sqlite3"))
    row = {transitions[0]!r}
    result = service.apply("a1", row["from"], row["signal"], "trace-1")
    assert result == {{"aggregate_id": "a1", "state": row["to"], "created": True}}
""",
        "tests/test_resilience.py": f"""from {prefix}.infrastructure.sqlite_outbox import SQLiteAggregateOutbox

def test_store_reopens_and_replays_pending_events(tmp_path):
    path = tmp_path / "app.sqlite3"
    SQLiteAggregateOutbox(path).save_with_event(aggregate_id="a1", state="received", version=1, payload={{}}, event_id="e1", idempotency_key="k1", event_type="created")
    assert SQLiteAggregateOutbox(path).pending()[0]["event_id"] == "e1"
""",
        "tests/test_generated_runtime_depth.py": f"""import importlib.util
import inspect
import sqlite3
from types import SimpleNamespace
import pytest
pytest.importorskip("{prefix}.application.services.dispute_service")
pytest.importorskip("{prefix}.infrastructure.runtime_adapters")
from {prefix}.application.services.dispute_service import DisputeApplicationService
from {prefix}.domain.aggregates.dispute_case import DisputeCase, DomainError
from {prefix}.infrastructure.runtime_adapters import InMemoryCaseRepository, SQLiteMemoryTransactionalOutbox, SystemClockAdapter, Uuid4IdGenerator, build_runtime_adapters

PAYLOAD = {{"dispute_id": "d1", "transaction_reference": "t1", "amount": "1.00", "reason": "fixture"}}

def test_repository_clock_ids_and_profiles_are_executable(tmp_path, monkeypatch):
    repository = InMemoryCaseRepository()
    repository.put("d1", PAYLOAD)
    assert repository.get("d1") == PAYLOAD and repository.values() == [PAYLOAD]
    assert SystemClockAdapter().now().tzinfo is not None
    assert Uuid4IdGenerator().new_id() != Uuid4IdGenerator().new_id()
    monkeypatch.setenv("UPI_RUNTIME_PROFILE", "in_memory")
    assert build_runtime_adapters().profile_id == "in_memory"
    monkeypatch.setenv("UPI_SQLITE_PATH", str(tmp_path / "nested" / "runtime.sqlite3"))
    assert build_runtime_adapters("sqlite_file").profile_id == "sqlite_file"
    with pytest.raises(ValueError, match="unsupported runtime profile"):
        build_runtime_adapters("unknown")

def test_runtime_outbox_duplicate_integrity_and_crash_are_atomic(tmp_path):
    store = SQLiteMemoryTransactionalOutbox(str(tmp_path / "nested" / "outbox.sqlite3"))
    event = SimpleNamespace(event_id="e1", idempotency_key="k1")
    assert store.save_case_and_event("d1", PAYLOAD, event) is True
    assert store.save_case_and_event("d1", PAYLOAD, event) is False
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.save_case_and_event("d2", PAYLOAD, SimpleNamespace(event_id="e2", idempotency_key="k2"), crash_before_commit=True)
    store.connection.execute("INSERT INTO cases(case_id,payload) VALUES('d3','{{}}')")
    store.connection.execute("INSERT INTO outbox(event_id,idempotency_key,case_id,payload) VALUES('e3','k3','d3','{{}}')")
    with pytest.raises(sqlite3.IntegrityError):
        store.connection.execute("INSERT INTO outbox(event_id,idempotency_key,case_id,payload) VALUES('e4','k3','d3','{{}}')")
    assert store.save_case_and_event("d4", PAYLOAD, SimpleNamespace(event_id="e1", idempotency_key="k4")) is False

def test_dispute_service_exercises_governed_workflow_and_rejections():
    workflow_name = "{prefix}.application.workflows.dispute_workflow"
    try:
        workflow_spec = importlib.util.find_spec(workflow_name)
    except ModuleNotFoundError:
        workflow_spec = None
    if len(inspect.signature(DisputeApplicationService).parameters) != 1 or workflow_spec is None:
        pytest.skip("workflow-centric adapter is not selected")
    from {prefix}.application.workflows.dispute_workflow import next_state
    service = DisputeApplicationService(InMemoryCaseRepository())
    assert service.create(PAYLOAD, "key") == service.create(PAYLOAD, "key")
    assert service.workflow_policy("investigation")["human_review_required"] is True
    service._cases["d1"].state = "evidence_pending"
    assert service.action("d1", "investigation", "investigated")["state"] == "investigation"
    assert service.action("d1", "resolution_proposed", "proposed")["state"] == "resolution_proposed"
    assert service.action("d1", "resolved", "approved")["state"] == "resolved"
    service._cases["d1"].state = "investigation"
    with pytest.raises(DomainError):
        service.action("d1", "closed", "invalid")
    import {prefix}.application.services.dispute_service as service_module
    service._cases["d1"].state = "investigation"
    original = service_module.next_state
    service_module.next_state = lambda current, signal: "wrong"
    try:
        with pytest.raises(ValueError, match="workflow policy"):
            service.action("d1", "resolution_proposed", "invalid-policy")
    finally:
        service_module.next_state = original
    with pytest.raises(KeyError):
        next_state("received", "unknown")
    case = DisputeCase("bad", "tx", "1", "fixture")
    with pytest.raises(DomainError, match="invalid transition"):
        case.transition("closed", "invalid")

def test_event_driven_service_and_aggregate_branches_are_executable():
    if len(inspect.signature(DisputeApplicationService).parameters) != 2:
        pytest.skip("event-driven outbox adapter is not selected")
    adapters = build_runtime_adapters("in_memory")
    service = DisputeApplicationService(adapters.case_repository, adapters.transactional_outbox)
    assert service.create(PAYLOAD, "event-key") == service.create(PAYLOAD, "event-key")
    assert service.get("d1")["state"] == "received"
    assert len(service.list()) == 1
    from {prefix}.domain.state_machines.dispute_lifecycle import TRANSITION_TABLE
    target = TRANSITION_TABLE["received"][0]
    assert service.action("d1", target, "valid-event")["state"] == target
    with pytest.raises(DomainError, match="invalid transition"):
        service.action("d1", "closed", "invalid")

def test_hexagonal_service_and_aggregate_branches_are_executable():
    workflow_name = "{prefix}.application.workflows.dispute_workflow"
    try:
        workflow_spec = importlib.util.find_spec(workflow_name)
    except ModuleNotFoundError:
        workflow_spec = None
    if len(inspect.signature(DisputeApplicationService).parameters) != 1 or workflow_spec is not None:
        pytest.skip("hexagonal adapter is not selected")
    service = DisputeApplicationService(InMemoryCaseRepository())
    assert service.create(PAYLOAD, "hex-key") == service.create(PAYLOAD, "hex-key")
    assert service.get("d1")["state"] == "received"
    assert len(service.list()) == 1
    from {prefix}.domain.state_machines.dispute_lifecycle import TRANSITION_TABLE
    target = TRANSITION_TABLE["received"][0]
    assert service.action("d1", target, "valid-hexagonal")["state"] == target
    with pytest.raises(DomainError, match="invalid transition"):
        service.action("d1", "closed", "invalid")
""",
        "tests/test_architecture_conformance.py": f"""from pathlib import Path

def test_runtime_layers_and_no_factory_dependency_are_packaged():
    root = Path(__file__).resolve().parents[1]
    required = {required_runtime_paths!r}
    assert all((root / path).is_file() for path in required)
    assert "factory" not in (root / required[1]).read_text(encoding="utf-8")
""",
        "tests/test_report_integrity.py": f"""import json
from pathlib import Path

def test_canonical_semantic_report_matches_fingerprint():
    root = Path(__file__).resolve().parents[1]
    report = json.loads((root / "evidence/semantic_model.json").read_text(encoding="utf-8"))
    assert report["semantic_fingerprint"] == {fingerprint!r}
    assert report["finite_scope"]["requirement_count"] == {len(requirements)}
""",
    }
    test_paths = sorted(
        path for path in files if path.startswith("tests/test_") and path.endswith(".py")
    )
    trace = {
        "schema_version": TEST_MODEL_VERSION,
        "finite_model_version": semantic_model["schema_version"],
        "semantic_fingerprint": fingerprint,
        "execution": {
            "rootdir": ".",
            "confcutdir": ".",
            "command": "python -m pytest -q -c pytest.ini --rootdir=. --confcutdir=.",
        },
        "requirements": [{**row, "test_paths": list(test_paths)} for row in requirements],
        "test_paths": test_paths,
    }
    files["evidence/executable_test_trace.json"] = (
        json.dumps(trace, indent=2, sort_keys=True) + "\n"
    )
    files["openapi/openapi.json"] = json.dumps(
        {
            "openapi": "3.1.0",
            "info": {"title": app_id, "version": "1.0.0"},
            "x-required-endpoints": api_identities,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    files["evidence/test_measurements.json"] = (
        json.dumps(
            {
                "schema_version": "upi-app-factory.raw-test-measurements.v1",
                "collected_test_count": None,
                "failed_test_count": None,
                "missing_test_path_count": 0,
                "testing_depth_score": None,
                "score_status": "WITHHELD_UNTIL_EXECUTION",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return files


def _trace_payload(trace: Mapping[str, Any] | Path | str) -> Mapping[str, Any]:
    if isinstance(trace, Mapping):
        return trace
    path = Path(trace)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TestArchitectureError("trace document must be an object")
    return value


def validate_trace_paths(
    application_root: Path, trace: Mapping[str, Any] | Path | str | None = None
) -> dict[str, Any]:
    """Prove every declared test reference resolves to a physical in-package file."""
    root = Path(application_root).resolve()
    payload = _trace_payload(trace or root / "evidence/executable_test_trace.json")
    declared: set[str] = set(str(item) for item in payload.get("test_paths", []))
    for row in payload.get("requirements", []):
        if isinstance(row, Mapping):
            declared.update(str(item) for item in row.get("test_paths", []))
    missing: list[str] = []
    unsafe: list[str] = []
    for relative in sorted(declared):
        rel = Path(relative)
        target = (root / rel).resolve()
        if rel.is_absolute() or not target.is_relative_to(root):
            unsafe.append(relative)
        elif not target.is_file():
            missing.append(relative)
    return {
        "status": "PASS" if declared and not missing and not unsafe else "FAIL",
        "declared_test_path_count": len(declared),
        "missing_test_path_count": len(missing),
        "missing_paths": missing,
        "unsafe_paths": unsafe,
    }


def collect_test_inventory(application_root: Path) -> dict[str, Any]:
    """Collect raw test definitions; this function intentionally awards no score."""
    root = Path(application_root).resolve()
    modules: list[dict[str, Any]] = []
    collection_errors: list[str] = []
    total = 0
    for path in sorted((root / "tests").rglob("test_*.py")) if (root / "tests").is_dir() else []:
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError as exc:
            collection_errors.append(f"{relative}:{exc.lineno}")
            continue
        names = sorted(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )
        total += len(names)
        modules.append({"path": relative, "test_definition_count": len(names), "test_names": names})
    trace = (
        validate_trace_paths(root)
        if (root / "evidence/executable_test_trace.json").is_file()
        else {
            "status": "FAIL",
            "missing_test_path_count": 0,
            "missing_paths": [],
            "unsafe_paths": [],
        }
    )
    eligible = total > 0 and not collection_errors and trace["status"] == "PASS"
    return {
        "schema_version": "upi-app-factory.raw-test-inventory.v1",
        "collected_test_count": total,
        "test_module_count": len(modules),
        "modules": modules,
        "collection_errors": collection_errors,
        "trace_validation": trace,
        "testing_depth_score": None,
        "score_eligible": eligible,
    }


__all__ = ["render_executable_tests", "validate_trace_paths", "collect_test_inventory"]
