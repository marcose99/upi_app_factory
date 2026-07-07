#!/usr/bin/env python3
"""Validate Phase 14T autonomous safe-repair catalog operator loop artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.run_autonomous_safe_repair_catalog_operator_loop import (
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
