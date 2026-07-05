#!/usr/bin/env python3
"""Validate project-level debugging and prompt-quality documentation.

This validator is intentionally simple and beginner-readable.
It checks that the project contains the minimum guidance needed to keep future
factory work understandable, debuggable, and governance-aware.
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES: dict[str, list[str]] = {
    "docs/project_debugging_guide.md": [
        "Golden debug loop",
        "Beginner-friendly code standard",
        "Factory run debugging",
        "Failure triage map",
        "What to collect before asking for help",
        "Debugging principles",
        "NIST SP 800-218",
        "OWASP Logging Cheat Sheet",
        "OWASP Error Handling Cheat Sheet",
    ],
    "docs/prompt_quality_guide.md": [
        "High-impact prompt template",
        "Prompt statements that improve code quality",
        "Prompt statements that improve architecture quality",
        "Prompt statements that improve governance quality",
        "Prompt statements that improve debugging quality",
        "Prompt statements that improve phase automation",
        "Anti-prompts to avoid",
        "OpenAI Prompt Engineering Guide",
        "OpenAI Reasoning Best Practices",
    ],
}


def validate_file(relative_path: str, required_terms: list[str]) -> list[str]:
    """Return validation errors for one required documentation file."""
    errors: list[str] = []
    path = PROJECT_ROOT / relative_path

    if not path.exists():
        return [f"Missing required file: {relative_path}"]

    text = path.read_text(encoding="utf-8")
    for term in required_terms:
        if term not in text:
            errors.append(f"{relative_path} is missing required term: {term}")

    return errors


def main() -> int:
    errors: list[str] = []

    for relative_path, required_terms in REQUIRED_FILES.items():
        errors.extend(validate_file(relative_path, required_terms))

    result = {"passed": not errors, "errors": errors}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
