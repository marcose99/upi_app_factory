from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tools.lifecycle_orchestrator.run_resolution import preferred_phase_run


class RepairError(RuntimeError):
    """Raised when a bounded repair cannot be applied safely."""


def load_object(path: Path, label: str) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RepairError(f"{label} must be a JSON object")
    return raw


def write_object_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def latest_phase_run(
    state_root: Path,
    phase: str,
) -> Path | None:
    configured = os.environ.get("UPI_APP_FACTORY_SOURCE_REPO")
    candidates = [Path(configured)] if configured else []
    candidates.append(Path.cwd())
    for candidate in candidates:
        project_root = candidate.resolve()
        if (
            (project_root / ".git").exists()
            and (project_root / "tools/lifecycle_orchestrator").is_dir()
        ):
            return preferred_phase_run(
                state_root,
                phase,
                project_root=project_root,
            )
    lifecycle_root = state_root / "lifecycle_runs"
    if not lifecycle_root.is_dir():
        return None
    runs = sorted(
        path
        for path in lifecycle_root.glob(f"{phase.lower()}-*")
        if path.is_dir() and (path / "run.json").is_file()
    )
    return runs[-1] if runs else None



def relative_diagnostic_path(filename: str, worktree: Path) -> str:
    path = Path(filename)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(worktree).as_posix()
        except ValueError as exc:
            raise RepairError(
                f"Ruff diagnostic escaped worktree: {filename}"
            ) from exc
    text = path.as_posix()
    return text[2:] if text.startswith("./") else text


def collect_ruff_findings(
    python: str,
    worktree: Path,
) -> list[dict[str, Any]]:
    completed = subprocess.run(
        [python, "-m", "ruff", "check", ".", "--output-format=json"],
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
    )
    if not completed.stdout.strip():
        if completed.returncode == 0:
            return []
        raise RepairError(
            "Ruff failed without machine-readable diagnostics: "
            + completed.stderr.strip()
        )
    raw = json.loads(completed.stdout)
    if not isinstance(raw, list):
        raise RepairError("Ruff JSON output must be a list")
    findings: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise RepairError("Invalid Ruff diagnostic")
        filename = item.get("filename")
        if not isinstance(filename, str):
            raise RepairError("Ruff diagnostic is missing filename")
        findings.append(
            {
                "path": relative_diagnostic_path(filename, worktree),
                "code": item.get("code"),
                "message": item.get("message"),
                "fix_available": item.get("fix") is not None,
            }
        )
    return findings


def changed_paths(worktree: Path) -> set[str]:
    raw = subprocess.check_output(
        [
            "git",
            "-C",
            str(worktree),
            "status",
            "--porcelain=v1",
            "-z",
            "-uall",
        ]
    )
    paths: set[str] = set()
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        text = entry.decode("utf-8")
        path_text = text[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        paths.add(path_text)
    return paths


def rollback_to_implemented(run_dir: Path) -> dict[str, Any]:
    run_path = run_dir / "run.json"
    run = load_object(run_path, "Lifecycle run")
    completed = run.get("completed_states")
    if not isinstance(completed, list):
        raise RepairError("completed_states must be a list")
    required = {
        "PREFLIGHT_PASSED",
        "WORKTREE_READY",
        "IMPLEMENTED",
    }
    if not required.issubset(set(completed)):
        raise RepairError("Lifecycle cannot be rolled back to IMPLEMENTED")

    keep = required
    run["completed_states"] = [
        item for item in completed if item in keep
    ]
    evidence = run.get("step_evidence")
    if not isinstance(evidence, dict):
        raise RepairError("step_evidence must be an object")
    run["step_evidence"] = {
        key: value for key, value in evidence.items() if key in keep
    }
    run["current_state"] = "IMPLEMENTED"
    run["status"] = "IMPLEMENTED"
    run.pop("failure", None)
    run["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

    removed = []
    steps_dir = run_dir / "steps"
    if steps_dir.is_dir():
        for path in sorted(steps_dir.glob("*.json")):
            prefix = path.name.split("_", 1)[0]
            if prefix.isdigit() and int(prefix) >= 4:
                removed.append(path.name)
                path.unlink()
    candidate_manifest = run_dir / "candidate_manifest.json"
    if candidate_manifest.is_file():
        candidate_manifest.unlink()

    write_object_atomic(run_path, run)
    return {
        "status": "PASSED",
        "new_state": "IMPLEMENTED",
        "removed_step_files": removed,
    }


def classify_failure_gate(run: dict[str, Any]) -> str:
    failure = run.get("failure")
    if not isinstance(failure, dict):
        return "UNKNOWN"
    message = str(failure.get("message", ""))
    for gate in (
        "Ruff",
        "MyPy",
        "Pytest",
        "Phase 13G",
        "candidate",
        "secret",
    ):
        if gate in message:
            return gate
    return "UNKNOWN"


def apply_ruff_safe_repair(
    *,
    phase: str,
    manifest_path: Path,
    state_root: Path,
    python: str,
    attempt: int,
) -> dict[str, Any]:
    manifest = load_object(manifest_path, "Phase manifest")
    candidates_raw = manifest.get("candidate_paths")
    if not isinstance(candidates_raw, list):
        raise RepairError("candidate_paths must be a list")
    candidates = {
        item for item in candidates_raw if isinstance(item, str)
    }
    if len(candidates) != len(candidates_raw):
        raise RepairError("candidate_paths contains invalid entries")

    run_dir = latest_phase_run(state_root, phase)
    if run_dir is None:
        raise RepairError(f"No lifecycle run found for {phase}")
    run = load_object(run_dir / "run.json", "Lifecycle run")
    if run.get("status") != "FAILED":
        raise RepairError("Lifecycle run is not in FAILED state")
    gate = classify_failure_gate(run)
    if gate != "Ruff":
        raise RepairError(
            f"Failure gate {gate} is not eligible for Ruff repair"
        )

    worktree_raw = run.get("worktree")
    if not isinstance(worktree_raw, str):
        raise RepairError("Lifecycle run does not record its worktree")
    worktree = Path(worktree_raw).resolve()
    if not worktree.is_dir():
        raise RepairError("Lifecycle worktree was not found")

    repair_dir = run_dir / "repairs" / f"attempt_{attempt:02d}"
    repair_dir.mkdir(parents=True, exist_ok=True)
    pre_status = subprocess.check_output(
        ["git", "-C", str(worktree), "status", "--short"],
        text=True,
    )
    (repair_dir / "pre_repair_status.txt").write_text(
        pre_status,
        encoding="utf-8",
    )

    findings = collect_ruff_findings(python, worktree)
    if not findings:
        raise RepairError("Ruff failure produced no active findings")
    outside = [
        item for item in findings if item["path"] not in candidates
    ]
    if outside:
        raise RepairError(
            "Ruff findings escaped candidate scope: "
            + json.dumps(outside, sort_keys=True)
        )
    unsafe = [
        item
        for item in findings
        if not item["fix_available"]
        or not str(item["path"]).endswith(".py")
    ]
    if unsafe:
        raise RepairError(
            "Ruff findings are not eligible for automatic safe repair: "
            + json.dumps(unsafe, sort_keys=True)
        )

    python_paths = sorted({str(item["path"]) for item in findings})
    completed = subprocess.run(
        [python, "-m", "ruff", "check", "--fix", "--", *python_paths],
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
    )
    (repair_dir / "ruff_safe_fix.stdout").write_text(
        completed.stdout,
        encoding="utf-8",
    )
    (repair_dir / "ruff_safe_fix.stderr").write_text(
        completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RepairError("Ruff safe repair did not complete successfully")

    full = subprocess.run(
        [python, "-m", "ruff", "check", "."],
        cwd=worktree,
        text=True,
        capture_output=True,
        check=False,
    )
    (repair_dir / "ruff_full.stdout").write_text(
        full.stdout,
        encoding="utf-8",
    )
    (repair_dir / "ruff_full.stderr").write_text(
        full.stderr,
        encoding="utf-8",
    )
    if full.returncode != 0:
        raise RepairError("Full Ruff gate still fails after safe repair")

    observed = changed_paths(worktree)
    if observed != candidates:
        raise RepairError(
            "Repair changed the exact candidate scope: "
            f"expected={sorted(candidates)}, observed={sorted(observed)}"
        )

    rollback = rollback_to_implemented(run_dir)
    report = {
        "status": "REPAIRED",
        "phase": phase,
        "repair": "RUFF_SAFE_FIX",
        "attempt": attempt,
        "findings": findings,
        "changed_python_paths": python_paths,
        "candidate_scope_preserved": True,
        "rollback": rollback,
        "llm_calls": 0,
    }
    write_object_atomic(repair_dir / "repair_report.json", report)
    return report


def try_bounded_repair(
    *,
    phase: str,
    manifest_path: Path,
    state_root: Path,
    python: str,
    attempt: int,
) -> dict[str, Any]:
    run_dir = latest_phase_run(state_root, phase)
    if run_dir is None:
        raise RepairError(f"No lifecycle run found for {phase}")
    run = load_object(run_dir / "run.json", "Lifecycle run")
    gate = classify_failure_gate(run)
    if gate != "Ruff":
        raise RepairError(
            f"{gate} failure classified; no automatic semantic "
            "repair is authorized"
        )
    return apply_ruff_safe_repair(
        phase=phase,
        manifest_path=manifest_path,
        state_root=state_root,
        python=python,
        attempt=attempt,
    )
