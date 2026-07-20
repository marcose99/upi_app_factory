from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class ResolvedStateRoots:
    project_root: Path
    browser_state_root: Path
    portfolio_state_root: Path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def canonical_project_root(project_root: Path | None = None) -> Path:
    if project_root is not None:
        return project_root.expanduser().resolve()
    configured = os.getenv("UPI_APP_FACTORY_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def default_browser_state_root() -> Path:
    configured = os.getenv("UPI_APP_FACTORY_PORTAL_RUN_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg_state = Path(
        os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
    ).expanduser()
    return (xdg_state / "upi_app_factory" / "operator_portal_runs").resolve()


def default_portfolio_state_root(project_root: Path) -> Path:
    return (
        project_root
        / "workspace"
        / "factory_generated"
        / "upi_dispute_resolution"
        / "lifecycle_artifacts"
        / "phase51"
    ).resolve()


def resolve_portfolio_state_root(
    *,
    project_root: Path | None = None,
    portfolio_state_root: Path | None = None,
) -> Path:
    resolved_project = canonical_project_root(project_root)
    env_value = os.getenv("UPI_APP_FACTORY_PORTFOLIO_STATE_ROOT")
    selected = (
        portfolio_state_root
        if portfolio_state_root is not None
        else Path(env_value).expanduser()
        if env_value
        else default_portfolio_state_root(resolved_project)
    )
    resolved = selected.expanduser().resolve()
    tmp_root = Path("/tmp").resolve()
    if not (_is_relative_to(resolved, resolved_project) or _is_relative_to(resolved, tmp_root)):
        raise ValueError("portfolio state root must stay in the worktree or /tmp")
    return resolved


def resolve_state_roots(
    *,
    project_root: Path | None = None,
    browser_state_root: Path | None = None,
    portfolio_state_root: Path | None = None,
) -> ResolvedStateRoots:
    resolved_project = canonical_project_root(project_root)
    resolved_browser = (
        browser_state_root.expanduser().resolve()
        if browser_state_root is not None
        else default_browser_state_root()
    )
    resolved_portfolio = resolve_portfolio_state_root(
        project_root=resolved_project,
        portfolio_state_root=portfolio_state_root,
    )
    return ResolvedStateRoots(
        project_root=resolved_project,
        browser_state_root=resolved_browser,
        portfolio_state_root=resolved_portfolio,
    )
