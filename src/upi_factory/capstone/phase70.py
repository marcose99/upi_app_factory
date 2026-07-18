from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from factory.application_engineering.multi_domain_profiles import (
    PHASE70_SCHEMA_VERSION,
    Phase70Error,
    validate_phase70_portfolio,
)


DEFAULT_REQUIREMENTS_ROOT = Path("tests/fixtures/phase68_70")
DEFAULT_GOVERNANCE_PATH = Path("factory_governance/phase68_70/phase70_profile_governance.json")


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def run_phase70_validation(
    *,
    project_root: Path | None = None,
    requirements_root: Path | None = None,
    governance_path: Path | None = None,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    root = (project_root or repository_root()).resolve()
    req_root = (requirements_root or root / DEFAULT_REQUIREMENTS_ROOT).resolve()
    gov_path = (governance_path or root / DEFAULT_GOVERNANCE_PATH).resolve()
    if runtime_root is not None:
        return validate_phase70_portfolio(
            project_root=root,
            requirements_root=req_root,
            governance_path=gov_path,
            runtime_root=runtime_root.resolve(),
        )
    with tempfile.TemporaryDirectory(prefix="upi_phase70_reference_apps_") as temporary:
        return validate_phase70_portfolio(
            project_root=root,
            requirements_root=req_root,
            governance_path=gov_path,
            runtime_root=Path(temporary),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 70 multi-domain application-engineering portfolio.")
    parser.add_argument("--project-root", type=Path, default=repository_root())
    parser.add_argument("--requirements-root", type=Path)
    parser.add_argument("--governance-path", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args(argv)
    try:
        result = run_phase70_validation(
            project_root=args.project_root,
            requirements_root=args.requirements_root,
            governance_path=args.governance_path,
            runtime_root=args.runtime_root,
        )
    except (OSError, json.JSONDecodeError, Phase70Error, AssertionError) as exc:
        print(_canonical_json({"schema_version": PHASE70_SCHEMA_VERSION, "status": "FAIL", "error": str(exc)}), end="")
        return 1
    print(_canonical_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
