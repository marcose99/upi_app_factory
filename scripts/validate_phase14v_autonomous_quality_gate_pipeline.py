from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from scripts.run_autonomous_quality_gate_pipeline_hardening import (
    DEFAULT_AUDIT_PATH,
    validate_autonomous_quality_gate_pipeline_hardening,
)

JsonDict = dict[str, Any]


def load_json_object(path: Path) -> JsonDict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return cast(JsonDict, value)


def main() -> int:
    audit = load_json_object(DEFAULT_AUDIT_PATH)
    errors = validate_autonomous_quality_gate_pipeline_hardening(audit)
    if errors:
        print("Phase 14V validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Phase 14V autonomous quality-gate pipeline artifacts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
