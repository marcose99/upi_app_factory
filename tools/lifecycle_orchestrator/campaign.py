from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from tools.lifecycle_orchestrator.repairs import (
    RepairError,
    latest_phase_run,
    load_object,
    try_bounded_repair,
    write_object_atomic,
)


class CampaignError(RuntimeError):
    """Raised when a governed multi-phase campaign cannot proceed."""


def state_root() -> Path:
    configured = os.environ.get("UPI_APP_FACTORY_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = Path(xdg_state).expanduser() if xdg_state else Path.home() / ".local/state"
    return (base / "upi_app_factory").resolve()


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def parse_approvals(value: str) -> set[str]:
    approvals = {
        item.strip() for item in value.split(",") if item.strip()
    }
    expected = {"commit", "merge", "push"}
    if approvals != expected:
        raise CampaignError(
            "Campaign requires exactly: commit,merge,push"
        )
    return approvals


def validate_campaign(
    campaign_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    campaign = load_object(campaign_path, "Campaign manifest")
    if campaign.get("schema_version") != 1:
        raise CampaignError("Unsupported campaign schema version")
    campaign_id = campaign.get("campaign")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise CampaignError("Campaign id is required")
    phases = campaign.get("phases")
    if not isinstance(phases, list) or not phases:
        raise CampaignError("Campaign phases are required")
    observed = []
    for item in phases:
        if not isinstance(item, dict):
            raise CampaignError("Campaign phase entry must be an object")
        phase = item.get("phase")
        manifest_value = item.get("manifest")
        if not isinstance(phase, str) or not phase:
            raise CampaignError("Campaign phase id is required")
        if not isinstance(manifest_value, str) or not manifest_value:
            raise CampaignError("Campaign manifest path is required")
        manifest_path = Path(manifest_value)
        if not manifest_path.is_absolute():
            manifest_path = project_root / manifest_path
        manifest = load_object(
            manifest_path.resolve(),
            f"{phase} manifest",
        )
        if manifest.get("phase") != phase:
            raise CampaignError(f"Phase mismatch for {phase}")
        manifest_status = manifest.get("status")
        if manifest_status not in {"ACTIVE", "DRAFT"}:
            raise CampaignError(
                f"Phase {phase} must be ACTIVE or DRAFT"
            )
        if manifest.get("protected_actions") != [
            "commit",
            "merge",
            "push",
        ]:
            raise CampaignError(
                f"Phase {phase} protected actions are unexpected"
            )
        llm = manifest.get("llm")
        if not isinstance(llm, dict):
            raise CampaignError(f"Phase {phase} LLM policy is missing")
        if llm.get("enabled") is not False or llm.get("allowed_calls") != 0:
            raise CampaignError(f"Phase {phase} must prohibit LLM calls")
        observed.append(
            {
                "phase": phase,
                "manifest": str(manifest_path.resolve()),
                "manifest_status": str(manifest_status),
            }
        )
    return {
        "campaign": campaign,
        "campaign_id": campaign_id,
        "phases": observed,
    }


def latest_campaign_run(root: Path, campaign_id: str) -> Path | None:
    campaign_root = root / "campaign_runs"
    if not campaign_root.is_dir():
        return None
    prefix = campaign_id.replace("_", "-") + "-"
    candidates = sorted(
        path
        for path in campaign_root.glob(prefix + "*")
        if path.is_dir() and (path / "campaign.json").is_file()
    )
    return candidates[-1] if candidates else None


def initialize_campaign(
    *,
    root: Path,
    campaign_id: str,
    campaign_path: Path,
    phases: list[dict[str, str]],
    approvals: set[str],
    resume: bool,
    project_root: Path,
) -> tuple[Path, dict[str, Any]]:
    existing = latest_campaign_run(root, campaign_id) if resume else None
    if existing is not None:
        state = load_object(
            existing / "campaign.json",
            "Campaign state",
        )
        if state.get("status") != "CLOSED":
            return existing, state

    run_id = f"{campaign_id.replace('_', '-')}-{timestamp()}"
    run_dir = root / "campaign_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    state = {
        "schema_version": 1,
        "campaign": campaign_id,
        "run_id": run_id,
        "status": "CREATED",
        "current_phase": None,
        "completed_phases": [],
        "phase_results": {},
        "approvals": sorted(approvals),
        "campaign_manifest": str(campaign_path),
        "project_root": str(project_root),
        "phases": phases,
        "repair_attempts": {},
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "llm_calls": 0,
    }
    write_object_atomic(run_dir / "campaign.json", state)
    return run_dir, state


def update_state(
    run_dir: Path,
    state: dict[str, Any],
) -> None:
    state["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    write_object_atomic(run_dir / "campaign.json", state)


def materialize_active_manifest(
    item: dict[str, str],
    run_dir: Path,
) -> Path:
    phase = item["phase"]
    source = Path(item["manifest"]).resolve()
    manifest = load_object(source, f"{phase} manifest")
    status = manifest.get("status")
    if status == "ACTIVE":
        return source
    if status != "DRAFT":
        raise CampaignError(
            f"Phase {phase} cannot be activated from status {status}"
        )

    active = dict(manifest)
    active["status"] = "ACTIVE"
    target = (
        run_dir
        / "active_manifests"
        / f"phase{phase.lower()}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    write_object_atomic(target, active)
    return target


def lifecycle_status(
    root: Path,
    phase: str,
) -> dict[str, Any] | None:
    run_dir = latest_phase_run(root, phase)
    if run_dir is None:
        return None
    return load_object(run_dir / "run.json", "Lifecycle run")


def run_lifecycle(
    *,
    project_root: Path,
    manifest_path: Path,
    output_path: Path,
) -> int:
    command = [
        str(project_root / "bin/upi-app-factory"),
        "lifecycle",
        "run",
        str(manifest_path),
        "--approve",
        "commit,merge,push",
        "--resume",
        "--project-root",
        str(project_root),
    ]
    with output_path.open("a", encoding="utf-8") as handle:
        command_text = "$ " + " ".join(command) + "\n"
        handle.write(command_text)
        handle.flush()
        print(command_text, end="")
        process = subprocess.Popen(
            command,
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if process.stdout is None:
            raise CampaignError("Lifecycle output stream was not created")
        for line in process.stdout:
            print(line, end="")
            handle.write(line)
            handle.flush()
        return process.wait()


def run_campaign(
    *,
    campaign_path: Path,
    project_root: Path,
    approvals: set[str],
    resume: bool,
) -> dict[str, Any]:
    validated = validate_campaign(campaign_path, project_root)
    campaign = validated["campaign"]
    campaign_id = validated["campaign_id"]
    phases = validated["phases"]
    root = state_root()
    root.mkdir(parents=True, exist_ok=True)

    run_dir, state = initialize_campaign(
        root=root,
        campaign_id=campaign_id,
        campaign_path=campaign_path,
        phases=phases,
        approvals=approvals,
        resume=resume,
        project_root=project_root,
    )
    if state.get("status") == "CLOSED":
        return state

    max_repairs_raw = campaign.get("max_repair_attempts", 2)
    if not isinstance(max_repairs_raw, int) or not 0 <= max_repairs_raw <= 3:
        raise CampaignError("max_repair_attempts must be between 0 and 3")
    max_repairs = max_repairs_raw
    python = str(project_root / ".venv/bin/python")
    if not Path(python).is_file():
        python = sys.executable

    completed_raw = state.get("completed_phases")
    results_raw = state.get("phase_results")
    attempts_raw = state.get("repair_attempts")
    if not isinstance(completed_raw, list):
        raise CampaignError("completed_phases must be a list")
    if not isinstance(results_raw, dict):
        raise CampaignError("phase_results must be an object")
    if not isinstance(attempts_raw, dict):
        raise CampaignError("repair_attempts must be an object")
    completed_phases = cast(list[str], completed_raw)
    phase_results = cast(dict[str, Any], results_raw)
    repair_attempts = cast(dict[str, Any], attempts_raw)

    state["status"] = "RUNNING"
    update_state(run_dir, state)

    for item in phases:
        phase = item["phase"]
        manifest_path = materialize_active_manifest(item, run_dir)
        if phase in completed_phases:
            status = lifecycle_status(root, phase)
            if status is None or status.get("status") != "CLOSED":
                raise CampaignError(
                    f"Campaign records {phase} complete but lifecycle is not CLOSED"
                )
            continue

        state["current_phase"] = phase
        update_state(run_dir, state)
        phase_log = run_dir / f"{phase.lower()}_lifecycle.log"

        while True:
            returncode = run_lifecycle(
                project_root=project_root,
                manifest_path=manifest_path,
                output_path=phase_log,
            )
            status = lifecycle_status(root, phase)
            if returncode == 0 and status is not None:
                if status.get("status") != "CLOSED":
                    raise CampaignError(
                        f"{phase} command succeeded without CLOSED state"
                    )
                break

            current_attempt_raw = repair_attempts.get(phase, 0)
            if not isinstance(current_attempt_raw, int):
                raise CampaignError("Repair attempt count is invalid")
            current_attempt = current_attempt_raw + 1
            if current_attempt > max_repairs:
                state["status"] = "FAILED"
                state["failure"] = {
                    "phase": phase,
                    "reason": "repair attempts exhausted",
                }
                update_state(run_dir, state)
                raise CampaignError(
                    f"{phase} failed after {max_repairs} repair attempts"
                )
            try:
                repair = try_bounded_repair(
                    phase=phase,
                    manifest_path=manifest_path,
                    state_root=root,
                    python=python,
                    attempt=current_attempt,
                )
            except RepairError as exc:
                state["status"] = "FAILED"
                state["failure"] = {
                    "phase": phase,
                    "reason": str(exc),
                    "repair_attempt": current_attempt,
                }
                update_state(run_dir, state)
                raise CampaignError(
                    f"{phase} failed and no safe repair was available: {exc}"
                ) from exc
            repair_attempts[phase] = current_attempt
            phase_results.setdefault(phase, {})
            phase_result = phase_results[phase]
            if not isinstance(phase_result, dict):
                raise CampaignError("Phase result must be an object")
            phase_result.setdefault("repairs", [])
            repairs = phase_result["repairs"]
            if not isinstance(repairs, list):
                raise CampaignError("Phase repairs must be a list")
            repairs.append(repair)
            update_state(run_dir, state)

        closed = lifecycle_status(root, phase)
        if closed is None:
            raise CampaignError(f"Closed lifecycle state missing for {phase}")
        phase_results.setdefault(phase, {})
        result = phase_results[phase]
        if not isinstance(result, dict):
            raise CampaignError("Phase result must be an object")
        result.update(
            {
                "status": "CLOSED",
                "run_id": closed.get("run_id"),
                "feature_commit": closed.get("feature_commit"),
                "protected_actions_performed": closed.get(
                    "protected_actions_performed"
                ),
                "llm_calls": closed.get("llm_calls", 0),
            }
        )
        completed_phases.append(phase)
        state["current_phase"] = None
        update_state(run_dir, state)

    state["status"] = "CLOSED"
    state["current_phase"] = None
    state["closed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    update_state(run_dir, state)
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a governed resumable multi-phase factory campaign"
    )
    parser.add_argument("action", choices=("run", "status", "validate"))
    parser.add_argument("campaign_manifest", type=Path)
    parser.add_argument("--approve", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    project_root = parsed.project_root.resolve()
    campaign_path = parsed.campaign_manifest.resolve()

    if parsed.action == "validate":
        result = validate_campaign(campaign_path, project_root)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    campaign = load_object(campaign_path, "Campaign manifest")
    campaign_id = campaign.get("campaign")
    if not isinstance(campaign_id, str):
        raise CampaignError("Campaign id is missing")

    if parsed.action == "status":
        existing = latest_campaign_run(state_root(), campaign_id)
        if existing is None:
            print("No campaign run found.")
            return 0
        print(
            json.dumps(
                load_object(existing / "campaign.json", "Campaign state"),
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    approvals = parse_approvals(parsed.approve)
    result = run_campaign(
        campaign_path=campaign_path,
        project_root=project_root,
        approvals=approvals,
        resume=parsed.resume,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
