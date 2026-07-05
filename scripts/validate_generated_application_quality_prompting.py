#!/usr/bin/env python3
"""Validate generated-application quality prompting standards.

This validator is intentionally small and beginner-readable. It verifies that
high-value generated-application quality terms are present in the shared guide,
manifest, and every governed agent prompt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUIDE_PATH = PROJECT_ROOT / "docs/generated_application_quality_prompting_guide.md"
MANIFEST_PATH = (
    PROJECT_ROOT
    / "factory_governance/generated_application_quality"
    / "generated_application_quality_manifest.json"
)
PROMPT_DIR = PROJECT_ROOT / "factory_governance/agent_prompts/prompts"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(read_text(path)))


def contains_term(text: str, term: str) -> bool:
    return term.lower() in text.lower()


def validate() -> list[str]:
    errors: list[str] = []

    if not GUIDE_PATH.exists():
        errors.append(f"Missing guide: {GUIDE_PATH.relative_to(PROJECT_ROOT)}")
        return errors

    if not MANIFEST_PATH.exists():
        errors.append(f"Missing manifest: {MANIFEST_PATH.relative_to(PROJECT_ROOT)}")
        return errors

    if not PROMPT_DIR.exists():
        errors.append(f"Missing prompt directory: {PROMPT_DIR.relative_to(PROJECT_ROOT)}")
        return errors

    manifest = read_json(MANIFEST_PATH)
    required_terms = manifest.get("required_prompt_terms", [])
    if not required_terms:
        errors.append("Manifest does not define required_prompt_terms")
        return errors

    guide_text = read_text(GUIDE_PATH)
    manifest_text = json.dumps(manifest, sort_keys=True)

    for term in required_terms:
        if not contains_term(guide_text, term):
            errors.append(f"Guide is missing required term: {term}")
        if not contains_term(manifest_text, term):
            errors.append(f"Manifest is missing required term: {term}")

    prompt_paths = sorted(PROMPT_DIR.glob("*.md"))
    if not prompt_paths:
        errors.append("No governed agent prompts found")
        return errors

    for prompt_path in prompt_paths:
        prompt_text = read_text(prompt_path)
        for term in required_terms:
            if not contains_term(prompt_text, term):
                errors.append(f"{prompt_path.name} is missing required term: {term}")

    return errors


def main() -> int:
    errors = validate()
    result = {"errors": errors, "passed": not errors}
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
