from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Mapping

import pytest

from factory.application_engineering.runtime_architecture import (
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
