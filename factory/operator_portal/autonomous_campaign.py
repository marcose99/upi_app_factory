from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any, cast


class AutonomousCampaignPortalError(RuntimeError):
    """Raised when a portal campaign action is not allowed."""


def load_json_object(
    path: Path,
    label: str,
) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AutonomousCampaignPortalError(
            f"{label} must be a JSON object"
        )
    return cast(dict[str, Any], value)


class AutonomousCampaignService:
    def __init__(
        self,
        *,
        project_root: Path,
        campaign_config: Path,
        state_root: Path | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.campaign_config = campaign_config.resolve()
        self.state_root = (
            state_root.resolve()
            if state_root is not None
            else Path(
                os.environ.get(
                    "UPI_APP_FACTORY_STATE_DIR",
                    str(
                        Path.home()
                        / ".local/state/upi_app_factory"
                    ),
                )
            ).resolve()
        )
        config = load_json_object(
            self.campaign_config,
            "Campaign config",
        )
        campaign_id = config.get("campaign_id")
        if not isinstance(campaign_id, str) or not campaign_id:
            raise AutonomousCampaignPortalError(
                "Campaign config has no campaign_id"
            )
        self.campaign_id = campaign_id

    @property
    def binary(self) -> Path:
        return self.project_root / "bin/upi-app-factory-autonomous"

    @property
    def supervisor_state_path(self) -> Path:
        return (
            self.state_root
            / "autonomous_campaigns"
            / self.campaign_id
            / "supervisor.json"
        )

    @property
    def events_path(self) -> Path:
        return (
            self.state_root
            / "autonomous_campaigns"
            / self.campaign_id
            / "events.jsonl"
        )

    def command(self, action: str) -> list[str]:
        if action == "run":
            return [
                str(self.binary),
                "run",
                str(self.campaign_config),
                "--approve",
                "commit,merge,push",
                "--resume",
                "--project-root",
                str(self.project_root),
            ]
        if action in {"status", "pause", "resume", "cancel"}:
            return [
                str(self.binary),
                action,
                str(self.campaign_config),
                "--project-root",
                str(self.project_root),
            ]
        raise AutonomousCampaignPortalError(
            f"Unsupported campaign action: {action}"
        )

    def status(self) -> dict[str, Any]:
        if not self.supervisor_state_path.is_file():
            return {
                "status": "NOT_STARTED",
                "campaign_id": self.campaign_id,
            }
        return load_json_object(
            self.supervisor_state_path,
            "Supervisor state",
        )

    def events(self, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1:
            raise AutonomousCampaignPortalError(
                "Event limit must be positive"
            )
        if not self.events_path.is_file():
            return []
        records: list[dict[str, Any]] = []
        for line in self.events_path.read_text(
            encoding="utf-8"
        ).splitlines():
            value: object = json.loads(line)
            if isinstance(value, dict):
                records.append(cast(dict[str, Any], value))
        return records[-limit:]

    def execute(
        self,
        action: str,
        *,
        dry_run: bool,
        approved: bool,
    ) -> dict[str, Any]:
        command = self.command(action)
        if action == "run" and not approved:
            raise AutonomousCampaignPortalError(
                "Campaign run requires protected-action approval"
            )
        if dry_run:
            return {
                "status": "DRY_RUN",
                "action": action,
                "command": command,
                "shell": False,
            }
        result = subprocess.run(
            command,
            cwd=self.project_root,
            check=False,
            text=True,
            capture_output=True,
            shell=False,
        )
        return {
            "status": (
                "PASSED" if result.returncode == 0 else "FAILED"
            ),
            "action": action,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "shell": False,
        }
