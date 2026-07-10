from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.lifecycle_orchestrator.maintenance import (
    repair_and_resume,
    supersede_failed_run,
)


def main() -> int:
    parser = argparse.ArgumentParser(prog="upi-app-factory-lifecycle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    supersede = subparsers.add_parser("supersede-run")
    supersede.add_argument("--run-id", required=True)
    supersede.add_argument("--reason", required=True)
    supersede.add_argument(
        "--state-root",
        type=Path,
        default=Path.home() / ".local/state/upi_app_factory",
    )
    supersede.add_argument(
        "--evidence-export-dir",
        type=Path,
        default=Path.home() / "Downloads",
    )
    supersede.add_argument("--approve-supersede", action="store_true")

    repair = subparsers.add_parser("repair-resume")
    repair.add_argument("--run-id", required=True)
    repair.add_argument("--repair-id", required=True)
    repair.add_argument("--manifest", type=Path, required=True)
    repair.add_argument("--project-root", type=Path, required=True)
    repair.add_argument(
        "--state-root",
        type=Path,
        default=Path.home() / ".local/state/upi_app_factory",
    )
    repair.add_argument("--python", required=True)
    repair.add_argument("--approve", default="")
    parsed = parser.parse_args()
    if parsed.command == "supersede-run":
        result = supersede_failed_run(
            state_root=parsed.state_root,
            run_id=parsed.run_id,
            reason=parsed.reason,
            evidence_export_dir=parsed.evidence_export_dir,
            approved=parsed.approve_supersede,
        )
    else:
        approvals = tuple(item.strip() for item in parsed.approve.split(",") if item.strip())
        result = repair_and_resume(
            state_root=parsed.state_root,
            run_id=parsed.run_id,
            repair_id=parsed.repair_id,
            manifest_path=parsed.manifest,
            project_root=parsed.project_root,
            python=parsed.python,
            approvals=approvals,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
