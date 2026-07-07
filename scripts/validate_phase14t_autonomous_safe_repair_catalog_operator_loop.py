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

"""Validate Phase 14T autonomous safe-repair catalog operator loop artifacts."""

import json
from typing import Any, cast

from scripts.run_autonomous_safe_repair_catalog_operator_loop import (  # noqa: E402
    DEFAULT_AUDIT_PATH,
    build_autonomous_safe_repair_catalog_operator_loop,
    validate_autonomous_safe_repair_catalog_operator_loop,
)

JsonDict = dict[str, Any]
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_audit(path: Path) -> JsonDict:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Audit payload must be a JSON object: {path}")
    return cast(JsonDict, loaded)


def main() -> int:
    audit_path = PROJECT_ROOT / DEFAULT_AUDIT_PATH
    audit = _load_audit(audit_path) if audit_path.exists() else build_autonomous_safe_repair_catalog_operator_loop()
    errors = validate_autonomous_safe_repair_catalog_operator_loop(audit)
    if errors:
        print("Phase 14T validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Phase 14T autonomous safe-repair catalog operator loop artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
