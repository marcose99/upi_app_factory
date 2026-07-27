from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from factory.operator_portal.state_roots import (
    default_browser_state_root,
    resolve_portfolio_state_root,
    resolve_state_roots,
)


ROOT = Path(__file__).resolve().parents[1]


def test_browser_state_defaults_to_repository_relative_var_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg state with spaces"))
    monkeypatch.delenv("UPI_APP_FACTORY_PORTAL_RUN_ROOT", raising=False)
    monkeypatch.delenv("UPI_APP_FACTORY_ROOT", raising=False)

    resolved = default_browser_state_root()

    assert resolved == ROOT / ".var" / "upi_app_factory" / "runs"


def test_explicit_state_roots_support_repository_relocation_with_spaces(tmp_path: Path) -> None:
    relocated = tmp_path / "repo relocation with spaces"
    portfolio = relocated / "state" / "portfolio"
    browser = tmp_path / "external browser state"
    relocated.mkdir(parents=True)

    roots = resolve_state_roots(
        project_root=relocated,
        browser_state_root=browser,
        portfolio_state_root=portfolio,
    )

    assert roots.project_root == relocated.resolve()
    assert roots.browser_state_root == browser.resolve()
    assert roots.portfolio_state_root == portfolio.resolve()


def test_portfolio_state_allows_explicit_external_override(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = Path("/var/tmp/upi-app-factory-outside-state")

    resolved = resolve_portfolio_state_root(project_root=project, portfolio_state_root=outside)

    assert resolved == outside


def test_portfolio_state_allows_literal_tmp_even_when_tempdir_cache_changes(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    cached_tempdir = tmp_path / "cached-tempdir"
    cached_tempdir.mkdir()
    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = str(cached_tempdir)
    try:
        resolved = resolve_portfolio_state_root(
            project_root=project,
            portfolio_state_root=Path("/tmp") / "upi-app-factory-portfolio-state",
        )
    finally:
        tempfile.tempdir = previous_tempdir

    assert resolved == Path("/tmp/upi-app-factory-portfolio-state")


def test_portal_script_runs_from_unrelated_current_directory(tmp_path: Path) -> None:
    unrelated_cwd = tmp_path / "unrelated current directory"
    unrelated_cwd.mkdir()
    portfolio_root = ROOT / "workspace" / "factory_generated" / "linux_neutral_path_tests" / tmp_path.name
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "UPI_APP_FACTORY_ROOT": str(ROOT),
        "UPI_APP_FACTORY_PORTAL_RUN_ROOT": str(tmp_path / "runs"),
        "UPI_APP_FACTORY_PORTFOLIO_STATE_ROOT": str(portfolio_root),
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path\n"
                "from factory.operator_portal.state_roots import resolve_state_roots\n"
                "roots = resolve_state_roots()\n"
                f"assert roots.project_root == Path({str(ROOT)!r}).resolve()\n"
            ),
        ],
        cwd=unrelated_cwd,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
