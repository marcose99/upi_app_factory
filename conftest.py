from __future__ import annotations

import os
from pathlib import Path

import pytest

from factory.prerequisite_artifacts import (
    DEFAULT_MUTABLE_TEST_ROOTS,
    materialize_clean_clone_test_evidence,
    restore_mutable_test_roots,
    snapshot_mutable_test_roots,
)


PROJECT_ROOT = Path(__file__).resolve().parent
_PYTEST_MUTABLE_ROOT_SNAPSHOT: dict[str, object] | None = None


def _selected_path(argument: str) -> Path | None:
    if not argument or argument.startswith("-"):
        return None
    raw_path = argument.split("::", 1)[0]
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _is_runtime_generated_test_session(config: pytest.Config) -> bool:
    mutable_roots = [
        (PROJECT_ROOT / relative).resolve()
        for relative in DEFAULT_MUTABLE_TEST_ROOTS
        if relative.startswith("workspace/")
    ]
    selected_paths = [
        path
        for raw_argument in config.invocation_params.args
        if (path := _selected_path(str(raw_argument))) is not None
    ]
    if not selected_paths:
        return False
    return all(
        any(path == mutable_root or path.is_relative_to(mutable_root) for mutable_root in mutable_roots)
        for path in selected_paths
    )


def pytest_configure(config: pytest.Config) -> None:
    del config
    os.environ["UPI_APP_FACTORY_ROOT_CONFTEST_ACTIVE"] = "1"


def pytest_sessionstart(session: pytest.Session) -> None:
    global _PYTEST_MUTABLE_ROOT_SNAPSHOT

    if _is_runtime_generated_test_session(session.config):
        _PYTEST_MUTABLE_ROOT_SNAPSHOT = None
        return

    result = materialize_clean_clone_test_evidence(PROJECT_ROOT)
    if result["status"] != "PASSED":
        raise pytest.UsageError(
            "failed to materialize clean-clone prerequisite evidence: "
            + ", ".join(result["errors"])
        )
    snapshot = snapshot_mutable_test_roots(PROJECT_ROOT)
    if snapshot["status"] != "SNAPSHOTTED":
        raise pytest.UsageError(
            "failed to snapshot mutable governed runtime roots: "
            + ", ".join(snapshot["errors"])
        )
    _PYTEST_MUTABLE_ROOT_SNAPSHOT = snapshot


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    del session, exitstatus

    if _PYTEST_MUTABLE_ROOT_SNAPSHOT is None:
        return
    result = restore_mutable_test_roots(_PYTEST_MUTABLE_ROOT_SNAPSHOT)
    if result["status"] != "RESTORED":
        raise pytest.UsageError(
            "failed to restore mutable governed runtime roots: "
            + ", ".join(result["errors"])
        )
