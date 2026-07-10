from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from tools.lifecycle_orchestrator.models import (
    ApprovalSet,
    CommandResult,
    LifecycleState,
    STATE_ORDER,
)


SCHEMA_VERSION = 1
NUMBERED_EVIDENCE_PATTERN = re.compile(r"^checkpoint_[0-9]{3}\.json$")
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


class LifecycleError(RuntimeError):
    """Raised when a lifecycle governance or evidence boundary is crossed."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LifecycleError(f"{label} must be a JSON object")
    return {str(key): value for key, value in raw.items()}


def state_root() -> Path:
    configured = os.environ.get("UPI_APP_FACTORY_STATE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = (
        Path(xdg_state).expanduser()
        if xdg_state
        else Path.home() / ".local" / "state"
    )
    return (base / "upi_app_factory").resolve()


def export_root() -> Path:
    configured = os.environ.get("UPI_APP_FACTORY_EXPORT_DIR")
    if configured:
        root = Path(configured).expanduser().resolve()
    else:
        downloads = Path.home() / "Downloads"
        root = downloads if downloads.is_dir() else (
            Path.home() / ".local" / "share" / "upi_app_factory" / "exports"
        )
    root.mkdir(parents=True, exist_ok=True)
    return root


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise LifecycleError(
            f"Git command failed: git {' '.join(arguments)}\n"
            f"{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def git_success(root: Path, *arguments: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def repository_fingerprint(root: Path) -> dict[str, str]:
    return {
        "head": git(root, "rev-parse", "HEAD"),
        "status_sha256": sha256_bytes(
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(root),
                    "status",
                    "--porcelain=v1",
                    "-z",
                    "-uall",
                ]
            )
        ),
        "diff_sha256": sha256_bytes(
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(root),
                    "diff",
                    "--binary",
                    "--no-ext-diff",
                ]
            )
        ),
    }


def parse_validation_metrics(stdout: str, stderr: str) -> dict[str, Any]:
    text = stdout + "\n" + stderr
    metrics: dict[str, Any] = {}

    pytest_matches = re.findall(r"(?m)(\d+)\s+passed\b", text)
    if pytest_matches:
        metrics["pytest_passed"] = int(pytest_matches[-1])

    mypy_matches = re.findall(
        r"Success: no issues found in (\d+) source files",
        text,
    )
    if mypy_matches:
        metrics["mypy_source_files"] = int(mypy_matches[-1])

    if "All checks passed!" in text:
        metrics["ruff"] = "PASSED"

    if '"passed": true' in text and '"errors": []' in text:
        metrics["structured_validation"] = "PASSED"

    return metrics


def numbered_checkpoint_files(run_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in run_dir.iterdir()
        if path.is_file() and NUMBERED_EVIDENCE_PATTERN.fullmatch(path.name)
    )


def atomic_write_text_validated(
    path: Path,
    content: str,
    validator: Callable[[str], None],
) -> None:
    validator(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    validator(temporary.read_text(encoding="utf-8"))
    temporary.replace(path)


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LifecycleError(f"Manifest field {key!r} must be a string")
    return value


def _require_string_list(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise LifecycleError(f"Manifest field {key!r} must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise LifecycleError(
                f"Manifest field {key!r} must contain strings"
            )
        result.append(item)
    return result


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise LifecycleError("Unsupported lifecycle manifest schema")
    if manifest.get("status") != "ACTIVE":
        raise LifecycleError("Lifecycle manifest must be ACTIVE")

    _require_string(manifest, "phase")
    _require_string(manifest, "name")
    _require_string(manifest, "base_branch")
    _require_string(manifest, "feature_branch")
    _require_string(manifest, "commit_message")
    candidate_paths = _require_string_list(manifest, "candidate_paths")
    if len(candidate_paths) != len(set(candidate_paths)):
        raise LifecycleError("candidate_paths contains duplicates")
    if not candidate_paths:
        raise LifecycleError("candidate_paths must not be empty")

    protected = _require_string_list(manifest, "protected_actions")
    unsupported = set(protected) - {"commit", "merge", "push"}
    if unsupported:
        raise LifecycleError(
            "Lifecycle run cannot automate these protected actions: "
            + ", ".join(sorted(unsupported))
        )

    required_command_keys = (
        "implementation_commands",
        "targeted_validation_commands",
        "full_validation_commands",
    )
    for key in required_command_keys:
        if key not in manifest:
            raise LifecycleError(f"Manifest field {key!r} is required")

    for key in (
        *required_command_keys,
        "post_restore_validation_commands",
    ):
        commands = manifest.get(key, [])
        if not isinstance(commands, list):
            raise LifecycleError(f"{key} must be a list")
        for command in commands:
            if not isinstance(command, dict):
                raise LifecycleError(f"{key} entries must be objects")
            _require_string(command, "name")
            argv = command.get("argv")
            if (
                not isinstance(argv, list)
                or not argv
                or not all(isinstance(item, str) for item in argv)
            ):
                raise LifecycleError(
                    f"{key} command argv must be a non-empty string list"
                )
            if any(
                token in {"|", "&&", ";", ">", "<"}
                for token in argv
            ):
                raise LifecycleError(
                    "Shell control operators are prohibited in argv"
                )

    runtime_noise = manifest.get("runtime_noise_paths", [])
    if not isinstance(runtime_noise, list) or not all(
        isinstance(item, str) for item in runtime_noise
    ):
        raise LifecycleError("runtime_noise_paths must be a string list")

    llm = manifest.get("llm")
    if (
        not isinstance(llm, dict)
        or llm.get("enabled") is not False
        or llm.get("allowed_calls") != 0
    ):
        raise LifecycleError("Lifecycle manifests require zero LLM calls")

    return manifest


def manifest_digest(manifest: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(manifest))


def infer_git_lifecycle_position(
    *,
    base_commit: str,
    feature_commit: str | None,
    main_commit: str,
    remote_commit: str,
) -> str:
    if feature_commit is None or feature_commit == base_commit:
        if main_commit == base_commit and remote_commit == base_commit:
            return "UNCOMMITTED"
        raise LifecycleError(
            "Main or remote advanced without a feature commit"
        )
    if main_commit == base_commit and remote_commit == base_commit:
        return "COMMITTED_NOT_MERGED"
    if main_commit == feature_commit and remote_commit == base_commit:
        return "MERGED_NOT_PUSHED"
    if main_commit == feature_commit and remote_commit == feature_commit:
        return "ALREADY_SYNCHRONIZED"
    raise LifecycleError("Unsupported Git lifecycle position")


class LifecycleEngine:
    def __init__(
        self,
        project_root: Path,
        manifest_path: Path,
        approvals: ApprovalSet,
        *,
        resume: bool = False,
        dry_run: bool = False,
    ) -> None:
        self.project_root = project_root.resolve()
        self.manifest_path = manifest_path.resolve()
        self.manifest = validate_manifest(
            load_json_object(self.manifest_path, "Lifecycle manifest")
        )
        self.approvals = approvals
        self.resume = resume
        self.dry_run = dry_run
        self.phase = _require_string(self.manifest, "phase")
        self.phase_slug = self.phase.lower()
        self.branch = _require_string(
            self.manifest,
            "feature_branch",
        )
        self.base_branch = _require_string(
            self.manifest,
            "base_branch",
        )
        self.commit_message = _require_string(
            self.manifest,
            "commit_message",
        )
        self.candidate_paths = _require_string_list(
            self.manifest,
            "candidate_paths",
        )
        self.run_dir = self._resolve_run_dir()
        self.steps_dir = self.run_dir / "steps"
        self.logs_dir = self.run_dir / "logs"
        self.steps_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "run.json"
        self.state = self._load_or_create_state()
        self.state["approvals"] = self.approvals.to_dict()
        self._save_state()
        self.worktree = Path(
            str(self.state["worktree"])
        ).expanduser().resolve()
        self.python = self._resolve_python()

    def _resolve_run_dir(self) -> Path:
        root = state_root() / "lifecycle_runs"
        root.mkdir(parents=True, exist_ok=True)
        if self.resume:
            candidates = sorted(
                (
                    path
                    for path in root.glob(f"{self.phase_slug}-*")
                    if path.is_dir() and (path / "run.json").is_file()
                ),
                reverse=True,
            )
            for candidate in candidates:
                state = load_json_object(
                    candidate / "run.json",
                    "Lifecycle state",
                )
                if (
                    state.get("phase") == self.phase
                    and state.get("status") != "CLOSED"
                ):
                    return candidate
        run_id = (
            f"{self.phase_slug}-"
            + dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        )
        return root / run_id

    def _load_or_create_state(self) -> dict[str, Any]:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        digest = manifest_digest(self.manifest)
        if self.state_path.is_file():
            existing_state = load_json_object(
                self.state_path,
                "Lifecycle state",
            )
            if existing_state.get("manifest_digest") != digest:
                raise LifecycleError(
                    "Manifest changed since this lifecycle run started"
                )
            return existing_state

        worktree_root = os.environ.get(
            "UPI_APP_FACTORY_WORKTREE_ROOT",
            str(
                self.project_root.parent
                / ".upi_app_factory_worktrees"
            ),
        )
        worktree = (
            Path(worktree_root).expanduser().resolve()
            / f"{self.phase_slug}-{self.branch.split('/')[-1]}"
        )
        state: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_dir.name,
            "phase": self.phase,
            "name": self.manifest["name"],
            "status": LifecycleState.CREATED.value,
            "current_state": LifecycleState.CREATED.value,
            "completed_states": [],
            "manifest_path": str(self.manifest_path),
            "manifest_digest": digest,
            "project_root": str(self.project_root),
            "worktree": str(worktree),
            "feature_branch": self.branch,
            "base_branch": self.base_branch,
            "base_commit": None,
            "feature_commit": None,
            "approvals": self.approvals.to_dict(),
            "dry_run": self.dry_run,
            "llm_calls": 0,
            "protected_actions_performed": [],
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "step_evidence": {},
        }
        write_json(self.state_path, state)
        return state

    def _resolve_python(self) -> str:
        candidate = self.project_root / ".venv" / "bin" / "python"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        return sys.executable

    def _save_state(self) -> None:
        self.state["updated_at"] = utc_now()
        write_json(self.state_path, self.state)

    def _state_completed(self, state: LifecycleState) -> bool:
        return state.value in self.state.get("completed_states", [])

    def _record_state(
        self,
        state: LifecycleState,
        evidence: dict[str, Any],
    ) -> None:
        evidence_path = (
            self.steps_dir
            / f"{STATE_ORDER.index(state):02d}_{state.value.lower()}.json"
        )
        write_json(evidence_path, evidence)
        completed = list(self.state.get("completed_states", []))
        if state.value not in completed:
            completed.append(state.value)
        self.state["completed_states"] = completed
        self.state["current_state"] = state.value
        self.state["status"] = state.value
        step_evidence = dict(self.state.get("step_evidence", {}))
        step_evidence[state.value] = {
            "path": str(evidence_path),
            "sha256": sha256_file(evidence_path),
        }
        self.state["step_evidence"] = step_evidence
        self._save_state()

    def _verify_completed_evidence(
        self,
        state: LifecycleState,
    ) -> None:
        record = self.state.get("step_evidence", {}).get(state.value)
        if not isinstance(record, dict):
            raise LifecycleError(
                f"Missing evidence record for completed state {state.value}"
            )
        path = Path(str(record.get("path", "")))
        expected_hash = record.get("sha256")
        if (
            not path.is_file()
            or not isinstance(expected_hash, str)
            or sha256_file(path) != expected_hash
        ):
            raise LifecycleError(
                f"Evidence integrity failure for {state.value}"
            )

    def _complete_or_run(
        self,
        state: LifecycleState,
        action: Callable[[], dict[str, Any]],
    ) -> None:
        if self._state_completed(state):
            self._verify_completed_evidence(state)
            print(f"[resume] {state.value}: verified and skipped")
            return
        evidence = action()
        self._record_state(state, evidence)
        print(f"[complete] {state.value}")

    def _require_approval(self, action: str) -> None:
        if not self.approvals.approved(action):
            raise LifecycleError(
                f"Protected action {action!r} lacks approval"
            )

    def _resolve_tokens(
        self,
        argv: Sequence[str],
        cwd: Path,
    ) -> list[str]:
        replacements = {
            "{repo}": str(self.project_root),
            "{worktree}": str(self.worktree),
            "{python}": self.python,
            "{phase}": self.phase,
            "{run_dir}": str(self.run_dir),
            "{cwd}": str(cwd),
        }
        result: list[str] = []
        for token in argv:
            resolved = token
            for marker, value in replacements.items():
                resolved = resolved.replace(marker, value)
            result.append(resolved)
        return result

    def _run_commands(
        self,
        commands: list[dict[str, Any]],
        *,
        cwd: Path,
        category: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        environment = os.environ.copy()
        existing_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            str(cwd)
            if not existing_pythonpath
            else str(cwd) + os.pathsep + existing_pythonpath
        )
        environment["UPI_APP_FACTORY_STATE_DIR"] = str(state_root())
        environment["UPI_APP_FACTORY_EXPORT_DIR"] = str(export_root())

        for index, command in enumerate(commands, start=1):
            name = _require_string(command, "name")
            argv_raw = command["argv"]
            assert isinstance(argv_raw, list)
            argv = self._resolve_tokens(argv_raw, cwd)
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
            log_path = (
                self.logs_dir
                / f"{category}_{index:02d}_{safe_name}.log"
            )
            started = time.monotonic()
            completed = subprocess.run(
                argv,
                cwd=str(cwd),
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            duration = round(time.monotonic() - started, 6)
            combined = (
                "$ "
                + shlex.join(argv)
                + "\n\n[stdout]\n"
                + completed.stdout
                + "\n[stderr]\n"
                + completed.stderr
            )
            log_path.write_text(combined, encoding="utf-8")
            result = CommandResult(
                name=name,
                argv=argv,
                returncode=completed.returncode,
                duration_seconds=duration,
                stdout_sha256=sha256_bytes(
                    completed.stdout.encode("utf-8")
                ),
                stderr_sha256=sha256_bytes(
                    completed.stderr.encode("utf-8")
                ),
                metrics=parse_validation_metrics(
                    completed.stdout,
                    completed.stderr,
                ),
                log_file=str(log_path),
            )
            results.append(result.to_dict())
            if completed.returncode != 0:
                raise LifecycleError(
                    f"Command failed ({name}): {shlex.join(argv)}; "
                    f"see {log_path}"
                )
        return results

    def _preflight(self) -> dict[str, Any]:
        if git(self.project_root, "branch", "--show-current") != self.base_branch:
            raise LifecycleError(
                f"Source checkout must be on {self.base_branch}"
            )
        if git(self.project_root, "status", "--porcelain"):
            raise LifecycleError("Source checkout must be clean")
        git(self.project_root, "fetch", "--prune", "--tags", "origin")
        local_base = git(
            self.project_root,
            "rev-parse",
            self.base_branch,
        )
        remote_base = git(
            self.project_root,
            "rev-parse",
            f"origin/{self.base_branch}",
        )
        if local_base != remote_base:
            raise LifecycleError(
                "Local and remote base branch are not synchronized"
            )
        self.state["base_commit"] = local_base
        self._save_state()
        return {
            "state": LifecycleState.PREFLIGHT_PASSED.value,
            "local_base": local_base,
            "remote_base": remote_base,
            "source_clean": True,
            "approvals": self.approvals.to_dict(),
            "llm_calls": 0,
        }

    def _prepare_worktree(self) -> dict[str, Any]:
        base_commit = str(self.state["base_commit"])
        if self.worktree.exists():
            if not git_success(
                self.worktree,
                "rev-parse",
                "--is-inside-work-tree",
            ):
                raise LifecycleError(
                    "Existing lifecycle worktree path is invalid"
                )
            if git(
                self.worktree,
                "branch",
                "--show-current",
            ) != self.branch:
                raise LifecycleError(
                    "Existing lifecycle worktree uses another branch"
                )
        else:
            self.worktree.parent.mkdir(parents=True, exist_ok=True)
            if git_success(
                self.project_root,
                "show-ref",
                "--verify",
                f"refs/heads/{self.branch}",
            ):
                git(
                    self.project_root,
                    "worktree",
                    "add",
                    str(self.worktree),
                    self.branch,
                )
            else:
                git(
                    self.project_root,
                    "worktree",
                    "add",
                    "-b",
                    self.branch,
                    str(self.worktree),
                    base_commit,
                )
        head = git(self.worktree, "rev-parse", "HEAD")
        if head != base_commit and not self._state_completed(
            LifecycleState.COMMITTED
        ):
            raise LifecycleError(
                "Uncommitted lifecycle worktree is not at the base commit"
            )
        return {
            "state": LifecycleState.WORKTREE_READY.value,
            "worktree": str(self.worktree),
            "branch": self.branch,
            "head": head,
        }

    def _implementation(self) -> dict[str, Any]:
        commands = self.manifest["implementation_commands"]
        assert isinstance(commands, list)
        results = self._run_commands(
            commands,
            cwd=self.worktree,
            category="implementation",
        )
        return {
            "state": LifecycleState.IMPLEMENTED.value,
            "commands": results,
            "repository_fingerprint": repository_fingerprint(
                self.worktree
            ),
        }

    def _validation(
        self,
        *,
        key: str,
        state: LifecycleState,
        category: str,
    ) -> dict[str, Any]:
        commands = self.manifest.get(key, [])
        assert isinstance(commands, list)
        results = self._run_commands(
            commands,
            cwd=self.worktree,
            category=category,
        )
        observed_metrics = {
            result["name"]: result["metrics"]
            for result in results
        }
        return {
            "state": state.value,
            "commands": results,
            "observed_metrics": observed_metrics,
            "count_policy": "OBSERVE_NOT_HARDCODE",
            "all_exit_codes_zero": True,
        }

    def _candidate_verification(self) -> dict[str, Any]:
        status_raw = subprocess.check_output(
            [
                "git",
                "-C",
                str(self.worktree),
                "status",
                "--porcelain=v1",
                "-z",
                "-uall",
            ]
        )
        observed: dict[str, str] = {}
        for raw in status_raw.split(b"\0"):
            if not raw:
                continue
            text = raw.decode("utf-8")
            code = text[:2]
            path_text = text[3:]
            if " -> " in path_text:
                path_text = path_text.split(" -> ", 1)[1]
            observed[path_text] = code

        expected = set(self.candidate_paths)
        if set(observed) != expected:
            raise LifecycleError(
                "Candidate path set mismatch; expected "
                f"{sorted(expected)}, observed {sorted(observed)}"
            )

        secret_findings: list[dict[str, str]] = []
        records: list[dict[str, Any]] = []
        for relative in self.candidate_paths:
            path = self.worktree / relative
            if not path.is_file() or path.is_symlink():
                raise LifecycleError(
                    f"Candidate is not a regular file: {relative}"
                )
            data = path.read_bytes()
            text = data.decode("utf-8")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    secret_findings.append(
                        {
                            "path": relative,
                            "pattern": pattern.pattern,
                        }
                    )
            records.append(
                {
                    "path": relative,
                    "status_code": observed[relative],
                    "size": len(data),
                    "sha256": sha256_bytes(data),
                }
            )
        if secret_findings:
            raise LifecycleError(
                "High-confidence secret pattern found in candidate"
            )
        write_json(self.run_dir / "candidate_manifest.json", records)
        return {
            "state": LifecycleState.CANDIDATE_VERIFIED.value,
            "candidate_file_count": len(records),
            "candidate_files": records,
            "high_confidence_secret_findings": [],
        }

    def _restore_runtime_noise(self, root: Path) -> list[str]:
        raw_paths = self.manifest.get("runtime_noise_paths", [])
        assert isinstance(raw_paths, list)
        existing = [
            item
            for item in raw_paths
            if git_success(root, "ls-files", "--error-unmatch", item)
        ]
        if existing:
            git(root, "restore", "--source=HEAD", "--worktree", "--", *existing)
        return existing

    def _verify_candidate_stability(self) -> list[dict[str, Any]]:
        manifest_path = self.run_dir / "candidate_manifest.json"
        if not manifest_path.is_file():
            raise LifecycleError("Candidate manifest is missing")
        raw: object = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
        if not isinstance(raw, list):
            raise LifecycleError("Candidate manifest must be a list")
        records: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise LifecycleError(
                    "Candidate manifest entries must be objects"
                )
            record = {str(key): value for key, value in item.items()}
            relative = record.get("path")
            expected_hash = record.get("sha256")
            expected_size = record.get("size")
            if (
                not isinstance(relative, str)
                or not isinstance(expected_hash, str)
                or not isinstance(expected_size, int)
            ):
                raise LifecycleError(
                    "Candidate manifest entry is invalid"
                )
            path = self.worktree / relative
            if (
                not path.is_file()
                or path.stat().st_size != expected_size
                or sha256_file(path) != expected_hash
            ):
                raise LifecycleError(
                    f"Candidate changed after validation: {relative}"
                )
            records.append(record)
        if {str(item["path"]) for item in records} != set(
            self.candidate_paths
        ):
            raise LifecycleError(
                "Candidate manifest path set changed"
            )
        return records

    def _commit(self) -> dict[str, Any]:
        self._require_approval("commit")
        base_commit = str(self.state["base_commit"])
        current = git(self.worktree, "rev-parse", "HEAD")
        if current == base_commit:
            self._verify_candidate_stability()
            git(self.worktree, "add", "--", *self.candidate_paths)
            staged = {
                item
                for item in git(
                    self.worktree,
                    "diff",
                    "--cached",
                    "--name-only",
                ).splitlines()
                if item
            }
            if staged != set(self.candidate_paths):
                raise LifecycleError(
                    "Staged file set does not match candidate paths"
                )
            if git(self.worktree, "diff", "--name-only"):
                raise LifecycleError(
                    "Unexpected unstaged tracked files remain"
                )
            if git(
                self.worktree,
                "ls-files",
                "--others",
                "--exclude-standard",
            ):
                raise LifecycleError("Unexpected untracked files remain")
            git(
                self.worktree,
                "commit",
                "-m",
                self.commit_message,
            )
            action = "CREATED"
            current = git(self.worktree, "rev-parse", "HEAD")
        else:
            action = "ALREADY_CREATED"

        parent = git(self.worktree, "rev-parse", f"{current}^")
        message = git(
            self.worktree,
            "log",
            "-1",
            "--format=%s",
            current,
        )
        if parent != base_commit or message != self.commit_message:
            raise LifecycleError(
                "Existing feature commit does not match lifecycle contract"
            )
        changed = {
            item
            for item in git(
                self.worktree,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                current,
            ).splitlines()
            if item
        }
        if changed != set(self.candidate_paths):
            raise LifecycleError(
                "Committed path set differs from candidate paths"
            )
        if git(self.worktree, "status", "--porcelain"):
            raise LifecycleError("Feature worktree is not clean after commit")

        self.state["feature_commit"] = current
        actions = list(self.state["protected_actions_performed"])
        if "commit" not in actions:
            actions.append("commit")
        self.state["protected_actions_performed"] = actions
        self._save_state()
        return {
            "state": LifecycleState.COMMITTED.value,
            "action": action,
            "commit": current,
            "parent": parent,
            "message": message,
            "committed_paths": sorted(changed),
        }

    def _merge(self) -> dict[str, Any]:
        self._require_approval("merge")
        feature_commit = str(self.state["feature_commit"])
        base_commit = str(self.state["base_commit"])
        current_main = git(
            self.project_root,
            "rev-parse",
            self.base_branch,
        )
        if current_main == base_commit:
            if git(self.project_root, "status", "--porcelain"):
                raise LifecycleError("Base checkout is not clean before merge")
            git(
                self.project_root,
                "merge",
                "--ff-only",
                self.branch,
            )
            action = "PERFORMED"
        elif current_main == feature_commit:
            action = "ALREADY_MERGED"
        else:
            raise LifecycleError(
                "Base branch is neither lifecycle base nor feature commit"
            )
        merged = git(
            self.project_root,
            "rev-parse",
            self.base_branch,
        )
        if merged != feature_commit:
            raise LifecycleError("Fast-forward merge did not reach feature commit")
        if git(self.project_root, "status", "--porcelain"):
            raise LifecycleError("Base checkout is not clean after merge")
        actions = list(self.state["protected_actions_performed"])
        if "merge" not in actions:
            actions.append("merge")
        self.state["protected_actions_performed"] = actions
        self._save_state()
        return {
            "state": LifecycleState.MERGED.value,
            "action": action,
            "merged_commit": merged,
            "merge_type": "fast-forward",
        }

    def _push(self) -> dict[str, Any]:
        self._require_approval("push")
        feature_commit = str(self.state["feature_commit"])
        base_commit = str(self.state["base_commit"])
        git(self.project_root, "fetch", "--prune", "--tags", "origin")
        remote = git(
            self.project_root,
            "rev-parse",
            f"origin/{self.base_branch}",
        )
        if remote == base_commit:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.project_root),
                    "push",
                    "--porcelain",
                    "origin",
                    f"refs/heads/{self.base_branch}:"
                    f"refs/heads/{self.base_branch}",
                ],
                check=True,
            )
            action = "PUSHED"
        elif remote == feature_commit:
            action = "ALREADY_SYNCHRONIZED"
        else:
            raise LifecycleError(
                "Remote base branch moved to an unexpected commit"
            )
        git(self.project_root, "fetch", "--prune", "--tags", "origin")
        remote_after = git(
            self.project_root,
            "rev-parse",
            f"origin/{self.base_branch}",
        )
        local_after = git(
            self.project_root,
            "rev-parse",
            self.base_branch,
        )
        divergence = git(
            self.project_root,
            "rev-list",
            "--left-right",
            "--count",
            f"origin/{self.base_branch}...{self.base_branch}",
        ).split()
        if (
            remote_after != feature_commit
            or local_after != feature_commit
            or divergence != ["0", "0"]
        ):
            raise LifecycleError(
                "Local and remote base branches are not synchronized"
            )
        if git_success(
            self.project_root,
            "show-ref",
            "--verify",
            f"refs/remotes/origin/{self.branch}",
        ):
            raise LifecycleError(
                "Lifecycle feature branch was unexpectedly pushed"
            )
        actions = list(self.state["protected_actions_performed"])
        if "push" not in actions:
            actions.append("push")
        self.state["protected_actions_performed"] = actions
        self._save_state()
        return {
            "state": LifecycleState.PUSHED.value,
            "action": action,
            "local_commit": local_after,
            "remote_commit": remote_after,
            "divergence": [0, 0],
            "feature_branch_pushed": False,
        }

    def _close(self) -> dict[str, Any]:
        closure = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "phase": self.phase,
            "run_id": self.state["run_id"],
            "status": "CLOSED",
            "base_commit": self.state["base_commit"],
            "feature_commit": self.state["feature_commit"],
            "completed_states": [
                *list(self.state["completed_states"]),
                LifecycleState.CLOSED.value,
            ],
            "approvals": self.approvals.to_dict(),
            "protected_actions_performed": (
                self.state["protected_actions_performed"]
            ),
            "llm_calls": 0,
            "tag_performed": False,
            "release_performed": False,
        }
        write_json(self.run_dir / "closure.json", closure)
        return closure

    def _package_run(self) -> dict[str, str]:
        package = export_root() / (
            f"{self.state['run_id']}_lifecycle_evidence.tar.gz"
        )
        with tarfile.open(package, "w:gz") as archive:
            for path in sorted(self.run_dir.rglob("*")):
                if path.is_file():
                    archive.add(
                        path,
                        arcname=path.relative_to(self.run_dir),
                    )
        checksum = package.with_suffix(package.suffix + ".sha256")
        checksum.write_text(
            f"{sha256_file(package)}  {package.name}\n",
            encoding="utf-8",
        )
        return {
            "evidence_package": str(package),
            "evidence_checksum": str(checksum),
        }

    def _dry_run_plan(self) -> dict[str, Any]:
        plan = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": utc_now(),
            "phase": self.phase,
            "status": "DRY_RUN_PLANNED",
            "manifest": str(self.manifest_path),
            "manifest_digest": manifest_digest(self.manifest),
            "feature_branch": self.branch,
            "base_branch": self.base_branch,
            "candidate_paths": self.candidate_paths,
            "protected_actions": self.manifest[
                "protected_actions"
            ],
            "approvals": self.approvals.to_dict(),
            "state_order": [state.value for state in STATE_ORDER],
            "repository_mutations": 0,
            "llm_calls": 0,
        }
        write_json(self.run_dir / "dry_run_plan.json", plan)
        self.state["status"] = "DRY_RUN_PLANNED"
        self.state["current_state"] = "DRY_RUN_PLANNED"
        self._save_state()
        return plan

    def run(self) -> dict[str, Any]:
        if self.dry_run:
            return self._dry_run_plan()
        try:
            self._complete_or_run(
                LifecycleState.PREFLIGHT_PASSED,
                self._preflight,
            )
            self._complete_or_run(
                LifecycleState.WORKTREE_READY,
                self._prepare_worktree,
            )
            self._complete_or_run(
                LifecycleState.IMPLEMENTED,
                self._implementation,
            )
            self._complete_or_run(
                LifecycleState.TARGETED_VALIDATED,
                lambda: self._validation(
                    key="targeted_validation_commands",
                    state=LifecycleState.TARGETED_VALIDATED,
                    category="targeted",
                ),
            )
            self._restore_runtime_noise(self.worktree)
            self._complete_or_run(
                LifecycleState.CANDIDATE_VERIFIED,
                self._candidate_verification,
            )
            self._complete_or_run(
                LifecycleState.FULLY_VALIDATED,
                lambda: self._validation(
                    key="full_validation_commands",
                    state=LifecycleState.FULLY_VALIDATED,
                    category="full",
                ),
            )
            self._restore_runtime_noise(self.worktree)
            post_restore_commands = self.manifest.get(
                "post_restore_validation_commands",
                [],
            )
            if not isinstance(post_restore_commands, list):
                raise LifecycleError(
                    "post_restore_validation_commands must be a list"
                )
            self._complete_or_run(
                LifecycleState.POST_RESTORE_VALIDATED,
                lambda: self._validation(
                    key="post_restore_validation_commands",
                    state=LifecycleState.POST_RESTORE_VALIDATED,
                    category="post_restore",
                ),
            )
            self._complete_or_run(
                LifecycleState.COMMITTED,
                self._commit,
            )
            self._complete_or_run(
                LifecycleState.MERGED,
                self._merge,
            )
            self._complete_or_run(
                LifecycleState.PUSHED,
                self._push,
            )
            self._complete_or_run(
                LifecycleState.CLOSED,
                self._close,
            )
            self.state["status"] = LifecycleState.CLOSED.value
            self._save_state()
            closure = load_json_object(
                self.run_dir / "closure.json",
                "Lifecycle closure",
            )
            closure.update(self._package_run())
            return closure
        except Exception as error:
            self.state["status"] = LifecycleState.FAILED.value
            self.state["failure"] = {
                "type": type(error).__name__,
                "message": str(error),
                "at": utc_now(),
            }
            self._save_state()
            raise


def latest_run(phase: str | None = None) -> dict[str, Any] | None:
    root = state_root() / "lifecycle_runs"
    if not root.exists():
        return None
    pattern = "*" if phase is None else f"{phase.lower()}-*"
    candidates = sorted(
        (
            path
            for path in root.glob(pattern)
            if path.is_dir() and (path / "run.json").is_file()
        ),
        reverse=True,
    )
    if not candidates:
        return None
    return load_json_object(candidates[0] / "run.json", "Lifecycle state")
