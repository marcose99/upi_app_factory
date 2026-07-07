#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ruff: noqa: E402
# PHASE16_DIRECT_EXECUTION_IMPORT_BOOTSTRAP
from pathlib import Path as _Phase16BootstrapPath
import sys as _phase16_bootstrap_sys

_PHASE16_BOOTSTRAP_REPO_ROOT = _Phase16BootstrapPath(__file__).resolve().parents[1]
if str(_PHASE16_BOOTSTRAP_REPO_ROOT) not in _phase16_bootstrap_sys.path:
    _phase16_bootstrap_sys.path.insert(0, str(_PHASE16_BOOTSTRAP_REPO_ROOT))
# END_PHASE16_DIRECT_EXECUTION_IMPORT_BOOTSTRAP

import json
from typing import Any, cast

from scripts.run_autonomous_phase_discovery_and_planning import (  # noqa: E402
    DEFAULT_AUDIT_PATH,
    DOC_PATH,
    POLICY_PATH,
    build_autonomous_phase_discovery_and_planning,
    validate_autonomous_phase_discovery_and_planning,
)

JsonDict = dict[str, Any]


def _load_json(path: Path) -> JsonDict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return cast(JsonDict, data)


def main() -> int:
    errors: list[str] = []
    for path in (DOC_PATH, POLICY_PATH, DEFAULT_AUDIT_PATH):
        if not path.exists():
            errors.append(f"Missing required artifact: {path}")
    plan = build_autonomous_phase_discovery_and_planning(execute_readonly_gates=False)
    errors.extend(validate_autonomous_phase_discovery_and_planning(plan))
    if DEFAULT_AUDIT_PATH.exists():
        errors.extend(validate_autonomous_phase_discovery_and_planning(_load_json(DEFAULT_AUDIT_PATH)))
    if errors:
        print("Phase 14U validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Phase 14U autonomous phase discovery artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
