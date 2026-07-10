from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any

from tools.lifecycle_orchestrator.repairs import try_bounded_repair


class LifecycleMaintenanceError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LifecycleMaintenanceError(f"JSON object required: {path}")
    return value


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def supersede_failed_run(
    *,
    state_root: Path,
    run_id: str,
    reason: str,
    evidence_export_dir: Path,
    approved: bool,
) -> dict[str, Any]:
    if not approved:
        raise LifecycleMaintenanceError("Explicit supersede approval required")
    run_dir = state_root / "lifecycle_runs" / run_id
    run_path = run_dir / "run.json"
    if not run_path.is_file():
        raise LifecycleMaintenanceError(f"Run is not discoverable: {run_id}")
    run = _load(run_path)
    if run.get("status") != "FAILED":
        raise LifecycleMaintenanceError("Only FAILED runs may be superseded")
    if run.get("feature_commit") not in (None, ""):
        raise LifecycleMaintenanceError("Committed runs require a separate governed disposition")
    if run.get("protected_actions_performed") not in ([], None):
        raise LifecycleMaintenanceError(
            "Run performed protected actions and cannot be superseded here"
        )
    incident = state_root / "incidents/superseded_lifecycle_runs" / run_id
    incident.mkdir(parents=True, exist_ok=True)
    shutil.copy2(run_path, incident / "run.original.json")
    record = {
        "schema_version": 1,
        "run_id": run_id,
        "disposition": "SUPERSEDED_FAILED_RUN",
        "reason": reason,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "protected_actions_performed": [],
        "deletion_performed": False,
    }
    _write(incident / "supersession_record.json", record)
    evidence_export_dir.mkdir(parents=True, exist_ok=True)
    archive = evidence_export_dir / f"{run_id}_superseded_evidence.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(run_dir, arcname=run_id)
        bundle.add(incident, arcname=incident.name)
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(
        f"{_sha256(archive)}  {archive.name}\n",
        encoding="utf-8",
    )
    run_path.rename(run_dir / "run.superseded.json")
    _write(run_dir / "superseded.json", record)
    return {
        **record,
        "archive": str(archive),
        "checksum": str(checksum),
        "discoverable": False,
    }


def repair_and_resume(
    *,
    state_root: Path,
    run_id: str,
    repair_id: str,
    manifest_path: Path,
    project_root: Path,
    python: str,
    approvals: tuple[str, ...],
) -> dict[str, Any]:
    if set(approvals) != {"commit", "merge", "push"}:
        raise LifecycleMaintenanceError("Exactly commit, merge, and push must be approved")
    run_dir = state_root / "lifecycle_runs" / run_id
    run = _load(run_dir / "run.json")
    if run.get("status") != "FAILED":
        raise LifecycleMaintenanceError("Run must be FAILED")
    attempts = run.setdefault("maintenance_repair_attempts", {})
    if not isinstance(attempts, dict):
        raise LifecycleMaintenanceError("maintenance_repair_attempts must be an object")
    attempt = int(attempts.get(repair_id, 0)) + 1
    if attempt > 2:
        raise LifecycleMaintenanceError("Repair attempt limit exceeded")
    result = try_bounded_repair(
        phase=str(run.get("phase")),
        manifest_path=manifest_path,
        state_root=state_root,
        python=python,
        attempt=attempt,
    )
    attempts[repair_id] = attempt
    run["maintenance_repair_attempts"] = attempts
    _write(run_dir / "run.json", run)
    completed = subprocess.run(
        [
            str(project_root / "bin/upi-app-factory"),
            "lifecycle",
            "run",
            str(manifest_path),
            "--approve",
            ",".join(approvals),
            "--resume",
            "--project-root",
            str(project_root),
        ],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LifecycleMaintenanceError(
            "Lifecycle resume failed after governed repair: " + completed.stdout + completed.stderr
        )
    closed = _load(run_dir / "run.json")
    if closed.get("status") != "CLOSED":
        raise LifecycleMaintenanceError("Lifecycle command returned success without CLOSED state")
    return {
        "run_id": run_id,
        "repair_id": repair_id,
        "attempt": attempt,
        "repair_result": result,
        "status": "CLOSED",
        "protected_actions_performed": closed.get("protected_actions_performed"),
        "tag_performed": closed.get("tag_performed", False),
        "release_performed": closed.get("release_performed", False),
        "llm_calls": closed.get("llm_calls", 0),
    }
