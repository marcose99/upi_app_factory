from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Iterable

from tools.autonomous_supervisor.catalog import RepairCatalog
from tools.autonomous_supervisor.evidence import package_directory, sha256
from tools.autonomous_supervisor.state import (
    append_jsonl,
    load_json_object,
    utc_now,
    write_json_atomic,
)


class SupervisorError(RuntimeError):
    """Raised when the governed autonomous supervisor must fail closed."""


def run_command(
    argv: list[str],
    *,
    cwd: Path | None = None,
    log_path: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> int:
    handle = (
        log_path.open("a", encoding="utf-8")
        if log_path is not None
        else None
    )
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if process.stdout is None:
            raise SupervisorError("Command output stream is unavailable")
        for line in process.stdout:
            print(line, end="")
            if handle is not None:
                handle.write(line)
                handle.flush()
        returncode = process.wait()
    finally:
        if handle is not None:
            handle.close()
    if check and returncode != 0:
        raise SupervisorError(
            f"Command failed with exit code {returncode}: "
            f"{' '.join(argv)}"
        )
    return returncode


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
    ).strip()


def latest_phase_run(
    state_root: Path,
    phase: str,
) -> Path | None:
    root = state_root / "lifecycle_runs"
    if not root.is_dir():
        return None
    candidates = sorted(
        path
        for path in root.glob(f"{phase.lower()}-*")
        if path.is_dir() and (path / "run.json").is_file()
    )
    return candidates[-1] if candidates else None


def worktree_status(worktree: Path) -> dict[str, str]:
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
    observed: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        text = entry.decode("utf-8")
        relative = text[3:]
        if " -> " in relative:
            relative = relative.split(" -> ", 1)[1]
        observed[relative] = text[:2]
    return observed


def candidate_paths(manifest_path: Path) -> list[str]:
    manifest = load_json_object(manifest_path)
    raw = manifest.get("candidate_paths")
    if not isinstance(raw, list) or not raw:
        raise SupervisorError("candidate_paths must be a non-empty list")
    values = [item for item in raw if isinstance(item, str) and item]
    if len(values) != len(raw):
        raise SupervisorError("candidate_paths contains invalid values")
    return values


def verify_candidate_scope(
    worktree: Path,
    expected: Iterable[str],
) -> None:
    expected_set = set(expected)
    observed_set = set(worktree_status(worktree))
    if observed_set != expected_set:
        raise SupervisorError(
            "Candidate scope mismatch after normalization; "
            f"expected={sorted(expected_set)}, "
            f"observed={sorted(observed_set)}"
        )


class AutonomousCampaignSupervisor:
    def __init__(
        self,
        *,
        project_root: Path,
        config_path: Path,
        approvals: tuple[str, ...],
        resume: bool,
    ) -> None:
        self.project_root = project_root.resolve()
        self.config_path = config_path.resolve()
        self.approvals = approvals
        self.resume = resume
        self.config = load_json_object(self.config_path)
        self.campaign_id = self._required_string("campaign_id")
        self.phases = self._required_string_list("phases")
        self.state_root = Path(
            os.environ.get(
                "UPI_APP_FACTORY_STATE_DIR",
                str(
                    Path.home()
                    / ".local/state/upi_app_factory"
                ),
            )
        ).resolve()
        self.export_dir = Path(
            os.environ.get(
                "UPI_APP_FACTORY_EXPORT_DIR",
                str(
                    Path.home()
                    / ".local/share/upi_app_factory/exports"
                ),
            )
        ).resolve()
        self.export_dir.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.execution_dir = (
            self.state_root
            / "autonomous_runs"
            / self.campaign_id
            / stamp
        )
        self.execution_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = (
            self.state_root
            / "autonomous_campaigns"
            / self.campaign_id
            / "supervisor.json"
        )
        self.events_path = (
            self.state_root
            / "autonomous_campaigns"
            / self.campaign_id
            / "events.jsonl"
        )
        self.control_path = (
            self.state_root
            / "autonomous_campaigns"
            / self.campaign_id
            / "control.json"
        )
        self.python = self._resolve_python()
        previous_state = (
            load_json_object(self.state_path)
            if self.resume and self.state_path.is_file()
            else {}
        )
        previous_attempts = previous_state.get("repair_attempts", {})
        self.repair_attempts = (
            {
                str(key): int(value)
                for key, value in previous_attempts.items()
            }
            if isinstance(previous_attempts, dict)
            else {}
        )
        previous_start = previous_state.get("start_commit")
        self.start_commit = (
            str(previous_start)
            if isinstance(previous_start, str) and previous_start
            else git(self.project_root, "rev-parse", "main")
        )
        self.catalog = RepairCatalog.load(
            self.project_root
            / self._required_string("repair_catalog")
        )
        self.prerequisite_manifest = load_json_object(
            self.project_root
            / self._required_string("prerequisite_manifest")
        )
        self.runtime_noise_policy = load_json_object(
            self.project_root
            / self._required_string("runtime_noise_policy")
        )
        limits = load_json_object(
            self.project_root
            / self._required_string("supervisor_limits")
        )
        self.max_cycles = int(limits.get("max_campaign_cycles", 20))
        self.default_max_attempts = int(
            limits.get("max_repair_attempts_per_phase", 3)
        )

    def _required_string(self, key: str) -> str:
        value = self.config.get(key)
        if not isinstance(value, str) or not value:
            raise SupervisorError(f"{key} must be a non-empty string")
        return value

    def _required_string_list(self, key: str) -> tuple[str, ...]:
        value = self.config.get(key)
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            raise SupervisorError(f"{key} must be a list of strings")
        return tuple(value)

    def _resolve_python(self) -> Path:
        candidate = self.project_root / ".venv/bin/python"
        return candidate if candidate.is_file() else Path(sys.executable)

    def event(
        self,
        event_type: str,
        *,
        phase: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        append_jsonl(
            self.events_path,
            {
                "at": utc_now(),
                "campaign_id": self.campaign_id,
                "event_type": event_type,
                "phase": phase,
                "details": details or {},
            },
        )

    def write_state(
        self,
        status: str,
        *,
        phase: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        current = (
            load_json_object(self.state_path)
            if self.state_path.is_file()
            else {}
        )
        write_json_atomic(
            self.state_path,
            {
                **current,
                "schema_version": 1,
                "campaign_id": self.campaign_id,
                "status": status,
                "current_phase": phase,
                "updated_at": utc_now(),
                "start_commit": self.start_commit,
                "repair_attempts": self.repair_attempts,
                "details": details or {},
            },
        )

    def check_control(self) -> None:
        if not self.control_path.is_file():
            return
        control = load_json_object(self.control_path)
        action = str(control.get("action", "RUN")).upper()
        if action == "PAUSE":
            self.write_state("PAUSED")
            self.event("SUPERVISOR_PAUSED")
            raise SystemExit(75)
        if action == "CANCEL":
            self.write_state("CANCELLED")
            self.event("SUPERVISOR_CANCELLED")
            raise SystemExit(76)

    def preflight(self) -> None:
        if git(self.project_root, "branch", "--show-current") != "main":
            raise SupervisorError("Source checkout must be on main")
        if git(self.project_root, "status", "--porcelain"):
            raise SupervisorError("Source main must be clean")
        run_command(
            [
                "git",
                "-C",
                str(self.project_root),
                "fetch",
                "--prune",
                "--tags",
                "origin",
            ],
            log_path=self.execution_dir / "preflight_fetch.log",
        )
        local_main = git(self.project_root, "rev-parse", "main")
        origin_main = git(
            self.project_root,
            "rev-parse",
            "origin/main",
        )
        if local_main != origin_main:
            raise SupervisorError("Local main and origin/main differ")
        required = {"commit", "merge", "push"}
        if set(self.approvals) != required:
            raise SupervisorError(
                "Exactly commit, merge, and push must be approved"
            )
        self.event(
            "PREFLIGHT_PASSED",
            details={
                "local_main": local_main,
                "origin_main": origin_main,
            },
        )

    def _runtime_noise_paths(self) -> tuple[str, ...]:
        raw = self.runtime_noise_policy.get("paths", [])
        if not isinstance(raw, list) or not all(
            isinstance(item, str) and item for item in raw
        ):
            raise SupervisorError("runtime noise paths are invalid")
        return tuple(raw)

    def restore_runtime_noise(
        self,
        worktree: Path,
        *,
        phase: str,
        label: str,
    ) -> None:
        observed = worktree_status(worktree)
        records: list[dict[str, str]] = []
        for relative in self._runtime_noise_paths():
            code = observed.get(relative)
            if code is None:
                continue
            tracked = subprocess.run(
                [
                    "git",
                    "-C",
                    str(worktree),
                    "ls-files",
                    "--error-unmatch",
                    relative,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode == 0
            if tracked:
                subprocess.check_call(
                    [
                        "git",
                        "-C",
                        str(worktree),
                        "checkout",
                        "--",
                        relative,
                    ]
                )
                action = "RESTORED_FROM_HEAD"
            else:
                target = worktree / relative
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
                action = "REMOVED_UNTRACKED"
            records.append(
                {
                    "path": relative,
                    "previous_status": code,
                    "action": action,
                }
            )
        write_json_atomic(
            self.execution_dir
            / f"{phase.lower()}_runtime_noise_{label}.json",
            {
                "status": "PASSED",
                "phase": phase,
                "label": label,
                "records": records,
            },
        )

    def provision_prerequisites(
        self,
        worktree: Path,
        *,
        phase: str,
    ) -> None:
        raw = self.prerequisite_manifest.get("artifacts")
        if not isinstance(raw, list):
            raise SupervisorError("Prerequisite artifacts must be a list")
        records: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise SupervisorError(
                    "Prerequisite artifact entry must be an object"
                )
            relative = item.get("path")
            expected = item.get("sha256")
            if not isinstance(relative, str) or not isinstance(
                expected,
                str,
            ):
                raise SupervisorError(
                    "Prerequisite path and hash are required"
                )
            source = self.project_root / relative
            target = worktree / relative
            if not source.is_file() or sha256(source) != expected:
                raise SupervisorError(
                    f"Prerequisite source is invalid: {relative}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if sha256(target) != expected:
                raise SupervisorError(
                    f"Prerequisite copy is invalid: {relative}"
                )
            records.append(
                {
                    "path": relative,
                    "sha256": expected,
                    "size": target.stat().st_size,
                }
            )
        write_json_atomic(
            self.execution_dir
            / f"{phase.lower()}_prerequisites.json",
            {
                "status": "PASSED",
                "phase": phase,
                "artifacts": records,
            },
        )

    def classify_failure(self, run_state: dict[str, Any]) -> str:
        failure = run_state.get("failure")
        message = (
            str(failure.get("message", ""))
            if isinstance(failure, dict)
            else ""
        )
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

    def apply_ruff_safe_fix(
        self,
        *,
        phase: str,
        worktree: Path,
        manifest_path: Path,
    ) -> None:
        expected = candidate_paths(manifest_path)
        diagnostics_path = (
            self.execution_dir
            / f"{phase.lower()}_ruff_diagnostics.json"
        )
        code = run_command(
            [
                str(self.python),
                "-m",
                "ruff",
                "check",
                ".",
                "--output-format=json",
            ],
            cwd=worktree,
            log_path=diagnostics_path,
            check=False,
        )
        if code == 0:
            return
        diagnostics = json.loads(
            diagnostics_path.read_text(encoding="utf-8")
        )
        if not isinstance(diagnostics, list) or not diagnostics:
            raise SupervisorError("Ruff diagnostics are invalid")
        candidates = {
            path for path in expected if path.endswith(".py")
        }
        affected: set[str] = set()
        for item in diagnostics:
            if not isinstance(item, dict):
                raise SupervisorError("Ruff diagnostic is invalid")
            filename = item.get("filename")
            if not isinstance(filename, str):
                raise SupervisorError(
                    "Ruff diagnostic filename is missing"
                )
            path = Path(filename)
            relative = (
                path.resolve().relative_to(worktree).as_posix()
                if path.is_absolute()
                else path.as_posix().removeprefix("./")
            )
            if relative not in candidates or item.get("fix") is None:
                raise SupervisorError(
                    "Ruff failure is not safely repairable within scope"
                )
            affected.add(relative)
        run_command(
            [
                str(self.python),
                "-m",
                "ruff",
                "check",
                "--fix",
                "--",
                *sorted(affected),
            ],
            cwd=worktree,
            log_path=(
                self.execution_dir
                / f"{phase.lower()}_ruff_safe_fix.log"
            ),
        )
        run_command(
            [str(self.python), "-m", "ruff", "check", "."],
            cwd=worktree,
            log_path=(
                self.execution_dir
                / f"{phase.lower()}_ruff_after_fix.log"
            ),
        )
        verify_candidate_scope(worktree, expected)

    def rollback_to_implemented(
        self,
        run_dir: Path,
        *,
        phase: str,
        reason: str,
    ) -> None:
        run_path = run_dir / "run.json"
        state = load_json_object(run_path)
        completed = state.get("completed_states")
        if not isinstance(completed, list):
            raise SupervisorError("completed_states must be a list")
        keep = {
            "PREFLIGHT_PASSED",
            "WORKTREE_READY",
            "IMPLEMENTED",
        }
        if not keep.issubset(set(completed)):
            raise SupervisorError(
                f"{phase} cannot be rolled back to IMPLEMENTED"
            )
        state["completed_states"] = [
            item for item in completed if item in keep
        ]
        evidence = state.get("step_evidence")
        if not isinstance(evidence, dict):
            raise SupervisorError("step_evidence must be an object")
        state["step_evidence"] = {
            key: value for key, value in evidence.items() if key in keep
        }
        state["current_state"] = "IMPLEMENTED"
        state["status"] = "IMPLEMENTED"
        state.pop("failure", None)
        state["updated_at"] = utc_now()
        state["autonomous_repair_resume"] = {
            "reason": reason,
            "rolled_back_to": "IMPLEMENTED",
            "stale_evidence_invalidated": True,
        }
        steps = run_dir / "steps"
        if steps.is_dir():
            for path in sorted(steps.glob("*.json")):
                prefix = path.name.split("_", 1)[0]
                if prefix.isdigit() and int(prefix) >= 4:
                    path.unlink()
        candidate_manifest = run_dir / "candidate_manifest.json"
        if candidate_manifest.is_file():
            candidate_manifest.unlink()
        write_json_atomic(run_path, state)

    def lifecycle_resume(
        self,
        *,
        phase: str,
        manifest_path: Path,
    ) -> int:
        return run_command(
            [
                str(self.project_root / "bin/upi-app-factory"),
                "lifecycle",
                "run",
                str(manifest_path),
                "--approve",
                "commit,merge,push",
                "--resume",
                "--project-root",
                str(self.project_root),
            ],
            cwd=self.project_root,
            log_path=(
                self.execution_dir
                / f"{phase.lower()}_lifecycle_resume.log"
            ),
            check=False,
        )

    def repair_failed_phase(self, phase: str) -> None:
        attempt = self.repair_attempts.get(phase, 0) + 1
        self.repair_attempts[phase] = attempt
        run_dir = latest_phase_run(self.state_root, phase)
        if run_dir is None:
            raise SupervisorError(f"No lifecycle run found for {phase}")
        run_path = run_dir / "run.json"
        state = load_json_object(run_path)
        worktree = Path(str(state["worktree"])).resolve()
        manifest_path = Path(str(state["manifest_path"])).resolve()
        gate = self.classify_failure(state)
        rule = self.catalog.automatic_rule_for_gate(gate)
        max_attempts = (
            rule.max_attempts
            if rule is not None
            else self.default_max_attempts
        )
        if rule is None or attempt > max_attempts:
            self.create_incident(
                phase=phase,
                run_dir=run_dir,
                reason=(
                    f"No authorized automatic repair for {gate} "
                    f"at attempt {attempt}"
                ),
            )
            raise SupervisorError(
                f"{phase} failed closed at gate {gate}"
            )
        self.check_control()
        self.restore_runtime_noise(
            worktree,
            phase=phase,
            label=f"attempt_{attempt}",
        )
        self.provision_prerequisites(worktree, phase=phase)
        expected = candidate_paths(manifest_path)
        verify_candidate_scope(worktree, expected)

        if rule.repair_id == "RUFF_SAFE_FIX":
            self.apply_ruff_safe_fix(
                phase=phase,
                worktree=worktree,
                manifest_path=manifest_path,
            )
            reason = rule.repair_id
        elif rule.repair_id == "PYTEST_PREREQUISITE_REPLAY":
            code = run_command(
                [
                    str(self.python),
                    "-m",
                    "pytest",
                    "--lf",
                    "-q",
                    "--tb=short",
                ],
                cwd=worktree,
                log_path=(
                    self.execution_dir
                    / f"{phase.lower()}_pytest_replay.log"
                ),
                check=False,
            )
            self.restore_runtime_noise(
                worktree,
                phase=phase,
                label=f"after_pytest_{attempt}",
            )
            if code != 0:
                self.create_incident(
                    phase=phase,
                    run_dir=run_dir,
                    reason="Pytest remained failing after normalization",
                )
                raise SupervisorError(
                    f"{phase} has an unapproved semantic test failure"
                )
            verify_candidate_scope(worktree, expected)
            reason = rule.repair_id
        elif rule.repair_id == "RUNTIME_NOISE_RESTORE":
            verify_candidate_scope(worktree, expected)
            reason = rule.repair_id
        else:
            raise SupervisorError(
                f"Unsupported repair implementation: {rule.repair_id}"
            )

        self.rollback_to_implemented(
            run_dir,
            phase=phase,
            reason=reason,
        )
        self.event(
            "REPAIR_APPLIED",
            phase=phase,
            details={
                "repair_id": rule.repair_id,
                "attempt": attempt,
            },
        )

    def campaign_manifest_path(self) -> Path:
        return (
            self.project_root
            / self._required_string("campaign_manifest")
        )

    def run_campaign_once(self) -> int:
        binary = self.project_root / "bin/upi-app-factory-campaign"
        manifest = self.campaign_manifest_path()
        run_command(
            [
                str(binary),
                "validate",
                str(manifest),
                "--project-root",
                str(self.project_root),
            ],
            cwd=self.project_root,
            log_path=self.execution_dir / "campaign_validation.log",
        )
        return run_command(
            [
                str(binary),
                "run",
                str(manifest),
                "--approve",
                "commit,merge,push",
                "--resume",
                "--project-root",
                str(self.project_root),
            ],
            cwd=self.project_root,
            log_path=self.execution_dir / "campaign_run.log",
            check=False,
        )

    def failed_phase(self) -> str | None:
        for phase in self.phases:
            run_dir = latest_phase_run(self.state_root, phase)
            if run_dir is None:
                continue
            state = load_json_object(run_dir / "run.json")
            if state.get("status") == "FAILED":
                return phase
        return None

    def all_phases_closed(self) -> bool:
        for phase in self.phases:
            run_dir = latest_phase_run(self.state_root, phase)
            if run_dir is None:
                return False
            state = load_json_object(run_dir / "run.json")
            if state.get("status") != "CLOSED":
                return False
        return True

    def progress(self) -> None:
        for cycle in range(1, self.max_cycles + 1):
            self.check_control()
            self.write_state(
                "RUNNING",
                details={"cycle": cycle},
            )
            if self.all_phases_closed():
                return
            code = self.run_campaign_once()
            if code == 0 and self.all_phases_closed():
                return
            phase = self.failed_phase()
            if phase is None:
                raise SupervisorError(
                    "Campaign stopped without a failed phase"
                )
            self.repair_failed_phase(phase)
            run_dir = latest_phase_run(self.state_root, phase)
            if run_dir is None:
                raise SupervisorError(
                    f"Lifecycle run disappeared for {phase}"
                )
            state = load_json_object(run_dir / "run.json")
            manifest = Path(str(state["manifest_path"])).resolve()
            self.lifecycle_resume(
                phase=phase,
                manifest_path=manifest,
            )
        raise SupervisorError(
            "Autonomous campaign exceeded its cycle limit"
        )

    def verify_closure(self) -> dict[str, Any]:
        run_command(
            [
                "git",
                "-C",
                str(self.project_root),
                "fetch",
                "--prune",
                "--tags",
                "origin",
            ],
            log_path=self.execution_dir / "final_fetch.log",
        )
        previous = self.start_commit
        records: dict[str, Any] = {}
        for phase in self.phases:
            run_dir = latest_phase_run(self.state_root, phase)
            if run_dir is None:
                raise SupervisorError(f"No lifecycle run for {phase}")
            state = load_json_object(run_dir / "run.json")
            if state.get("status") != "CLOSED":
                raise SupervisorError(f"{phase} is not CLOSED")
            if state.get("base_commit") != previous:
                raise SupervisorError(
                    f"{phase} breaks the campaign commit chain"
                )
            commit = state.get("feature_commit")
            if not isinstance(commit, str) or not commit:
                raise SupervisorError(
                    f"{phase} feature commit is missing"
                )
            records[phase] = {
                "run_id": state.get("run_id"),
                "base_commit": state.get("base_commit"),
                "commit": commit,
                "completed_states": state.get("completed_states"),
                "llm_calls": state.get("llm_calls", 0),
            }
            previous = commit

        local_main = git(
            self.project_root,
            "rev-parse",
            "main",
        )
        origin_main = git(
            self.project_root,
            "rev-parse",
            "origin/main",
        )
        if local_main != previous or origin_main != previous:
            raise SupervisorError(
                "Main does not point to the final campaign commit"
            )
        if git(
            self.project_root,
            "rev-list",
            "--left-right",
            "--count",
            "origin/main...main",
        ).split() != ["0", "0"]:
            raise SupervisorError("Local/remote divergence is not 0/0")
        if git(self.project_root, "status", "--porcelain"):
            raise SupervisorError("Source main is not clean")

        report = {
            "status": "PASSED",
            "campaign_id": self.campaign_id,
            "phase_records": records,
            "local_main": local_main,
            "origin_main": origin_main,
            "local_remote_divergence": [0, 0],
            "repair_attempts": self.repair_attempts,
            "tags_created": False,
            "release_performed": False,
            "llm_calls": 0,
        }
        write_json_atomic(
            self.execution_dir / "closure.json",
            report,
        )
        return report

    def create_incident(
        self,
        *,
        phase: str,
        run_dir: Path,
        reason: str,
    ) -> Path:
        incident = (
            self.execution_dir
            / "incidents"
            / f"{phase.lower()}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        incident.mkdir(parents=True, exist_ok=True)
        write_json_atomic(
            incident / "incident.json",
            {
                "status": "FAIL_CLOSED",
                "phase": phase,
                "reason": reason,
                "created_at": utc_now(),
                "repair_attempts": self.repair_attempts,
            },
        )
        state = load_json_object(run_dir / "run.json")
        worktree = Path(str(state["worktree"])).resolve()
        (incident / "git_status.txt").write_text(
            git(worktree, "status", "--short") + "\n",
            encoding="utf-8",
        )
        (incident / "git_diff.patch").write_text(
            subprocess.check_output(
                ["git", "-C", str(worktree), "diff", "--binary"],
                text=True,
            ),
            encoding="utf-8",
        )
        destination = self.export_dir / (
            f"{self.campaign_id}-{phase.lower()}-incident-"
            f"{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.tar.gz"
        )
        package_directory(incident, destination)
        return destination

    def execute(self) -> dict[str, Any]:
        self.write_state("STARTING")
        self.preflight()
        self.progress()
        closure = self.verify_closure()
        self.write_state("CLOSED", details=closure)
        destination = self.export_dir / (
            f"{self.campaign_id}-autonomous-closure-"
            f"{self.execution_dir.name}.tar.gz"
        )
        package, checksum = package_directory(
            self.execution_dir,
            destination,
        )
        closure["evidence_package"] = str(package)
        closure["evidence_checksum"] = str(checksum)
        return closure


def validate_configuration(
    project_root: Path,
    config_path: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    config = load_json_object(config_path.resolve())
    required_files = (
        "campaign_manifest",
        "repair_catalog",
        "prerequisite_manifest",
        "runtime_noise_policy",
        "supervisor_limits",
    )
    for key in required_files:
        value = config.get(key)
        if not isinstance(value, str) or not (root / value).is_file():
            raise SupervisorError(
                f"Configured file is missing for {key}"
            )
    phases = config.get("phases")
    if not isinstance(phases, list) or not phases:
        raise SupervisorError("phases must be a non-empty list")
    RepairCatalog.load(root / str(config["repair_catalog"]))
    return {
        "status": "PASSED",
        "campaign_id": config.get("campaign_id"),
        "phase_count": len(phases),
        "llm_calls": 0,
    }
