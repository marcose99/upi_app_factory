from __future__ import annotations

from pathlib import Path

from tools.lifecycle_orchestrator.run_resolution import resolution_report


class LifecycleRunResolutionService:
    """Read-only façade for portal and operator reporting surfaces."""

    def __init__(self, *, project_root: Path, state_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.state_root = state_root.resolve()

    def report(
        self,
        phase: str,
        *,
        expected_manifest_path: Path | None = None,
        expected_base_commit: str | None = None,
    ) -> dict[str, object]:
        report = resolution_report(
            self.state_root,
            phase,
            project_root=self.project_root,
            expected_manifest_path=expected_manifest_path,
            expected_base_commit=expected_base_commit,
        )
        return {
            **report,
            "service": "operator_portal_lifecycle_run_resolution",
            "read_only": True,
            "mutation_performed": False,
        }
