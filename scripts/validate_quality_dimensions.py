#!/usr/bin/env python3
"""Validate factory and generated-application quality dimension coverage.

The validator is intentionally simple and beginner-readable. It checks that the
repository contains a two-layer quality model and that every governed agent
prompt reminds agents to analyze both the factory and the application generated
by the factory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "factory_governance" / "quality_dimensions" / "quality_dimensions_manifest.json"
GUIDE_PATH = PROJECT_ROOT / "docs" / "factory_and_application_quality_dimensions.md"
PROMPT_DIR = PROJECT_ROOT / "factory_governance" / "agent_prompts" / "prompts"

MIN_FACTORY_DIMENSIONS = 10
MIN_APPLICATION_DIMENSIONS = 10
REQUIRED_TERMS = [
    "factory quality dimensions",
    "generated application quality dimensions",
    "validation",
    "evaluation",
    "observability",
    "traceability",
    "auditability",
    "security",
    "testability",
    "operational readiness",
    "beginner-readable",
    "debug-friendly",
]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _contains_all_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() not in lowered]


def validate() -> list[str]:
    errors: list[str] = []

    if not MANIFEST_PATH.exists():
        errors.append(f"Missing quality dimensions manifest: {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")
        return errors
    if not GUIDE_PATH.exists():
        errors.append(f"Missing quality dimensions guide: {GUIDE_PATH.relative_to(PROJECT_ROOT)}")
        return errors
    if not PROMPT_DIR.exists():
        errors.append(f"Missing governed agent prompt directory: {PROMPT_DIR.relative_to(PROJECT_ROOT)}")
        return errors

    manifest = _load_json(MANIFEST_PATH)
    factory_dimensions = manifest.get("factory_quality_dimensions", [])
    app_dimensions = manifest.get("generated_application_quality_dimensions", [])

    if not isinstance(factory_dimensions, list) or len(factory_dimensions) < MIN_FACTORY_DIMENSIONS:
        errors.append("factory_quality_dimensions must contain at least 10 dimensions")
    if not isinstance(app_dimensions, list) or len(app_dimensions) < MIN_APPLICATION_DIMENSIONS:
        errors.append("generated_application_quality_dimensions must contain at least 10 dimensions")

    manifest_text = json.dumps(manifest, sort_keys=True)
    guide_text = GUIDE_PATH.read_text(encoding="utf-8")

    for term in _contains_all_terms(manifest_text + "\n" + guide_text, REQUIRED_TERMS):
        errors.append(f"Quality dimensions documentation is missing required term: {term}")

    prompt_files = sorted(PROMPT_DIR.glob("*.md"))
    if not prompt_files:
        errors.append("No governed agent prompt files found")
        return errors

    for prompt_file in prompt_files:
        text = prompt_file.read_text(encoding="utf-8")
        missing_terms = _contains_all_terms(text, REQUIRED_TERMS)
        for term in missing_terms:
            errors.append(f"Prompt {prompt_file.name} is missing required quality-dimension term: {term}")

    return errors


def main() -> int:
    errors = validate()
    print(json.dumps({"passed": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
