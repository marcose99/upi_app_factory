#!/usr/bin/env python3
"""Validate Phase 14S governed multi-phase autonomous continuation artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.run_governed_autonomous_continuation import (
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
