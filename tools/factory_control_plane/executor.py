from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.factory_control_plane.common import (
    ControlPlaneError,
    resolve_under_root,
    sha256_text,
    utc_now,
)
from tools.factory_control_plane.manifest import Activity


ALLOWED_EXECUTABLES = {
    "python",
    "python3",
    "git",
    "pytest",
    "ruff",
    "mypy",
    "test",
    "true",
}


@dataclass(frozen=True)
class ActivityResult:
    activity_id: str
    action: str
    kind: str
    returncode: int
    stdout_sha256: str
    stderr_sha256: str
    stdout: str
    stderr: str
    started_at: str
    finished_at: str

    def to_record(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "action": self.action,
            "kind": self.kind,
            "returncode": self.returncode,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class CapabilityExecutor:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def run(self, activity: Activity) -> ActivityResult:
        return self._run(activity, {})

    def observe(
        self,
        activity: Activity,
        subject: str,
        reference: str,
    ) -> ActivityResult:
        return self._run(
            activity,
            {
                "UPI_APP_FACTORY_OBSERVATION_SUBJECT": subject,
                "UPI_APP_FACTORY_OBSERVATION_REF": reference,
            },
        )

    def _run(
        self,
        activity: Activity,
        extra_env: dict[str, str],
    ) -> ActivityResult:
        if not activity.argv:
            raise ControlPlaneError("argv must not be empty")
        for value in activity.argv:
            if "\x00" in value or "\n" in value:
                raise ControlPlaneError("argv contains forbidden control data")
        executable = Path(activity.argv[0]).name
        if executable not in ALLOWED_EXECUTABLES:
            raise ControlPlaneError(f"executable is not allowlisted: {executable}")
        cwd = resolve_under_root(self.project_root, activity.cwd)
        env = {
            key: os.environ[key]
            for key in activity.environment_allowlist
            if (
                key in os.environ
                and "\x00" not in os.environ[key]
                and "\n" not in os.environ[key]
            )
        }
        env["PYTHONPATH"] = str(self.project_root)
        env.update(extra_env)
        started = utc_now()
        completed = subprocess.run(
            list(activity.argv),
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=activity.timeout_seconds,
        )
        finished = utc_now()
        return ActivityResult(
            activity_id=activity.id,
            action=activity.action,
            kind=activity.kind,
            returncode=completed.returncode,
            stdout_sha256=sha256_text(completed.stdout),
            stderr_sha256=sha256_text(completed.stderr),
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started,
            finished_at=finished,
        )
