#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from factory.native_capability_prerun.improvement_workflow import FactoryImprovementError, ImprovementWorkflowConfig, run_factory_improvement_workflow  # noqa: E402


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan governed factory capability improvements.")
    parser.add_argument("--improvement-requirements", type=Path, required=True)
    parser.add_argument(
        "--improvement-requirements-sha256",
        "--improvement-sha256",
        dest="improvement_sha256",
        required=True,
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--requirements-document", type=Path)
    parser.add_argument("--application-id")
    parser.add_argument("--plan-only", action="store_true", default=True)
    parser.add_argument("--allow-source-changes", action="store_true")
    parser.add_argument("--authorization")
    parser.add_argument("--max-repair-cycles", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.allow_source_changes and (args.requirements_document is None or args.application_id is None):
        print(
            json.dumps(
                {
                    "schema_version": "factory-improvement-workflow.v2",
                    "status": "FACTORY_IMPROVEMENT_WORKFLOW_FAILED_CLOSED",
                    "error": (
                        "requirements_document and application_id are required when "
                        "--allow-source-changes requests governed execution"
                    ),
                    "merge_push_release_performed": False,
                    "real_payment_calls": "disabled",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    try:
        result = run_factory_improvement_workflow(
            ImprovementWorkflowConfig(
                improvement_requirements=args.improvement_requirements,
                improvement_sha256=args.improvement_sha256,
                output_root=args.output_root,
                factory_root=PROJECT_ROOT,
                requirements_document=args.requirements_document,
                application_id=args.application_id,
                plan_only=not bool(args.allow_source_changes),
                authorization=args.authorization,
                max_repair_cycles=args.max_repair_cycles,
            )
        )
    except (FactoryImprovementError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": "factory-improvement-workflow.v2",
                    "status": "FACTORY_IMPROVEMENT_WORKFLOW_FAILED_CLOSED",
                    "error": str(exc),
                    "merge_push_release_performed": False,
                    "real_payment_calls": "disabled",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
