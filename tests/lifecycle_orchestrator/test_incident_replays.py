from __future__ import annotations

import pytest

from tools.lifecycle_orchestrator import cli
from tools.lifecycle_orchestrator.engine import (
    LifecycleError,
    infer_git_lifecycle_position,
    parse_validation_metrics,
)


def test_phase46d_parser_incident_accepts_new_test_count() -> None:
    metrics = parse_validation_metrics(
        "................................\n826 passed in 45.62s\n",
        "",
    )
    assert metrics["pytest_passed"] == 826


def test_resume_after_local_merge_before_push() -> None:
    assert infer_git_lifecycle_position(
        base_commit="base",
        feature_commit="feature",
        main_commit="feature",
        remote_commit="base",
    ) == "MERGED_NOT_PUSHED"


def test_resume_after_remote_push() -> None:
    assert infer_git_lifecycle_position(
        base_commit="base",
        feature_commit="feature",
        main_commit="feature",
        remote_commit="feature",
    ) == "ALREADY_SYNCHRONIZED"


def test_unsupported_git_position_fails_closed() -> None:
    with pytest.raises(LifecycleError):
        infer_git_lifecycle_position(
            base_commit="base",
            feature_commit="feature",
            main_commit="unexpected",
            remote_commit="base",
        )

def test_status_without_runs_returns_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def no_latest_run(_phase: str | None) -> None:
        return None

    monkeypatch.setattr(cli, "latest_run", no_latest_run)
    assert cli.main(["status", "--phase", "99Z"]) == 0
    assert "No lifecycle runs found." in capsys.readouterr().out

