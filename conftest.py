from __future__ import annotations

from pathlib import Path

import pytest

from factory.prerequisite_artifacts import (
    materialize_clean_clone_test_evidence,
    restore_mutable_test_roots,
    snapshot_mutable_test_roots,
)


PROJECT_ROOT = Path(__file__).resolve().parent
_PYTEST_MUTABLE_ROOT_SNAPSHOT: dict[str, object] | None = None


def pytest_sessionstart(session: pytest.Session) -> None:
    global _PYTEST_MUTABLE_ROOT_SNAPSHOT

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
