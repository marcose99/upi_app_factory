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

from factory.native_capability_prerun import NativeCapabilityError, PreRunConfig, run_capability_prerun  # noqa: E402


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the mandatory native capability pre-run gate.")
    parser.add_argument("--requirements-document", type=Path, required=True)
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--expected-requirements-sha256")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_capability_prerun(
            PreRunConfig(
                requirements_document=args.requirements_document,
                application_id=args.application_id,
                output_root=args.output_root,
                factory_root=PROJECT_ROOT,
                expected_requirements_sha256=args.expected_requirements_sha256,
            )
        )
    except (NativeCapabilityError, OSError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": "native-capability-prerun.v1",
                    "status": "NATIVE_CAPABILITY_PRE_RUN_FAILED_CLOSED",
                    "error": str(exc),
                    "real_payment_calls": "disabled",
                    "llm_claims_used": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    # A completed pre-run can still end in a governed NO_GO decision without being
    # a controller/runtime failure. Fail closed only on execution errors above.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
