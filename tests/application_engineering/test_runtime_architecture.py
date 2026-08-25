from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
from typing import Mapping

import pytest

from factory.application_engineering.runtime_architecture import (
    RuntimeArchitectureError,
    render_runtime_architecture_files,
    validate_runtime_architecture,
)
from factory.application_engineering.semantic_realization import (
    build_semantic_model,
    render_semantic_files,
)


def _model() -> dict[str, object]:
    return build_semantic_model(
        {
            "workflows": [
                {
                    "id": "WF-1",
                    "from": "received",
                    "to": "reviewed",
                    "signal": "review",
                    "deadline": "P1D",
                    "reentry": "retry",
                    "human_review": True,
                }
            ],
            "events": [{"id": "EV-1", "name": "reviewed"}],
        }
    )


def _write(root: Path, files: Mapping[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    for relative in (
        "app/__init__.py",
        "app/sample_app/__init__.py",
        "app/sample_app/application/__init__.py",
        "app/sample_app/infrastructure/__init__.py",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def test_runtime_validator_requires_policy_consumption_and_atomic_persistence(
    tmp_path: Path,
) -> None:
    files = {}
    files.update(render_semantic_files(_model(), "sample_app"))
    files.update(render_runtime_architecture_files(_model(), "sample_app"))
    _write(tmp_path, files)
    result = validate_runtime_architecture(tmp_path, "sample_app")
    assert result["status"] == "PASS"
    assert all(result["checks"].values())


def test_sqlite_transaction_crash_replay_and_idempotency(tmp_path: Path) -> None:
    files = {}
    files.update(render_semantic_files(_model(), "sample_app"))
    files.update(render_runtime_architecture_files(_model(), "sample_app"))
    _write(tmp_path, files)
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)
    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("app.sample_app.infrastructure.sqlite_outbox")
        store = module.SQLiteAggregateOutbox(tmp_path / "runtime.sqlite3")

        def crash() -> None:
            raise RuntimeError("crash")

        with pytest.raises(RuntimeError):
            store.save_with_event(
                aggregate_id="a",
                state="reviewed",
                version=1,
                payload={},
                event_id="e",
                idempotency_key="k",
                event_type="reviewed",
                before_commit=crash,
            )
        assert store.aggregate("a") is None and store.pending() == []
        args = dict(
            aggregate_id="a",
            state="reviewed",
            version=1,
            payload={},
            event_id="e",
            idempotency_key="k",
            event_type="reviewed",
        )
        assert store.save_with_event(**args) is True
        assert store.save_with_event(**args) is False
        assert store.mark_published("e") is True
        assert store.mark_published("e") is False
    finally:
        sys.path.remove(str(tmp_path))
        for name in list(sys.modules):
            if name == "app" or name.startswith("app."):
                sys.modules.pop(name, None)

def test_runtime_renderer_uses_non_overlapping_semantic_router() -> None:
    model = build_semantic_model(
        {
            "workflows": [{"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}],
            "events": [{"id": "EV-1", "name": "reviewed"}],
            "apis": [
                {"id": "API-CUSTOM", "method": "GET", "path": "/v1/custom-semantic"},
                {"id": "API-LEGACY", "method": "GET", "path": "/v1/disputes/{dispute_id}/timeline"},
            ],
        }
    )
    files = render_runtime_architecture_files(
        model,
        "sample_app",
        reserved_identities=("GET /v1/disputes/{dispute_id}/timeline",),
    )
    assert "app/sample_app/interfaces/api/main.py" not in files
    routes = files["app/sample_app/interfaces/api/semantic_routes.py"]
    assert "APIRouter" in routes
    assert '@router.get("/v1/custom-semantic")' in routes
    assert "/v1/disputes/{dispute_id}/timeline" not in routes
    evidence = json.loads(files["evidence/runtime_architecture.json"])
    contract = evidence["api_route_contract"]
    assert contract["duplicate_identities"] == []
    assert "GET /v1/custom-semantic" in contract["semantic_owned_identities"]
    assert "GET /v1/disputes/{dispute_id}/timeline" in contract["non_semantic_owned_identities"]


def test_runtime_renderer_standalone_mode_emits_complete_api_entrypoint(tmp_path: Path) -> None:
    model = build_semantic_model(
        {
            "workflows": [{"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}],
            "events": [{"id": "EV-1", "name": "reviewed"}],
            "apis": [{"id": "API-CUSTOM", "method": "POST", "path": "/cases"}],
        }
    )
    files = {}
    files.update(render_semantic_files(model, "sample_app"))
    files.update(render_runtime_architecture_files(model, "sample_app"))
    assert "app/sample_app/interfaces/api/main.py" in files
    assert "app/sample_app/interfaces/api/semantic_routes.py" in files
    main = files["app/sample_app/interfaces/api/main.py"]
    routes = files["app/sample_app/interfaces/api/semantic_routes.py"]
    assert "app.include_router(semantic_router)" in main
    assert '@app.get("/v1/disputes/{dispute_id}/timeline")' in main
    assert '@router.post("/cases")' in routes
    evidence = json.loads(files["evidence/runtime_architecture.json"])
    contract = evidence["api_route_contract"]
    assert contract["composition_mode"] == "standalone"
    assert contract["duplicate_identities"] == []
    assert "POST /cases" in contract["semantic_owned_identities"]


def test_duplicate_custom_semantic_route_ownership_fails_closed() -> None:
    model = build_semantic_model(
        {
            "workflows": [{"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}],
            "events": [{"id": "EV-1", "name": "reviewed"}],
            "apis": [
                {"id": "API-1", "method": "POST", "path": "/cases"},
                {"id": "API-2", "method": "POST", "path": "/cases"},
            ],
        }
    )
    with pytest.raises(Exception, match="duplicate semantic API route ownership"):
        render_runtime_architecture_files(model, "sample_app")


def test_conceptual_api_requirement_is_preserved_without_route_materialization() -> None:
    model = build_semantic_model(
        {
            "workflows": [{"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}],
            "events": [{"id": "EV-1", "name": "reviewed"}],
            "apis": [{"id": "API-CONCEPT", "name": "Local API capability", "description": "Conceptual API requirement without an executable route specification."}],
        }
    )
    files = render_runtime_architecture_files(model, "sample_app")
    routes = files["app/sample_app/interfaces/api/semantic_routes.py"]
    evidence = json.loads(files["evidence/runtime_architecture.json"])
    contract = evidence["api_route_contract"]
    assert "@router." not in routes
    assert contract["requested_semantic_identities"] == []
    assert contract["conceptual_api_requirement_ids"] == ["API-CONCEPT"]


def test_partial_semantic_route_specification_fails_closed() -> None:
    model = build_semantic_model(
        {
            "workflows": [{"id": "WF-1", "from": "received", "to": "reviewed", "signal": "review"}],
            "events": [{"id": "EV-1", "name": "reviewed"}],
            "apis": [{"id": "API-PARTIAL", "method": "POST", "description": "Missing path must not be guessed."}],
        }
    )
    with pytest.raises(RuntimeArchitectureError, match="requires both method and path"):
        render_runtime_architecture_files(model, "sample_app")
