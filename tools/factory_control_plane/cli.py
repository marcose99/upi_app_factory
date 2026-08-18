from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from tools.factory_control_plane.common import (
    ControlPlaneError,
    default_state_root,
    project_root_from,
)
from tools.factory_control_plane.engine import ControlPlaneEngine
from tools.factory_control_plane.policy import StandingPolicy
from tools.factory_control_plane.worker import InboxWorker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upi-app-factory-control-plane")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--policy", default="config/control_plane/standing_policy.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate").add_argument("manifest")
    sub.add_parser("run").add_argument("manifest")
    sub.add_parser("resume").add_argument("manifest")
    sub.add_parser("status").add_argument("campaign_id")
    explain = sub.add_parser("policy-explain")
    explain.add_argument("action")
    explain.add_argument("risk")
    sub.add_parser("seal-evidence").add_argument("campaign_id")
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--inbox", default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    project_root = project_root_from(Path(args.project_root))
    state_root = (
        Path(args.state_root).resolve()
        if args.state_root
        else default_state_root(project_root)
    )
    policy_path = (project_root / str(args.policy)).resolve()
    try:
        if args.command == "policy-explain":
            decision = StandingPolicy(policy_path).evaluate(args.action, args.risk)
            print(json.dumps(decision.to_record(), indent=2, sort_keys=True))
            return 0
        engine = ControlPlaneEngine(project_root, state_root, policy_path)
        try:
            if args.command == "validate":
                manifest = engine.validate(Path(args.manifest))
                result = {
                    "status": "valid",
                    "campaign_id": manifest.campaign_id,
                    "manifest_sha256": manifest.digest,
                }
            elif args.command in {"run", "resume"}:
                result = engine.run(Path(args.manifest))
            elif args.command == "status":
                result = engine.status(args.campaign_id)
            elif args.command == "seal-evidence":
                result = engine.seal_evidence(args.campaign_id)
            elif args.command == "worker":
                inbox = Path(args.inbox).resolve() if args.inbox else state_root / "inbox"
                worker = InboxWorker(inbox, engine)
                result = worker.run_once() if args.once else worker.run_polling()
            else:
                raise ControlPlaneError("unsupported command")
        finally:
            engine.close()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
