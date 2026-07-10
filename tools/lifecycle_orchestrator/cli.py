from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from tools.lifecycle_orchestrator.engine import (
    LifecycleEngine,
    LifecycleError,
    latest_run,
    load_json_object,
    validate_manifest,
)
from tools.lifecycle_orchestrator.models import ApprovalSet


def resolve_manifest(project_root: Path, phase: str) -> Path:
    direct = Path(phase).expanduser()
    if direct.suffix == ".json" and direct.is_file():
        return direct.resolve()
    normalized = phase.lower()
    return (
        project_root
        / "config"
        / "lifecycle"
        / "phases"
        / f"{normalized}.json"
    ).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="upi-app-factory lifecycle",
    )
    actions = parser.add_subparsers(dest="action", required=True)

    run_parser = actions.add_parser("run")
    run_parser.add_argument("phase")
    run_parser.add_argument("--approve", default="")
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--project-root", default=".")

    status_parser = actions.add_parser("status")
    status_parser.add_argument("--phase")

    validate_parser = actions.add_parser("validate-manifest")
    validate_parser.add_argument("phase")
    validate_parser.add_argument("--project-root", default=".")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "lifecycle":
        arguments = arguments[1:]

    parser = build_parser()
    parsed = parser.parse_args(arguments)

    if parsed.action == "run":
        project_root = Path(parsed.project_root).resolve()
        manifest_path = resolve_manifest(project_root, parsed.phase)
        approvals = ApprovalSet.from_csv(parsed.approve)
        engine = LifecycleEngine(
            project_root,
            manifest_path,
            approvals,
            resume=parsed.resume,
            dry_run=parsed.dry_run,
        )
        result = engine.run()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if parsed.action == "status":
        latest = latest_run(parsed.phase)
        if latest is None:
            print("No lifecycle runs found.")
            return 0
        print(json.dumps(latest, indent=2, sort_keys=True))
        return 0

    if parsed.action == "validate-manifest":
        project_root = Path(parsed.project_root).resolve()
        path = resolve_manifest(project_root, parsed.phase)
        manifest = validate_manifest(
            load_json_object(path, "Lifecycle manifest")
        )
        print(
            json.dumps(
                {
                    "status": "PASSED",
                    "phase": manifest["phase"],
                    "manifest": str(path),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    raise LifecycleError("Unsupported lifecycle action")


if __name__ == "__main__":
    raise SystemExit(main())
