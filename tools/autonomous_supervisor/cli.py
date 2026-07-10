from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from tools.autonomous_supervisor.engine import (
    AutonomousCampaignSupervisor,
    validate_configuration,
)
from tools.autonomous_supervisor.state import (
    load_json_object,
    write_json_atomic,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repository-native governed autonomous campaign supervisor"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("config", type=Path)
    validate.add_argument("--project-root", type=Path, default=Path.cwd())

    run = subparsers.add_parser("run")
    run.add_argument("config", type=Path)
    run.add_argument(
        "--approve",
        required=True,
        choices=["commit,merge,push"],
    )
    run.add_argument("--resume", action="store_true")
    run.add_argument("--project-root", type=Path, default=Path.cwd())

    for name in ("status", "pause", "resume", "cancel"):
        command = subparsers.add_parser(name)
        command.add_argument("config", type=Path)
        command.add_argument(
            "--project-root",
            type=Path,
            default=Path.cwd(),
        )

    return parser


def control_path(project_root: Path, config_path: Path) -> Path:
    config = load_json_object(config_path.resolve())
    campaign_id = config.get("campaign_id")
    if not isinstance(campaign_id, str) or not campaign_id:
        raise ValueError("campaign_id is missing")
    import os
    state_root = Path(
        os.environ.get(
            "UPI_APP_FACTORY_STATE_DIR",
            str(Path.home() / ".local/state/upi_app_factory"),
        )
    ).resolve()
    return (
        state_root
        / "autonomous_campaigns"
        / campaign_id
        / "control.json"
    )


def status_payload(project_root: Path, config_path: Path) -> dict[str, object]:
    config = load_json_object(config_path.resolve())
    campaign_id = str(config["campaign_id"])
    import os
    state_root = Path(
        os.environ.get(
            "UPI_APP_FACTORY_STATE_DIR",
            str(Path.home() / ".local/state/upi_app_factory"),
        )
    ).resolve()
    state_path = (
        state_root
        / "autonomous_campaigns"
        / campaign_id
        / "supervisor.json"
    )
    if not state_path.is_file():
        return {
            "status": "NOT_STARTED",
            "campaign_id": campaign_id,
        }
    return load_json_object(state_path)


def main(argv: Sequence[str] | None = None) -> int:
    parsed = build_parser().parse_args(argv)
    project_root = parsed.project_root.resolve()
    config_path = parsed.config.resolve()

    if parsed.command == "validate":
        report = validate_configuration(project_root, config_path)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if parsed.command == "run":
        supervisor = AutonomousCampaignSupervisor(
            project_root=project_root,
            config_path=config_path,
            approvals=("commit", "merge", "push"),
            resume=bool(parsed.resume),
        )
        report = supervisor.execute()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if parsed.command == "status":
        print(
            json.dumps(
                status_payload(project_root, config_path),
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    action = {
        "pause": "PAUSE",
        "resume": "RUN",
        "cancel": "CANCEL",
    }[parsed.command]
    path = control_path(project_root, config_path)
    write_json_atomic(
        path,
        {
            "action": action,
            "requested_by": "operator",
        },
    )
    print(
        json.dumps(
            {
                "status": "PASSED",
                "action": action,
                "control_path": str(path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
