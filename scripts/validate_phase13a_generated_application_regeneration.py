#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP_ID = "upi_dispute_resolution"
RUN_ID = "first_governed_generation_run_001"

DOCS = ROOT / "docs" / "phase13a"
WORKSPACE = ROOT / "workspace" / "factory_generated" / APP_ID / "lifecycle_artifacts" / "phase13a"
RUN_ROOT = ROOT / "workspace" / "factory_generated" / APP_ID / "generation_runs" / RUN_ID
RESET_SCRIPT = ROOT / "scripts" / "reset_generated_application_workspace.py"

REQUIRED_FILES = [
    "generated_application_delete_recreate_contract.json",
    "generated_application_delete_recreate_runbook.md",
]

REQUIRED_TERMS = {
    "generated_application_delete_recreate_contract.json": [
        "reset_target",
        "archive_root",
        "reset_manifest_root",
        "protected_paths",
        "canonical_recreated_skeleton",
    ],
    "generated_application_delete_recreate_runbook.md": [
        "delete and recreate",
        "Dry-run command",
        "Each reset writes a reset manifest",
    ],
}


def _check_root(root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for name in REQUIRED_FILES:
        path = root / name
        if not path.exists():
            errors.append({"path": str(path.relative_to(ROOT)), "error": "missing_file"})
            continue
        text = path.read_text(encoding="utf-8")
        for term in REQUIRED_TERMS.get(name, []):
            if term not in text:
                errors.append({"path": str(path.relative_to(ROOT)), "error": f"missing_term:{term}"})
    return errors


def validate() -> dict[str, Any]:
    errors = _check_root(DOCS) + _check_root(WORKSPACE) + _check_root(RUN_ROOT)

    if not RESET_SCRIPT.exists():
        errors.append({"path": str(RESET_SCRIPT.relative_to(ROOT)), "error": "missing_reset_script"})
    else:
        text = RESET_SCRIPT.read_text(encoding="utf-8")
        for term in [
            "ensure_safe_path",
            "generated_application_archives",
            "reset_manifests",
            "recreate_skeleton",
            "--dry-run",
            "--no-archive",
        ]:
            if term not in text:
                errors.append({"path": str(RESET_SCRIPT.relative_to(ROOT)), "error": f"missing_reset_script_term:{term}"})

    return {
        "passed": not errors,
        "phase": "Phase 13A",
        "app_id": APP_ID,
        "run_id": RUN_ID,
        "regeneration_contract_files_checked": len(REQUIRED_FILES) * 3,
        "reset_script_checked": RESET_SCRIPT.exists(),
        "errors": errors,
    }


def main() -> int:
    result = validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
