from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.lifecycle_orchestrator.run_resolution import (
    RunResolutionError,
    authoritative_closed_phase_run,
    preferred_phase_run,
)


def replay_duplicate_run_incident(
    *,
    state_root: Path,
    project_root: Path,
    phase: str,
    expected_manifest_path: Path,
) -> dict[str, Any]:
    preferred = preferred_phase_run(
        state_root,
        phase,
        project_root=project_root,
        expected_manifest_path=expected_manifest_path,
    )
    try:
        authoritative = authoritative_closed_phase_run(
            state_root,
            phase,
            project_root=project_root,
            expected_manifest_path=expected_manifest_path,
        )
    except RunResolutionError as exc:
        return {
            "status": "FAILED_CLOSED",
            "phase": phase,
            "reason": str(exc),
            "preferred_run": preferred.name if preferred else None,
            "mutation_performed": False,
        }
    return {
        "status": (
            "AUTHORITATIVE_CLOSED_SELECTED"
            if authoritative is not None
            else "NO_AUTHORITATIVE_CLOSED_RUN"
        ),
        "phase": phase,
        "authoritative_run": (authoritative[0].name if authoritative is not None else None),
        "preferred_run": preferred.name if preferred else None,
        "mutation_performed": False,
    }


def write_replay_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
