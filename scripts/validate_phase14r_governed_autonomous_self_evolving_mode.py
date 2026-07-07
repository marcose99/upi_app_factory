#!/usr/bin/env python3
"""Validate Phase 14R governed autonomous self-evolving mode artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

from scripts.build_governed_autonomous_self_evolving_mode import (
    DEFAULT_AUDIT_PATH,
    DOC_PATH,
    POLICY_PATH,
    build_governed_autonomous_self_evolving_mode,
    validate_governed_autonomous_self_evolving_mode,
)

JsonDict = dict[str, Any]

REQUIRED_POLICY_KEYS = {
    "allowed_autonomous_actions",
    "blocked_autonomous_actions",
    "human_approval_required_for",
    "parallel_execution_policy",
    "certification_boundary",
}


def _load_json(path: Path) -> JsonDict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return cast(dict[str, Any], data)
def validate_artifacts(audit_path: Path = DEFAULT_AUDIT_PATH) -> list[str]:
    errors: list[str] = []
    if not DOC_PATH.exists():
        errors.append(f"Missing documentation: {DOC_PATH}")
    if not POLICY_PATH.exists():
        errors.append(f"Missing policy: {POLICY_PATH}")
    else:
        policy = _load_json(POLICY_PATH)
        missing = sorted(REQUIRED_POLICY_KEYS - set(policy))
        if missing:
            errors.append("Policy missing keys: " + ", ".join(missing))
        blocked = policy.get("blocked_autonomous_actions", [])
        for required in ["auto_merge", "auto_tag", "auto_push", "auto_release", "auto_certify"]:
            if required not in blocked:
                errors.append(f"Policy does not block {required}")
    plan = build_governed_autonomous_self_evolving_mode(execute_readonly_gates=False)
    errors.extend(validate_governed_autonomous_self_evolving_mode(plan))
    if not audit_path.exists():
        errors.append(f"Missing audit evidence: {audit_path}")
    else:
        audit = _load_json(audit_path)
        errors.extend(validate_governed_autonomous_self_evolving_mode(audit))
    return errors


def main() -> int:
    audit_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_AUDIT_PATH
    errors = validate_artifacts(audit_path)
    if errors:
        print("Phase 14R validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Phase 14R governed autonomous self-evolving mode artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
