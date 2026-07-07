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

"""Validate Phase 14S governed multi-phase autonomous continuation artifacts."""

import json
from typing import Any, cast

from scripts.run_governed_autonomous_continuation import (  # noqa: E402
    DEFAULT_AUDIT_PATH,
    build_multi_phase_autonomous_continuation_runner,
    validate_multi_phase_autonomous_continuation_runner,
)

JsonDict = dict[str, Any]


def load_audit(path: Path) -> JsonDict:
    if not path.exists():
        return build_multi_phase_autonomous_continuation_runner(execute_gates=False)
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"Audit JSON must be an object: {path}")
    return cast(JsonDict, raw)


def main() -> int:
    audit = load_audit(DEFAULT_AUDIT_PATH)
    errors = validate_multi_phase_autonomous_continuation_runner(audit)
    if errors:
        print("Phase 14S validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Phase 14S multi-phase autonomous continuation artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
